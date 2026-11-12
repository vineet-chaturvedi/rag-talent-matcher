# 01 · System Architecture

How the system is put together: the components, the layers of code, the data model, and how a request travels through it.

---

## 1. Components and how they talk

```
┌──────────┐ HTML/forms ┌──────────────────┐ HTTP/JSON  ┌────────────────────────────────────────────────────┐
│ Browser  │ ─────────▶ │ Next.js portal   │ ─────────▶ │  FastAPI backend (Python, port 8010)               │
│ (cookie) │ ◀───────── │ :3000 (Step 11)  │ ◀───────── │                                                    │
└──────────┘ streamed   └──────────────────┘ Bearer JWT │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
                                           │  │ API      │─▶│ Services │─▶│ Ingestion worker │  │
                                           │  │ routers  │  │ (rules)  │  │ (background)     │  │
                                           │  └──────────┘  └──────────┘  └──────────────────┘  │
                                           └─────┬───────────────┬──────────────────┬───────────┘
                                                 │ SQL           │ files            │ HTTP
                                                 ▼               ▼                  ▼
                                   ┌──────────────────┐ ┌───────────────┐  ┌──────────────────────┐
                                   │ SQLite app.db    │ │ data/uploads/ │  │ Ollama (port 11434)  │
                                   │ (source of truth)│ │ (resume files)│  │  qwen2.5:3b / 7b     │
                                   └──────────────────┘ └───────────────┘  │  nomic-embed-text    │
                                   ┌──────────────────┐                    └──────────────────────┘
                                   │ ChromaDB         │
                                   │ data/chroma/     │
                                   │ (vector index)   │
                                   └──────────────────┘
```

| Component | Role | Runs where |
|---|---|---|
| **Next.js portal** (Step 11) | The web UI. Renders pages on its server and calls FastAPI server-to-server with the user's token; signs in/out with Server Actions; redirects visitors to login (proxy); forwards `/api/*` for resume uploads (rewrite); relays the agent's live stream through `/bff/agent/{id}` (Route Handler, Step 13). Details in section 8 and docs 15–17 | `npm run dev`, port 3000 |
| **FastAPI app** | Receives HTTP requests, validates input, returns JSON | Inside `uvicorn` |
| **Ingestion worker** | Processes the resume queue in the background | Same process as FastAPI (an asyncio task) |
| **SQLite** (`data/app.db`) | Employees, resumes, profiles, skills, chunks, projects, matches | A single file |
| **File storage** (`data/uploads/`) | Original PDF / DOCX files | Local disk |
| **ChromaDB** (`data/chroma/`) | Chunk vectors for meaning-based search | Inside the Python process |
| **Ollama** | Runs the AI models; answers `/api/chat` and `/api/embed` | Separate program on the same PC |

---

## 2. Code layers (separation of concerns)

Each layer has one job and only talks to the layer below it.

```
app/api/          HTTP: URLs, status codes, request/response shapes     (knows FastAPI)
app/auth/         Who are you, what may you do: passwords, tokens, role checks (Step 9)
   │ calls
app/services/     Business rules: upsert employees, new resume = current, save a profile
   │ calls
app/ingestion/    Files & pipeline: validate, store, extract text, the worker
app/extraction/   AI step 1: prompt, schema, LLM call, verification, skills, dates
app/rag/          AI step 2: chunking, embeddings, vector store, keyword index (FTS5), search
app/matching/     AI step 3: role → requirements (LLM), hybrid retrieval (RRF), rule scoring, LLM judge, match runs
app/agent/        AI step 4: the tool-calling staffing agent (loop, prompts, read-only tools) (Step 10)
   │ uses
app/db/           Tables (models), connections (session), enums
app/llm/          The ONLY code that talks to Ollama
app/schemas/      The JSON shapes the API accepts and returns
app/config.py     All settings, read from .env
```

**Why layers?**
- **One place per concern:** switching ChromaDB for Qdrant touches only `app/rag/vector_store.py`; switching Ollama for a cloud API touches only `app/llm/ollama_client.py`.
- **Reuse:** the same `add_resume()` service serves single and bulk uploads; the same `extract_profile()` serves the worker, a dev endpoint and an evaluation script.
- **Testability:** pure functions (dates, skills, chunking) can be tested without a server.

---

## 3. Folder structure

