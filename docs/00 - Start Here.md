# 00 · Start Here: RAG Talent Matcher Learning Guide

This is the entry point to the documentation for the **RAG Learning Project**: a system that finds the best-matching **current employees** for **internal project roles**, using their resumes, a local AI (Ollama) and Retrieval-Augmented Generation (RAG). Everything runs on one Windows PC with no GPU, and resumes never leave the machine.

---

## 1. What the system does, in one picture

```
                    ┌──────────────────────── ADMIN ────────────────────────┐
                    │  uploads employees.csv (HR data) + resume files       │
                    └───────────────────────────┬───────────────────────────┘
                                                ▼
   ┌───────────────────────────── INGESTION (background, once per resume) ─────────────────────────────┐
   │  check & store ─▶ extract text ─▶ AI reads resume ─▶ code checks facts ─▶ chunks ─▶ vectors ─▶ READY │
   └──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                ▼
                       Knowledge base: SQLite (facts, text) + ChromaDB (meaning vectors)
                                                ▲
   ┌──────────────────────────────── MATCHING (per project role) ────────────────────────────────────┐
   │  role description ─▶ requirements ─▶ filters + keyword + meaning search ─▶ fusion ─▶ AI judge ─▶  │
   │                                                     ranked employees with evidence quotes         │
   └──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                ▲
                    ┌──────────────────── RESOURCE MANAGER ─────────────────────┐
                    │  "Who should join the Retail migration as DevOps lead?"   │
                    └────────────────────────────────────────────────────────────┘
```

---

## 2. The documents and when to read them

| # | Document | Read it when you want to… |
|---|---|---|
| 00 | **Start Here** (this file) | Get oriented, see progress, find the right document |
| 01 | **System Architecture** | Understand the big picture: components, layers, data model, folders |
| 02 | **Python Guide** | Understand any Python syntax you see in the code |
| 03 | **AI & RAG Concepts** | Understand any AI word: what it is, how it works, where we use it |
| 04 | **Pipeline Deep Dive** | Follow one resume through every stage, with real example data |
| 05 | **API, Scripts & Configuration Reference** | Look up an endpoint, a script or a `.env` setting |
| 06 | **Technology Choices & Enterprise Stack** | Know why each tool was chosen and what enterprises use instead |
| 07 | **Build Journal & Findings** | See what happened at each step, the numbers measured, and the lessons |
| 08 | **Troubleshooting** | Fix an error (every problem hit so far, with cause and fix) |
| 09 | **Step 5 Explained** (structured extraction with the LLM) | Understand Step 5 fully: why, flow, AI ideas, every file, alternatives and enterprise options |
| 10 | **Step 6 Explained** (chunking, embeddings, semantic search) | The same for Step 6 |
| 11 | **Step 7 Explained** (hybrid retrieval) | The same for Step 7 |
| 12 | **Step 8 Explained** (scoring and the LLM judge) | The same for Step 8 |
| 13 | **Step 9 Explained** (authentication and roles) | The same for Step 9 |
| 14 | **Step 10 Explained** (the staffing agent) | What an agent is, agentic AI fundamentals, and our agent |
| 16 | **Step 12 Explained** (the admin portal pages) | Page patterns (URL state, Server Actions, uploads, confirmations), every file, findings; 12a Employees and Resumes, 12b Projects and matching, 12c Users and Account |
| 15 | **Step 11 Explained** (the Next.js frontend) | Next.js 16 fundamentals (server/client components, streaming, Server Actions), the portal's architecture, security and tests, v1 vs v2 |
| 18 | **Real Resume Corpus Notes** | Everything in the 9 real resumes, how real resumes differ from our samples, and what the pipeline does wrong with each (the extraction fix and test set start here) |
| 17 | **Step 13 Explained** (the agent chat page) | Streaming an AI answer to the browser (SSE, the `/bff` relay, why the rewrite buffered), live tool steps, stop, stored conversations |
| 19 | **Step 14 Explained** (evaluation and feedback) | Measuring every layer (extraction, retrieval, matching, agent), automatic agent checks, one-command reports with regression flags, 👍/👎 feedback turned into test data |
| 20 | **Changing Models** | Swap any model from `.env`, local (Ollama) or cloud (Claude, GPT, Gemini, Azure, Bedrock, Vertex AI, Voyage, Cohere, any OpenAI-compatible server): the routine, what differs between models and providers, data protection, which models suit this project |
| 21 | **Step 15 Explained** (production deployment on any cloud) | PostgreSQL + pgvector + migrations, file storage (S3, Cloud Storage, Azure Blob), background jobs through queues (SQS, Pub/Sub, Service Bus) and separate workers, Docker, and deployment recipes for AWS, Google Cloud, Azure and your own server |

