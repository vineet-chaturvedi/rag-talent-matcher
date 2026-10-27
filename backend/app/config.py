"""
Central configuration.

Every setting has a default here, and can be overridden by an environment
variable or a line in backend/.env (names are case-insensitive:
EMBED_MODEL in .env -> settings.embed_model in Python).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Where to read values from. extra="ignore" = unknown keys in .env don't crash the app.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- App ----
    app_name: str = "RAG Talent Matcher"
    environment: str = "development"
    log_level: str = "INFO"

    # ---- Ollama ----
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 300.0
    embed_model: str = "nomic-embed-text"
    fast_llm_model: str = "qwen2.5:3b"
    quality_llm_model: str = "qwen2.5:7b"
    llm_num_ctx: int = 8192

    # ---- Database ----
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    db_echo: bool = False

    # ---- Frontend ----
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


@lru_cache  # read .env once, then reuse the same Settings object everywhere
def get_settings() -> Settings:
    return Settings()