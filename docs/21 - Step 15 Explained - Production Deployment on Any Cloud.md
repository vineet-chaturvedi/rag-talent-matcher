# 21 · Step 15 Explained: Production Deployment on Any Cloud

This document explains Step 15 from start to finish: **why** it exists, **what** you get, **how** every part works, **every file**, how to deploy on **AWS, Google Cloud, Azure or your own server**, and what is still left for later.

**Read first:** 01 (System Architecture), 06 (Technology Choices §3). **Read with:** 20 (Changing Models), 05 (Reference), 08 (Troubleshooting §6d).

---

## 1. Where Step 15 sits

| Step | Gave us | What Step 15 changes |
|---|---|---|
| 2, 20 | One model router: `<provider>/<model>` | Two more providers: **Amazon Bedrock** and **Google Vertex AI** |
| 3 | SQLite, tables made with `create_all` | **PostgreSQL** as well, with **Alembic migrations** |
| 4 | Files in `data/uploads`, a worker inside the API | Files in **S3 / Cloud Storage / Azure Blob**; jobs through **SQS / Pub/Sub / Service Bus**; **separate worker processes** |
| 6–7 | ChromaDB + SQLite FTS5 | **pgvector** + PostgreSQL full-text search with the same BM25 ranking |
| 11 | `npm run dev` / `uvicorn` | **Docker images** for API, worker and portal; **docker compose** for the whole system |

Everything from Steps 1–14 still works exactly as before on your PC: SQLite, ChromaDB, local files, the built-in worker. Step 15 adds choices; it removes none.

---

## 2. Why we need Step 15

On one PC the app is one process with files on disk. In a company that runs it for real, four things change:

| On a PC | In production | Why it matters |
|---|---|---|
| SQLite file | A managed database server | Several app copies share one database; backups, failover, point-in-time restore |
| Files in a folder | Object storage (a bucket) | Containers are disposable and have no permanent disk; buckets are durable, encrypted, access-controlled |
| A background task in the API process | A queue + separate workers | Restarting the API must not kill an LLM step; workers scale on their own (more when 500 resumes arrive) |
| Run from a terminal | Container images | The same, tested package runs on every cloud; nothing "works on my machine" only |

The design rule that makes this cheap: **every outside service sits behind one small interface, chosen in `.env`**. The business code (extraction, retrieval, scoring, the judge, the agent) never knows where files, jobs or the database live.

---

## 3. What you get

```
                ┌──────────────────────── one codebase, one set of images ───────────────────────┐
  Portal  ──▶   API (FastAPI)  ──publish──▶  Queue  ──▶  Worker(s)  ──▶  Models (any provider)
  (Next.js)        │                          local | sqs | pubsub | servicebus    ollama | openai | azure |
                   │                                                               anthropic | gemini |
                   ├──▶ Database: SQLite | PostgreSQL (+ pgvector, full-text)       bedrock | vertex | compat
                   └──▶ Files: local | s3 | gcs | azure
```

| `.env` setting | Choices | Default |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///…` · `postgresql+asyncpg://…` | SQLite |
| `VECTOR_STORE` | `auto` (pgvector with PostgreSQL, ChromaDB with SQLite) · `chroma` · `pgvector` | `auto` |
| `STORAGE_BACKEND` | `local` · `s3` · `gcs` · `azure` | `local` |
| `QUEUE_BACKEND` | `local` (the database is the queue) · `sqs` · `pubsub` · `servicebus` | `local` |
| `WORKER_ENABLED` | `true` (a worker inside the API) · `false` (run `python -m app.worker` separately) | `true` |
| Model settings | `ollama/…` `openai/…` `azure/…` `anthropic/…` `gemini/…` `bedrock/…` `vertex/…` `compat/…` | Ollama |

Any combination works: Postgres on AWS with Vertex AI models, local files with SQS, and so on.

---

## 4. The layers, one by one

### 4.1 Models: Amazon Bedrock and Google Vertex AI (Step 15a)

**Bedrock** (`app/llm/bedrock.py`). One adapter for every Bedrock chat model through the **Converse API** (Claude, Llama, Mistral, Amazon Nova, DeepSeek …), tool calls and streaming included. Embeddings use the model family's own format: **Titan Text Embeddings** (v1, v2 with 256/512/1024 sizes) and **Cohere Embed** (v3, v4).

