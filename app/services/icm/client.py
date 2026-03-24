import time
import asyncio
import httpx
import structlog
from tenacity import (
    stop_after_attempt,
    wait_exponential,
    wait_none,
    retry_if_exception,
    AsyncRetrying,
)
from app.services.icm.exceptions import ICMServiceUnavailableError, ICMError
from app.services.icm.error_mapping import map_icm_error

logger = structlog.get_logger()


def _is_retryable(exc: BaseException) -> bool:
    """Retry on 5xx responses and connection errors; never on 4xx or typed ICM errors."""
    if isinstance(exc, ICMError):
        return False
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


class _AsyncCircuitBreaker:
    """
    Minimal async-native circuit breaker.

    States: CLOSED -> OPEN (after fail_max failures) -> HALF_OPEN (after reset_timeout) -> CLOSED
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, fail_max: int = 5, reset_timeout: float = 30.0):
        self._fail_max = fail_max
        self._reset_timeout = reset_timeout
        self._failures = 0
        self._state = self.CLOSED
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()
        self._probe_in_flight: bool = False

    def _is_open(self) -> bool:
        # INVARIANT: Must only be called while self._lock is held by the caller.
        # Mutates self._state; calling without the lock is a data race.
        if self._state == self.CLOSED:
            return False
        if self._state == self.HALF_OPEN:
            # Being managed by call_async; let call_async handle probe_in_flight check
            return False
        # OPEN state: check timeout
        if time.monotonic() - (self._opened_at or 0) >= self._reset_timeout:
            self._state = self.HALF_OPEN
            return False  # allow the probe
        return True

    async def call_async(self, func, *args, **kwargs):
        async with self._lock:
            if self._is_open():
                raise ICMServiceUnavailableError(
                    "ICM circuit breaker is open; service unavailable"
                )
            # In HALF_OPEN: only allow one probe at a time
            if self._state == self.HALF_OPEN:
                if self._probe_in_flight:
                    raise ICMServiceUnavailableError(
                        "ICM circuit breaker: probe already in flight"
                    )
                self._probe_in_flight = True

        try:
            result = await func(*args, **kwargs)
        except Exception:
            async with self._lock:
                self._failures += 1
                if self._state == self.HALF_OPEN:
                    # Failed probe — re-open immediately
                    self._state = self.OPEN
                    self._opened_at = time.monotonic()
                    self._probe_in_flight = False
                elif self._failures >= self._fail_max:
                    self._state = self.OPEN
                    self._opened_at = time.monotonic()
                    logger.warning("circuit_breaker_opened", failures=self._failures)
            raise
        else:
            async with self._lock:
                # Successful call — reset
                self._failures = 0
                self._state = self.CLOSED
                self._probe_in_flight = False
            return result


class _SecretStr:
    """Wraps a secret string to prevent accidental logging or repr exposure."""
    def __init__(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "**REDACTED**"

    def __str__(self) -> str:
        return "**REDACTED**"


class ICMClient:
    """
    Base class for all Siebel REST service clients.

    Provides:
    - OAuth2 token management (cached, refreshed 60s before expiry)
    - Retry with exponential backoff (3 attempts, 1/2/4s, 5xx only)
    - Circuit breaker (5 failures threshold, 30s recovery)
    """

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        token_url: str,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout: int = 30,
        max_connections: int = 50,
        max_keepalive: int = 20,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
        _test_no_wait: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self._client_secret = _SecretStr(client_secret)
        self.token_url = token_url
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._token_lock = asyncio.Lock()
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=connect_timeout, read=read_timeout, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=max_connections, max_keepalive_connections=max_keepalive),
        )
        self._breaker = _AsyncCircuitBreaker(
            fail_max=circuit_failure_threshold,
            reset_timeout=float(circuit_recovery_timeout),
        )
        # In tests, skip exponential wait to avoid sleeping
        self._retry_wait = wait_none() if _test_no_wait else wait_exponential(multiplier=1, min=1, max=4)

    async def _fetch_token(self) -> None:
        """Fetch a new OAuth2 token and cache it."""
        response = await self._http.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self._client_secret.get(),
            },
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        self._token_expiry = time.monotonic() + data.get("expires_in", 3600) - 60

    async def _ensure_token(self) -> str:
        """Return a valid token, refreshing if expired."""
        async with self._token_lock:
            if self._token is None or time.monotonic() >= self._token_expiry:
                await self._fetch_token()
            return self._token  # type: ignore[return-value]

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def _call(self, method: str, path: str, **kwargs) -> dict:
        """Execute an authenticated HTTP call with retry logic."""
        # Capture headers once before retry loop to avoid mutation issues
        original_headers = kwargs.pop("headers", {})

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=self._retry_wait,
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        ):
            with attempt:
                token = await self._ensure_token()
                headers = {**original_headers, "Authorization": f"Bearer {token}"}
                response = await self._http.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    **kwargs,
                )
                if not response.is_success:
                    try:
                        body = response.json()
                        exc = map_icm_error(body)
                        if response.status_code >= 500:
                            # Re-raise as HTTPStatusError so tenacity retries
                            raise httpx.HTTPStatusError(
                                str(exc), request=response.request, response=response
                            )
                        raise exc
                    except (ValueError, KeyError):
                        response.raise_for_status()
                return response.json()

        raise ICMServiceUnavailableError("Unexpected retry exhaustion")  # pragma: no cover

    async def _call_with_breaker(self, method: str, path: str, **kwargs) -> dict:
        """Wrap _call with circuit breaker protection."""
        return await self._breaker.call_async(self._call, method, path, **kwargs)

    async def _call_bytes(self, method: str, path: str, **kwargs) -> bytes:
        """Like _call, but returns raw bytes instead of parsed JSON."""
        original_headers = kwargs.pop("headers", {})

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=self._retry_wait,
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        ):
            with attempt:
                token = await self._ensure_token()
                headers = {**original_headers, "Authorization": f"Bearer {token}"}
                response = await self._http.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    **kwargs,
                )
                response.raise_for_status()
                return response.content

        raise ICMServiceUnavailableError("Unexpected retry exhaustion")  # pragma: no cover

    async def _get_bytes(self, path: str, **kwargs) -> bytes:
        return await self._breaker.call_async(self._call_bytes, "GET", path, **kwargs)

    async def _get(self, path: str, **kwargs) -> dict:
        return await self._call_with_breaker("GET", path, **kwargs)

    async def _post(self, path: str, **kwargs) -> dict:
        return await self._call_with_breaker("POST", path, **kwargs)

    async def _put(self, path: str, **kwargs) -> dict:
        return await self._call_with_breaker("PUT", path, **kwargs)

    async def _delete(self, path: str, **kwargs) -> dict:
        return await self._call_with_breaker("DELETE", path, **kwargs)
