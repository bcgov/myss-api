# app/domains/registration/service.py
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.domains.registration.models import (
    AccountCreationType,
    RegistrationSessionState,
)

# Invite token TTL — OQ-D1-06: FDD does not specify; defaulting to 72 hours
INVITE_TOKEN_TTL_HOURS = 72
# Registration session TTL — total time to complete all 5 steps
SESSION_TTL_HOURS = 168  # 7 days


class RegistrationService:
    """Manages registration wizard state in PostgreSQL.

    Replaces: Session["RegistrationID"], Session["poaModel"],
              Session["ValidRegistration"], TempData["step1complete"]

    Each registration session is keyed by a cryptographic UUID token
    delivered to the client in the step URL and invite email link.
    The server never stores the token in a server-side session.
    """

    def __init__(self, session: AsyncSession, redis: aioredis.Redis) -> None:
        self._session = session
        self._redis = redis

    def _generate_token(self) -> str:
        return str(uuid.uuid4())

    def _generate_invite_token(self) -> str:
        return str(uuid.uuid4())

    def hash_pin(self, pin: str) -> tuple[str, str]:
        """Hash a 4-digit PIN using PBKDF2-HMAC-SHA256 with a random salt.

        Returns (hash_hex, salt_hex). Replaces TAAPCD_AAE_PASSCODE hash+salt.
        """
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, iterations=260_000)
        return key.hex(), salt.hex()

    def verify_pin(self, pin: str, stored_hash: str, stored_salt: str) -> bool:
        """Verify a PIN against stored hash and salt."""
        salt = bytes.fromhex(stored_salt)
        key = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, iterations=260_000)
        return hmac.compare_digest(key.hex(), stored_hash)

    async def start_registration(
        self,
        account_creation_type: AccountCreationType,
    ) -> str:
        """Create a new RegistrationSession row and return the session token.

        Sets step_reached = 1 because step 1 (session creation) completes
        immediately. Convention: step_reached = N means steps 1..N are done.
        """
        token = self._generate_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)

        await self._session.execute(
            text(
                "INSERT INTO registration_sessions "
                "(token, account_creation_type, step_reached, expires_at) "
                "VALUES (:token, :act, 1, :exp)"
            ),
            {"token": token, "act": account_creation_type.value, "exp": expires_at},
        )
        await self._session.commit()
        return token

    async def get_session_by_token(self, token: str) -> Optional[RegistrationSessionState]:
        """Load a RegistrationSession by token. Returns None if not found or expired."""
        result = await self._session.execute(
            text(
                "SELECT token, account_creation_type, step_reached, poa_data, "
                "registrant_data, spouse_data, invite_token, invite_token_used, "
                "pin_hash, pin_salt, user_id, expires_at "
                "FROM registration_sessions "
                "WHERE token = :token AND expires_at > NOW()"
            ),
            {"token": token},
        )
        row = result.fetchone()
        if row is None:
            return None

        return RegistrationSessionState(
            token=row.token,
            account_creation_type=AccountCreationType(row.account_creation_type),
            step_reached=row.step_reached,
            poa_data=row.poa_data,
            registrant_data=row.registrant_data,
            spouse_data=row.spouse_data,
            invite_token=row.invite_token,
            invite_token_used=bool(row.invite_token_used),
            pin_hash=row.pin_hash,
            pin_salt=row.pin_salt,
            user_id=row.user_id,
            expires_at=row.expires_at,
        )

    async def advance_step(self, token: str, to_step: int) -> None:
        """Update step_reached for an existing session. Never regresses below the current step."""
        result = await self._session.execute(
            text(
                "UPDATE registration_sessions "
                "SET step_reached = GREATEST(step_reached, :step) "
                "WHERE token = :token"
            ),
            {"step": to_step, "token": token},
        )
        if result.rowcount == 0:
            raise ValueError(f"Registration session not found: {token}")
        await self._session.commit()

    async def save_registrant_data(
        self,
        token: str,
        registrant_data: dict,
        spouse_data: Optional[dict] = None,
    ) -> None:
        """Persist personal information (step 2) to the session row."""
        result = await self._session.execute(
            text(
                "UPDATE registration_sessions "
                "SET registrant_data = :rd, spouse_data = :sd, step_reached = GREATEST(step_reached, 2) "
                "WHERE token = :token"
            ),
            {"rd": registrant_data, "sd": spouse_data, "token": token},
        )
        if result.rowcount == 0:
            raise ValueError(f"Registration session not found: {token}")
        await self._session.commit()

    async def issue_invite_token(self, token: str) -> str:
        """Generate a single-use invite token for email verification (BR-D1-09)."""
        invite = self._generate_invite_token()
        result = await self._session.execute(
            text(
                "UPDATE registration_sessions "
                "SET invite_token = :invite, invite_token_used = false, "
                "    step_reached = GREATEST(step_reached, 3) "
                "WHERE token = :token"
            ),
            {"invite": invite, "token": token},
        )
        if result.rowcount == 0:
            raise ValueError(f"Registration session not found: {token}")
        await self._session.commit()
        return invite

    async def consume_invite_token(self, invite_token: str) -> Optional[str]:
        """Mark an invite token as used. Returns the session token, or None if not found/used.

        BR-D1-09: Invite token is single-use. Uses a single atomic UPDATE...RETURNING
        to prevent TOCTOU race conditions under concurrent requests.
        """
        result = await self._session.execute(
            text(
                "UPDATE registration_sessions "
                "SET invite_token_used = true, step_reached = GREATEST(step_reached, 4) "
                "WHERE invite_token = :invite AND invite_token_used = false "
                "  AND expires_at > NOW() "
                "RETURNING token"
            ),
            {"invite": invite_token},
        )
        row = result.fetchone()
        if row is None:
            return None
        await self._session.commit()
        return row.token

    async def save_pin(self, token: str, pin: str) -> None:
        """Hash and persist the PIN (step 4). BR-D1-10."""
        pin_hash, pin_salt = self.hash_pin(pin)
        result = await self._session.execute(
            text(
                "UPDATE registration_sessions "
                "SET pin_hash = :ph, pin_salt = :ps, step_reached = GREATEST(step_reached, 5) "
                "WHERE token = :token"
            ),
            {"ph": pin_hash, "ps": pin_salt, "token": token},
        )
        if result.rowcount == 0:
            raise ValueError(f"Registration session not found: {token}")
        await self._session.commit()

    async def complete_registration(
        self,
        token: str,
        user_id: int,
    ) -> None:
        """Link the registration session to the created user (step 6 — BCeID link).

        BR-D1-21: In the full implementation (Task 16), this will be called within
        an outer transaction that also creates the User and Profile rows and calls
        ICM INT330. For now it owns its own commit.
        """
        result = await self._session.execute(
            text(
                "UPDATE registration_sessions "
                "SET user_id = :uid, step_reached = 6 "
                "WHERE token = :token"
            ),
            {"uid": user_id, "token": token},
        )
        if result.rowcount == 0:
            raise ValueError(f"Registration session not found: {token}")
        await self._session.commit()
