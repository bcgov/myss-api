import pytest
from unittest.mock import AsyncMock
from app.domains.registration.service import RegistrationService


@pytest.mark.asyncio
async def test_start_registration_sets_step_1():
    """Newly created session has step_reached = 1 (step 1 = session created)."""
    session = AsyncMock()
    redis = AsyncMock()
    svc = RegistrationService(session=session, redis=redis)
    from unittest.mock import MagicMock
    await svc.start_registration(account_creation_type=MagicMock(value="new"))
    # Verify the INSERT SQL includes step_reached = 1
    call_args = session.execute.call_args
    sql_text = str(call_args[0][0].text)
    assert ", 1," in sql_text, "step_reached should be 1 in the INSERT"
