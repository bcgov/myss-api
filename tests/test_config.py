import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the lru_cache on get_settings between tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_accepts_defaults_in_local(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    s = Settings()
    assert s.database_url.startswith("sqlite")
    assert s.environment == "local"


def test_settings_rejects_insecure_jwt_in_prod(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("ICM_BASE_URL", "https://icm.example.com")
    monkeypatch.setenv("ICM_CLIENT_ID", "id")
    monkeypatch.setenv("ICM_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ICM_TOKEN_URL", "https://icm.example.com/token")
    monkeypatch.setenv("JWT_SECRET", "change-me-in-production")
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings()


def test_settings_rejects_missing_icm_in_prod(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("JWT_SECRET", "a-real-secret-that-is-long-enough")
    monkeypatch.delenv("ICM_BASE_URL", raising=False)
    with pytest.raises(ValidationError, match="ICM_"):
        Settings()


def test_settings_reads_all_icm_vars(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("ICM_BASE_URL", "https://icm.example.com")
    monkeypatch.setenv("ICM_CLIENT_ID", "myid")
    monkeypatch.setenv("ICM_CLIENT_SECRET", "mysecret")
    monkeypatch.setenv("ICM_TOKEN_URL", "https://icm.example.com/token")
    s = Settings()
    assert s.icm_base_url == "https://icm.example.com"
    assert s.icm_client_id == "myid"
