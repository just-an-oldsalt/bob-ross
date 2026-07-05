"""Configuration for Bob Ross, loaded from environment (BOBROSS_* / .env).

Secure by default: read-only mode is on, writes are disabled, TLS is verified.
Secrets are marked ``repr=False`` so they never leak into logs or tracebacks.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthMode(str, Enum):
    rest = "rest"
    legacy = "legacy"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOBROSS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Connection ──────────────────────────────────────────────────
    landscape_url: str = Field(..., description="Base URL of the Landscape server.")
    tls_verify: bool = True
    request_timeout: float = 30.0

    # ── Auth (one mode required) ────────────────────────────────────
    api_token: str | None = Field(default=None, repr=False)  # REST bearer
    access_key: str | None = Field(default=None, repr=False)  # legacy HMAC
    secret_key: str | None = Field(default=None, repr=False)  # legacy HMAC
    auth_mode: AuthMode | None = None  # derived below

    # ── Safety ──────────────────────────────────────────────────────
    read_only: bool = True
    allow_writes: bool = False
    confirm_ttl_seconds: int = 300
    audit_log_path: Path = Path("audit.log.jsonl")

    @model_validator(mode="after")
    def _resolve_auth(self) -> "Settings":
        if self.api_token:
            self.auth_mode = AuthMode.rest
        elif self.access_key and self.secret_key:
            self.auth_mode = AuthMode.legacy
        else:
            raise ValueError(
                "No Landscape credentials found. Set BOBROSS_API_TOKEN (REST) "
                "or both BOBROSS_ACCESS_KEY and BOBROSS_SECRET_KEY (legacy)."
            )
        if not self.landscape_url.startswith(("http://", "https://")):
            raise ValueError("BOBROSS_LANDSCAPE_URL must start with http:// or https://")
        return self

    @property
    def writes_enabled(self) -> bool:
        """Writes are only possible when explicitly opted in on both switches."""
        return (not self.read_only) and self.allow_writes
