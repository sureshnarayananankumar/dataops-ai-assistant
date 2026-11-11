"""
config.py - Central place for all application settings.

Settings are read from the .env file in the project root (one level above
backend/). Every other module imports `settings` from here instead of reading
environment variables directly, so configuration lives in ONE place.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[0]=app, [1]=backend, [2]=project root
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

PLACEHOLDER_KEYS = {"", "your-google-api-key-here", "your-openai-api-key-here"}


class Settings(BaseSettings):
    # --- Which provider to use: "gemini" or "openai" ---
    llm_provider: str = "gemini"

    # --- Google Gemini (free tier available) ---
    google_api_key: str = ""
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"

    # --- OpenAI (optional, paid) ---
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # --- RAG ---
    chunk_size: int = 1000
    chunk_overlap: int = 150
    top_k: int = 4

    # --- Storage ---
    data_dir: str = "./data"
    chroma_collection: str = "dataops_docs"

    # --- CORS ---
    frontend_origin: str = "http://localhost:5173"

    # Field names map to env vars case-insensitively (google_api_key <- GOOGLE_API_KEY).
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Derived values (computed, not read from .env) ----
    @property
    def provider(self) -> str:
        return self.llm_provider.strip().lower()

    @property
    def chat_model(self) -> str:
        return self.gemini_chat_model if self.provider == "gemini" else self.openai_chat_model

    @property
    def embedding_model(self) -> str:
        return (
            self.gemini_embedding_model if self.provider == "gemini" else self.openai_embedding_model
        )

    @property
    def api_key_configured(self) -> bool:
        """True if the key for the selected provider is filled in (never reveals it)."""
        key = self.google_api_key if self.provider == "gemini" else self.openai_api_key
        return key.strip() not in PLACEHOLDER_KEYS

    @property
    def data_path(self) -> Path:
        """Absolute path of the data folder (relative paths start at backend/)."""
        p = Path(self.data_dir)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()

    @property
    def uploads_path(self) -> Path:
        return self.data_path / "uploads"

    @property
    def chroma_path(self) -> Path:
        return self.data_path / "chroma"


@lru_cache
def get_settings() -> Settings:
    """Create Settings once and reuse it (lru_cache = simple singleton)."""
    return Settings()


settings = get_settings()