```
QUALITY_LLM_MODEL=bedrock/apac.anthropic.claude-sonnet-4-5-20250929-v1:0   # "apac." = an inference profile
EMBED_MODEL=bedrock/amazon.titan-embed-text-v2:0
AWS_REGION=ap-south-1
```

- **Credentials:** boto3's standard chain, never a key in `.env` on AWS. The ECS task role / EC2 instance profile provides them; on a laptop use `AWS_PROFILE` or `aws sso login`. IAM needs `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`.
- **Structured output** (extraction, role parsing and the judge need JSON that follows a schema) is tried in three ways, and the one that works is remembered per model:
  1. **native**: Converse's `outputConfig` JSON schema;
  2. **tool**: a forced call to a tool whose input schema *is* the schema (Claude, Mistral Large, Nova);
  3. **prompt**: the schema in the instructions, with the JSON taken from the answer (any model; Pydantic checks it anyway).
- boto3 is synchronous. Calls run in worker threads, and a stream is read in a thread and handed to the event loop chunk by chunk. If the reader stops early (the user presses Stop), the stream is closed and the thread ends.
- Errors: throttling, outages, missing access or model → "retryable" (the worker pauses). A refused request → a real failed attempt.

**Vertex AI** (`app/llm/router.py`, `google_auth.py`, `openai_compat.py`, `anthropic_client.py`, `embedding_apis.py`):

| Model setting | Goes to | How |
|---|---|---|
| `vertex/gemini-2.5-pro`, `vertex/meta/llama-…` | Vertex's OpenAI-compatible endpoint | The OpenAI SDK, with a fresh Google token on every request (`google/` added to bare names) |
| `vertex/claude-sonnet-4-5@20250929` | Claude on Vertex | Anthropic's SDK (`AnthropicVertex`): the same Messages API, the model in the URL |
| `vertex/gemini-embedding-001`, `vertex/text-embedding-005` | Vertex `:predict` | Plain HTTP with the task type (`RETRIEVAL_QUERY` / `RETRIEVAL_DOCUMENT`) |

- **Credentials:** Application Default Credentials. On Google Cloud that's the attached service account (Cloud Run, GKE Workload Identity); on a laptop, `gcloud auth application-default login`.
- Tokens live about an hour. `GoogleToken` refreshes them in a thread before they expire, once at a time, and every Vertex client shares it.
- `VERTEX_LOCATION` picks the region (`asia-south1` = Mumbai, `global` for the global endpoint), and `VERTEX_CLAUDE_LOCATION` sets Claude's region if it differs.

Both count as **cloud** (resumes leave your network), so they need `ALLOW_CLOUD_MODELS=true`, as in doc 20 §5.3. Choose the region for data residency, for example Bedrock `ap-south-1` with `apac.` inference profiles, or Vertex `asia-south1`.

### 4.2 Database: PostgreSQL, pgvector, Alembic (Step 15b)

**One code path, two databases.** Only `DATABASE_URL` changes. What had to be made portable:

| Difference | SQLite | PostgreSQL | What the code does |
|---|---|---|---|
| Text longer than `VARCHAR(n)` | stored anyway | **row refused** | `app/db/base.py` cuts it to the column (with a warning) on both, so an unusually long job title from the LLM can't break production |
| `now()` time zone | UTC | the server's zone | every PostgreSQL connection sets `timezone=UTC` |
| NULLs in `ORDER BY … DESC` | last | **first** | `nulls_last()` where it matters (jobs without dates) |
| Schema changes | `create_all` + ad-hoc `ALTER` | needs real migrations | **Alembic** (below) |
| Keyword search | FTS5 + BM25 | none built in | a generated `tsvector` column + GIN index + **BM25 in SQL** (below) |
| Vectors | ChromaDB files | none built in | **pgvector** (below) |

