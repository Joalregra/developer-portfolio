"""Application settings, read once from environment variables and `backend/.env`.

Secrets are `SecretStr` so they never show up in a repr or a log line by accident.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed configuration. Every value can be overridden with an environment variable."""

    # An empty line such as `GROQ_API_KEY=` in .env.example means "not set", not an empty secret.
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", extra="ignore", env_ignore_empty=True
    )

    app_name: str = "Johan Rendon Portfolio API"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]
    # Rejects bigger bodies before parsing them (SEC-04). The 1000-character limit on a message
    # is checked later by Pydantic; this one protects the server from huge uploads.
    max_body_bytes: int = Field(default=16_384, gt=0)

    # Database. The app user can only INSERT and SELECT (DATA-07); migrations use the owner.
    database_url: SecretStr | None = None
    migration_database_url: SecretStr | None = None
    # Only the retention job reads it (user portfolio_retention: SELECT and DELETE). The running
    # app never needs it, so it can stay unset there.
    retention_database_url: SecretStr | None = None
    chat_log_retention_days: int = Field(default=90, gt=0)

    # LLM providers. Model names are configuration, not code: free tiers change often (LLM-01).
    groq_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    groq_model: str | None = None
    gemini_model: str | None = None
    guard_model: str | None = None
    knowledge_dir: Path = BASE_DIR / "knowledge"
    # Random string placed in the system prompt to detect prompt leakage (PI-07).
    canary_token: SecretStr | None = None
    # Public address of the portfolio. Answers may link to it; every other link is removed.
    site_url: str | None = None
    # Low temperature: answers should stick to the knowledge, and OWASP lists it against jailbreaks.
    llm_temperature: float = Field(default=0.3, ge=0, le=1)
    # Includes the model's hidden reasoning. Real answers use about 150; this leaves headroom.
    llm_max_output_tokens: int = Field(default=800, gt=0)
    # Prompt Guard returns a score from 0 to 1. Normal questions score below 0.001 and clear
    # attacks above 0.99, so anything from here up is blocked.
    guard_threshold: float = Field(default=0.8, gt=0, le=1)

    # Abuse limits for the public chat endpoint (section 9.4 of the backend brief).
    chat_enabled: bool = True
    # Country of the visitor comes from Cloudflare's CF-IPCountry header. Only trust it once the
    # API is really behind Cloudflare; otherwise anyone could set it.
    trust_cloudflare_headers: bool = False
    rate_limit_per_minute: int = Field(default=10, gt=0)
    rate_limit_per_day: int = Field(default=30, gt=0)
    daily_llm_budget: int = Field(default=300, gt=0)
    # Repeated questions are answered from memory, without a model call. 0 switches it off.
    answer_cache_ttl_seconds: int = Field(default=86_400, ge=0)
    answer_cache_max_entries: int = Field(default=500, gt=0, le=10_000)

    # Time limits for every external call (ERR-06).
    guard_timeout_seconds: float = Field(default=3.0, gt=0)
    groq_timeout_seconds: float = Field(default=12.0, gt=0)
    gemini_timeout_seconds: float = Field(default=15.0, gt=0)
    request_timeout_seconds: float = Field(default=25.0, gt=0)

    @model_validator(mode="after")
    def require_explicit_https_origins_in_production(self) -> Self:
        """Fail at startup rather than serve production open to the wrong origins (SEC-02)."""
        if self.environment != "production":
            return self
        unsafe = [
            origin
            for origin in self.cors_origins
            if not origin.startswith("https://") or "localhost" in origin or "*" in origin
        ]
        if unsafe or not self.cors_origins:
            raise ValueError("In production, CORS_ORIGINS must list only explicit https origins.")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def missing_chat_settings(self) -> list[str]:
        """Names of the settings the chat needs but that are not set. Empty when all are there."""
        required = {
            "GROQ_API_KEY": self.groq_api_key,
            "GROQ_MODEL": self.groq_model,
            "GUARD_MODEL": self.guard_model,
            "CANARY_TOKEN": self.canary_token,
        }
        return [name for name, value in required.items() if value is None]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings. Cached so `.env` is parsed only once."""
    return Settings()
