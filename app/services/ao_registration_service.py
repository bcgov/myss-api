"""AO Registration Service — handles AO registration session lifecycle."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt

from app.models.ao_registration import AORegistrationSession
from app.services.icm.admin import SiebelAdminClient
from app.services.icm.exceptions import ICMError

AO_SESSION_EXPIRY_DAYS = 30


class AOLoginError(Exception):
    """Raised when AO login credentials are invalid."""


class AORegistrationService:
    """Service for AO registration session management."""

    def __init__(self, admin_client: SiebelAdminClient | None = None) -> None:
        self._admin_client = admin_client

    async def login(
        self,
        sr_number: str,
        sin: str,
        worker_idir: str,
    ) -> AORegistrationSession:
        """Validate SR number + SIN against ICM, create and return a new AO session.

        Raises AOLoginError if credentials are invalid.
        """
        if self._admin_client is None:
            raise AOLoginError("No ICM admin client configured")

        try:
            await self._admin_client.validate_ao_login(sr_number, sin)
        except ICMError as exc:
            raise AOLoginError("Invalid SR number or SIN") from exc

        # Hash the SIN off the event loop — bcrypt is intentionally slow
        sin_hash = await asyncio.get_event_loop().run_in_executor(
            None, lambda: bcrypt.hashpw(sin.encode(), bcrypt.gensalt()).decode()
        )

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=AO_SESSION_EXPIRY_DAYS)

        session = AORegistrationSession(
            session_token=uuid4(),
            worker_idir=worker_idir,
            applicant_sr_num=sr_number,
            applicant_sin_hash=sin_hash,
            step_reached=1,
            expires_at=expires_at,
        )
        return session

    def get_step_data(self, session: AORegistrationSession, step: int) -> dict:
        """Return current step data for the given session."""
        return {
            "step": step,
            "step_reached": session.step_reached,
            "applicant_sr_num": session.applicant_sr_num,
            "data": {},
        }

    def advance_step(self, session: AORegistrationSession, step: int) -> AORegistrationSession:
        """Advance step_reached if the submitted step is the current frontier."""
        if step >= session.step_reached:
            session.step_reached = step + 1
        return session
