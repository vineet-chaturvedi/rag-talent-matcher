# 06 · Technology Choices & Enterprise Stack

Why each tool was chosen, what the alternatives are, and what a large company would run in production.

- **Part 1:** decision records: for each major choice, the problem, the options, the decision and its consequences.
- **Part 2:** quick comparison table.
- **Part 3:** the enterprise, production-grade stack and the upgrade path.

There is no single "best" tool for every company. The right choice depends on scale, budget, cloud provider and compliance rules. Our learning build was chosen for three constraints: **learn the concepts clearly, run on a 16 GB CPU-only laptop, keep resumes private.**

---

# Part 1: Decision records

### DR-1 · Web framework: FastAPI
- **Problem:** an HTTP API that calls slow AI models without freezing, validates input, and documents itself.
- **Options:** FastAPI · Flask · Django (+ REST framework).
- **Decision:** **FastAPI**: async by design (essential for 60-second LLM calls), Pydantic validation built in, automatic `/docs`.
- **Consequences:** all I/O code must be async (`httpx`, `aiosqlite`); slow synchronous libraries run in threads.

### DR-2 · Database: SQLite via async SQLAlchemy
- **Problem:** store employees, resumes, profiles, skills, chunks and match history, with relationships and safe concurrent writes.
- **Options:** SQLite · PostgreSQL · MySQL; ORM: SQLAlchemy · SQLModel · raw SQL.
- **Decision:** **SQLite** (one file, zero install) behind **SQLAlchemy 2**, so moving to PostgreSQL is a change of `DATABASE_URL`.
- **Consequences:** one writer at a time (fine for one user; WAL mode and a busy timeout added). Foreign keys must be switched on per connection. Schema changes need Alembic migrations later.

### DR-3 · PDF and DOCX text: pypdfium2 + python-docx
- **Problem:** reliable text from varied resume layouts, with a licence safe for company use.
- **Options:** PyMuPDF (excellent, **AGPL**) · pypdfium2 (Apache-2.0/BSD) · pdfplumber · pypdf · Docling · Unstructured.
- **Decision:** **pypdfium2** (equal results to PyMuPDF on our samples, permissive licence) and **python-docx** (reads tables in document order).
- **Consequences:** scanned PDFs need OCR, deferred; detected and marked failed for now.