**Alembic migrations** (`alembic.ini`, `migrations/`):
- `0001_baseline`: the Steps 3–14 schema, on any database. On PostgreSQL it also enables `vector`, adds the full-text column and index, and creates the vector collection registry.
- `0002_job_leases`: lease columns and worker heartbeats (§4.4). It uses `batch_alter_table`, because SQLite can't alter tables in place.
- **SQLite and table rebuilds:** some schema changes make SQLite rebuild a table (copy, drop, rename). With foreign keys on, dropping `resumes` would cascade-delete every chunk, skill and match result. `migrate()` turns foreign keys off while migrations run (Alembic's rule for SQLite), checks every foreign key afterwards, and turns them back on. A test rebuilds `resumes` on a filled database and checks every row survives.
- **Your existing database:** at the first start it is recognised as "made before migrations" (it has tables but no `alembic_version`). It gets the Step 13b columns if they're missing, is **stamped** at `0001`, and is then upgraded. Tested on a copy of your PC database: every row count is unchanged.
- **At startup** (`DB_AUTO_MIGRATE=true`, the default) the app migrates itself, behind a PostgreSQL advisory lock so that ten replicas starting at once migrate exactly once. **In production** the usual practice is `DB_AUTO_MIGRATE=false` plus a release step `alembic upgrade head` (Compose has a `migrate` service for this). The app then refuses to start on an out-of-date schema and tells you why.
- A test (`test_models_and_migrations_match`) fails if a model change has no migration.

**Keyword search on PostgreSQL** (`app/rag/keyword_index.py`). The aim is to rank like SQLite's FTS5, because retrieval's quality was measured with it:
- **Words:** every character that isn't a letter or digit separates words ("node.js" → node js, "ci/cd" → ci cd), with no stemming. That is FTS5's `unicode61` behaviour, implemented with `regexp_replace` in the generated column and applied to the search terms the same way.
- **Ranking:** FTS5's exact BM25, `idf · tf·(k1+1) / (tf + k1·(1−b+b·len/avglen))`, computed in SQL. It uses term frequency from tsvector positions and statistics over all chunks.
- **Measured** on your data copy (25 resumes): the same people top every match run, the top 10 keyword hits are identical, and 17–18 of 20 keyword ranks match. The rest are near-ties where the order can differ.

**pgvector** (`app/rag/vector_store.py`):
- Each embedding model and size gets its own table (`emb_<hash>`, listed in `vector_collections`), created on first use with the right vector size, as Chroma collections were.
- An **HNSW** cosine index is created for up to 2,000 dimensions (`vector`), or up to 4,000 with `halfvec` on pgvector ≥ 0.7. Bigger vectors are searched exactly.
- A filtered search ("only these employees") filters first and then sorts exactly. An approximate index search with a filter can quietly return fewer results.
- `ON DELETE CASCADE` to `resumes`: deleting a resume deletes its vectors, with no orphans.
- **Moving your data:** `python -m scripts.migrate_to_postgres --target postgresql+asyncpg://…` copies every table (keeping the ids and fixing the sequences) and every Chroma vector, then compares the counts. Nothing is re-embedded. Tested on your data copy: 1,335 rows and 826 vectors.

### 4.3 Files: local, S3, Cloud Storage, Azure Blob (Step 15c)

`app/storage/`: one interface (`put`, `get`, `delete`, `exists`, `local_path`), four backends.

- **Keys, not paths:** `EMP-1001/ab12cd34ef56ab78.pdf` (the employee code plus the first 16 characters of the file's SHA-256), the same on every backend. The user's file name is only kept in the database, for downloads. Rows stored before Step 15 (with the full local path) still work.
- **Private and encrypted:**

  | Backend | Encryption at rest | Your own key (optional) |
  |---|---|---|
  | S3 | `AES256` | `S3_KMS_KEY_ID` (SSE-KMS) |
  | Cloud Storage | Google-managed | `GCS_KMS_KEY_NAME` (CMEK) |
  | Azure Blob | always on | set on the account |

  Files are **never** given a public or pre-signed link: the API streams them to signed-in admins only.
- **Text extraction** needs a file on disk. Cloud backends download it to a private temporary file (mode 0600) that is deleted right after.
- **Safety:** keys are checked (no `..`, no `//`, safe characters only), and the local backend refuses anything outside `UPLOAD_DIR`. An upload stores the file before the database row, and a failed row deletes only its own file; it leaves alone a file another upload of the same resume owns (the race is tested).
- **Moving your files:** `python -m scripts.migrate_files --from-local ./data/uploads` (with `--dry-run` first). Each file is checked against its fingerprint before and after copying; the row is updated only after the copy is confirmed, and local files are never deleted. `--check` lists resumes whose file is missing.

### 4.4 Background jobs: queues and workers (Step 15d)

`app/jobs/`. The industry-standard design is **at-least-once delivery with idempotent consumers**:

```
API: upload ──commit row──▶ publish {"kind": "ingest", "id": 42} ──▶ queue
Worker: receive ──▶ CLAIM the row in the database ──▶ do the stage ──▶ ack
                    (UPDATE … SET status='parsing', lease_expires_at=now+5min
                     WHERE id=42 AND status='queued'  → exactly one worker wins)
```

- **The database stays the source of truth.** A message only says *what* and *which row*. If a message arrives twice, late, or after the work is done, the claim finds nothing to do and the message is dropped. No job runs twice at the same time, on SQLite or PostgreSQL.
- **Leases:** the worker renews its claim every third of `WORKER_LEASE_SECONDS`, and the message's invisibility with it, so a 10-minute LLM step on a CPU never looks like a dead worker. If the worker dies (`kill -9`, out of memory, a deploy), the lease runs out. The **sweeper** (any worker, every minute) then puts the job back; after `WORKER_MAX_ATTEMPTS` tries it is marked failed.
- **Lost messages:** a publish that failed after the commit is caught by the sweeper, which re-sends jobs waiting longer than `WORKER_REDISPATCH_SECONDS`.
- **Graceful stop** (Ctrl+C, or SIGTERM from Docker/ECS/Kubernetes): no new jobs are taken. Running jobs get `WORKER_SHUTDOWN_SECONDS`, then are **handed back** at once: the stage is undone without counting the attempt, and a judged match run keeps its finished verdicts. Before Step 15, a stopped match run was marked failed; now another worker continues it.
- **Order of work** keeps the doc 07 fix ("each resume ready as soon as its own LLM step ends"). After **parse** the resume goes back to the queue, so a whole batch is parsed (and broken files reported) first. After **extract** it goes straight on to **embed**.
- **Model service down:** the job is retried after `OLLAMA_RETRY_SECONDS`, the attempt is not counted, and that consumer pauses.
- **Heartbeats:** each worker reports every 30 s. The dashboard shows "3 workers running", and the health check counts them.

| `QUEUE_BACKEND` | Service | Retry with delay | Long jobs | Dead letters |
|---|---|---|---|---|
| `local` | none: the database (status + leases), like before | the worker skips the job until the time | the lease | `WORKER_MAX_ATTEMPTS` → failed |
| `sqs` | Amazon SQS | change the visibility timeout | extend the visibility | the queue's redrive policy (DLQ) |
| `pubsub` | Google Pub/Sub (pull) | modify the ack deadline | extend the ack deadline | a dead-letter topic |
| `servicebus` | Azure Service Bus | a scheduled copy, then complete | renew the lock | the built-in dead-letter sub-queue |

**Running workers:**
- One machine: nothing to do. The API's built-in worker (`WORKER_ENABLED=true`) is enough.
- Containers: set `WORKER_ENABLED=false` on the API and run any number of `python -m app.worker` (`--concurrency N`; `--healthcheck` for container health checks).
- `WORKER_CONCURRENCY`: 1 for an LLM on a CPU; more with a GPU server or cloud models.

### 4.5 Containers (Step 15e)

| File | What |
|---|---|
| `backend/Dockerfile` | Multi-stage: dependencies are built in a separate stage. The image runs as a **non-root** user, and the code is read-only to it. One image for **API, worker and migrations**; it contains no `.env` and no secrets. ChromaDB is left out (`WITH_CHROMA=true` keeps it). Health check: `/api/health/live` |
| `frontend/Dockerfile` | Next.js **standalone** server (only the needed `node_modules`), non-root, Node 26 as in `.nvmrc`. `BACKEND_URL` / `HTTPS` are build arguments, because the `/api` rewrite and security headers are fixed at build time |
| `docker-compose.yml` | postgres (pgvector) → **migrate** (runs once) → api + worker(s) → portal; optional `ollama` profile (with a GPU block) |
| `.env.docker.example` | Compose's own settings: database password, JWT secret, ports (copy to `.env`) |

**Health endpoints** for load balancers and orchestrators:

| Endpoint | Purpose | Answers |
|---|---|---|
| `/api/health/live` | liveness: restart the container only if this fails | always 200 |
| `/api/health/ready` | readiness: send traffic only when 200 | 200, or 503 while the database is unreachable |
| `/api/health` | full check for people (the dashboard) | database kind, vector store, file storage, job queue, workers |

Outside development, `/api/health` shows only the *kind* of service (`s3`, `sqs`), not bucket names or queue URLs: it is public, and SQS URLs contain the AWS account number.

---

## 5. Deploying

### 5.1 Your own server or PC, with Docker

```powershell
cp .env.docker.example .env                 # set POSTGRES_PASSWORD and JWT_SECRET in it
docker compose up -d --build                # portal http://localhost:3000, API http://localhost:8010/docs
docker compose run --rm api python -m scripts.create_user --role admin --email you@company.com --name "You"
docker compose up -d --scale worker=3       # more workers
```

- **Models:** Ollama on the same PC works (`OLLAMA_BASE_URL=http://host.docker.internal:11434`, the default). On Windows, Ollama must listen on all addresses: set the user environment variable `OLLAMA_HOST=0.0.0.0` and restart Ollama (doc 08 §6d). Alternatively, run `docker compose --profile ollama up -d` and set `OLLAMA_BASE_URL=http://ollama:11434`.
- **Moving your existing data in:** start only postgres, run `migrate_to_postgres` with `--target postgresql+asyncpg://rag:<password>@localhost:5432/rag`, then start the rest. Uploads go to the `uploads` volume: copy `backend/data/uploads/*` with `docker compose cp`, or use S3/MinIO with `migrate_files`.

### 5.2 AWS

| Part | Service |
|---|---|
| API, worker, portal | **ECS on Fargate**: 3 services from the 2 images; the worker service autoscales on the SQS queue's length; an Application Load Balancer in front (HTTPS with ACM) |
| Database | **RDS for PostgreSQL 16** (or Aurora PostgreSQL), Multi-AZ; `CREATE EXTENSION vector` is allowed |
| Files | **S3**: Block Public Access on, versioning, SSE-KMS |
| Jobs | **SQS** standard queue: visibility timeout ≥ 300 s, a dead-letter queue (maxReceiveCount 5) |
| Models | **Bedrock** (Claude via `apac.` profiles in Mumbai, Titan embeddings), or Ollama/vLLM on a GPU EC2 (`compat/`) |
| Secrets | **Secrets Manager**: `JWT_SECRET` and the database URL, injected into the task as environment variables |

```
DATABASE_URL=postgresql+asyncpg://rag:…@rag.xxxx.ap-south-1.rds.amazonaws.com:5432/rag
DB_AUTO_MIGRATE=false            # a one-off ECS task runs `alembic upgrade head` per release
STORAGE_BACKEND=s3   S3_BUCKET=acme-talent-resumes   S3_KMS_KEY_ID=alias/talent
QUEUE_BACKEND=sqs    SQS_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/123456789012/resume-jobs
AWS_REGION=ap-south-1
ALLOW_CLOUD_MODELS=true
QUALITY_LLM_MODEL=bedrock/apac.anthropic.claude-sonnet-4-5-20250929-v1:0
FAST_LLM_MODEL=bedrock/apac.anthropic.claude-haiku-4-5-20251001-v1:0
EMBED_MODEL=bedrock/amazon.titan-embed-text-v2:0      EMBED_DIMENSIONS=1024
WORKER_ENABLED=false             # on the API service; the worker service runs `python -m app.worker`
```

The task role needs these IAM permissions:
- S3: `s3:GetObject`, `PutObject` and `DeleteObject` on `arn:aws:s3:::acme-talent-resumes/resumes/*`;
- SQS: `SendMessage`, `ReceiveMessage`, `DeleteMessage` and `ChangeMessageVisibility` on the queue;
- Bedrock: `InvokeModel` and `InvokeModelWithResponseStream` on the chosen models;
- KMS: `Encrypt`, `Decrypt` and `GenerateDataKey` on the key.

### 5.3 Google Cloud

| Part | Service |
|---|---|
| API, portal | **Cloud Run** services (HTTPS built in) |
| Worker | A long-running container: **Cloud Run worker pools**, or a **GKE** deployment, or a Compute Engine VM (a Cloud Run *service* expects HTTP requests, not a background loop) |
| Database | **Cloud SQL for PostgreSQL 16**, with the `vector` extension; the Cloud SQL connector or a private IP |
| Files | **Cloud Storage**: uniform access, public access prevention, optional CMEK |
| Jobs | **Pub/Sub**: a topic + pull subscription, ack deadline 600 s, a dead-letter topic |
| Models | **Vertex AI**: Gemini, Claude on Vertex, `gemini-embedding-001` |
| Secrets | **Secret Manager**, mounted as environment variables |

```
DATABASE_URL=postgresql+asyncpg://rag:…@10.20.0.3:5432/rag
STORAGE_BACKEND=gcs  GCS_BUCKET=acme-talent-resumes
QUEUE_BACKEND=pubsub PUBSUB_TOPIC=resume-jobs  PUBSUB_SUBSCRIPTION=resume-jobs-worker  PUBSUB_PROJECT=acme-talent
ALLOW_CLOUD_MODELS=true  VERTEX_PROJECT=acme-talent  VERTEX_LOCATION=asia-south1
QUALITY_LLM_MODEL=vertex/gemini-2.5-pro   FAST_LLM_MODEL=vertex/gemini-2.5-flash
EMBED_MODEL=vertex/gemini-embedding-001   EMBED_DIMENSIONS=768
```

The service account needs `roles/cloudsql.client`, `roles/storage.objectUser` on the bucket, `roles/pubsub.publisher` and `roles/pubsub.subscriber`, and `roles/aiplatform.user`.

### 5.4 Azure

| Part | Service |
|---|---|
| API, portal | **Container Apps** (HTTPS ingress) |
| Worker | **Container Apps** without ingress, scaled by **KEDA** on the Service Bus queue length (down to 0 when idle) |
| Database | **Azure Database for PostgreSQL – Flexible Server 16**: add `VECTOR` to the server parameter `azure.extensions` first |
| Files | **Blob Storage**: anonymous access disabled; the identity has *Storage Blob Data Contributor* |
| Jobs | **Service Bus** queue: lock duration 5 min, max delivery count 5 (then the dead-letter sub-queue) |
| Models | **Azure OpenAI** (`azure/<deployment>`), or Azure AI Foundry models through `compat/` |
| Secrets | **Key Vault** references in the Container Apps secrets; a **managed identity** for Storage and Service Bus (no keys) |

```
DATABASE_URL=postgresql+asyncpg://rag:…@acme-talent.postgres.database.azure.com:5432/rag
STORAGE_BACKEND=azure  AZURE_STORAGE_ACCOUNT_URL=https://acmetalent.blob.core.windows.net  AZURE_STORAGE_CONTAINER=resumes
QUEUE_BACKEND=servicebus  SERVICEBUS_NAMESPACE=acme-talent.servicebus.windows.net  SERVICEBUS_QUEUE=resume-jobs
ALLOW_CLOUD_MODELS=true  AZURE_OPENAI_ENDPOINT=https://acme-talent.openai.azure.com  AZURE_OPENAI_API_KEY=(Key Vault)
QUALITY_LLM_MODEL=azure/gpt-4o-prod   EMBED_MODEL=azure/text-embedding-3-large   EMBED_DIMENSIONS=1024
```

### 5.5 Moving from your PC to any of these

1. **Database:** create the PostgreSQL database, then `python -m scripts.migrate_to_postgres --target <URL>`.
2. **Files:** set the `STORAGE_BACKEND` settings, then `python -m scripts.migrate_files --from-local ./data/uploads --dry-run`, then run it again without `--dry-run`, then `--check`.
3. **Models (optional):** change the model settings. If `EMBED_MODEL` changes, resumes are re-embedded automatically at the next start (doc 20).
4. **Measure:** `python -m scripts.evaluate_all --note "PostgreSQL + <models>"`, and compare with your baseline (doc 19).

---

## 6. Every file

| File | New / changed | Purpose |
|---|---|---|
| `app/llm/bedrock.py` | new | Bedrock: Converse chat, streaming, the 3 structured-output modes, Titan/Cohere embeddings |
| `app/llm/google_auth.py` | new | Google credentials (ADC) and an always-fresh token |
| `app/llm/router.py` | changed | `bedrock/`, `vertex/`; Claude-on-Vertex vs OpenAI-compatible routing; SDK and setting checks for the health page |
| `app/llm/openai_compat.py`, `anthropic_client.py`, `embedding_apis.py`, `models.py` | changed | the Vertex endpoint and token; Claude on Vertex; Vertex embeddings; embedding profiles for Bedrock |
| `app/db/session.py` | changed | per-database engine settings (pool, UTC, statement timeout), migrations at startup, legacy stamping |
| `app/db/base.py` | changed | text cut to its column on every database |
| `app/db/unmanaged.py` | new | tables/columns that exist without an ORM model (FTS, pgvector), for Alembic |
| `alembic.ini`, `migrations/` | new | migrations `0001` baseline, `0002` job leases |
| `app/rag/keyword_index.py` | changed | PostgreSQL full-text search with FTS5's word rules and BM25 |
| `app/rag/vector_store.py` | changed | one async interface; ChromaDB and pgvector backends |
| `app/storage/` | new | the file storage interface; local, S3, GCS, Azure Blob |
| `app/ingestion/storage.py` | changed | file checks and storage keys (saving moved to `app/storage`) |
| `app/ingestion/pipeline.py` | new (was `worker.py`) | the stages of one resume (parse, extract, embed) |
| `app/jobs/` | new | jobs, queues (local, SQS, Pub/Sub, Service Bus), leases, handlers, the worker runtime |
| `app/worker.py` | new | `python -m app.worker` (signals, `--concurrency`, `--healthcheck`) |
| `app/matching/runner.py` | changed | a stopped judge no longer fails the run (it is handed over); startup failing of runs removed |
| `app/api/resumes.py`, `matching.py`, `health.py`, `main.py`, `deps.py` | changed | jobs published after commit; workers online; storage errors as 503; live/ready probes; infrastructure in health |
| `app/db/models/*` | changed / new | lease columns; `WorkerHeartbeat` |
| `scripts/migrate_to_postgres.py`, `scripts/migrate_files.py` | new | moving data and files |
| `tests/` (6 test files + stand-ins), `pytest.ini`, `requirements-dev.txt` | new | 53 tests, run on SQLite and PostgreSQL; they never read `backend/.env` |
| `Dockerfile`s, `.dockerignore`s, `docker-compose.yml`, `.env.docker.example` | new | containers |
| `frontend/…/health-card.tsx`, `pipeline-card.tsx`, `next.config.ts`, `schema.d.ts` | changed | the setup and worker count on the dashboard; standalone builds for Docker |

---

## 7. Ideas you'll meet in Step 15

| Idea | Meaning here |
|---|---|
| **Ports and adapters** | The business code talks to an interface ("store this file"); an adapter per service does the work. Changing cloud = changing adapters, not code |
| **At-least-once + idempotency** | Queues may deliver a message twice; the claim in the database makes doing it twice harmless |
| **Lease / heartbeat** | A claim that expires unless renewed: the standard way to notice a dead worker without asking it |
| **Advisory lock** | A named PostgreSQL lock that isn't tied to a row: only one replica migrates at a time |
| **Expand-migrate-contract** | How to change a schema without downtime: add the new column, move the data, remove the old later. Our migrations only add, so old and new app versions can run side by side during a deploy |
| **12-factor config** | All settings come from the environment, so the same image runs everywhere and secrets stay out of the image |
| **Liveness vs readiness** | "Is it alive?" (restart if not) vs "can it take traffic?" (route around it if not) |
| **Workload identity** | The platform gives the container an identity (IAM role, service account, managed identity): no keys to leak or rotate |

---

## 8. What was tested

Every test runs the **real SDKs** (boto3, google-auth, openai, anthropic, google-cloud-storage, azure-storage-blob). Only the network is faked, and the stand-ins refuse requests the real services refuse.

| What | Result |
|---|---|
| `python -m pytest`, SQLite | 51 passed, 2 skipped (PostgreSQL-only tests) |
| `TEST_DATABASE_URL=postgresql+asyncpg://… python -m pytest`, PostgreSQL 16 + pgvector 0.6, server time zone Asia/Kolkata | 51 passed, 2 skipped (SQLite-only checks) |
| Earlier suites | provider checks 47/47; agent evaluation 12/14, the same as before Step 15 |
| Migrations | upgrade/downgrade/upgrade on both databases; `--sql` output; a copy of your PC database upgraded with every row count unchanged |
| Parity, a copy of your data on SQLite vs PostgreSQL | the same people at the top of every match run; top 10 keyword hits identical; 17–18 of 20 keyword ranks equal |
| **Multiple processes, real HTTP:** API + 2 workers, PostgreSQL, SQS + S3 (moto server), a 2.5 s "LLM" | 6 resumes in parallel; **`kill -9` of a worker mid-extraction**: its resume came back after the lease and finished, all 6 READY; a worker **stopped mid-judging**: the run stayed open and another worker completed it (both verdicts); no errors in any log |
| **Docker images** built from the real Dockerfiles; the full **docker compose** stack | migrate → api → worker → portal all healthy; login and bulk upload through the portal; the worker container processed both resumes; original file download; `--scale worker=3` → "3 workers running" |

**Bugs that only showed up in these tests:**
- **The empty `public/` folder.** Git doesn't keep it, so the frontend image build would have failed on your PC. The Dockerfile now creates it.
- **A new Docker volume is owned by root.** Uploads failed with "permission denied". The image now pre-creates the data folders owned by the app user, and a storage failure returns a clear 503 instead of a 500.
- **`a//b.pdf` passed key validation.** S3 treats it as a different key from `a/b.pdf`. Validation now rejects empty path segments.
- **Postgres ranked short chunks first.** `ts_rank_cd` put "Kubernetes basics." above a chunk naming both Kubernetes and Terraform. It was replaced with FTS5's BM25.

The model stand-ins cover only Pub/Sub and Service Bus in-process: their SDKs are tested for call shapes, not against the real services. Test those two once against the real services before relying on them.

---

## 9. Limitations and what's next

- **Not yet built:**
  - **SSO** (Entra ID / Okta via OIDC): logins are still the app's own.
  - **Observability:** structured JSON logs, OpenTelemetry traces and metrics, and LLM tracing (Langfuse). Today it's plain logs plus the health endpoints.
  - **Infrastructure as code:** Terraform or Bicep for the services in §5. The tables there are the checklist.
  - **CI/CD:** a pipeline that runs the tests on both databases, builds and scans the images (Trivy), and pushes them.
  - **A secrets manager integration:** today secrets come from environment variables. The orchestrators in §5 fill those from their secret stores, which is the common pattern.
- **Keyword ranking on PostgreSQL** matches FTS5's formula. Rare differences remain in near-ties, so measure with `evaluate_all` after moving (doc 19).
- **Pub/Sub publishes without a delay:** a delayed job is published at once, and its retry delay is applied when it is received.
- **Bedrock structured output** depends on the model. The three-mode fallback copes, but check the log line "structured output via …" for your model.
- **Changing database or model is a migration of data,** not just a setting: use the scripts in §5.5 and keep the old setup until the evaluations agree.

---

## 10. Glossary

| Term | Meaning |
|---|---|
| **Alembic** | SQLAlchemy's migration tool: versioned, reviewable schema changes |
| **pgvector** | A PostgreSQL extension for storing vectors and nearest-neighbour search (HNSW, IVFFlat) |
| **HNSW** | The graph index used for fast approximate nearest-neighbour search |
| **tsvector / GIN** | PostgreSQL's searchable form of text, and the index type that makes it fast |
| **Object storage** | Files ("objects") in buckets behind an API: S3, Cloud Storage, Blob Storage |
| **SSE-KMS / CMEK** | Encryption at rest with your own key, managed in the cloud's key service |
| **Visibility timeout / ack deadline / lock** | How long a received message stays hidden from other workers (SQS / Pub/Sub / Service Bus) |
| **Dead-letter queue (DLQ)** | Where messages go after failing too often, for a person to look at |
| **Lease** | A claim that expires unless renewed |
| **Liveness / readiness probe** | Health checks that decide restarting vs routing traffic |
| **Inference profile** | Bedrock's cross-region routing for a model (`apac.`, `us.`, `eu.`, `global.`) |
| **ADC** | Google's Application Default Credentials |
| **Managed identity / workload identity / task role** | The identity the platform gives a container, so no keys are needed |
| **Standalone output** | Next.js's build mode that bundles a self-contained server for containers |