```
rag-talent-matcher/
├── .gitignore                 keeps secrets, data and environments out of git
├── docker-compose.yml         the whole system in containers (Step 15e, doc 21) + .env.docker.example
├── samples/                   fictional test data (employees.csv, resumes/, roles.json, README.md)
├── docs/                      this guide
├── frontend/                  Next.js portal (Step 11): see section 8 for its structure; Dockerfile
└── backend/
    ├── .env / .env.example    settings (real / template)
    ├── requirements*.txt      libraries: core, -cloud (providers, buckets, queues), -dev (tests); .lock = your PC
    ├── Dockerfile             one image for API, worker and migrations (Step 15e)
    ├── alembic.ini, migrations/   database schema migrations (Step 15b)
    ├── tests/                 pytest suite, runs on SQLite and PostgreSQL (Step 15)
    ├── data/                  app.db, uploads/, chroma/   (git-ignored: personal data)
    ├── scripts/               developer tools: seed_demo, inspect_db, upload_samples, compare_extraction,
    │                          try_search, load_roles, evaluate_*, create_user, api_login, try_agent,
    │                          migrate_to_postgres, migrate_files (Step 15)
    └── app/
        ├── main.py            creates the app, starts/stops the built-in worker, registers routers
        ├── worker.py          `python -m app.worker`: a separate background worker (Step 15d)
        ├── config.py          Settings (from .env)
        ├── api/               deps, health, overview, auth, users, employees, resumes, search,
        │                      projects, matching, agent, dev
        ├── auth/              passwords, tokens, login_guard, dependencies (Step 9)
        ├── services/          employees, resumes, profiles, indexing, users
        ├── ingestion/         storage (file checks, keys), text_extraction, pipeline (the stages of one resume)
        ├── storage/           where files live: local, s3, gcs, azure_blob (Step 15c)
        ├── jobs/              background jobs: queues (local, sqs, pubsub, servicebus), leases, handlers,
        │                      the worker runtime (Step 15d)
        ├── extraction/        schema, prompts, skills, dates, postprocess, extractor
        ├── rag/               chunking, embeddings, vector_store, keyword_index, search
        ├── matching/          requirements, retrieval (hybrid + RRF), scoring, judge, runner
        ├── agent/             loop, prompts, tools (Step 10)
        ├── schemas/           employee, resume, profile, search, project, matching, auth, agent, overview
        ├── llm/               router + one adapter per provider: ollama_client, openai_compat, anthropic_client,
        │                      bedrock, google_auth, embedding_apis; models (model-specific rules)
        └── db/                base, enums, session (engine, migrations at startup), unmanaged, models/
```

---

## 4. Data model (14 tables + 1 search index)

```
users ──────────────┐ (who uploaded / created / ran a match)
                    │
employees 1 ─── * resumes 1 ─── 1 resume_profiles   headline, summary, total years, education, certifications, raw LLM output
    │                 │ 1
    │                 ├──── * experiences            one row per job: title, company, start, end, current
    │                 ├──── * resume_chunks          text pieces; same ids as the vectors in ChromaDB
    │                 └──── * resume_skills * ─── 1 skills     years, last used year, evidence quote
    │
projects 1 ─── * project_roles 1 ─── * match_runs 1 ─── * match_results * ─── 1 employees

users 1 ─── * agent_conversations 1 ─── * agent_messages   (Step 10: each user sees only their own)
```

| Table | Holds | Key rules |
|---|---|---|
| `users` | People who log in (admin, resource_manager) | Unique email; Argon2id password hash; deactivated, never deleted (Step 9) |
| `employees` | HR master data + availability | Unique `employee_code`; `allocation_percent` 0–100 |
| `resumes` | One row per uploaded file version | Unique `file_hash` (duplicates rejected); `is_current`; `status` = the pipeline stage; `lease_expires_at` = the worker holding it; `stored_path` = the storage key |
| `resume_profiles` | LLM-extracted summary data | One per resume |
| `experiences` | Jobs from the resume | Cascade-deleted with the resume |
| `skills` | Canonical skill names (shared catalogue) | Unique name |
| `resume_skills` | Resume ↔ skill link with years, last used, evidence | Composite key (resume, skill) |
| `resume_chunks` | Chunk text, section, token estimate, embedding model | Source of truth for the vector index **and** the keyword index |
| `chunks_fts` | SQLite only: FTS5 virtual table, a word index over chunk text (Step 7) | Rebuilt from `resume_chunks` at startup if counts differ. PostgreSQL instead has a generated `resume_chunks.search_vector` column + GIN index (Step 15) |
| `emb_<hash>`, `vector_collections` | PostgreSQL only: pgvector tables, one per embedding model and size (Step 15) | Created on first use; vectors cascade-deleted with their resume |
| `worker_heartbeats` | Background workers alive (Step 15d) | Each worker reports every 30 s; "N workers running" |
| `alembic_version` | The schema's migration revision (Step 15b) | Written by Alembic only |
| `projects`, `project_roles` | Internal projects and the positions to fill | Role holds description + parsed requirements (Step 7) |
| `match_runs`, `match_results` | Every matching run and its ranked results with reasons | Kept for audit and caching (Step 8); the run's judge lease and attempts (Step 15d) |
| `agent_conversations`, `agent_messages` | Chats with the staffing agent, every message incl. tool calls and results | Private to their owner (Step 10) |