### DR-4 · Background processing: our own worker, database as queue
- **Problem:** process thousands of resumes (~1 minute each) without blocking uploads, surviving restarts.
- **Options:** Celery / RQ / Dramatiq with Redis · Temporal · our own asyncio worker.
- **Decision:** **our own worker**: each resume's `status` is the queue, so there's nothing extra to install and every line is readable.
- **Consequences:** one worker process (matches the CPU's capacity anyway); replace with Celery or Temporal when scaling out.

### DR-5 · Model runtime: Ollama by default, any provider through a router
- **Problem:** run LLMs and embeddings locally, privately, on a CPU, and still be able to use cloud or company models when wanted.
- **Options:** Ollama · LM Studio · llama.cpp · vLLM (GPU) · cloud APIs · an LLM gateway (LiteLLM, Portkey).
- **Decision:** **Ollama** by default: simplest install, REST API, model management, CPU-optimised engine (llama.cpp inside). Since 2026-11-06, a **model router** (`app/llm/router.py`, doc 20) sends any model setting written as `<provider>/<model>` to OpenAI, Azure OpenAI, Anthropic, Gemini, Voyage, Cohere, or any OpenAI-compatible server.
- **Consequences:**
  - CPU speed limits local model size (3–9B).
  - The rest of the code doesn't know the provider, so switching is one `.env` line.
  - Cloud models are refused until `ALLOW_CLOUD_MODELS=true`, because resumes are personal data.

### DR-6 · LLMs: qwen2.5 3B (fast) and 7B (quality); Qwen 3.5 under test
- **Problem:** reliable JSON extraction and reasoning within CPU limits.
- **Options:** qwen2.5 / qwen3.5, llama3.2:3b, gemma4, granite, phi-4-mini; cloud: Claude, GPT, Gemini.
- **Decision:** **qwen2.5** for strong instruction-following and JSON. Extraction uses the **3B**: same accuracy as the 7B on our checks (13/14) at half the time.
- **Consequences:**
  - The 3B's Qwen Research Licence must be reviewed before company use.
  - **qwen3.5:4b / 9b** (Apache 2.0) are the candidates to measure with `evaluate_all`.
  - Cloud models are one `.env` line away (doc 20 §5).

### DR-7 · Structured extraction: schema-constrained output + code verification
- **Problem:** turn free text into trustworthy facts.
- **Options:** free-text prompting · JSON by prompt only · schema-constrained decoding · commercial resume parsers.
- **Decision:** **structured outputs with a Pydantic schema** (Ollama `format`; OpenAI `response_format`; Claude through a forced tool), plus deterministic checks (evidence grounding, job-level grounding, skill normalisation, date maths in code).
- **Consequences:** valid JSON every time; hallucinated skills and inflated years are caught by code, not trusted.

### DR-8 · Embeddings: nomic-embed-text, swappable
- **Options:** nomic-embed-text · qwen3-embedding · bge-m3 · mxbai-embed-large · embeddinggemma · commercial APIs (OpenAI text-embedding-3, Voyage, Cohere, Gemini).
- **Decision:** **nomic-embed-text**: small (~270 MB), fast on CPU, good retrieval quality; requires task prefixes.
- **Consequences:**
  - `app/llm/models.py` knows each model's query/document prompts, and each embedding model gets its own vector collection (vector sizes differ).
  - Changing the model re-embeds automatically at the next start (doc 20).

### DR-9 · Chunking: our own, domain-aware
- **Options:** LangChain / LlamaIndex splitters · Chonkie · Docling HybridChunker · our own.
- **Decision:** **our own**: profile card from structured data, one chunk per job at real job boundaries, the rest; contextual headers; anonymisation.
- **Consequences:** no generic library knows what a "job" is; we maintain ~200 lines. A library can replace just the generic splitting.

### DR-10 · Vector store: ChromaDB (embedded)
- **Options:** ChromaDB · Qdrant · pgvector · FAISS · LanceDB · Milvus · managed services.
- **Decision:** **ChromaDB**: runs inside Python, persists to disk, cosine HNSW, metadata filters, Apache 2.0, telemetry off.
- **Consequences:** single-process; SQLite remains the source of truth, so the index can be rebuilt or migrated to pgvector or Qdrant.

### DR-11 · No RAG framework
- **Options:** LangChain · LlamaIndex · Haystack · plain code.
- **Decision:** **plain code**, so every step is visible and understandable while learning.
- **Consequences:** more code to write; frameworks can be adopted later for specific parts.

### DR-12 · Model providers: own small adapters over the official SDKs, not a gateway library
- **Problem:** use Claude, GPT, Gemini, Azure OpenAI and enterprise embeddings without rewriting the app.
- **Options:** LiteLLM (one library, 100+ providers) · our own adapters on the official SDKs · a hosted gateway (Portkey, Kong, Azure API Management).
- **Decision:** **own adapters**:
  - one for OpenAI-compatible APIs (covers OpenAI, Azure, Gemini chat, vLLM, OpenRouter, Groq, Mistral, gateways);
  - one for Anthropic;
  - plain HTTP for Voyage, Cohere and Gemini embeddings.

  About 800 readable lines, two optional dependencies (`requirements-cloud.txt`), and every translation step is visible for learning.
- **Consequences:**
  - A provider's new features need a small change in its adapter.
  - A company gateway (LiteLLM proxy, Portkey) can still be used through `compat/`, and gives central keys, budgets and logging.

---

# Part 2: Quick comparison

| Part | We use | Main alternatives | Why ours (for now) |
|---|---|---|---|
| Web API framework | **FastAPI** | Flask, Django | Async, validation, `/docs` |
| Web server | **Uvicorn** | Hypercorn, Gunicorn + Uvicorn workers | FastAPI's standard partner |
| Relational database | **SQLite** | PostgreSQL, MySQL | Zero install; PostgreSQL for many users |
| ORM | **SQLAlchemy 2 (async)** | SQLModel, Django ORM, raw SQL | Industry standard; database-independent |
| Settings | **pydantic-settings** | python-dotenv, dynaconf | Typed and validated |
| PDF text | **pypdfium2** | PyMuPDF (AGPL), pdfplumber, pypdf, Docling | Accurate, permissive licence |
| Word text | **python-docx** | docx2txt, mammoth, Docling | Tables in document order |
| Background jobs | **Own worker** | Celery, RQ, Dramatiq, Temporal | No extra servers; restart-safe |
| Model runtime | **Ollama** (+ router to any provider) | LM Studio, llama.cpp, vLLM, LiteLLM | Easiest local setup; cloud is one line away |
| LLM | **qwen2.5:3b / 7b** | qwen3.5, llama3.2:3b, gemma4, phi-4-mini; Claude, GPT, Gemini | JSON reliability; fits a CPU |
| Embeddings | **nomic-embed-text** | qwen3-embedding, bge-m3, mxbai-embed-large; OpenAI, Voyage, Cohere, Gemini | Small, fast, proven |
| Chunking | **Own** | LangChain, Chonkie, Docling | Uses job structure |
| Vector database | **ChromaDB** | Qdrant, pgvector, FAISS, LanceDB, Milvus | Embedded, simple |
| Keyword search (Step 7) | **SQLite FTS5** | Elasticsearch, OpenSearch, rank-bm25 | Already in SQLite |
| RAG framework | **None** | LangChain, LlamaIndex, Haystack | Learn every step |
| Frontend (Step 11) | **Next.js** | React + Vite, Vue/Nuxt, SvelteKit | Widely used |

---

# Part 3: Enterprise, production-grade stack

The options below are the **widely adopted, production-proven** choices large organisations use. The *architecture* of our build is already enterprise-grade; some *components* are prototype-grade and get swapped before going live.

## 3.1 Already industry standard in our build

| Part | Our choice | Standing |
|---|---|---|
| Backend language | **Python** | The default language for AI/ML systems |
| API framework | **FastAPI** | Among the most widely used Python API frameworks; used in production by large companies |
| Data validation | **Pydantic** | The standard; FastAPI, LangChain and the OpenAI SDK are built on it |
| ORM | **SQLAlchemy 2** | The most established Python ORM |
| Frontend | **Next.js** | One of the most popular React frameworks |
| Version control | **Git** | Universal |
| Retrieval design | Structured extraction, then hybrid search (vector + BM25), then fusion, then LLM reranking with citations | What serious RAG systems use; most tutorials only do "vector search, then LLM" |
| Engineering patterns | Database as source of truth, idempotent re-indexing, grounding checks, evaluation scripts, crash recovery | The habits that separate production systems from demos |
| Model access | One router, `<provider>/<model>`, a data-protection switch for cloud models | The same idea as an enterprise LLM gateway, built small |

## 3.2 Learning choice vs enterprise production choice

| Layer | Ours (learning) | Enterprise production choice | Why we didn't start there |
|---|---|---|---|
| Relational database | SQLite | **PostgreSQL**, usually managed (AWS RDS / Aurora, Azure Database for PostgreSQL, Google Cloud SQL) | Needs a server or Docker; SQLite works for one user |
| Vector search | ChromaDB (embedded) | **pgvector** inside PostgreSQL (one database for everything), **Qdrant**, **Elasticsearch / OpenSearch** (vectors + BM25 in one engine), or managed: **Azure AI Search**, **Pinecone**, Vertex AI Vector Search | Chroma needs no server; ideal for learning |
| Keyword search | SQLite FTS5 | **Elasticsearch / OpenSearch**, or PostgreSQL full-text search | Same reason |
| File storage (resumes) | Local `data/uploads/` folder | **Object storage**: AWS S3, Azure Blob Storage, Google Cloud Storage (MinIO on-premise), encrypted, with lifecycle rules | Local disk is fine on one PC |
| Document parsing / OCR | pypdfium2 + python-docx; no OCR | **Azure AI Document Intelligence**, **AWS Textract**, Google Document AI; open source: **Docling**, Unstructured, Tesseract / PaddleOCR | Cloud services send data out; open-source OCR needs extra installs |
| Background jobs | Our own worker (database as queue) | **Celery** or **RQ** with Redis / RabbitMQ; **Temporal** for long, multi-step workflows; cloud queues (AWS SQS, Azure Service Bus) | No extra servers; you can read every line |
| LLM serving | Ollama on a CPU (cloud APIs possible through the router) | **vLLM** or Hugging Face **TGI** on **GPU servers**; or **managed APIs** under an enterprise agreement: **Azure OpenAI**, **AWS Bedrock**, **Google Vertex AI** (data not used for training, regional hosting) | No GPU; everything stays on the laptop |
| LLM gateway | Our router (`app/llm/router.py`) | **LiteLLM proxy**, **Portkey** or a cloud API gateway: central keys, budgets, rate limits, fallbacks, cost tracking (usable through `compat/`) | One user; the router is enough |
| LLM | qwen2.5 3B / 7B (any model via `.env`) | Larger open models (30–70B class) on GPUs, or frontier models (Claude, GPT, Gemini) through managed APIs | 3–9B is what a 16 GB CPU can run |
| Embeddings | nomic-embed-text (any via `.env`) | **Voyage**, **OpenAI text-embedding-3**, **Cohere embed**, **Gemini embedding**, or open **bge-m3** / **qwen3-embedding** on GPUs | Small and fast on CPU |
| Reranking | Local cross-encoder (optional) + LLM judge | Cross-encoders (**bge-reranker**, **Cohere Rerank**, Voyage rerank) before the LLM judge | Fewer moving parts while learning |
| Caching | None | **Redis** for repeated queries, embeddings and sessions | Not needed for one user |
| Authentication | JWT built ourselves (Step 9) | **SSO** with the company identity provider (**Microsoft Entra ID**, **Okta**) via OIDC / SAML, plus role-based access control (RBAC) | Needs the company's identity setup |
| Secrets | `.env` file | **Azure Key Vault**, **AWS Secrets Manager**, **HashiCorp Vault** | Fine on a laptop |
| Packaging & deployment | `uvicorn` on a PC | **Docker** images on **Kubernetes** (AKS / EKS / GKE) or a managed container service (Azure Container Apps, AWS ECS, Cloud Run) | Not needed to learn RAG |
| Infrastructure | Manual | **Infrastructure as Code**: Terraform, Bicep, Pulumi | Same |
| CI/CD | Manual git commits | **GitHub Actions**, GitLab CI, Azure DevOps: tests, linting and evaluations on every change | Same |
| Code quality | Manual | **pytest** (tests), **ruff** (linting/formatting), **mypy** (type checking), pre-commit hooks | Added in hardening |
| Observability | Log lines | **OpenTelemetry** traces, **Prometheus + Grafana** metrics, central logs (ELK, Azure Monitor, CloudWatch), LLM tracing (**Langfuse**, LangSmith) | Later concern |
| RAG / LLM evaluation | Our own scripts (Step 14, `evaluate_all`) | Our scripts **plus** **Ragas**, **DeepEval** or promptfoo, run in CI on a fixed test set | Learn the idea first |
| PII protection | Regex anonymisation | **Microsoft Presidio** or cloud DLP services for detecting and masking personal data | Regex is enough for the samples |
| Guardrails | Grounding checks | Input / output filters (e.g. NeMo Guardrails, Guardrails AI, cloud content safety) against prompt injection and data leakage | Small internal tool |

## 3.3 Enterprise requirements beyond technology

For an HR system, these matter as much as the tools:

- **Data protection:** India's **DPDP Act** (purpose limitation, consent, retention limits, deletion on request). Our delete cascades, local-only processing by default, and the `ALLOW_CLOUD_MODELS` switch help. Before using a cloud model for real employees, a data processing agreement, no-training terms, retention and data residency must be checked.
- **Fairness and human oversight:** anonymise what the AI sees, keep a human as the final decision maker, and test rankings for bias. If the company also operates in the EU, the **EU AI Act** classifies AI used for recruitment and work allocation as **high-risk**, which brings documentation, risk management, bias testing and human-oversight obligations.
- **Audit trail:** who searched, who was shortlisted, and why. Our stored match runs with evidence are designed for this.
- **Access control:** only authorised people see resumes (least privilege), and every access is logged.
- **Security reviews:** penetration testing, dependency scanning (e.g. Dependabot, Snyk), and licence checks (we already avoided AGPL PyMuPDF and noted the Qwen 3B licence).
- **Reliability:** backups and restore tests, defined uptime targets, and monitoring alerts.

## 3.4 Reference production architecture

```
Users ──SSO (Entra ID / Okta)──▶ Next.js frontend ──▶ API gateway ──▶ FastAPI (Docker, Kubernetes, several replicas)
                                                                         │
           ┌─────────────────────────────┬───────────────────────────────┼──────────────────────────┐
           ▼                             ▼                               ▼                          ▼
  PostgreSQL + pgvector          Object storage (S3 / Blob)        Job queue (Celery/Temporal)   LLM gateway (LiteLLM)
  (profiles, chunks, vectors,    (original resumes, encrypted)     → ingestion workers          → vLLM on GPUs, or
   audit log, FTS / BM25)                                            parse / extract / embed       Azure OpenAI / Bedrock
           │
  Observability: OpenTelemetry · Prometheus/Grafana · Langfuse      Secrets: Key Vault / Secrets Manager
  Quality: pytest · Ragas/DeepEval in CI                             Infra: Terraform · GitHub Actions
```

## 3.5 Upgrade path from our build

Each outside dependency sits behind **one adapter**, chosen in `.env`. Step 15 (doc 21) built the main ones:

| To switch to… | Change | Status |
|---|---|---|
| PostgreSQL + pgvector | `DATABASE_URL=postgresql+asyncpg://...`; Alembic migrations; full-text search with FTS5's BM25; `scripts/migrate_to_postgres` moves data and vectors | ✅ Step 15b |
| Amazon Bedrock / Vertex AI | `.env` only: `bedrock/<model id>`, `vertex/<model>` (credentials from the platform, no keys) | ✅ Step 15a |
| Azure OpenAI / Gemini / Claude / GPT | `.env` only: `azure/<deployment>`, `gemini/...`, `anthropic/...`, `openai/...`, the key, and `ALLOW_CLOUD_MODELS=true` (doc 20) | ✅ Steps 14–15 |
| A GPU server with vLLM | `.env` only: `COMPAT_BASE_URL=http://<server>:8000/v1` and `QUALITY_LLM_MODEL=compat/<model>` | ✅ |
| Object storage | `STORAGE_BACKEND=s3 / gcs / azure` (`app/storage`); `scripts/migrate_files` moves files | ✅ Step 15c |
| A message queue + separate workers | `QUEUE_BACKEND=sqs / pubsub / servicebus`, `python -m app.worker` (`app/jobs`, leases, at-least-once) | ✅ Step 15d |
| Containers | `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` | ✅ Step 15e |
| Qdrant / OpenSearch / Azure AI Search | One more class in `app/rag/vector_store.py` (the interface is async and small) | Possible |
| Celery / Temporal | One more queue class in `app/jobs` (or replace the runtime); the handlers stay the same | Possible |
| SSO | Replace the token check in `app/api/deps.py` (Step 9) with OIDC validation (Entra ID, Okta) | Next |
| Observability | Structured logs, OpenTelemetry traces/metrics, LLM tracing (Langfuse) | Next |
| Infrastructure as code, CI/CD | Terraform / Bicep for doc 21 §5; a pipeline running the tests on both databases and building the images | Next |
