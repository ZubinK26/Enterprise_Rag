from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _PACKAGE_DIR.parent


class Settings(BaseSettings):
    """Application configuration loaded from environment and optional `.env` file."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Enterprise RAG + Agent Evaluator"

    docs_dir: Path = Field(default=_PACKAGE_DIR / "data" / "docs")
    vector_store_dir: Path = Field(default=_PACKAGE_DIR / "data" / "vector_store")
    logs_db_path: Path = Field(default=_PACKAGE_DIR / "data" / "logs.db")

    llm_api_key: str = ""
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_model: str = "gemini-3-flash-preview"
    embedding_model: str = ""

    default_top_k: int = Field(default=3, ge=1, le=50)


@lru_cache
def get_settings() -> Settings:
    return Settings()
