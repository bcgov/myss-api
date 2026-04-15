import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.icm.exceptions import ICMError


@pytest.mark.asyncio
async def test_unhandled_icm_error_returns_502():
    """Unmapped ICMError subclasses should return 502 via base-class fallthrough handler."""

    @app.get("/_test/raise-icm")
    async def _raise():
        raise ICMError("icm upstream failure")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/_test/raise-icm")

        assert response.status_code == 502
        assert "upstream" in response.json()["detail"].lower()
    finally:
        # Remove the throwaway route so it doesn't leak to other tests
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/_test/raise-icm"]
