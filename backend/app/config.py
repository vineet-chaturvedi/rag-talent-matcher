"""
Central configuration.

Every setting has a default here, and can be overridden by an environment
variable or a line in backend/.env (names are case-insensitive:
EMBED_MODEL in .env -> settings.embed_model in Python).
"""
from functools import lru_cache
from typing import Literal

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
    ollama_retry_seconds: float = 30.0   # if Ollama is down, the worker waits this long before trying again

    # ---- Structured extraction (Step 5) ----
    extraction_model_role: Literal["fast", "quality"] = "quality"  # which of the two LLMs reads resumes
    extraction_max_output_tokens: int = 2048   # hard cap on the JSON answer length
    extraction_max_input_chars: int = 16000    # ~4,000 tokens; longer resumes are truncated (with a warning)

    # ---- Chunking, embeddings & vector store (Step 6) ----
    chroma_dir: str = "./data/chroma"               # ChromaDB's files (git-ignored, rebuildable)
    chroma_collection: str = "resume_chunks"
    chunk_max_chars: int = 1200                     # ~300 tokens: one focused topic per chunk
    chunk_overlap_chars: int = 150                  # text repeated between neighbouring chunks
    embed_batch_size: int = 16                      # chunks sent to Ollama per /api/embed call
    anonymize_chunks: bool = True                   # remove name, email, phone from indexed text

    # ---- Matching: role parsing & hybrid retrieval (Step 7) ----
    role_parse_model_role: Literal["fast", "quality"] = "quality"  # which LLM reads role descriptions
    retrieval_vector_pool: int = 80          # nearest chunks fetched from ChromaDB
    retrieval_keyword_pool: int = 200        # best BM25 chunks fetched from the keyword index
    rrf_k: int = 60                          # Reciprocal Rank Fusion constant (60 is the standard value)
    rrf_weight_skills: float = 1.0           # how much each signal counts in the fusion
    rrf_weight_keyword: float = 1.0
    rrf_weight_vector: float = 1.0
    default_skill_min_years: float = 2.0     # years assumed "enough" when a role doesn't say

    # ---- Scoring & LLM judge (Step 8) ----
    score_skills_share: float = 0.85         # fit = 85% skill coverage + 15% retrieval relevance
    score_experience_floor: float = 0.6      # factor for "not enough years" ranges from 0.6 to 1.0
    score_availability_floor: float = 0.7    # factor for "not free in time" ranges from 0.7 to 1.0
    score_location_floor: float = 0.9        # factor for "other city" ranges from 0.9 to 1.0
    judge_model_role: Literal["fast", "quality"] = "quality"  # which LLM judges candidates
    judge_top_n: int = 5                     # how many top candidates the judge reads per run (default)
    judge_weight: float = 0.4                # final = (1 - w) × rule score + w × judge score
    judge_max_output_tokens: int = 1024      # cap on the judge's JSON answer
    judge_max_dossier_chars: int = 6000      # ~1,500 tokens of resume evidence per candidate

    # ---- Agent (Step 10) ----
    agent_model_role: Literal["fast", "quality"] = "quality"  # which LLM runs the agent (tool use needs quality)
    agent_max_steps: int = 4                 # tool rounds per question before the agent must answer
    agent_temperature: float = 0.0           # 0 = most predictable tool choices
    agent_max_output_tokens: int = 1024      # cap on one reply
    agent_history_messages: int = 10         # earlier user/assistant messages sent as memory
    agent_tool_result_chars: int = 6000      # tool results are cut beyond this (context window protection)

    # ---- Authentication (Step 9) ----
    jwt_secret: str | None = None            # signs login tokens; REQUIRED in production (see .env.example)
    access_token_minutes: int = 480          # how long a login lasts (480 = one working day)
    auth_cookie_name: str = "rtm_access"     # HttpOnly cookie used by the browser frontend

    # ---- Frontend ----
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def jwt_secret_value(self) -> str:
        """The signing secret. In development a random one is made if .env has none (logins end on restart)."""
        if self.jwt_secret:
            return self.jwt_secret
        if not self.is_development:
            raise RuntimeError("JWT_SECRET must be set in production (see .env.example).")
        global _DEV_SECRET
        if _DEV_SECRET is None:
            import secrets
            _DEV_SECRET = secrets.token_urlsafe(48)
        return _DEV_SECRET

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def agent_model(self) -> str:
        return self.fast_llm_model if self.agent_model_role == "fast" else self.quality_llm_model

    @property
    def judge_model(self) -> str:
        return self.fast_llm_model if self.judge_model_role == "fast" else self.quality_llm_model

    @property
    def score_weights(self):
        from app.matching.scoring import ScoreWeights   # imported here to avoid a circular import
        return ScoreWeights(self.score_skills_share, self.score_experience_floor,
                            self.score_availability_floor, self.score_location_floor)

    @property
    def role_parse_model(self) -> str:
        return self.fast_llm_model if self.role_parse_model_role == "fast" else self.quality_llm_model

    @property
    def extraction_model(self) -> str:
        return self.fast_llm_model if self.extraction_model_role == "fast" else self.quality_llm_model


_DEV_SECRET: str | None = None   # random development secret, created once per server start


@lru_cache
def get_settings() -> Settings:
    return Settings()
