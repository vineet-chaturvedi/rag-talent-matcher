# 05 · API, Scripts & Configuration Reference

Look-up reference for everything you can call or configure. Live, clickable documentation of every endpoint is always at **http://127.0.0.1:8010/docs** while the server runs.

**How to read this document:** each endpoint lists its method and path, what it does, its inputs, an example and the possible status codes.

---

## 1. HTTP status codes used

| Code | Meaning in this API |
|---|---|
| 200 | OK |
| 201 | Created (a resume, project or role) |
| 202 | Accepted: a match run started; the LLM judge continues in the background |
| 204 | Deleted; no content returned |
| 400 | Bad input (wrong file type, invalid CSV, too many files) |
| 401 | Not logged in, or the token is invalid/expired, or the account is deactivated (Step 9) |
| 403 | Logged in, but your role may not do this (admin-only action) |
| 404 | Not found (employee, resume or profile) |
| 409 | Conflict (duplicate file; retrying a resume that isn't failed; searching candidates for a role whose requirements aren't parsed yet) |
| 413 | Payload too large (CSV over 5 MB) |
| 422 | Validation error: the request didn't match the expected shape (the response names the field) |
| 502 | The LLM returned unusable output |
| 429 | Too many failed logins (5 in 15 minutes for one email) |
| 503 | A dependency is down (Ollama or the database) |

---

## 2. Endpoints

**Access (Step 9):** everything except `GET /`, `GET /api/health` and `/api/auth/login|token|logout` needs a logged-in user (Bearer token or the `rtm_access` cookie). **Admin only:** employee import, resume uploads, retry, delete, re-extract, re-embed, `/api/users`, `/api/dev/*`.

### 2.0 Authentication and users (Step 9)

