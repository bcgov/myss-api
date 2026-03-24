import pytest
from unittest.mock import AsyncMock, MagicMock
from app.domains.service_requests.service import ServiceRequestService


@pytest.mark.asyncio
async def test_save_form_draft_rolls_back_on_no_match():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    svc = ServiceRequestService(sr_client=AsyncMock(), session=session)
    result = await svc.save_form_draft("nonexistent", {"q": "a"}, 0, user_id="u1")

    assert result is None
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
