"""Unit tests for PINService helper methods."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.account.pin_service import PINService
from app.services.icm.exceptions import PINValidationError


@pytest.mark.asyncio
async def test_validate_or_raise_passes_on_valid_pin():
    mock_client = MagicMock()
    mock_client.validate_pin = AsyncMock(return_value={"valid": True})
    svc = PINService(client=mock_client)

    # Should not raise
    await svc.validate_or_raise("bceid-1234", "1234")
    mock_client.validate_pin.assert_awaited_once_with("bceid-1234", "1234")


@pytest.mark.asyncio
async def test_validate_or_raise_raises_on_invalid_pin():
    mock_client = MagicMock()
    mock_client.validate_pin = AsyncMock(return_value={"valid": False})
    svc = PINService(client=mock_client)

    with pytest.raises(PINValidationError):
        await svc.validate_or_raise("bceid-1234", "0000")
