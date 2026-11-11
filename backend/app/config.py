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
    # env_ignore_empty: "KEY=" (nothing after =) means "use the default", e.g. an unused API key or EMBED_DIMENSIONS
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True)

    # ---- App ----
    app_name: str = "RAG Talent Matcher"
    environment: str = "development"
    log_level: str = "INFO"

    # ---- Ollama and the models (any Ollama model can be used: see app/llm/models.py) ----
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 300.0
    embed_model: str = "nomic-embed-text"
    fast_llm_model: str = "qwen2.5:3b"
    quality_llm_model: str = "qwen2.5:7b"
    llm_num_ctx: int = 8192
    # Thinking (step-by-step reasoning before answering, qwen3/qwen3.5/deepseek-r1 ...): off = skip it (fast on
    # a CPU), on = always, default = whatever the model does by itself.
    llm_think: Literal["off", "on", "default"] = "off"
    # Only for an embedding model app/llm/models.py doesn't know: how to write the query / the stored text,
    # with {text} where the text goes (copy it from the model's card). Empty = use the known template.
    embed_query_template: str | None = None
    embed_document_template: str | None = None
    # After EMBED_MODEL changes, re-embed the resumes made with the old model at the next start (minutes).
    auto_reembed_on_model_change: bool = True
    embed_dimensions: int | None = None      # API embeddings that can shorten vectors (OpenAI -3, Voyage, Cohere,
                                             # Gemini): e.g. 1024. Empty = the model's full size.

    # ---- Cloud and other providers (app/llm/router.py): a model setting "<provider>/<model>" uses them ----
    # Resumes are personal data: models outside this computer / network are refused unless this is true.
    allow_cloud_models: bool = False
    cloud_timeout_seconds: float = 120.0
    openai_api_key: str | None = None
    openai_base_url: str | None = None       # empty = api.openai.com
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None  # https://<resource>.openai.azure.com
    azure_openai_api_version: str = "2024-10-21"
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    anthropic_max_tokens: int = 4096         # Claude requires a limit; used when a task sets none
    gemini_api_key: str | None = None
    gemini_openai_base_url: str | None = None   # empty = Google's OpenAI-compatible endpoint (chat)
    gemini_native_base_url: str | None = None   # empty = Google's native API (embeddings with task types)
    compat_base_url: str | None = None       # any OpenAI-compatible server, e.g. http://localhost:8000/v1
    compat_api_key: str | None = None
    voyage_api_key: str | None = None
    voyage_base_url: str | None = None       # empty = https://api.voyageai.com/v1/embeddings
    cohere_api_key: str | None = None
    cohere_base_url: str | None = None       # empty = https://api.cohere.com/v2/embed
    # Amazon Bedrock (bedrock/<model id>): credentials from boto3's standard chain (IAM role, AWS_PROFILE ...)
    aws_region: str | None = None            # e.g. ap-south-1 (Mumbai); empty = AWS_REGION / the profile's region
    aws_profile: str | None = None           # a named profile from ~/.aws (laptops); empty on AWS (IAM role)
    bedrock_endpoint_url: str | None = None  # a VPC (PrivateLink) endpoint; empty = the public regional endpoint
    bedrock_max_tokens: int = 4096           # answer limit when a task sets none (some models default to 512)
    # Google Vertex AI (vertex/<model>): credentials from Application Default Credentials (service account)
    vertex_project: str | None = None        # empty = GOOGLE_CLOUD_PROJECT / the credentials' project
    vertex_location: str = "us-central1"     # e.g. asia-south1 (Mumbai), europe-west4, or global
    vertex_claude_location: str | None = None   # Claude's region if it differs (e.g. us-east5, europe-west1)
    vertex_base_url: str | None = None       # replaces https://<location>-aiplatform.googleapis.com/v1

    # ---- Database ----
    # sqlite+aiosqlite:///./data/app.db (one machine) | postgresql+asyncpg://user:password@host:5432/db (production)
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    db_echo: bool = False
    db_auto_migrate: bool = True             # run migrations at startup; false = `alembic upgrade head` per release
    db_pool_size: int = 10                   # PostgreSQL: connections kept open per process
    db_max_overflow: int = 20                # PostgreSQL: extra connections under load
    db_pool_timeout_seconds: float = 30.0    # PostgreSQL: wait this long for a free connection, then fail
    db_statement_timeout_ms: int = 0         # PostgreSQL: cancel any query running longer (0 = no limit)

    # ---- Uploads & ingestion (Step 4) ----
    # Where resume files are kept (app/storage): local = UPLOAD_DIR; s3 / gcs / azure = a private bucket
    storage_backend: Literal["local", "s3", "gcs", "azure"] = "local"
    storage_prefix: str = "resumes/"         # folder inside the bucket / container (cloud backends)
    upload_dir: str = "./data/uploads"       # local backend
    s3_bucket: str | None = None
    s3_region: str | None = None             # empty = AWS_REGION
    s3_endpoint_url: str | None = None       # S3-compatible stores (MinIO, R2); empty = AWS
    s3_kms_key_id: str | None = None         # your KMS key (SSE-KMS); empty = S3-managed encryption (SSE-S3)
    gcs_bucket: str | None = None
    gcs_kms_key_name: str | None = None      # projects/../keyRings/../cryptoKeys/.. (CMEK); empty = Google-managed
    azure_storage_container: str | None = None
    azure_storage_account_url: str | None = None        # https://<account>.blob.core.windows.net (managed identity)
    azure_storage_connection_string: str | None = None  # alternative (a secret: development, Azurite)
    max_upload_mb: int = 25              # per file (Word files with embedded fonts reach 12+ MB, doc 18)
    max_files_per_batch: int = 200       # per bulk-upload request
    # Background jobs (app/jobs): resume processing and the LLM judge.
    queue_backend: Literal["local", "sqs", "pubsub", "servicebus"] = "local"   # local = the database is the queue
    worker_enabled: bool = True          # run a worker inside the API process (one machine); false = separate
                                         # worker processes only (python -m app.worker)
    worker_concurrency: int = 1          # jobs one worker runs at once (an LLM on a CPU: 1; GPU / cloud models: more)
    worker_poll_seconds: float = 5.0     # how long an idle worker waits for a job before looking again
    worker_max_attempts: int = 3         # retries for unexpected errors (and for workers dying mid-job)
    worker_lease_seconds: float = 300.0  # a job's claim; renewed every third of it while the job runs
    worker_sweep_seconds: float = 60.0   # how often a worker recovers jobs whose worker died
    worker_redispatch_seconds: float = 900.0   # message broker: re-send jobs waiting this long (lost messages)
    worker_shutdown_seconds: float = 30.0      # on stop, running jobs get this long to finish, then are handed back
    sqs_queue_url: str | None = None     # QUEUE_BACKEND=sqs: https://sqs.<region>.amazonaws.com/<account>/<queue>
    sqs_region: str | None = None        # empty = AWS_REGION
    sqs_endpoint_url: str | None = None  # a VPC endpoint or a local emulator; empty = AWS
    pubsub_topic: str | None = None      # QUEUE_BACKEND=pubsub: "resume-jobs" or projects/<p>/topics/resume-jobs
    pubsub_subscription: str | None = None   # a PULL subscription of that topic
    pubsub_project: str | None = None    # empty = GOOGLE_CLOUD_PROJECT
    servicebus_queue: str | None = None  # QUEUE_BACKEND=servicebus: the queue name
    servicebus_namespace: str | None = None   # <namespace>.servicebus.windows.net (managed identity)
    servicebus_connection_string: str | None = None   # alternative (a secret: development)
    min_chars_per_page: int = 100        # less text than this per PDF page = probably a scanned image
    ollama_retry_seconds: float = 30.0   # if Ollama is down, the worker waits this long before trying again

    # ---- Structured extraction (Step 5) ----
    extraction_model_role: str = "quality"   # fast | quality | an Ollama model tag: which LLM reads resumes
    extraction_max_output_tokens: int = 2048   # hard cap on the JSON answer length
    extraction_max_input_chars: int = 16000    # ~4,000 tokens per model call; longer resumes are read in parts

    # ---- Chunking, embeddings & vector store (Step 6) ----
    # auto = pgvector when the database is PostgreSQL (vectors next to the data), ChromaDB with SQLite
    vector_store: Literal["auto", "chroma", "pgvector"] = "auto"
    chroma_dir: str = "./data/chroma"               # ChromaDB's files (git-ignored, rebuildable)
    chroma_collection: str = "resume_chunks"
    chunk_max_chars: int = 1200                     # ~300 tokens: one focused topic per chunk
    chunk_overlap_chars: int = 150                  # text repeated between neighbouring chunks
    embed_batch_size: int = 16                      # chunks sent to Ollama per /api/embed call
    anonymize_chunks: bool = True                   # remove name, email, phone from indexed text

    # ---- Matching: role parsing & hybrid retrieval (Step 7) ----
    role_parse_model_role: str = "quality"   # fast | quality | an Ollama model tag: reads role descriptions
    retrieval_vector_pool: int = 80          # nearest chunks fetched from ChromaDB
    retrieval_keyword_pool: int = 200        # best BM25 chunks fetched from the keyword index
    rrf_k: int = 60                          # Reciprocal Rank Fusion constant (60 is the standard value)
    rrf_weight_skills: float = 1.0           # how much each signal counts in the fusion
    rrf_weight_keyword: float = 1.0
    rrf_weight_vector: float = 1.0
    # Optional 4th signal: a cross-encoder reranker (app/rag/reranker.py). Empty = off.
    # Try "Xenova/ms-marco-MiniLM-L-6-v2" (needs `pip install fastembed`; ~80 MB download on first use) and
    # compare with `python -m scripts.evaluate_real_retrieval` before keeping it on.
    rerank_model: str = ""
    rerank_pool: int = 30                    # how many of the best-fused people get reranked
    rerank_chunks_per_person: int = 8        # their best chunks (by the earlier signals), at most this many
    rrf_weight_rerank: float = 1.0
    models_dir: str = "./data/models"        # where downloaded models are kept
    default_skill_min_years: float = 2.0     # years assumed "enough" when a role doesn't say

    # ---- Scoring & LLM judge (Step 8) ----
    score_skills_share: float = 0.85         # fit = 85% skill coverage + 15% retrieval relevance
    score_experience_floor: float = 0.6      # factor for "not enough years" ranges from 0.6 to 1.0
    score_availability_floor: float = 0.7    # factor for "not free in time" ranges from 0.7 to 1.0
    score_location_floor: float = 0.9        # factor for "other city" ranges from 0.9 to 1.0
    judge_model_role: str = "quality"        # fast | quality | an Ollama model tag: judges candidates
    judge_top_n: int = 5                     # how many top candidates the judge reads per run (default)
    judge_weight: float = 0.4                # final = (1 - w) × rule score + w × judge score
    judge_max_output_tokens: int = 1024      # cap on the judge's JSON answer
    judge_max_dossier_chars: int = 6000      # ~1,500 tokens of resume evidence per candidate

    # ---- Agent (Step 10) ----
    agent_model_role: str = "quality"        # fast | quality | an Ollama model tag: runs the agent (tool use)
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

    # ---- which model each task uses ("fast", "quality" or an exact model name) ----
    def model_for(self, choice: str) -> str:
        from app.llm.models import resolve_model
        return resolve_model(choice, self.fast_llm_model, self.quality_llm_model)

    @property
    def agent_model(self) -> str:
        return self.model_for(self.agent_model_role)

    @property
    def judge_model(self) -> str:
        return self.model_for(self.judge_model_role)

    @property
    def models_in_use(self) -> dict[str, str]:
        """Every model the app uses, per task (health check, evaluation reports)."""
        return {"embed_model": self.embed_model, "fast_llm_model": self.fast_llm_model,
                "quality_llm_model": self.quality_llm_model, "extraction_model": self.extraction_model,
                "role_parse_model": self.role_parse_model, "judge_model": self.judge_model,
                "agent_model": self.agent_model, "rerank_model": self.rerank_model or "(off)",
                "llm_think": self.llm_think}

    @property
    def embedding_signature(self) -> str:
        """What made the stored vectors: the model, plus the vector size if EMBED_DIMENSIONS shortens them.
        Stored on every chunk; a different signature at startup means the vectors must be made again."""
        return f"{self.embed_model}@{self.embed_dimensions}" if self.embed_dimensions else self.embed_model

    @property
    def vector_collection(self) -> str:
        """The ChromaDB collection of the current embedding model and size (each has its own)."""
        from app.llm.models import collection_name
        return collection_name(self.chroma_collection, self.embedding_signature)

    @property
    def score_weights(self):
        from app.matching.scoring import ScoreWeights   # imported here to avoid a circular import
        return ScoreWeights(self.score_skills_share, self.score_experience_floor,
                            self.score_availability_floor, self.score_location_floor)

    @property
    def role_parse_model(self) -> str:
        return self.model_for(self.role_parse_model_role)

    @property
    def extraction_model(self) -> str:
        return self.model_for(self.extraction_model_role)


_DEV_SECRET: str | None = None   # random development secret, created once per server start


@lru_cache
def get_settings() -> Settings:
    return Settings()
