"""Repository owning persistence of in-progress SR drafts (sr_drafts table)."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_requests import SRDraft


class SRDraftRepository:
    """Owns persistence of in-progress SR drafts in the `sr_drafts` table."""

    def __init__(self, session: Optional[AsyncSession] = None):
        self._session = session

    async def create(self, sr_id: str, user_id: str, sr_type: str) -> None:
        """Insert a new draft row for a freshly created SR."""
        if not self._session:
            return

        draft = SRDraft(sr_id=sr_id, user_id=user_id, sr_type=sr_type)
        self._session.add(draft)
        await self._session.commit()

    async def get(self, sr_id: str, user_id: str | None = None) -> Optional[SRDraft]:
        """Retrieve a draft by sr_id, optionally scoped to a specific user."""
        if not self._session:
            return None

        stmt = select(SRDraft).where(SRDraft.sr_id == sr_id)
        if user_id is not None:
            stmt = stmt.where(SRDraft.user_id == user_id)

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_form(
        self,
        sr_id: str,
        answers: dict,
        page_index: int,
        user_id: str | None = None,
    ) -> Optional[SRDraft]:
        """Update draft_json for an existing row. Returns the updated row or None."""
        if not self._session:
            return None

        stmt = (
            update(SRDraft)
            .where(SRDraft.sr_id == sr_id)
            .values(
                draft_json={"answers": answers, "page_index": page_index},
                updated_at=datetime.now(timezone.utc),
            )
            .returning(SRDraft)
        )
        if user_id is not None:
            stmt = stmt.where(SRDraft.user_id == user_id)

        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            await self._session.rollback()
            return None
        await self._session.commit()
        return row

    async def delete(self, sr_id: str, user_id: str | None = None) -> None:
        """Delete a draft row, optionally scoped to a specific user."""
        if not self._session:
            return

        stmt = delete(SRDraft).where(SRDraft.sr_id == sr_id)
        if user_id is not None:
            stmt = stmt.where(SRDraft.user_id == user_id)
        await self._session.execute(stmt)
        await self._session.commit()
