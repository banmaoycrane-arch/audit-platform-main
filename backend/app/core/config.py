from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
BACKEND_ENV_FILE = BACKEND_DIR / ".env"
DEFAULT_SQLITE_DATABASE_URL = f"sqlite:///{(BACKEND_DIR / 'finance_audit.db').as_posix()}"


class Settings(BaseSettings):
    database_url: str = DEFAULT_SQLITE_DATABASE_URL
    qdrant_url: str = "http://localhost:6333"
    qdrant_local_path: str = "qdrant_local_storage"
    qdrant_collection: str = "accounting_chunks"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: str = "storage/uploads"
    ai_provider: str = "openai-compatible"
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_local_model_enabled: bool = True
    ai_fallback_to_rules: bool = True
    embedding_dimension: int = 384
    secret_key: str | None = None

    model_config = SettingsConfigDict(env_file=BACKEND_ENV_FILE, env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