**Suggested reading order for a beginner:** 00 → 01 → 03 (sections 1–4) → 04 → 09 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 19 → 20 → 21 → 02 as needed → 07.

Documents 09–17, 19 and 21 are **step explainers**: one per step, each answering the same questions (why the step exists, what the user sees, the flow in order, the AI ideas, every file, Python used, alternatives from hobby to enterprise, limitations, how to try it).

---

## 3. Build roadmap and progress

| Step | What it builds | Status |
|---|---|---|
| 1 | Environment: Python, Node, Git, Ollama, models | ✅ Done |
| 2 | FastAPI backend skeleton, Ollama client, health check | ✅ Done |
| 3 | Database: 12 tables (SQLAlchemy + SQLite); 14 + a search index by Step 10 | ✅ Done |
| 4 | Resume intake: CSV import, uploads, text extraction, background worker | ✅ Done |
| 5 | Structured extraction with the LLM (+ 5b job-level grounding) | ✅ Done (5b real-model rerun pending) |
| 6 | Chunking, embeddings, ChromaDB, semantic search | ✅ Done |
| 7 | Hybrid retrieval: role parsing, skills + BM25 + vector search, RRF fusion, availability | ✅ Done (hybrid recall@5 = 1.00 on real models) |
| 8 | Scoring and LLM judge with verified citations, saved match runs | ✅ Done (Django re-run pending) |
| 9 | Authentication and roles: Argon2id passwords, JWT + HttpOnly cookie, admin / resource manager, audit columns | ✅ Done |
| 10 | The agent: tool calling (ReAct loop), 6 read-only tools, conversation memory, streaming (SSE) | ✅ Code done (real-model run pending) |
| 11 | Next.js frontend foundation (11b: server-rendered + streamed pages, Server Actions login, generated API types, accessible components, security headers, 53 automated tests) | ✅ Done (11b verification on the PC pending) |
| 12 | Admin portal pages: 12a Employees + Resumes, 12b Projects & matching, 12c Users + Account | ✅ Done (12c tests deferred) |
| 13 | Agent chat page: live tool steps, streamed answers via a `/bff` relay, stop, stored conversations | ✅ Done (tests and real-model run pending) |
| 13b | Extraction rebuilt for real resumes: .doc, sections, projects, code-based skills, undated experience | ✅ Code done, 107/107 offline (real-model run pending) |
| 14 | Evaluation and tuning: 14a agent evaluation (14 cases, 21 kinds of automatic checks), 14b `evaluate_all` with saved reports and regression flags, 14c 👍/👎 feedback on matches and answers + Feedback page + export to test data; 14d tuning next | 🔄 14a–14c done (first real baseline pending on the PC) |
| 15 | Production deployment on any cloud: 15a Bedrock + Vertex AI models, 15b PostgreSQL + pgvector + Alembic migrations, 15c file storage (local / S3 / Cloud Storage / Azure Blob), 15d background jobs through a queue (local / SQS / Pub/Sub / Service Bus) with separate, scalable workers, 15e Docker images + compose; 53 automated tests, run on SQLite and on PostgreSQL | ✅ 15a–15e done (doc 21) · next: SSO, observability, infrastructure as code, CI/CD |

---

## 4. Key facts at a glance

