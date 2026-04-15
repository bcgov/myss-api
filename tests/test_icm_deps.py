import pytest
from unittest.mock import patch

from app.services.icm.deps import _use_mock
from app.config import get_settings


def _fake_settings(environment: str, icm_base_url: str = ""):
    settings = get_settings()
    return settings.model_copy(update={"environment": environment, "icm_base_url": icm_base_url})


@pytest.mark.parametrize(
    "environment, icm_base_url, expected",
    [
        ("local", "", True),
        ("local", "https://icm.example.com", False),
        ("test", "", True),
        ("test", "https://icm.example.com", False),
        ("dev", "", False),
        ("prod", "", False),
        ("prod", "https://icm.example.com", False),
    ],
)
def test_use_mock_gate(environment: str, icm_base_url: str, expected: bool):
    fake = _fake_settings(environment, icm_base_url)
    with patch("app.services.icm.deps.get_settings", return_value=fake):
        assert _use_mock() is expected
