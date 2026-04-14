"""Tests for mock ICM client injection."""

import os
import pytest
from unittest.mock import patch

from app.services.icm.deps import get_siebel_client, clear_clients, _use_mock
from app.services.icm.payment import SiebelPaymentClient
from app.services.icm.account import SiebelAccountClient
from app.services.icm.mock.payment import MockPaymentClient
from app.services.icm.mock.account import MockAccountClient


@pytest.fixture(autouse=True)
def _clean_clients():
    """Reset client cache between tests."""
    clear_clients()
    yield
    clear_clients()


class TestUseMock:
    @patch.dict(os.environ, {"ENVIRONMENT": "local", "ICM_BASE_URL": ""})
    def test_returns_true_when_local_and_no_base_url(self):
        # get_settings is lru_cached, so we need to clear it
        from app.config import get_settings
        get_settings.cache_clear()
        assert _use_mock() is True
        get_settings.cache_clear()

    @patch.dict(os.environ, {"ENVIRONMENT": "local", "ICM_BASE_URL": "https://icm.example.com"})
    def test_returns_false_when_base_url_set(self):
        from app.config import get_settings
        get_settings.cache_clear()
        assert _use_mock() is False
        get_settings.cache_clear()

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "ICM_BASE_URL": "https://icm.example.com", "JWT_SECRET": "strong-secret-123456", "ICM_CLIENT_ID": "id", "ICM_CLIENT_SECRET": "sec", "ICM_TOKEN_URL": "https://tok"})
    def test_returns_false_when_not_local(self):
        from app.config import get_settings
        get_settings.cache_clear()
        assert _use_mock() is False
        get_settings.cache_clear()


class TestMockClientInjection:
    @patch.dict(os.environ, {"ENVIRONMENT": "local", "ICM_BASE_URL": ""})
    def test_returns_mock_payment_client_in_local_mode(self):
        from app.config import get_settings
        get_settings.cache_clear()
        client = get_siebel_client(SiebelPaymentClient)
        assert isinstance(client, MockPaymentClient)
        get_settings.cache_clear()

    @patch.dict(os.environ, {"ENVIRONMENT": "local", "ICM_BASE_URL": ""})
    def test_returns_mock_account_client_in_local_mode(self):
        from app.config import get_settings
        get_settings.cache_clear()
        client = get_siebel_client(SiebelAccountClient)
        assert isinstance(client, MockAccountClient)
        get_settings.cache_clear()

    @patch.dict(os.environ, {"ENVIRONMENT": "local", "ICM_BASE_URL": ""})
    def test_caches_mock_clients(self):
        from app.config import get_settings
        get_settings.cache_clear()
        client1 = get_siebel_client(SiebelPaymentClient)
        client2 = get_siebel_client(SiebelPaymentClient)
        assert client1 is client2
        get_settings.cache_clear()


class TestMockClientData:
    """Verify mock clients return expected data shapes."""

    @pytest.mark.asyncio
    async def test_payment_info_has_required_fields(self):
        client = MockPaymentClient()
        result = await client.get_payment_info("100100")
        assert "assistance_type" in result
        assert "mis_data" in result
        assert "allowances" in result["mis_data"]

    @pytest.mark.asyncio
    async def test_account_profile_has_required_fields(self):
        from app.services.icm.mock.data import ALICE_USER_ID
        client = MockAccountClient()
        result = await client.get_profile(ALICE_USER_ID)
        assert result["first_name"] == "Alice"
        assert result["case_status"] == "Active"
        assert "phone_numbers" in result

    @pytest.mark.asyncio
    async def test_unknown_id_returns_fallback(self):
        client = MockAccountClient()
        result = await client.get_profile("nonexistent-id")
        # Should return Alice's data as fallback
        assert result["first_name"] == "Alice"