| Item | Value |
|---|---|
| Backend | Python 3.13 · FastAPI · SQLAlchemy 2 (async) · SQLite + ChromaDB, or PostgreSQL + pgvector (Step 15) · Alembic |
| AI (local, via Ollama) | `qwen2.5:3b` (fast), `qwen2.5:7b` (quality), `nomic-embed-text` (embeddings) |
| Hardware | Windows, 16 GB RAM, no NVIDIA GPU (CPU inference) |
| Run the server | `uvicorn app.main:app --port 8010` (from `backend/`, venv active) |
| Run the portal | `npm run dev` (from `frontend/`) → http://localhost:3000 |
| Staffing assistant | http://localhost:3000/agent |
| API docs | http://127.0.0.1:8010/docs (click **Authorize** and log in first) |
| First admin | `python -m scripts.create_user --role admin --email ... --name ...` |
| Health | http://127.0.0.1:8010/api/health (containers: `/api/health/live`, `/api/health/ready`) |
| Tests | `python -m pytest` (from `backend/`; `tests/README.md`) |
| Everything in Docker | `cp .env.docker.example .env`, then `docker compose up -d --build` (doc 21 §5.1) |
| Separate worker | `python -m app.worker` (with `WORKER_ENABLED=false` on the API) |
| Sample data | `samples/` (16 fictional employees, 15 resumes, 3 roles with expected rankings) |
| Find candidates | `POST /api/roles/{id}/candidates` (after `python -m scripts.load_roles`) |
| Measure retrieval | `python -m scripts.evaluate_retrieval` (recall@5, recall@10, MRR per signal) |

---

## 5. Change log

| Date | Change |
|---|---|
| 2026-10-27 | Single reference document created (Python, AI vocabulary, tool choices), then extended with enterprise stack, findings and troubleshooting |
| 2026-10-27 | Split into this 9-document guide, each expanded with more examples, diagrams and flows |
| 2026-11-06 | Cloud and company models through `<provider>/<model>` (router, OpenAI-compatible, Anthropic, Voyage, Cohere, Gemini; `ALLOW_CLOUD_MODELS`); doc 20 §5 |
| 2026-11-11 | Step 15: Bedrock and Vertex AI models; PostgreSQL + pgvector with Alembic migrations; storage and queue adapters for AWS, Google Cloud and Azure; separate workers with leases; Docker images and compose; a pytest suite on both databases; explainer 21; docs 00, 01, 05, 06, 07, 08, 20 updated |
| 2026-11-06 | Any model from `.env`: `app/llm/models.py` (embedding prompts, thinking off, one vector collection per embedding model, automatic re-embedding); doc 20 |
| 2026-11-06 | Step 14c: feedback buttons on match results and agent answers, admin Feedback page, `export_feedback`; docs 05, 07, 16, 17, 19 |
| 2026-11-06 | Step 14a/14b: agent evaluation and one-command evaluation report; explainer 19; find_candidates scores on skills alone without a description |
| 2026-11-06 | Original resume files for admins; agent lists only people with the skill; depth credit for skill years |
| 2026-11-05 | Step 13b: extraction rebuilt for real resumes; docs 07, 09, 18 updated |
| 2026-11-05 | Doc 18: notes on 9 real resumes; audit of EMP-1017; extraction fix (action item 18) blocks Step 14 |
| 2026-10-30 | Step 13: agent chat page with streaming through a Route Handler relay (the `/api` rewrite buffered SSE); stored tool steps get summaries; explainer 17; docs 01, 05, 07, 08, 15 updated |
| 2026-10-30 | Step 12c: Users and Account pages; self-lockout safeguard |
| 2026-10-30 | Step 12b: Projects, roles, requirements editor, match runs with judge verdicts; typed match API |
| 2026-10-30 | Step 12a: Employees and Resumes pages; education-year grounding; explainer 16 |
| 2026-10-30 | Step 11b: frontend rebuilt the Next.js 16 way (server rendering + streaming, Server Actions, generated API types, Radix components, CSP, tests); `/api/overview`; docs 01, 05, 07, 08, 15 updated |
| 2026-10-30 | Step 11: Next.js 16 frontend foundation; explainer 15 |
| 2026-10-29 | Step 10: staffing agent (tools, loop, memory, streaming); explainer 14 |
| 2026-10-29 | Step 9: login, roles, user management, scripts log in; explainer 13; troubleshooting section 6 |
| 2026-10-28 | Step 8: rule score with factors, LLM judge with verified quotes, background match runs; explainer 12 |
| 2026-10-28 | Step explainers added: 09 (Step 5), 10 (Step 6), 11 (Step 7); checked against the code and real data |
| 2026-10-28 | Step 7: matching layer (role parsing, three retrieval signals, RRF, availability), keyword index, new endpoints and scripts, findings |

This guide is updated after every build step and every new finding.
