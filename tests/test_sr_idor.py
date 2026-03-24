"""Tests for IDOR fix: SR draft operations must include user_id in ORM WHERE clauses."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.service_requests.models import SRDraftResponse, SRType
from app.domains.service_requests.service import ServiceRequestService
from app.models.service_requests import SRDraft


_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_draft_orm_obj():
    """Create an SRDraft ORM instance to be returned by mocked queries."""
    obj = MagicMock(spec=SRDraft)
    obj.sr_id = "SR-001"
    obj.user_id = "user-abc"
    obj.sr_type = "ASSIST"
    obj.draft_json = {"answers": {"reason": "test"}, "page_index": 0}
    obj.updated_at = _NOW
    return obj


def _make_session_mock(scalar_return=None):
    """Create an AsyncMock session whose execute().scalar_one_or_none() returns the given value."""
    if scalar_return is None:
        scalar_return = _make_draft_orm_obj()
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = scalar_return
    session.execute.return_value = result_mock
    return session


def _compiled_sql(stmt) -> str:
    """Compile an ORM statement to a string for assertion."""
    return str(stmt.compile())


# ---------------------------------------------------------------------------
# get_draft must include user_id in WHERE clause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_draft_includes_user_id_in_query():
    """get_draft(sr_id, user_id=...) must include user_id in the ORM WHERE clause."""
    session = _make_session_mock()
    sr_client = AsyncMock()
    svc = ServiceRequestService(sr_client=sr_client, session=session)

    await svc.get_draft("SR-001", user_id="user-abc")

    session.execute.assert_awaited_once()
    stmt = session.execute.call_args[0][0]
    compiled = _compiled_sql(stmt)
    assert "user_id" in compiled, "ORM WHERE clause must reference user_id"


# ---------------------------------------------------------------------------
# save_form_draft must include user_id in WHERE clause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_form_draft_includes_user_id_in_query():
    """save_form_draft(sr_id, ..., user_id=...) must include user_id in the ORM WHERE clause."""
    session = _make_session_mock()
    sr_client = AsyncMock()
    svc = ServiceRequestService(sr_client=sr_client, session=session)

    await svc.save_form_draft(
        "SR-001", answers={"reason": "test"}, page_index=0, user_id="user-abc"
    )

    session.execute.assert_awaited_once()
    stmt = session.execute.call_args[0][0]
    compiled = _compiled_sql(stmt)
    assert "user_id" in compiled, "ORM WHERE clause must reference user_id"


# ---------------------------------------------------------------------------
# submit_sr draft deletion must include user_id in WHERE clause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_sr_delete_includes_user_id_in_query():
    """submit_sr(..., user_id=...) must include user_id when deleting the draft."""
    from app.domains.account.pin_service import PINService

    session = _make_session_mock()
    sr_client = AsyncMock()
    sr_client.finalize_sr_form = AsyncMock(return_value={"sr_number": "SR-NUM-001"})

    pin_svc = PINService(client=AsyncMock())
    pin_svc.validate = AsyncMock(return_value=True)

    svc = ServiceRequestService(sr_client=sr_client, session=session, pin_service=pin_svc)

    draft = SRDraftResponse(
        sr_id="SR-001",
        sr_type=SRType.ASSIST,
        draft_json={"answers": {"reason": "test"}, "page_index": 0},
        updated_at=_NOW,
    )

    with (
        patch.object(svc, "get_draft", return_value=draft) as mock_get_draft,
        patch(
            "app.domains.service_requests.pdf_generation_service.PDFGenerationService"
        ),
    ):
        await svc.submit_sr(
            sr_id="SR-001",
            pin="1234",
            spouse_pin=None,
            bceid_guid="guid-123",
            user_id="user-abc",
        )

        # get_draft should have been called with user_id
        mock_get_draft.assert_awaited_once_with("SR-001", user_id="user-abc")

        # Find the DELETE call (the last execute call on the session)
        delete_call = session.execute.call_args_list[-1]
        stmt = delete_call[0][0]
        compiled = _compiled_sql(stmt)

        assert "DELETE" in compiled.upper(), "Should be a DELETE statement"
        assert "user_id" in compiled, "DELETE WHERE clause must reference user_id"
