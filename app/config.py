"""Centralized application configuration using Pydantic BaseSettings.

All environment variables are validated at startup. Required vars (like ICM_*)
will raise a clear error in non-local environments rather than a KeyError at
first request time.
"""

import os
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment
    environment: str = "local"

    # Database
    database_url: str = "sqlite+aiosqlite:///./dev.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT (validated by auth/dependencies.py at startup)
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"

    # CORS
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # ICM / Siebel (required in non-local environments)
    icm_base_url: str = ""
    icm_client_id: str = ""
    icm_client_secret: str = ""
    icm_token_url: str = ""

    # Webhooks
    av_webhook_secret: str = ""

    # SIN encryption
    sin_hmac_key: str = "change-me-in-production"

    # Feature flags
    feature_t5_disabled: bool = False

    model_config = {"env_prefix": "", "case_sensitive": False}

    @model_validator(mode="after")
    def validate_production_config(self):
        if self.environment in ("local", "test"):
            return self
        insecure = {"change-me-in-production", "secret", ""}
        if self.jwt_secret in insecure:
            raise ValueError(
                "JWT_SECRET must be set to a secure value in non-local environments"
            )
        if not all(
            [
                self.icm_base_url,
                self.icm_client_id,
                self.icm_client_secret,
                self.icm_token_url,
            ]
        ):
            raise ValueError(
                "All ICM_* environment variables are required in non-local environments"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