| Method & path | Who | Purpose | Body / notes |
|---|---|---|---|
| `POST /api/auth/login` | anyone | Log in | `{"email", "password"}` → `{access_token, token_type, expires_at, user}` + HttpOnly cookie; 401 wrong; 429 locked |
| `POST /api/auth/token` | anyone | Same as an OAuth2 form (used by Swagger's **Authorize**) | `username` (= email), `password` |
| `POST /api/auth/logout` | anyone | Removes the cookie | 204 |
| `GET /api/auth/me` | signed in | Who am I | `UserOut` |
| `POST /api/auth/change-password` | signed in | Change own password | `{"current_password", "new_password"}` (≥ 12 chars) → 204 |
| `GET /api/users` | admin | List users | — |
| `POST /api/users` | admin | Create a user | `{"email", "full_name", "role": "admin|resource_manager", "password"}` → 201; 409 email exists |
| `PATCH /api/users/{id}` | admin | Change name, role, active, or reset password | any subset; 409 if it would remove the last active admin, or if an admin tries to deactivate or demote **themselves** (Step 12c) |

### 2.1 System

| Method & path | Purpose |
|---|---|
| `GET /` | Friendly message with links to `/docs` and `/api/health` |
| `GET /api/health` | Is everything working? Checks the database, Ollama, and that every model in `.env` is installed; shows the database kind and vector store, where files and jobs go, and how many workers run (Step 15). Public (no login): outside development only the *kind* of storage/queue is shown, never bucket names or queue URLs. Response model `HealthOut`, the same shape for 200 and 503 |
| `GET /api/health/live` | **Step 15:** liveness probe for containers and load balancers: the process answers. Always 200 |
| `GET /api/health/ready` | **Step 15:** readiness probe: 200 when the database answers, 503 otherwise (send no traffic yet) |
| `GET /api/overview` | Signed in. Counts for the dashboard tiles: employees (total/active), projects and roles by status, parsed roles, match runs by status (Step 11b) |

`/api/health` example response:
```json
{"app": "RAG Talent Matcher", "environment": "development", "status": "ok",
 "database": {"reachable": true},
 "ollama": {"reachable": true, "version": "0.40.11",
            "models": {"embed_model": {"name": "nomic-embed-text", "installed": true}, "...": "..."}}}
```
`status`: `ok` (200), `degraded` = a model is missing (200), `error` = database or Ollama unreachable (503, **with the same report in the body**, so the portal still shows which part failed).

`/api/overview` example response (counts only, never rows; every status is present, 0 if none):
```json
{"employees": {"total": 16, "active": 16},
 "projects":  {"total": 3, "by_status": {"planned": 3, "active": 0, "on_hold": 0, "completed": 0}},
 "roles":     {"total": 3, "by_status": {"open": 3, "filled": 0, "closed": 0}, "parsed": 3},
 "match_runs":{"total": 27, "by_status": {"running": 0, "completed": 27, "failed": 0}}}
```

### 2.2 Employees

| Method & path | Purpose | Inputs |
|---|---|---|
| `POST /api/employees/import` | Create or update employees from the HR CSV (upsert by `employee_code`) | multipart file `file` (UTF-8 CSV, ≤ 5 MB) |
| `GET /api/employees` | List employees with their current resume status | `search` (code, name, department, location), `availability` (`available`, `partial`, `allocated`, `on_leave`; Step 12a), `limit` (1–500, default 50), `offset` |
| `GET /api/employees/{employee_id}` | One employee with all resume versions | — |

**CSV columns:** `employee_code`*, `full_name`*, `email`, `department`, `designation`, `location`, `date_joined` (YYYY-MM-DD), `availability_status` (available / partial / allocated / on_leave), `allocation_percent` (0–100), `available_from`, `current_project_name`, `manager_name` (* required).

Import response:
```json
{"created": 16, "updated": 0, "failed": 1,
 "errors": [{"line": 4, "employee_code": "EMP-2002", "message": "allocation_percent: Input should be less than or equal to 100"}]}
```
Blank cells never overwrite existing values. All valid rows are saved in one transaction.

### 2.3 Resumes: upload and lifecycle

| Method & path | Purpose | Inputs / notes |
|---|---|---|
| `POST /api/employees/{employee_id}/resumes` | Upload one resume for a known employee | multipart `file` (PDF/DOCX ≤ 10 MB) → 201; 400 invalid; 409 duplicate |
| `POST /api/resumes/bulk` | Upload many resumes; employee found from the filename (`EMP-1001_anything.pdf`) | multipart `files` (≤ 200 per request); per-file results |
| `GET /api/resumes` | List resumes | `status` (queued…failed), `current_only` (default true), `limit`, `offset` |
| `GET /api/resumes` | List current resumes, newest first. `?status=`, `?current_only=` (default true), `?limit=` (≤500), `?offset=`. Each item is `ResumeListItem`: the resume plus `employee_code` and `employee_name` (Step 12a) | — |
| `GET /api/resumes/stats` | Queue overview: counts per status, worker running, `workers_online` (worker processes alive, Step 15), vector count | — |
| `GET /api/resumes/{resume_id}` | Details plus extracted text | `full_text=true` for all of it (default: first 1,500 characters) |
| `GET /api/resumes/{resume_id}/file` | **Admins.** The original uploaded file of any version, byte for byte, under the name it was uploaded with. PDFs open in the browser (`inline`); Word files always download. `?download=true` downloads a PDF too. `Cache-Control: private, no-store` | 403 for non-admins. 404 for an unknown id, or when the file is missing from `UPLOAD_DIR` |
| `GET /api/resumes/{resume_id}/profile` | The structured profile from the LLM: skills (years, last used, evidence), jobs, education (`degree`, `institution`, `year`: the year is grounded in the resume text, Step 12a), certifications, rejected skills, warnings, LLM stats | 404 until extracted |
| `GET /api/resumes/{resume_id}/chunks` | How the resume was cut into chunks (section, token estimate, text) | Debugging chunking |
| `POST /api/resumes/{resume_id}/retry` | Re-queue a failed resume (to `parsed` if text exists, else `queued`) | 409 if not failed |
| `POST /api/resumes/reextract` | Send all extracted/ready/failed resumes with text back to LLM extraction. Returns `{"requeued": n}` | Use after changing model, prompt or skill catalog |
| `POST /api/resumes/reembed` | Rebuild all chunks and vectors. Returns `{"requeued": n}` | Use after changing chunking or the embedding model |
| `DELETE /api/resumes/{resume_id}` | Delete one version: rows (cascade), file and vectors; the newest remaining version becomes current | 204 |

`/api/resumes/stats` example:
```json
{"total": 15, "by_status": {"queued": 0, "parsing": 0, "parsed": 0, "extracting": 0,
 "extracted": 0, "embedding": 0, "ready": 14, "failed": 1}, "worker_running": true, "vector_count": 60}
```

### 2.4 Search

| Method & path | Purpose | Body |
|---|---|---|
| `POST /api/search/semantic` | Find employees by **meaning** | `{"query": "container orchestration", "top_k": 10}` |

Response (abridged):
```json
{"query": "container orchestration",
 "results": [{"rank": 1, "employee_code": "EMP-1003", "full_name": "Priya Nair", "designation": "Senior DevOps Engineer",
              "location": "Pune", "availability_status": "available", "allocation_percent": 0, "score": 0.578,
              "matched_chunks": [{"section": "experience", "similarity": 0.578, "text": "Employee EMP-1003 | Experience | ..."}]}],
 "timings": {"embed_ms": 48, "vector_search_ms": 4, "total_ms": 62, "chunks_considered": 60}}
```

### 2.5 Projects, roles and matching (Step 7)

| Method & path | Purpose | Body / notes |
|---|---|---|
| `POST /api/projects` | Create a project | `{"name": "Retail Platform Migration", "client_name": "Northwind", "status": "planned", "start_date": "2026-11-15"}` → 201 |
| `GET /api/projects` | List projects with their roles (and parsed requirements) | — |
| `GET /api/projects/{project_id}` | One project with its roles (Step 12b) | 404 unknown project |
| `POST /api/projects/{project_id}/roles` | Add a role (a position to fill) | `{"title", "description" (≥ 20 chars), "location", "allocation_percent" (1–100, default 100), "start_date", "headcount", "min_experience_years"}` → 201; 404 unknown project |
| `GET /api/roles/{role_id}` | One role with its requirements | 404 unknown role |
| `PATCH /api/roles/{role_id}` | Change a role's details or status (Step 12b) | any subset of `title`, `description`, `location`, `allocation_percent`, `start_date`, `headcount`, `min_experience_years`, `status` (`open`/`filled`/`closed`); changing the description does **not** re-parse |
| `POST /api/roles/{role_id}/requirements/parse` | The LLM reads the description → structured requirements (stored on the role) | no body; ~30–60 s on a CPU; 502 unusable LLM output; 503 Ollama down |
| `PUT /api/roles/{role_id}/requirements` | A person corrects the requirements | the requirements JSON (below); names are normalised ("k8s" → Kubernetes); sets `edited_by_user: true`, keeps `parsed_by` |
| `POST /api/roles/{role_id}/candidates` | **Hybrid retrieval**: skills + keyword + vector, fused with RRF | `{"top_k": 15, "only_available": false, "signals": ["skills", "keyword", "vector"]}`; 409 if not parsed |

Requirements JSON:
```json
{"title": "DevOps / Platform Engineer (Kubernetes)", "seniority": "senior",
 "must_have": [{"name": "Kubernetes", "min_years": 3, "as_written": "hands-on Kubernetes in production"}],
 "nice_to_have": [{"name": "Helm", "min_years": null}],
 "min_total_years": 5, "location": null, "domain": ["retail"],
 "search_summary": "Platform engineer migrating services to Kubernetes on AWS ...",
 "parsed_by": "qwen2.5:7b", "parsed_at": "2026-10-28T05:32:55+00:00", "edited_by_user": false}
```
`seniority`: junior · mid · senior · lead · principal · unspecified.

Candidates response (abridged): `role_id`, `role_title`, `requirements` (exactly as the search used them: normalised, and with invented years/domains removed unless a person edited them), `timings` (`eligible`, `skills_ms`, `keyword_ms`, `vector_ms`, `total_ms`, `found_by` per signal) and `candidates[]` with `rank`, employee fields, `fused_score`, `ranks` (rank per signal, `null` = not found by it), `skill_score`, `must_matched[]` / `nice_matched[]` (`required`, `matched_with`, `direct`, `years`, `last_used_year`, `credit`, `evidence`, `weight` = rarity of that skill), `must_missing[]`, `keyword_snippets[]`, `vector_chunks[]`, `availability` (`status`, `allocation_percent`, `free_percent`, `available_from`, `fits`, `note`). See document 04 stage ⑩ for a full example.

**Tip:** `"signals": ["vector"]` runs one signal alone; that's how `evaluate_retrieval` compares them.

### 2.6 Match runs: scoring and the LLM judge (Step 8)

| Method & path | Purpose | Body / notes |
|---|---|---|
| `POST /api/roles/{role_id}/match` | Start a run: retrieve + rule-score now, LLM-judge the top N in the background | `{"top_k": 10, "judge_top_n": 5, "only_available": false}` (`top_k` 1–50, `judge_top_n` 0–20; 0 = no judge) → **202** with the run; 404 role · 409 not parsed · 503 Ollama down |
| `GET /api/match-runs/{run_id}` | The run and its ranked results; poll while `status` is `running` | `judged` / `to_judge` show progress. Typed since Step 12b: `score_breakdown` (`ScoreBreakdown`), `explanation` (`facts`, `judge` = `JudgeVerdictOut`, `judge_status` = pending/done/failed/not_requested, `judge_error`), `settings` (`MatchRunSettings`) |
| `GET /api/roles/{role_id}/match-runs` | History of runs for a role (newest first) | each: `top` (codes of the top 3), `top_names`, `judge_top_n`, `result_count` |

Run fields: `status` (running / completed / failed), `error_message`, `settings` (top_k, judge_top_n, weights, judge_weight, judge_model, embed_model, rrf_k, the requirements used, retrieval timings), `results[]`.

Each result: `rank`, employee fields, `final_score`, `score_breakdown` (`skills`, `relevance`, `experience`, `availability`, `location`, `fit`, `factors`, `rule_score`, `total_years`, `required_years`, `retrieval_ranks`, and after judging `judge_score`, `final_score`), `explanation`:
```json
{"facts": {"must_matched": [...], "must_missing": [...], "nice_matched": [...], "keyword_snippets": [...], "availability": {...}},
 "judge_status": "pending | done | failed | not_requested",
 "judge": {"rating": "strong", "summary": "...",
           "must_haves": [{"requirement": "Kubernetes", "met": "yes", "claimed": "yes", "quote": "Operate 14 EKS clusters (k8s 1.2x) hosting 300+ microservices.", "verified": true}],
           "strengths": [{"point": "...", "quote": "...", "verified": true}], "gaps": ["..."],
           "judge_score": 0.875, "quotes_verified": 5, "quotes_total": 6,
           "stats": {"model": "qwen2.5:7b", "seconds": 84.2, "prompt_tokens": 1820, "output_tokens": 310}}}
```
(The judge example values are illustrative.)

### 2.7 The agent (Step 10, signed-in users; each sees only their own conversations)

| Method & path | Purpose | Body / notes |
|---|---|---|
| `POST /api/agent/conversations` | Start a conversation | `{"title": null}` → 201 |
| `GET /api/agent/conversations` | My conversations, newest first | — |
| `GET /api/agent/conversations/{id}` | One conversation with every message (user, assistant, tool calls, tool results) in order | 404 if not yours. Tool messages include `summary` (the same one-line result the live stream showed; Step 13) |
| `DELETE /api/agent/conversations/{id}` | Delete it | 204 |
| `POST /api/agent/conversations/{id}/messages` | Ask the agent | `{"content": "...", "stream": true}` → Server-Sent Events; `"stream": false` → `{"answer", "events"}` |

Stream events (`data: {...}` lines): `tool_call` (name, arguments), `tool_result` (name, ok, summary), `token` (text), `answer` (text, steps, tool_calls, seconds, done_reason, message_id), `error` (message).

**Portal relay (Step 13, Next.js, not FastAPI):** `POST /bff/agent/{id}` with `{"content": "..."}` (1–4,000 characters). It adds the token from the session cookie, calls the streaming endpoint above and passes the events through unbuffered (`Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`). Errors are JSON `{"detail"}`: 401 no session, 404 unknown id, 422 empty or too long, 502 backend unreachable, others passed through from FastAPI. The browser's Stop cancels the upstream request.

Tools the agent can use (read-only): `find_candidates`, `search_employees`, `get_employee_profile`, `check_employee_availability`, `list_projects`, `get_match_results`.

### 2.7b Feedback (Step 14c)

| Method & path | Purpose | Body / notes |
|---|---|---|
| `PUT /api/match-results/{id}/feedback` | Rate one candidate of a match run (any signed-in user) | `{"rating": "up"\|"down", "reason": null\|"missing_skill"\|"too_little_experience"\|"not_available"\|"profile_wrong"\|"should_rank_higher"\|"should_rank_lower"\|"other", "comment": "..." (≤1,000)}`. Rating again replaces your rating |
| `DELETE /api/match-results/{id}/feedback` | Take your rating back | 204 |
| `PUT /api/agent/messages/{id}/feedback` | Rate one answer of **your** conversation | Same body; reasons `wrong_people`, `missed_someone`, `wrong_numbers`, `misunderstood`, `too_long`, `other`. 404 for someone else's message, 409 for a tool message |
| `DELETE /api/agent/messages/{id}/feedback` | Take it back | 204 |
| `GET /api/feedback?target=&rating=&limit=&offset=` | **Admins.** Counts plus every rating with its context (employee, role, run, or question and answer), newest first | 403 for others |

Match runs now include, per result, `result_id`, `my_feedback` (your rating), `feedback_up` and `feedback_down` (everyone's). Conversation messages include `feedback` (your rating). The stream's `answer` event includes `message_id`.

### 2.8 Development-only (disabled when `ENVIRONMENT=production`)

| Method & path | Purpose | Body / params |
|---|---|---|
| `POST /api/dev/chat` | Talk to the fast or quality model; see speed stats | `{"prompt": "...", "model": "fast", "temperature": 0, "system": null}` |
| `POST /api/dev/similarity` | Cosine similarity of two texts | `{"text_a": "...", "text_b": "...", "use_prefixes": true}` |
| `POST /api/dev/extract/{resume_id}` | Run LLM extraction on one resume **without saving**; shows raw LLM output and the processed profile | `model=fast` or `quality` |

---

## 3. Scripts (run from `backend/` with the venv active)

| Command | What it does | Server needed? |
|---|---|---|
| `python -m app.worker [--concurrency N]` | **Step 15:** a background worker on its own: resume processing and the LLM judge from the queue. Run any number (with `WORKER_ENABLED=false` on the API). Ctrl+C / SIGTERM: running jobs finish or are handed back. `--healthcheck`: exit 0 if this host's worker is alive (containers) | No (the database yes) |
| `alembic upgrade head` / `alembic current` / `alembic history` | **Step 15:** apply / show database schema migrations (`migrations/`). The app does `upgrade head` at startup unless `DB_AUTO_MIGRATE=false`. `alembic upgrade head --sql` prints the SQL for review. New migration: `alembic revision --autogenerate -m "..."`, then review it | No |
| `python -m scripts.migrate_to_postgres --target postgresql+asyncpg://...` | **Step 15:** copies every table (same ids) and every ChromaDB vector into an EMPTY PostgreSQL database with pgvector, then compares the counts. Nothing is re-embedded. Then set `DATABASE_URL` to the target | No |
| `python -m scripts.migrate_files --from-local ./data/uploads [--dry-run]` | **Step 15:** copies resume files into the storage backend in `.env` (`STORAGE_BACKEND`), checking each file's fingerprint before and after; updates the database row only after the copy is confirmed; never deletes local files | No |
| `python -m scripts.migrate_files --check` | **Step 15:** lists resumes whose file is missing from the configured storage | No |
| `python -m pytest` | **Step 15:** the automated tests (53), on SQLite, or on PostgreSQL with `TEST_DATABASE_URL` (`tests/README.md`). They never read `backend/.env` | No |
| `python -m scripts.evaluate_real_resumes [--offline] [--only R1 R4] [--show]` | Checks extraction against the 9 real resumes in `samples/real/` and `evaluation/real_resumes.json` (doc 18). `--offline`: the code alone with correct model answers; without it: the real model (stop the server first). Exit code 1 if any check fails |
| `python -m scripts.evaluate_all [--skip ...] [--only ...] [--with-model-extraction] [--note "..."]` | **Step 14:** runs every evaluation (extraction, retrieval on real and sample data, matching, agent) and writes `evaluation/reports/all-<time>.json` and `.md`. Flags any number lower than in the last report that ran that suite. Asks for a portal login for the sample suites (or uses `RTM_EMAIL`/`RTM_PASSWORD`). Exit code 1 on a failure or regression | For the sample suites (skipped without it); Ollama for the rest |
| `python -m scripts.export_feedback` | **Step 14c:** turns the portal's 👍/👎 into `evaluation/reports/feedback-labels-<time>.json` (per role: good / not good / disputed people) and `agent-cases-from-feedback-<time>.json` (draft agent test cases from 👎 answers) | No |
| `python -m scripts.evaluate_agent [--only A01 A04] [--show] [--email ...]` | **Step 14:** asks the 14 questions of `evaluation/agent_cases.json` through the real agent loop and checks tool choice, arguments, people named, order, invented codes or years, contact details and refusals. Writes `reports/agent-<time>.json` | No (Ollama yes) |
| `python -m scripts.load_real_resumes [--wait]` | Puts the 9 real resumes of `samples/real/` into the database, each on its own test employee (EMP-1018 to EMP-1025; R1 stays on Ajay, EMP-1017). It uses the same checks as a portal upload. Files already uploaded (same bytes) are skipped, so it is safe to run again. A code already used by someone else is never reused. `--wait` shows the worker's progress until every file is ready or failed | **Yes**, for processing (the worker runs inside the server) |
| `python -m scripts.evaluate_real_retrieval [--compare-rerank]` | 7 role queries on the real resumes: hit@3, R@5 and MRR for hybrid and for each signal alone. Run `load_real_resumes` first. Needs Ollama, but not the server. Exit code 0 only if hybrid hits every query | No (Ollama yes) |
| `python -m scripts.create_user --role admin --email ... --name ...` | Create a portal user directly in the database (first admin); password asked twice | No |
| `python -m scripts.create_user --secret` | Print a random `JWT_SECRET=` line for `.env` | No |
| `python -m scripts.inspect_db` | Prints every table, column, foreign key and row count | No |
| `python -m scripts.seed_demo` | Inserts 2 demo employees (`DEMO-…`) and runs example SQL queries | No |
| `python -m scripts.seed_demo --clean` | Deletes the demo employees and shows the cascade deletes | No |
| `python -m scripts.upload_samples` | Imports `samples/employees.csv`, bulk-uploads `samples/resumes/`, waits for the worker, prints a summary | **Yes** |
| `python -m scripts.compare_extraction` | Runs fast vs quality model extraction on 5 tricky resumes with correctness checks (nothing saved) | No (stop it, so the CPU isn't shared) |
| `python -m scripts.compare_extraction --models fast --codes EMP-1003 EMP-1015` | Same, for chosen models and employees | No |
| `python -m scripts.try_search` | Runs 7 meaning-based demo queries with the expected person for each | **Yes** |
| `python -m scripts.try_search "people who mentored a team"` | Your own query | **Yes** |
| `python -m scripts.load_roles` | Creates the 3 sample projects/roles from `samples/roles.json` and parses their requirements with the LLM (idempotent; `--reparse` to redo) | **Yes** |
| `python -m scripts.try_agent` | Chat with the agent in the terminal; shows tool calls, results and the streamed answer (`--demo` = 3 example questions) | **Yes** |
| `python -m scripts.evaluate_matching` | Starts a match run per sample role, waits for the judge, prints nDCG@5, MRR, pair order and a score table (`--judge-top-n 0` = rule score only, seconds) | **Yes** |
| `python -m scripts.evaluate_retrieval` | Per role: recall@5, recall@10, MRR and the ranks of the expected people, for hybrid and each signal alone | **Yes** |

---

## 4. Configuration (`backend/.env`)

All settings have defaults in `app/config.py`; `.env` overrides them. Restart the server after changing `.env`.

### App
| Setting | Default | Meaning |
|---|---|---|
| `APP_NAME` | RAG Talent Matcher | Shown in `/docs` and logs |
| `ENVIRONMENT` | development | `production` disables `/api/dev/*` |
| `LOG_LEVEL` | INFO | `DEBUG` shows more detail |

### Ollama and models
| Setting | Default | Meaning |
|---|---|---|
| `OLLAMA_BASE_URL` | http://localhost:11434 | Where Ollama listens |
| `OLLAMA_TIMEOUT_SECONDS` | 300 | Maximum wait for one Ollama answer |
| `EMBED_MODEL` | nomic-embed-text | Embedding model (any Ollama embedding model; doc 20) |
| `FAST_LLM_MODEL` | qwen2.5:3b | Small, fast model (e.g. `qwen3.5:4b`, Apache 2.0) |
| `QUALITY_LLM_MODEL` | qwen2.5:7b | Larger, more accurate model (e.g. `qwen3.5:9b`) |
| `LLM_NUM_CTX` | 8192 | Context window in tokens (sent with every request) |
| `LLM_THINK` | off | `off` / `on` / `default`: step-by-step "thinking" of reasoning models (off = fast on a CPU) |
| `EMBED_QUERY_TEMPLATE`, `EMBED_DOCUMENT_TEMPLATE` | empty | Only for an embedding model `app/llm/models.py` doesn't know: its query / document prompt with `{text}` |
| `AUTO_REEMBED_ON_MODEL_CHANGE` | true | After `EMBED_MODEL` changes, re-embed resumes made with the old model at the next start |
| `EMBED_DIMENSIONS` | empty | Shorter vectors for API embeddings that support it (OpenAI -3, Voyage, Cohere, Gemini), e.g. 1024 |

**Cloud and other providers** (doc 20 §5). A model setting `<provider>/<model>` uses them, e.g. `anthropic/claude-sonnet-4-5`, `openai/text-embedding-3-large`. An empty value means "not used / default".

| Setting | Default | Meaning |
|---|---|---|
| `ALLOW_CLOUD_MODELS` | false | Models outside this PC/network are refused until true (resumes are personal data) |
| `CLOUD_TIMEOUT_SECONDS` | 120 | Maximum wait for one cloud answer |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | empty | `openai/` models |
| `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION` | –, –, 2024-10-21 | `azure/<deployment>` models |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MAX_TOKENS` | –, –, 4096 | `anthropic/` models (Claude needs an output limit) |
| `GEMINI_API_KEY` (`GEMINI_OPENAI_BASE_URL`, `GEMINI_NATIVE_BASE_URL`) | empty | `gemini/` chat (OpenAI-compatible endpoint) and embeddings (native API with task types) |
| `COMPAT_BASE_URL`, `COMPAT_API_KEY` | empty | `compat/` models: any OpenAI-compatible server or gateway |
| `VOYAGE_API_KEY` (`VOYAGE_BASE_URL`), `COHERE_API_KEY` (`COHERE_BASE_URL`) | empty | `voyage/` and `cohere/` embeddings |
| `AWS_REGION`, `AWS_PROFILE`, `BEDROCK_ENDPOINT_URL`, `BEDROCK_MAX_TOKENS` | –, –, –, 4096 | **Step 15:** `bedrock/<model id>` chat and embeddings. Credentials from boto3's chain (IAM role on AWS, `AWS_PROFILE` on a laptop); a VPC endpoint; the answer limit when a task sets none |
| `VERTEX_PROJECT`, `VERTEX_LOCATION`, `VERTEX_CLAUDE_LOCATION`, `VERTEX_BASE_URL` | –, us-central1, –, – | **Step 15:** `vertex/<model>` (Gemini and partner models, `vertex/claude-…`, Vertex embeddings). Credentials: Application Default Credentials; project empty = `GOOGLE_CLOUD_PROJECT` / the credentials' |

Install the SDKs once if you use cloud models, cloud storage or a cloud queue: `pip install -r requirements-cloud.txt`.

### Database
| Setting | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | sqlite+aiosqlite:///./data/app.db | Or `postgresql+asyncpg://user:password@host:5432/db` (PostgreSQL 16 with pgvector; doc 21) |
| `DB_ECHO` | false | `true` prints every SQL statement |
| `DB_AUTO_MIGRATE` | true | Apply migrations at startup. `false` (production with several replicas): run `alembic upgrade head` per release; the app refuses to start on an old schema |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 10 / 20 | PostgreSQL: connections kept open per process / extra under load |
| `DB_POOL_TIMEOUT_SECONDS` | 30 | PostgreSQL: wait for a free connection, then fail |
| `DB_STATEMENT_TIMEOUT_MS` | 0 | PostgreSQL: cancel queries running longer (0 = no limit) |

### Uploads and file storage (Step 15c)
| Setting | Default | Meaning |
|---|---|---|
| `STORAGE_BACKEND` | local | `local` (a folder) · `s3` · `gcs` · `azure` |
| `UPLOAD_DIR` | ./data/uploads | `local`: where resume files are stored |
| `STORAGE_PREFIX` | resumes/ | Cloud: the folder inside the bucket / container |
| `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT_URL`, `S3_KMS_KEY_ID` | — | `s3`: the bucket; region (empty = `AWS_REGION`); an S3-compatible store (MinIO, R2); your KMS key (else SSE-S3) |
| `GCS_BUCKET`, `GCS_KMS_KEY_NAME` | — | `gcs`: the bucket; your Cloud KMS key (CMEK) |
| `AZURE_STORAGE_CONTAINER`, `AZURE_STORAGE_ACCOUNT_URL`, `AZURE_STORAGE_CONNECTION_STRING` | — | `azure`: the container; the account URL (managed identity) or a connection string (development) |
| `MAX_UPLOAD_MB` | 25 | Per file (Word files with embedded fonts reach 12+ MB). Accepted: PDF, DOCX, DOC |
| `MAX_FILES_PER_BATCH` | 200 | Per bulk upload |
| `MIN_CHARS_PER_PAGE` | 100 | Below this, a PDF page counts as a scanned image |

### Background jobs and workers (Step 15d)
| Setting | Default | Meaning |
|---|---|---|
| `QUEUE_BACKEND` | local | `local` (the database is the queue) · `sqs` · `pubsub` · `servicebus` |
| `WORKER_ENABLED` | true | A worker inside the API process. `false`: run `python -m app.worker` separately (containers) |
| `WORKER_CONCURRENCY` | 1 | Jobs one worker runs at once (an LLM on a CPU: 1) |
| `WORKER_POLL_SECONDS` | 5 | How long an idle worker waits for a job before looking again |
| `WORKER_MAX_ATTEMPTS` | 3 | Retries for unexpected errors and for workers that die mid-job |
| `WORKER_LEASE_SECONDS` | 300 | A job's claim, renewed while it runs; a dead worker's job returns after this |
| `WORKER_SWEEP_SECONDS` | 60 | How often workers recover jobs whose worker died |
| `WORKER_REDISPATCH_SECONDS` | 900 | Message broker: re-send jobs waiting this long (lost messages) |
| `WORKER_SHUTDOWN_SECONDS` | 30 | On stop, running jobs get this long, then go back to the queue |
| `OLLAMA_RETRY_SECONDS` | 30 | When the model service is down, the job is retried after this (attempt not counted) |
| `SQS_QUEUE_URL`, `SQS_REGION` | — | `sqs`: the queue URL; region (empty = `AWS_REGION`) |
| `PUBSUB_TOPIC`, `PUBSUB_SUBSCRIPTION`, `PUBSUB_PROJECT` | — | `pubsub`: topic and pull subscription (short or full names); project (empty = `GOOGLE_CLOUD_PROJECT`) |
| `SERVICEBUS_QUEUE`, `SERVICEBUS_NAMESPACE`, `SERVICEBUS_CONNECTION_STRING` | — | `servicebus`: the queue; namespace (managed identity) or a connection string |

### Extraction
| Setting | Default | Meaning |
|---|---|---|
| `EXTRACTION_MODEL_ROLE` | quality (our `.env`: **fast** since Step 7) | `fast`, `quality` or any Ollama model name: which model reads resumes |
| `EXTRACTION_MAX_OUTPUT_TOKENS` | 2048 | Cap on the JSON answer |
| `EXTRACTION_MAX_INPUT_CHARS` | 16000 | Characters per model call; longer resumes are read in parts (Step 13b) |

### Chunking, embeddings and vector store
| Setting | Default | Meaning |
|---|---|---|
| `VECTOR_STORE` | auto | `auto` = pgvector with PostgreSQL, ChromaDB with SQLite · `chroma` · `pgvector` (Step 15) |
| `CHROMA_DIR` | ./data/chroma | ChromaDB files |
| `CHROMA_COLLECTION` | resume_chunks | Collection name |
| `CHUNK_MAX_CHARS` | 1200 | ~300 tokens per chunk |
| `CHUNK_OVERLAP_CHARS` | 150 | Repeated text between neighbouring chunks |
| `EMBED_BATCH_SIZE` | 16 | Chunks per embedding call |
| `ANONYMIZE_CHUNKS` | true | Replace name, email, phone in indexed text |

### Role parsing and hybrid retrieval (Step 7)
| Setting | Default | Meaning |
|---|---|---|
| `ROLE_PARSE_MODEL_ROLE` | quality | `fast`, `quality` or a model name: reads role descriptions (once per role, so quality is affordable) |
| `RETRIEVAL_VECTOR_POOL` | 80 | Nearest chunks fetched from ChromaDB per search |
| `RETRIEVAL_KEYWORD_POOL` | 200 | Best BM25 chunks fetched from the keyword index |
| `RRF_K` | 60 | Reciprocal Rank Fusion constant; larger = flatter (rank differences matter less) |
| `RRF_WEIGHT_SKILLS` / `_KEYWORD` / `_VECTOR` | 1.0 | How much each signal counts in the fusion |
| `DEFAULT_SKILL_MIN_YEARS` | 2.0 | Years treated as "enough" for a required skill when the role gives none |

### Scoring and the LLM judge (Step 8)
| Setting | Default | Meaning |
|---|---|---|
| `SCORE_SKILLS_SHARE` | 0.85 | fit = share × skill score + (1 − share) × retrieval relevance |
| `SCORE_EXPERIENCE_FLOOR` | 0.6 | Experience factor ranges from this to 1.0 (not enough years lowers the score by up to 40%) |
| `SCORE_AVAILABILITY_FLOOR` | 0.7 | Availability factor ranges from this to 1.0 |
| `SCORE_LOCATION_FLOOR` | 0.9 | Location factor ranges from this to 1.0 |
| `JUDGE_MODEL_ROLE` | quality | `fast`, `quality` or a model name: which LLM judges |
| `JUDGE_TOP_N` | 5 | Default number of candidates judged per run |
| `JUDGE_WEIGHT` | 0.4 | final = (1 − w) × rule score + w × judge score |
| `JUDGE_MAX_OUTPUT_TOKENS` | 1024 | Cap on the judge's JSON answer |
| `JUDGE_MAX_DOSSIER_CHARS` | 6000 | Resume evidence per candidate (~1,500 tokens) |

### Agent (Step 10)
| Setting | Default | Meaning |
|---|---|---|
| `AGENT_MODEL_ROLE` | quality | `fast`, `quality` or a model name: which LLM runs the agent |
| `AGENT_MAX_STEPS` | 4 | Tool rounds per question; the round after that has no tools, so it must answer |
| `AGENT_TEMPERATURE` | 0 | Randomness of tool choices and wording |
| `AGENT_MAX_OUTPUT_TOKENS` | 1024 | Cap on one LLM reply |
| `AGENT_HISTORY_MESSAGES` | 10 | Earlier questions/answers sent as memory |
| `AGENT_TOOL_RESULT_CHARS` | 6000 | Tool results longer than this are cut |

### Authentication (Step 9)
| Setting | Default | Meaning |
|---|---|---|
| `JWT_SECRET` | (none) | Signs login tokens. **Required in production**; in development a random one is generated at startup (everyone is logged out on restart) |
| `ACCESS_TOKEN_MINUTES` | 480 | How long a login lasts |
| `AUTH_COOKIE_NAME` | rtm_access | Name of the HttpOnly login cookie |

Scripts that call the API log in with `RTM_EMAIL` / `RTM_PASSWORD` environment variables, or ask.

### Frontend-related (in `backend/.env`)
| Setting | Default | Meaning |
|---|---|---|
| `CORS_ORIGINS` | ["http://localhost:3000"] | Browser origins allowed to call the API directly. The portal's pages call FastAPI server-to-server and its browser calls go through the same-origin `/api` rewrite, so CORS matters only for other clients |
| `AUTH_COOKIE_NAME` | rtm_access | Must equal `SESSION_COOKIE` in `frontend/src/lib/auth/constants.ts` |

### The portal (`frontend/.env.local`, optional; validated at startup by `src/lib/env/schema.ts`)
| Setting | Default | Meaning |
|---|---|---|
| `BACKEND_URL` | http://127.0.0.1:8010 | Where FastAPI runs; must start with `http://` or `https://`. Read by the Next.js server only. Also compiled into the `/api` rewrite at **build** time (the rewrite now only carries resume uploads; the agent stream uses the `/bff` relay, which reads it at run time) |
| `HTTPS` | false | `true` when the portal is served over HTTPS: `Secure` cookie, HSTS, `upgrade-insecure-requests`. Keep `false` on `http://localhost` |
| `EXPOSE_TESTING_API` | (unset) | `1` only for test builds: enables Next.js's instant-navigation testing API (set automatically by `npm run test:e2e`) |
| `E2E_EMAIL`, `E2E_PASSWORD` | (unset) | The portal user the Playwright tests log in as; tests that need it are skipped without it |

### Portal scripts (`frontend/`, `npm run <name>`)
| Script | What it does |
|---|---|
| `dev` | Development server on port 3000 with instant reload |
| `build` / `start` | Production build (shows ○ static / ◐ partial prerender / ƒ dynamic per route) / serve it on port 3000 |
| `check` | `typecheck` + `lint` + `format:check` + `test`: run before every commit |
| `typecheck` | `next typegen` (route types such as `PageProps<"/login">`) then `tsc --noEmit` |
| `lint` | ESLint with the Next.js, React Hooks and React Compiler rules |
| `format` / `format:check` | Prettier (also sorts Tailwind classes) / check only |
| `test` / `test:watch` | Vitest unit tests once / re-run on save |
| `test:e2e` | Playwright: builds and starts the portal on port 3100 with the testing API, then runs `e2e/*.spec.ts` |
| `api:types` | Regenerates `src/lib/api/schema.d.ts` from `BACKEND_URL/openapi.json` (backend must be running) |

---

## 5. Everyday commands

| Task | Command |
|---|---|
| Activate the venv | `.\.venv\Scripts\Activate.ps1` |
| Start the server (development) | `uvicorn app.main:app --reload --port 8010` |
| Start the server (long AI jobs) | `uvicorn app.main:app --port 8010` (no `--reload`) |
| Check imports | `python -c "import app.main"` |
| Install / update libraries | `pip install -r requirements.txt` then `pip freeze > requirements.lock.txt` |
| List Ollama models | `ollama list` |
| Measure model speed | `ollama run qwen2.5:3b --verbose "hello"` |
| Portal: install / run | `cd frontend` → `npm install` → `npm run dev` (http://localhost:3000) |
| Portal: check code | `npm run check` (types, lint, formatting, unit tests) |
| Portal: after a backend API change | backend running → `npm run api:types` → `npm run typecheck` |
| Portal: browser tests | once: `npx playwright install chromium`; then `$env:E2E_EMAIL="..."; $env:E2E_PASSWORD="..."; npm run test:e2e` |
| Save progress | `git add .` then `git commit -m "message"` |