**Delete rules:** deleting an employee deletes their resumes, profiles, skills links, chunks and match results (`ON DELETE CASCADE`). Deleting a user only clears "uploaded by" links (`SET NULL`). The vector index is cleaned by the services layer.

---

## 5. Two flows

### 5.1 Ingestion flow (background)

```
POST /api/resumes/bulk ──▶ services.add_resume()
                               validate (type, magic bytes, size) ─▶ SHA-256 ─▶ duplicate? ─▶ store file (app/storage)
                               ─▶ old version: is_current = false, its vectors deleted
                               ─▶ new row: status = queued ─▶ commit ─▶ publish {"kind": "ingest", "id": …} (app/jobs)

Worker (built into the API, or any number of `python -m app.worker`): receive a job, CLAIM the resume (lease), work:
   queued    ─▶ parse   (pypdfium2 / python-docx, in a thread)                ─▶ parsed   ─▶ back to the queue
   parsed    ─▶ extract (the LLM + JSON schema, then code checks)              ─▶ extracted ─▶ straight on:
   extracted ─▶ embed   (chunks ─▶ vectors ─▶ ChromaDB / pgvector ─▶ database) ─▶ ready
   (the whole batch is parsed first; each resume is ready as soon as its own LLM step ends)
   errors:   file problem → failed · model service down → retry later, attempt not counted · other → retry ×3 → failed
   worker died: the lease runs out, the sweeper puts the resume back (doc 21 §4.4)
```

### 5.2 Search flow (per request)

```
POST /api/search/semantic {"query": "..."}
   embed query ("search_query: ...") ─▶ ChromaDB: 60 nearest chunks ─▶ keep current + ready resumes
   ─▶ group by employee (best chunk = score, keep 3 chunks as evidence) ─▶ ranked JSON
```

### 5.3 Matching flow (Step 7, per role)

```
POST /api/projects/{id}/roles            store the role: title, free-text description, allocation, start date
POST /api/roles/{id}/requirements/parse  LLM (quality model, ~30-60 s, once) → must-have / nice-to-have skills,
                                         seniority, min years, location, a search summary  → role.requirements
PUT  /api/roles/{id}/requirements        (optional) a person corrects what the AI parsed
POST /api/roles/{id}/candidates          ↓ (~100 ms, no LLM writing)
   eligible = active employees with a current READY resume  (+ availability check per person)
   ① skills  : SQL data from Step 5 — must/nice coverage, implied skills (EKS ⇒ Kubernetes), years, recency
   ② keyword : FTS5 BM25 over chunks for every spelling of the skills ("Kubernetes" OR "k8s" OR "EKS"...)
   ③ vector  : embed the search summary → ChromaDB nearest chunks, limited to eligible employees
   → Reciprocal Rank Fusion of the three rankings → candidates with per-signal ranks and evidence
```

See document 04 for each stage in detail.

### 5.4 Portal page flow (Step 11, per page view)

```
Browser GET /  ──▶ proxy.ts: cookie present and not expired?  no ─▶ 307 /login?next=/
                   │ yes
                   ▼
Next.js sends the STATIC SHELL at once (sidebar, title, skeletons)
   and, on its server, in parallel, each <Suspense> part:
     getCurrentUser()  ─ GET /api/auth/me      ─▶ menu by role, account menu, greeting   ("use cache: private")
     OverviewTiles     ─ GET /api/overview + /api/resumes/stats
     HealthCard        ─ GET /api/health  (asks Ollama)
     PipelineCard      ─ GET /api/resumes/stats
     ProjectsCard      ─ GET /api/projects
   every call: Authorization: Bearer <token from the HttpOnly cookie>
   each finished part streams into the open page; a failing part shows its own message
   FastAPI 401 on any call ─▶ /auth/session-expired (cookie deleted) ─▶ /login?expired=1

Sign in:  <form> POST ─▶ Server Action login(): zod ─▶ POST /api/auth/login ─▶ set cookie ─▶ redirect
```

---

## 6. Startup and shutdown sequence

