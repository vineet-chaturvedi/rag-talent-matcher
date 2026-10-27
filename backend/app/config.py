"""
Central configuration.

Every setting has a default here, and can be overridden by an environment
variable or a line in backend/.env (names are case-insensitive:
EMBED_MODEL in .env -> settings.embed_model in Python).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    # ---- Uploads & ingestion (Step 4) ----
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 10              # per file
    max_files_per_batch: int = 200       # per bulk-upload request
    worker_enabled: bool = True          # background processing on/off
    worker_poll_seconds: float = 5.0     # how often an idle worker re-checks the queue
    worker_max_attempts: int = 3         # retries for unexpected errors
    min_chars_per_page: int = 100        # less text than this per PDF page = probably a scanned image

    # ---- Frontend ----
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()