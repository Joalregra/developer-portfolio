from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]
    groq_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    database_url: str | None = None
    knowledge_path: Path = BASE_DIR / "knowledge" / "ChatbotKnowledge.en.md"


@lru_cache
def get_settings() -> Settings:
    return Settings()
