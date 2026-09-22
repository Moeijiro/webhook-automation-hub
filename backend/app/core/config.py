"""Application configuration, read from the environment or a local .env file."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # --- Runtime ---------------------------------------------------------
    environment: Literal["development", "production"] = "development"
    public_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"

    # --- Database --------------------------------------------------------
    database_url: str = "sqlite:///./webhook_hub.db"

    # --- Security --------------------------------------------------------
    secret_key: str = Field(default="dev-only-insecure-secret", min_length=8)
    access_token_ttl_minutes: int = Field(default=720, ge=5)
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    allow_registration: bool = True

    # --- Execution limits -------------------------------------------------
    max_payload_bytes: int = Field(default=64 * 1024, ge=1024, le=1024 * 1024)
    action_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    max_attempts: int = Field(default=3, ge=1, le=5)
    allow_private_network_targets: bool = False

    @field_validator("public_base_url", "frontend_url")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def _guard_production(self) -> "Settings":
        """Refuse to boot with a known-insecure configuration in production."""
        if self.environment == "production":
            if "insecure" in self.secret_key or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be a strong value in production")
            if self.allow_private_network_targets:
                raise ValueError(
                    "ALLOW_PRIVATE_NETWORK_TARGETS must be false in production: "
                    "it disables the SSRF guard on outbound actions"
                )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_url]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