```
uvicorn app.main:app
 ├─ import app.main: read settings, configure logging, create FastAPI app, add CORS, register routers
 └─ lifespan startup
     1. init_db()               run the Alembic migrations (DB_AUTO_MIGRATE), or check the schema is current
     2. make_model_client()     the model router: one client for every provider
     3. get_storage()           where resume files live (local / S3 / GCS / Azure Blob)
     4. get_vector_store()      ChromaDB (SQLite) or pgvector (PostgreSQL), the current model's collection
     5. ensure_keyword_index()  SQLite: the FTS5 table, rebuilt if out of sync; PostgreSQL: checked
     6. get_queue()             where jobs travel (local = the database / SQS / Pub/Sub / Service Bus)
     7. Worker.start()          only if WORKER_ENABLED: consumers + sweeper (recovers dead workers' jobs) +
                                heartbeat; otherwise run `python -m app.worker` separately (doc 21 §4.4)
 ... serve requests ...
 └─ lifespan shutdown (Ctrl+C / SIGTERM)
     1. worker.stop()           running jobs get WORKER_SHUTDOWN_SECONDS, then are handed back to the queue
     2. close the queue, the model clients and storage; dispose the database engine
```

---

## 7. Key design principles

| Principle | Where you see it |
|---|---|
| **LLM reads, code checks** | The LLM only copies and labels; code verifies evidence, normalises skills, computes years |
| **Source of truth vs index** | SQLite holds the truth; ChromaDB and the FTS5 keyword index can always be rebuilt (`/api/resumes/reembed`, restart) |
| **Several weak signals beat one strong one** | Retrieval fuses structured skills, keywords and vectors by rank (RRF) |
| **AI output is editable** | Parsed role requirements can be corrected by a person (`PUT …/requirements`, `edited_by_user`) |
| **Idempotent operations** | Re-extraction and re-embedding replace old data, never duplicate |
| **The queue is the database** | `resumes.status` survives crashes and restarts |
| **Fail clearly** | Typed errors (`InvalidFileError`, `ExtractionError`, `OllamaError`) with messages for humans |
| **Privacy and fairness by design** | Local models only; anonymised chunks; cascade deletes; human makes the final decision |
| **One adapter per outside system** | `ollama_client.py`, `vector_store.py`, `storage.py`, `session.py`; in the portal, `lib/api/client.ts` is the only door to FastAPI |
| **One authority for access** | FastAPI decides who may do what; the portal forwards the token and only hides what a role can't use |
| **Types flow from the backend** | Pydantic models → `/openapi.json` → generated TypeScript (`npm run api:types`) |
| **Static first, stream the rest** | Portal pages are a prerendered shell plus streamed per-user parts (Cache Components) |
| **Expected errors are data** | `ApiResult` values (backend) shown in place; only bugs reach error boundaries |

---

## 8. The portal's architecture (frontend, Step 11)

```
src/app/          ROUTES: thin page/layout files; Suspense boundaries; metadata
   │ uses
src/features/     BUSINESS AREAS: auth (Server Actions, zod schemas, forms), dashboard (queries, cards)
   │ uses
src/components/   SHARED UI: ui/ (design system on Radix), layout/ (shell, navigation), error boundaries
   │ uses
src/lib/          FOUNDATIONS: api/ (typed FastAPI client, generated types, errors),
                  auth/ (server session, cookie, JWT expiry, safe redirects), env/ (validated settings)
src/app/bff/      RELAYS (Step 13): Route Handlers that add the token and pass a live stream through
src/proxy.ts      optimistic login redirect before each page (skips /api and /bff)
```

| Concern | Portal design | Backend counterpart |
|---|---|---|
| Who may do what | Forwards the token; hides links by role (convenience) | `get_current_user`, `require_admin` (authority) |
| Data shapes | Generated from `/openapi.json` | Pydantic schemas in `app/schemas/` |
| Data access | Server-only DAL (`request()`, `features/*/queries.ts`) | `app/api/` routers |
| Login state | HttpOnly cookie `rtm_access`, set by a Server Action | JWT issued by `/api/auth/login` (`AUTH_COOKIE_NAME`) |
| Errors | `ApiResult` in place; `catchError` per section | `HTTPException` with `detail` |
| Security headers | CSP and friends in `next.config.ts` | CORS (only for direct browser calls) |
| Live streams | `/bff/agent/{id}` relay, `fetch` + stream reader + SSE parser in the chat | `StreamingResponse` of agent events (`app/api/agent.py`) |

**The agent chat flow (Step 13):** browser `POST /bff/agent/7` → the relay validates and adds the Bearer token → FastAPI runs the agent and streams `tool_call`, `tool_result`, `token` and `answer` events → the relay passes them through unbuffered (`no-transform`; the `/api` rewrite gzips and would hold them back) → the chat updates the turn per event. Stop aborts the browser request, which cancels the upstream one and the agent.

Doc 15 explains every file, the flows and the trade-offs; doc 16 the portal pages; doc 17 the chat.

