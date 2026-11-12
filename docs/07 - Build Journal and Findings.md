# 07 · Build Journal & Findings

What happened at each step: goal, what was built, what was measured on this PC, what went wrong, and the lessons. **This is the project's memory**: it explains *why* things are the way they are.

**Machine:** Windows · 16 GB RAM · no NVIDIA GPU (CPU-only AI) · Python 3.13 · Node 22 · Ollama 0.40 · models stored in `D:\OllamaModels`.

---

## Open action items

| # | Item | Why | How |
|---|---|---|---|
| 1 | **Re-extract all resumes with the 5b + Step 7 code** | Stored profiles predate job-level grounding (Divya: Django 13.3 y; Priya: every skill 6.2 y) and the neutral-summary prompt | `.env` → `EXTRACTION_MODEL_ROLE=fast`, restart (no `--reload`), `POST /api/resumes/reextract` (~12 min); this also re-embeds and fills the keyword index |
| 2 | ~~Switch extraction to the fast model~~ | Done in `.env.example`; copy into `.env` (remote tools can't write `.env`) | `Copy-Item .env.example .env` |
| 3 | Run `compare_extraction --models fast` with the 5b code on real models | Confirm the 16/16 result seen with the stand-in model | Server stopped, then run the script |
| 4 | ~~Neutral, name-free summaries~~ | Done in Step 7: prompt rule + pronoun neutralisation in chunks; takes effect after item 1 | — |
| 5 | ~~Enrich experience chunks with normalised skills~~ | Done in Step 7 (`Skills used:` line); takes effect after item 1 | — |
| 6 | Licence review before company use | `qwen2.5:3b` uses the Qwen Research Licence | Test `llama3.2:3b` with `compare_extraction` |
| 7 | ~~Real-model retrieval evaluation~~ | Done (table in Step 7b) | — |
| 8 | Keep RRF weights at 1.0 for now | Hybrid = skills = 1.00 recall@5; no consistent winner to tune towards with 3 roles | Revisit with a larger test set (Step 14) |
| 9 | ~~Re-run `evaluate_retrieval` after the 7b scoring update~~ | Done: Fatima now #2 in hybrid (see Step 7b) | — |
| 10 | ~~Minimum total years and seniority in ranking~~ (Step 8 experience factor; Divya vs Karthik remains a judgement call) | Karthik (1.5 y) sits above Divya for a 5-year role: retrieval ignores `min_total_years` | Step 8 scoring |
| 11 | Verify Step 5 evidence quotes support the skill (Step 8: judge quotes are verified against original resume text; Step 5's stored quotes still unchecked) | Jenkins' stored evidence for Priya is a Terraform sentence; the check accepts a skill when its name appears anywhere | Step 8 judge + a stricter evidence check |
| 12 | Re-parse roles once (optional) | Stored parses contain invented years; they're now cleaned at search time anyway | `python -m scripts.load_roles --reparse` |
| 13 | Verify the Step 11b portal on this PC | Sandbox: checks green, 7/10 browser tests before the last 3 fixes | `npm install`, `npm run check`, `npm run build`, `npm run test:e2e` (with `E2E_EMAIL`/`E2E_PASSWORD`) |
| 15 | Restart the backend for Step 12a | New `/api/resumes` fields, `?availability=` filter, typed re-extract result, education grounding | Stop uvicorn, start it again (or let `--reload` pick it up) |
| 16 | Tests for Step 12c (deferred) | Users and account pages are type-checked and built, not yet unit or browser tested | users schema unit tests; browser tests against a test database (they change accounts) |
| 17 | Verify Step 13 on this PC; tests deferred | Checked against the fake backend only; no unit or browser tests yet | `npm install` (react-markdown, remark-gfm), restart the backend, ask a question at `/agent` with Ollama running and watch the steps stream; later: unit tests for `createSseParser` / `messagesToTurns`, a Playwright chat spec |
| 18 | ~~**Fix extraction for real-world resumes**~~ Done in code (Step 13b below; offline 107/107) | Audit of EMP-1017 (3-page, 6,205-character resume, not in our sample format): category headers stored as skills, Python/Django/FastAPI/React/MySQL lost, projects ignored and attributed to the wrong job, PHP 5.2 y instead of ~13.7 y, RAG 8.7 y, MCA year lost | See "Audit: EMP-1017" below and doc 18 (9 real resumes, 15 pipeline problems P1–P15) |
| 19 | **Run the real-model check, then re-extract everything** | Offline checks prove the code; the model's answers must be checked too | `pip install -r requirements.txt` (olefile), set `MAX_UPLOAD_MB=25` in `.env`, stop the server, `python -m scripts.evaluate_real_resumes`, then start the server and **Re-extract all** on the Resumes page |
| 14 | Delete `_to_delete\frontend-v1\` when happy | The 7 replaced version-1 files were moved there, not deleted | Delete the folder in Explorer |

---

## Step 1: Environment and models

**Built:** Python 3.13, Node 22, Git, Ollama; pulled `nomic-embed-text`, `qwen2.5:3b`, `qwen2.5:7b`.

**Measured:**
| | qwen2.5:3b | qwen2.5:7b |
|---|---|---|
| Size | 1.9 GB | 4.7 GB |
| Cold load | 4.1 s | 10.2 s |
| Prefill | 85.7 tok/s | 36.7 tok/s |
| Decode | **16.7 tok/s** | **7.7 tok/s** |

nomic-embed-text: 768 numbers per text.

**Lessons**
- On a CPU, speed ≈ memory bandwidth ÷ model size (the 7B is 2.4× bigger, 2.2× slower).
- A 12-word prompt became 42 tokens because of the chat template.
- Licences differ between sizes of the same model family.

---

## Step 2: Backend skeleton

**Built:** FastAPI app, settings from `.env`, the Ollama client (the only module that talks to Ollama), `/api/health`, dev endpoints for chat and similarity.

**Problems:** port 8000 reserved by Windows (WinError 10013) → port 8010; `main.py` not found; health "degraded" because Ollama was reading an empty model folder. All in document 08.

**Lessons**
- A health check that tests every dependency finds configuration problems before they surface as confusing errors.
- Windows-specific issues (reserved ports, hidden file extensions, admin shells) cost more time than the code.

---

## Step 3: Database

**Built:** 12 tables with SQLAlchemy 2 (async) on SQLite; scripts to seed demo data and inspect tables.

**Measured:** deleting 2 demo employees removed 2 resumes, 5 skill links and 1 experience automatically (cascade); the shared skills catalogue stayed.

**Problem:** `greenlet` missing → use `sqlalchemy[asyncio]`.

**Lessons**
- SQLite ignores foreign keys unless `PRAGMA foreign_keys=ON` is set on every connection.
- Design for the domain: internal staffing needs **availability** fields that hiring tools don't.

---

## Step 4: Resume intake

**Built:** HR CSV import (upsert), single and bulk upload, validation (type, magic bytes, size, SHA-256 duplicates), text extraction (PDF and DOCX with tables), scanned-PDF detection, the background worker with a restart-safe queue.

**Measured:** 16 employees imported; 15 resumes uploaded; 14 parsed; 1 scanned PDF correctly failed (0 characters); a second upload of the same files → 15 duplicates rejected.

**Lessons**
- Two-column PDFs: keep the PDF's stored text order; "sort top-to-bottom" interleaves columns.
- DOCX: read paragraphs **and** tables in order; skills often live in tables.
- Licences matter for libraries too (PyMuPDF is AGPL; pypdfium2 is permissive).

---

## Step 5 and 5b: Structured extraction

**Built:** schema-constrained LLM extraction, evidence checks, skill normalisation catalog, date and experience maths in code, a multi-stage worker, profile endpoint, model comparison script.

**Measured (real models, before 5b):**
| Model | Checks | Avg per resume | 2,000 resumes |
|---|---|---|---|
| qwen2.5:3b | 13/14 | 50 s | ~28 h |
| qwen2.5:7b | 13/14 | 101 s | ~56 h |

Priya, 7B: 613 prompt tokens, 567 output tokens, 7.0 tok/s, 90.5 s. About 75% of the time is spent writing the answer.

**Finding:** both models copied the skills section into **every** job, inflating years (Divya: Django 13.3 y, last used 2026; Neha: AngularJS 10.3 y; Priya: Python and Bash 6.2 y). The single failing check revealed a systematic problem hidden in "passing" results.

**Fix (5b):** job-level grounding (a skill counts for a job only if written in that job's text; implied languages allowed, e.g. FastAPI → Python); skills removed from jobs are kept without years if mentioned elsewhere; stated durations ("React (1 yr)") cap years. Stand-in model test: 16/16. **Real-model rerun and re-extraction pending** (action items 1–3).

**Lessons**
- The LLM reads and labels; code verifies, normalises and calculates.
- Per-skill years derived from job dates are an **upper bound**.
- Look behind passing tests: one failure can point to a pattern affecting everything.

---

## Step 6: Chunking, embeddings, semantic search

**Built:** domain-aware chunking (profile card, one chunk per job, the rest; contextual headers; anonymisation), nomic embeddings with task prefixes, ChromaDB index, semantic search endpoint, demo script.

**Measured:** 14 resumes → **60 chunks**. 7 queries written without the resumes' words: expected person in the top 3 for **7/7**, at #1 for **5/7**. Similarity scores 0.52–0.67; #1 vs #2 often < 0.01 apart. First query 2,014 ms (model cold start), then ~50 ms.

**Findings**
- Score compression: absolute scores mean little, only the order matters.
- Short chunks are noisy and appear in unrelated results.
- Abbreviations ("k8s") are weakly linked to their meaning by the embedding model.
- Vector search always returns *someone*, even for skills nobody has.
- My own "expected" list missed a genuine insurance-domain match: ground truth needs care too.
- LLM summaries contain pronouns that reveal gender (anonymisation only removes names, emails and phones).

**Lessons**
- Pure vector search is good but not enough for ranking people; combine signals (Step 7).
- Keep the index rebuildable from the source of truth, so chunking can be improved freely.

---

## Step 7: Hybrid retrieval

**Built:**
- Projects and roles API; LLM **role parsing** into must-have / nice-to-have skills, seniority, minimum years, location and a search summary (stored, editable by a person).
- **Three retrieval signals:** structured skills (with implied skills, years and recency), **BM25 keyword search** with SQLite FTS5 over every catalog spelling, and vector search limited to eligible employees.
- **Reciprocal Rank Fusion** (k = 60, per-signal weights); availability verdict per person (free % now, or free before the start date); `only_available` filter.
- Chunk improvements: a `Skills used:` line per job (normalised skills found in that job's text), gendered pronouns neutralised; the extraction prompt now asks for name-free, pronoun-free summaries.
- Scripts `load_roles` (idempotent) and `evaluate_retrieval` (recall@5, recall@10, MRR per signal).

**Measured (stand-in test):** the user's real Step 5 data, re-embedded with a bag-of-words stand-in for nomic, stand-in role parses. 14 resumes → 60 chunks → 60 keyword-index rows (rebuilt automatically at startup).

| Run | Recall@5 | Recall@10 | MRR |
|---|---|---|---|
| hybrid | 0.92 | 1.00 | 1.00 |
| skills only | 1.00 | 1.00 | 1.00 |
| keyword only | 0.83 | 1.00 | 1.00 |
| vector only (stand-in) | 0.92 | 1.00 | 1.00 |

The one hybrid miss: Siddharth (EMP-1012, Terraform + AKS) ranked 6th for the DevOps role, behind Rahul (EMP-1014, mentions k8s/Helm) and Ananya (EMP-1001), who scored well on keywords and vectors; skills alone had him 3rd. Vector numbers here mean little (stand-in embeddings); the real-model run is action item 7.

**Findings**
- With only 15 employees, recall@10 is almost automatically 1.0; **recall@5 and the ranks** are the informative columns.
- Structured skills were the strongest single signal on this data. That is expected: it uses verified, normalised facts. Keyword and vector signals matter for things the catalog doesn't know (domains, rare tools, wording).
- Fusion can pull down a skills-only winner when two text signals agree on someone else: weights are a real design decision, to be set from evaluation, not guessed.
- Old (pre-5b) data shows in results: Priya is "missing" CI/CD and every skill has 6.2 years. Retrieval is only as good as the extraction underneath it.
- Pronoun neutralisation in code is a safety net only: "They specializes" shows it can break grammar. The real fix is the prompt (summary written without pronouns), effective after re-extraction.
- `.env` can't be written by the remote tools (protected file): settings changes for `.env` are delivered in `.env.example`.

### Step 7b: first real-model evaluation and fixes

**Measured (real qwen2.5 parse + real nomic vectors, after re-extraction with the fast model):**

| Run | Recall@5 | Recall@10 | MRR |
|---|---|---|---|
| **hybrid** | **1.00** | 1.00 | 1.00 |
| skills only | 1.00 | 1.00 | 1.00 |
| keyword only | 0.83 | 1.00 | 1.00 |
| vector only | 0.83 | 1.00 | 1.00 |

DevOps role: hybrid returned the **exact expected order** (Priya, Fatima, Siddharth, Vikram). Every expected person was in the top 5 for every role.

**Problem found (GenAI role):** Fatima ranked 4th, behind Karthik and Rohan, the documented **trap** ("know FastAPI, no LLM experience; must not outrank"). Three causes, found by reading the stored requirements and skills:
1. The 7B parser wrote non-catalog names: `"retrieval-augmented generation using vector databases"`, `"nlp fundamentals"`, `"llm evaluation"`, so those requirements matched nobody.
2. Matching was case-sensitive: `"llm evaluation"` ≠ Kavya's `"LLM evaluation"`.
3. Scoring let a **common** must-have (Python) plus **nice-to-haves** (FastAPI, Docker) outweigh the rare must-have that defines the role (LLMs).

**Fixes:** code splits compound requirement names into the known skills inside them and re-normalises at search time; case-insensitive matching; rarity (IDF) weights per skill; nice-to-haves gated by must-have coverage; more implications (LLM serving / prompt engineering / LLM evaluation ⇒ LLMs); prompt asks for one short skill per item.

**Result (skills signal, real data):** Kavya 0.571 → **Fatima 0.126** → Rohan 0.082 → Karthik 0.078.

**Re-run on the user's PC after the fix (real models):**

| GenAI role | before 7b | after 7b |
|---|---|---|
| hybrid top 4 | Kavya, Karthik, Rohan, **Fatima (4)** | Kavya, **Fatima (2)**, Karthik, Rohan |
| skills: Fatima | 4 | **2** |
| vector: Fatima | 6 | **5** (the vector query's "Key skills" line now lists RAG, Vector Databases, NLP instead of paraphrases) |

| Run (3 roles) | Recall@5 | Recall@10 | MRR |
|---|---|---|---|
| hybrid | 1.00 | 1.00 | 1.00 |
| skills | 1.00 | 1.00 | 1.00 |
| keyword | 0.83 | 1.00 | 1.00 |
| vector | **1.00** (was 0.83) | 1.00 | 1.00 |

Django and DevOps rankings unchanged (DevOps still exactly the expected order). Remaining ordering issue: Karthik (1.5 y) above Divya for a 5-year role → Step 8 (action item 10). **Step 7 complete.**

**Findings**
- Perfect recall@5 can hide a ranking error that matters: always read the **top-5 lists**, not only the averages.
- The LLM paraphrases even when given a list of names; **never trust free-text names from an LLM without normalising them in code.**
- Vector search alone placed Fatima 6th: her chunks describe MLOps, not RAG. Meaning search is right that she is a partial match; structure and keywords know she has LLM serving.

### Step 7c: checking the explainer documents against the real data

Writing documents 09 and 10 and checking every example against the user's database found three more things:
- **Invented requirements:** for the DevOps role (no years anywhere in its description) the 7B parser wrote Kubernetes 3 y, Terraform 2 y, CI/CD 2 y, AWS 3 y, 5 y total, and the domain "cloud". **Fix:** `ground_in_description()` keeps a number of years only if written next to "years" in the role text, and a domain only if its word appears there; applied when parsing and at search time (not to a person's edits). Rankings unchanged on the 3 sample roles.
- **Wrong evidence quotes from Step 5:** Jenkins and GitHub Actions for Priya carry a Terraform sentence as evidence (action item 11).
- **Implied beats direct when years are unknown:** Priya's AWS is matched via Amazon EKS (0.6) rather than her direct "AWS" (unknown years, 0.48).
- Documentation errors corrected: the keyword query never contained "eks" (it's not a Kubernetes spelling); the stage ⑩ example in document 04 had used stand-in values and now shows real ones.

**Lesson:** check every example in the documentation against real data. Writing the explanation found a hallucination that the evaluation numbers didn't show.

**Lessons**
- Retrieval aims for **recall** (never miss the right person); ordering precisely is the next stage's job.
- Rank-based fusion avoids comparing incompatible scores (BM25 −8.1, cosine 0.58, skill credit 0.71).
- Make AI interpretations **editable and recorded** (`parsed_by`, `edited_by_user`): a person must be able to fix a wrong reading of a role.

---

## Step 8: Scoring and the LLM judge

**Built:** a rule score (skill coverage + retrieval relevance, multiplied by experience, availability and location factors with floors); an LLM judge that assesses each must-have with a quote, plus strengths, gaps, rating and summary; code-side quote verification against **original resume text only** and a code-computed judge score; final = 0.6 × rule + 0.4 × judge; re-ranking of the judged top N only; match runs saved with settings and per-result breakdowns; background judging with progress, cancellation on shutdown and recovery at startup; `evaluate_matching` (nDCG@5, MRR, pair order). Seniority is now grounded in the role text. No schema change (`match_runs`/`match_results` from Step 3). The code was given in the chat for the user to type in.

**Measured (stand-in models on the user's real data; judge answers are fake, so only the rule score is meaningful):**

| | nDCG@5 | MRR | Pair order |
|---|---|---|---|
| Rule score only, 3 roles | 0.98 | 1.00 | 0.94 |

Django: Ananya, Rohan, Karthik, Divya (expected Divya above Karthik). DevOps: Priya, Fatima, Siddharth, then Ananya/Rahul, Vikram 6th (availability 0.4). GenAI: Kavya, Fatima, then Rohan.

**Findings during the build**
- **Weighted sums give irrelevant people a floor of points:** with an additive formula, being free, local and experienced gave ~45% of the score without any matching skill; a data scientist appeared between backend candidates. Switched to multiplicative factors (HR facts can only lower a skills-based fit).
- **Re-ranking the whole list after judging was unfair:** judge scores run lower than rule scores, so judged candidates fell below unjudged ones (Divya dropped to 8th). Fixed: re-rank only the judged top N.
- **"mid" matched "mid-November":** seniority grounding invented a 3-year requirement for the DevOps role. Plain "mid" removed.
- **The system must not quote itself:** the profile card (from Step 5's LLM output), chunk headers and "Skills used:" lines are generated text; quotes from them were being "verified". Evidence is now original resume lines only.
- **Judgement calls stay:** Divya vs Karthik for "at least 5 years of backend experience" depends on how a staffing team weighs old hands-on depth vs current but short experience.

### Step 8b: first real-model run (qwen2.5:7b judge)

| Role | Run | nDCG@5 | MRR | Pairs | Time |
|---|---|---|---|---|---|
| Django | failed (server restarted mid-run) | 0.99 | 1.00 | 0.83 | 172 s, 1 of 5 judged |
| DevOps | completed | 0.99 | 1.00 | 1.00 | 357 s for 5 (58–83 s each) |
| GenAI | completed | 1.00 | 1.00 | 1.00 | 413 s for 5 |

DevOps came out in exactly the expected order (Priya, Fatima, Siddharth, then Rahul, Vikram 5th). GenAI: Kavya, Fatima, then the trap candidates. The judge used ~740–1,030 prompt tokens and 290–545 output tokens per candidate.

**Bugs found in the real run, fixed in `judge.py`:**
1. **Renamed requirements → judge score 0.0.** For the Django role (requirements carry "5 years"), the prompt listed "Python (5.0+ years)"; the model echoed names like that, the code matched names exactly, and all 7 must-haves looked "not assessed": Ananya got judge 0.00 despite rating "good" and 3/3 verified strengths. Fix: names matched ignoring case and brackets, position fallback, prompt asks for names without years, raw answer stored.
2. **The judge quoted the AI's own summary.** Vikram 0/4 quotes verified: all were paraphrases from the profile card (Step 5's summary), never in the resume. Fix: the profile card is no longer in the dossier.
3. **The run interruption was ours:** the server was running with auto-reload and the assistant's update of `requirements.py` at that moment restarted it. The failure handling worked as designed (run marked failed with a clear message). Lesson: don't change code while a long AI job runs, and run the server without `--reload` for evaluations.

**Judge quality observations (7B):** rated Siddharth "no" on Kubernetes despite AKS (a Kubernetes service), and quoted "Skills" lines although told not to. Verification caught the quotes; the AKS miss is a model-knowledge limit (the rule score's implied-skill credit covers it).

**Pending:** re-run Django with the fixes; compare `JUDGE_MODEL_ROLE=fast`.

**Lessons**
- Test a scoring formula on the cases it must get right *and* on the people it must keep out.
- Different scales don't mix: combine within comparable groups, or by rank.
- Check what your citations point to: generated text is not evidence.

---

## Step 9: Authentication and roles

**Built:** login with email + password (Argon2id hashes via pwdlib), signed JWT access tokens (8 hours) sent as `Authorization: Bearer` or an HttpOnly, SameSite=Lax cookie; `get_current_user` (user re-loaded on every request, so deactivation is immediate) and `require_admin`; every router behind login, admin-only uploads/imports/re-processing/users/dev tools; user management that never deletes and protects the last admin; brute-force lockout (5 failures / 15 min → 429); identical errors and timing for unknown emails; `create_user` script (first admin, `--secret`); all API scripts log in (`RTM_EMAIL`/`RTM_PASSWORD`); "who did it" now recorded on resumes, projects and match runs. No schema change (Step 3 designed the columns). Files written directly to the project folder; version 0.8.0.

**Tested (stand-in models, real data):** 17 checks passed: no token → 401; health public; wrong password and unknown email give the same 401 message; admin `me`; resource manager via cookie can list projects; resource manager gets 403 on import, re-extract, users and dev chat; tampered token → "Invalid token."; Swagger form login; weak password rejected; email lower-cased on create; last admin can't be demoted; a deactivated user's existing token stops working; 6th wrong password → 429 with `Retry-After: 899`; scripts log in and run; `match_runs.created_by_id` filled. Argon2id hash + verify ≈ 91 ms (m = 64 MB, t = 3, p = 4).

**Decisions**
- Own login now, SSO later: Step 15 can swap token verification for the company identity provider (Entra ID / Okta via OpenID Connect) without touching roles or endpoints.
- Cookie *and* header: the browser uses the HttpOnly cookie (safer against XSS); scripts and Swagger use the header.
- One 8-hour token, no refresh tokens: simpler for learning; refresh tokens are the production upgrade.
- `EmailStr` not used: it needs an extra package and rejects `.local` test domains; a simple pattern + lower-casing instead.

**Done:** first admin created, secret set, scripts log in (`Logged in as admin@company.local (admin)`).

### Step 8c: full real-model evaluation (after the 8b fixes, with login)

| Role | nDCG@5 | MRR | Pairs | Time (5 judged) | Order |
|---|---|---|---|---|---|
| Django | **1.00** | 1.00 | **1.00** | 424 s | Ananya, Rohan, **Divya, Karthik** (exactly expected) |
| DevOps | **1.00** | 1.00 | **1.00** | 322 s | Priya, Fatima, Siddharth, Vikram (exactly expected) |
| GenAI | **1.00** | 1.00 | **1.00** | 387 s | Kavya, Fatima, then the trap candidates |

**Every expected ranking is now exact.** The open judgement call from Step 8 (Divya vs Karthik) was settled by the judge: the rule score had them tied (0.20 / 0.20); the judge rated Divya "partial" (Django "yes" with "Senior Django Developer, Nimbus Technologies Jul 2015 – Mar 2019") and Karthik "weak" ("lacks the required years"). Exactly the kind of reading the rule score can't do.

**Quote verification after the 8b fixes:** Ananya 10/10, Divya 6/6, Karthik 6/6, Priya 6/6, Fatima 6/6, Vikram 3/5 (was 0/4). Exception: Kavya 3/8, because the judge quoted our generated "Skills used:" lines; verification correctly refused them and downgraded those "yes" to "partly". **Fix (Step 8d):** "Skills used:" lines are no longer shown to the judge.

**Timing:** 68–82 s per candidate with qwen2.5:7b on this CPU; 5–7 minutes per role.

**Lessons**
- The judge earned its place: it resolved the one ordering the rule score couldn't, with quoted reasons.
- Telling a small model "don't quote X" is weaker than not showing it X. Remove misleading context instead of instructing around it.

---

## Step 10: The staffing agent

**Built:** a tool-calling agent (ReAct loop, hand-written, ~80 lines) on qwen2.5:7b via Ollama's `tools` support; 6 read-only tools wrapping Steps 5–8 (`find_candidates` builds an ad-hoc role and reuses retrieval + rule scoring; `search_employees`; `get_employee_profile`; `check_employee_availability`; `list_projects`; `get_match_results`); Pydantic validation of tool arguments with errors returned to the model; at most 4 tool rounds, then an answer without tools; streaming via a new `chat_stream()` and Server-Sent Events; conversations and every message (including tool calls and results) saved in two new tables (`agent_conversations`, `agent_messages`, created automatically); short-term memory = last 10 questions/answers; conversations private to their owner; `scripts/try_agent.py` (interactive and `--demo`). Version 0.9.0. Files written directly to the project folder.

**Tested (stand-in tool-calling model on the user's real data):** tool call → validated → real retrieval → streamed answer; a follow-up question received the earlier turn as memory; all messages saved in order (user, assistant tool request, tool result, answer); another user's conversation → 404; no login → 401. Tool specs simplified from ~4,000 to ~3,250 characters (no titles, no `anyOf` nulls) to save context and help small models.

**Design decisions**
- Agent on top of the pipeline, not instead of it: saved match runs (with the judge) stay the reliable path; the agent answers open questions and follow-ups.
- The LLM judge is not a tool (too slow for chat); the agent reads saved judge results.
- Read-only tools only: even a prompt-injected agent can't change data.
- Hand-written loop instead of LangGraph/PydanticAI: every moving part visible while learning.

**Pending:** real-model run (`python -m scripts.try_agent --demo`): tool choices, argument quality, time per question; compare `AGENT_MODEL_ROLE=fast`.

---

## Step 11: Next.js frontend foundation

**Built:** `frontend/` with Next.js 16.4.2 (App Router, Turbopack, Cache Components + partial prefetching as scaffolded), React 19.3, TypeScript, Tailwind 4; `/api/*` forwarded to FastAPI by rewrites (backend-for-frontend: same origin, no CORS, first-party HttpOnly cookie); `proxy.ts` (Next.js 16's renamed middleware) doing an optimistic login check from the token's `exp` (no secret in the frontend); one `api()` client with `ApiError` and automatic return to login on 401; session context from `/api/auth/me`; app shell with role-based navigation and a mobile layout; design tokens with dark mode; 7 UI components; login page with a safe `next` redirect; a live dashboard (health, models, pipeline stages, projects); placeholders for Steps 12–13. Files written directly to the project folder.

**Tested in a sandbox (stand-in models, user's real data, headless Chromium):** build, TypeScript and ESLint clean; redirect to login with `next`; wrong/right passwords; back to the requested page; `/login` when logged in → `/`; dashboard numbers (16 employees, 14/15 searchable, 3 roles, 58 chunks); RM vs admin menus; logout; 390 px mobile view.

**Findings**
- Next.js 16 changed things beyond the training data of most tools: `middleware.ts` is now `proxy.ts`, Cache Components are on by default, `LayoutProps<"/">` types are generated. The project ships its docs in `node_modules/next/dist/docs/` (and an `AGENTS.md` pointing to them); they were read before writing code.
- **Rewrites are compiled into production builds**: `BACKEND_URL` set only at `next start` was ignored (requests still went to :8010). Documented in the README.
- When the backend is down, the rewrite returns a bare 500: the error message now says "Is the backend running on port 8010?".
- Visual check caught two issues: model labels ("Fast Llm Model") and a squeezed mobile header. Both fixed.

- **First run on the user's PC: Next.js dev "Insight": "could not validate that a segment has instant navigation; `(portal)/page.tsx` dropped from rendering".** Cause: `AppShell` returned a spinner *instead of* `{children}` until `/api/auth/me` answered, so the page wasn't part of the rendered tree. Fix: the frame and the page always render; only the user corner waits (a placeholder), and admin-only links appear once the role is known. Verified in dev mode: no insight, navigation between pages instant. Lesson: in Next.js 16 a layout should never withhold `children`; let parts load inside it instead.

**Done:** user installed and ran the portal and logged in as admin@company.local.

### Step 11b: rebuilding the frontend foundation the Next.js 16 way

**Why:** asked whether version 1 was world-class, the honest review said no. It was a single-page app inside Next.js: data loaded in the browser with `useEffect`, hand-written API types, hand-made components, no tests, no security headers, and the dashboard downloaded up to 500 employees to count them. Steps 12–13 will add about ten pages, so this was the cheapest moment to change the architecture.

**Built (frontend 0.2.0, 83 files):**
- pages render on the server and stream each section behind `<Suspense>` (every route ◐ Partial Prerender);
- a server-only data access layer: `request()` reads the HttpOnly cookie and calls FastAPI server-to-server with a Bearer token, returning `ApiResult` values;
- the session via `getCurrentUser()` with `"use cache: private"`;
- login/logout as **Server Actions** (`useActionState`, zod), and a `/auth/session-expired` Route Handler;
- API types **generated** from `/openapi.json` (`openapi-typescript` + `openapi-fetch`, `npm run api:types`);
- shadcn/ui-style components on Radix with OKLCH tokens;
- per-section error boundaries (Next.js 16 `catchError`), plus `retry()` error pages;
- zod-validated settings and security headers (CSP without nonces, nosniff, frame-ancestors, Referrer-Policy, Permissions-Policy, HSTS when `HTTPS=true`);
- React Compiler and typed routes;
- a feature-based structure (`app/` routes → `features/` → `components/` → `lib/`);
- Prettier, Vitest (43 tests), Playwright (10 tests, including `@next/playwright` `instant()`), and `npm run check`.

**Backend 0.10.0:** `GET /api/overview` (counts by status for employees, projects, roles, match runs, plus parsed roles) and a typed `HealthOut` response model for `/api/health` (200 and 503), so the generated types are exact.

**Tested in a sandbox (stand-in models, copy of the real database):** types, lint, formatting and unit tests clean; production build passed; `/api/overview` returned 16 employees, 3 projects, 3 open roles (all parsed) and 27 completed runs. Playwright: 7 of 10 passing on the first run; the 3 failures led to findings 3–5 below, which are fixed (browser run not repeated; the user is verifying on the PC).

**Findings**
1. **The build stopped with "unstable value `Math.random()` while prerendering".** `openapi-fetch` creates a random request ID when a middleware is registered, and our auth middleware read the cookie only *after* that, so the randomness happened while Next.js was building the static shell. Fix: `request()` reads `cookies()` first and creates a middleware-free client per call. Lesson: under Cache Components, touch request data before anything non-deterministic; the build enforces it.
2. **`localhost:8010` passed URL validation** (it's a valid URL with the scheme `localhost:`), the exact mistake the comment warned about. A unit test caught it; `BACKEND_URL` must now be http(s).
3. **Sign out did nothing.** Radix renders the open menu in a portal at the end of `<body>`, so the submit button left its `<form>`. First fix: a hidden form outside the menu, linked with the button's `form=` attribute. That was still broken (see Step 12a, finding 2); final fix: `requestSubmit()`.
4. **Login without JavaScript failed.** Streamed Suspense content is revealed by an inline script, so a form inside `<Suspense>` never appears without JavaScript. Fix: the login form is static; the Server Action reads `?next=` from the Referer (validated by `safeNextPath`), and only the "session ended" notice streams.
5. **Test locator matched two alerts:** Next.js's route announcer is an empty `role="alert"`. Tests filter by text.
6. **Version 1's `error.tsx` used `reset()`;** Next.js 16 passes `retry()`, which re-fetches on the server.
7. **A redirect loop was designed out:** if FastAPI rejects a token that still *looks* valid, redirecting to `/login` would bounce back (the proxy sees a "valid" cookie). Pages can't change cookies, so the client redirects to a Route Handler that deletes the cookie first. Covered by the forged-token browser test.
8. **The nonce CSP and the static shell don't mix** (Next.js docs): nonces force per-request rendering. We chose the documented "without nonces" policy; the trade-off is recorded in doc 15.

**Design decisions:** FastAPI stays the only authority (Next.js never verifies the JWT, it forwards it); expected errors are values, bugs go to boundaries; live data is uncached and polled only while resumes are processing; the `/api` rewrite stays for browser-direct calls in Steps 12–13 (agent stream, upload progress).

## Step 12a: Employees and Resumes pages

**Built:**
- **Frontend pages:**
  - `/employees`: search and availability filter in the URL, 25 per page with the "limit + 1" trick, HR CSV import for admins;
  - `/employees/[id]`: HR facts, the AI profile with a resume quote per skill, experience, education, resume versions with admin upload/retry/delete;
  - `/resumes` (admins): drag-and-drop bulk upload with per-file results, filters by status, retry/delete with confirmation, re-extract/re-index all, live refresh while busy.
- **Shared pieces:** table, AlertDialog, native select, `ActionButton` (one Server Action per button), pagination, empty state, `IfAdmin`, safe URL-parameter parsing, a browser-side typed client for uploads.
- **Backend:** `ResumeListItem` (employee code and name, loaded with `selectinload`), `?availability=` on `/api/employees`, typed `RequeueResult` and `EducationOut`, education years grounded in the resume text.

**Tested (sandbox, stand-in models, copy of the real database):** 58 unit tests; production build with every route ◐ including `/employees/[id]`; Playwright 15/15 (5 new, read-only tests); a manual browser script for search, filters, bad parameters, 404s, a 4-file upload with every error case, delete with confirmation and re-index. No console errors.

**Findings**
1. **First dynamic route broke the build** (`usePathname()` outside Suspense on `/employees/[id]`): the menu's loading fallback read the URL. A fallback belongs to the prerendered shell, where a dynamic URL isn't known. Fix: `NavLinksStatic` for the fallback.
2. **Confirm dialogs and *Sign out* sent nothing.** The Step 11b `form=` fix was never re-tested in a browser. Radix closes the dialog/menu on click, removing the button before the browser submits its form. Fix: `form.requestSubmit()` in code. The full suite (15/15) now passes, sign-out included. Lesson: a fix isn't done until a browser test has exercised it.
3. **12 of 14 education years were chatter, not years** ("goes with the date 2014", "context.year", "goes here"). The 3B model echoed instruction-like text; it never invented a wrong year, but often omitted the real one. `ground_education()` takes the year from the resume line naming the institution, and keeps the model's year only if it appears there: 14/14 correct, an invented 2099 is dropped. It is applied at extraction and when old profiles are read. Found only because the new profile page shows the data.
4. **Next.js 16 keeps the previous page hidden in the DOM** for instant Back navigation, so loose test locators match old pages. Tests use exact roles.
5. **"1 pages"** spotted on a screenshot → `plural()`.
6. **Unreviewed changes in the user's folder** (`.nvmrc` = 26, `engines` in `package.json`, `browsing-topics` removed from the Permissions-Policy), dated 12:27: kept, and the working copy synced to them. Rule followed: never overwrite files the user changed; diff your device files against the last synced version before writing.

**Design decisions:** uploads go browser → rewrite → FastAPI, one file per request, 2 in parallel (Server Actions are limited to 1 MB and would buffer files in Next.js). Small changes are Server Actions with `refresh()`. Filters live in the URL. Roles are hidden for clarity and enforced by FastAPI. Live status polls only while something is in progress.

## Step 12b: Projects and matching pages

**Built:**
- **Pages:**
  - `/projects` and `/projects/[id]`: projects with roles, create a project, add a role;
  - `/roles/[id]`: description, AI-parsed requirements with view/correct modes (move between must/nice, minimum years, seniority, location, domain, search summary), start a match, run history, mark filled/close/reopen;
  - `/match-runs/[id]`: live judge progress and ranked candidate cards with skills found or missing (implied skills shown), availability, score parts and formula, and the judge's verdict per must-have with ✓ only for quotes found in the resume by code.
- **Shared:** `FormField`, `SubmitButton` (`useFormStatus`), `Textarea`; menu sections with `also` prefixes.
- **Backend:** typed match JSON (`ScoreBreakdown`, `Explanation`, `JudgeVerdictOut`, `MatchRunSettings`…), run summaries with names, `GET /api/projects/{id}`, `PATCH /api/roles/{id}`.

**Tested:**
- Typed models validated against every stored run: sandbox 27 runs/270 results; **the user's PC 9 runs/90 results, including 26 real qwen2.5:7b verdicts, 0 errors**.
- 69 unit tests and Playwright 20/20 passing; production build with every route ◐.
- A full browser journey (create → parse → correct → match → live judge → completed; Priya Nair first for the Kubernetes role) with no console errors.

**Findings**
1. `z.coerce.number("")` is 0: an emptied "Headcount" failed instead of defaulting → `intWithDefault()`.
2. Native browser validation (`minLength`) hid the server's clearer message → `noValidate` on the forms, as on the login form.
3. The stored match JSON was typed only after validating all historic rows, so no old run breaks.
4. Correcting requirements with "k8s" merged it into the existing "Kubernetes" (with the new years): intended, and shown at once.
5. `count()` doesn't wait for streamed content: two e2e tests skipped silently until they waited for the skeleton to go. Treat "skipped" as a result to investigate.
6. Sandbox artefact: no resume was "Searchable" (a 12a re-index was queued with the stand-in worker off), so the first match found nobody. The page's empty state explained it correctly; the worker was restarted.

**Design decisions:** the run page shows only stored data (audit trail); the judge's rating is displayed but the score is computed by code; reading the description again needs a confirmation because it replaces human corrections; editing a role never re-parses silently.

## Step 12c: Users and account pages

**Built:**
- `/users` (admins): account list (you marked, active first) with reset password (dialog), make admin (confirmed) or resource manager, deactivate (confirmed) or reactivate; a new-account form.
- `/account` (everyone): signed-in details and change password (current + new twice).
- Shared: Radix `Dialog`; `lib/forms.ts` (`FormState`, `formValues`) moved out of the projects feature; a password field with show/hide.
- **Backend:** admins can no longer deactivate or demote themselves (409; the last-admin rule already existed).

**Checked:** types, lint, formatting, production build (`/users`, `/account` ◐); the self-lockout 409 via curl. **Not tested** (the user asked to leave tests for now): no unit tests, browser tests or browser run for 12c; recorded as action item 16.

**Design decisions:** accounts are deactivated, never deleted (history); passwords are never returned to the page after an error; the zod password rule mirrors the backend (12+ characters, no edge spaces, no forced symbols, NIST SP 800-63B); "wrong current password" (400) is shown next to its field, while a 401 still ends the session.

## Step 13: The agent chat page

**Built:**
- `/agent` (new conversation, with example questions) and `/agent/[id]` (a stored conversation to continue, with Delete). A left column lists my conversations, newest first.
- The chat streams each tool call live (label, arguments, spinner → ✓/✗ and a one-line result), then the answer word by word, rendered as Markdown with employee codes linked. Stop aborts the run, and FastAPI stops too. Enter sends.
- Streaming goes browser → `POST /bff/agent/{id}` (a Route Handler) → FastAPI SSE. The relay reads the HttpOnly cookie on the server, validates the question, passes the stream through with `Cache-Control: no-cache, no-transform`, and cancels upstream when the browser goes away. `proxy.ts` skips `/bff`.
- Pure helpers: `createSseParser()` (chunks → events) and `messagesToTurns()` (stored messages → the same `Turn` shape as the live view).
- **Backend:** stored tool messages carry the same `summary` as the live stream (`summarise_tool_result`, now public); messages are returned in id order.

**Measured:**

| Path | Response | Event arrival (7 events, 0.7 s apart) |
|---|---|---|
| `/api` rewrite | gzip | all at 4.2 s (buffered) |
| `/bff` Route Handler, `no-transform` | not compressed | 0.0, 0.7 … 4.2 s (live) |

**Tested (sandbox, fake backend, production build):** new question (URL `/agent/{id}` at 76 ms, step + summary + answer), links, a follow-up using the history, sidebar refresh, reload identical to the live view, Stop, Delete; no console errors. **Not done:** unit and browser tests (deferred), a real-model run on this PC (action item 17).

**Findings:** the rewrite buffers SSE because of compression, and only a timed client measurement shows it. `EventSource` can't POST. Small models write chatter before tool calls, so the answer is cleared on `tool_call`. The proxy has to skip the relay, or an expired session becomes an HTML redirect that `fetch` can't use.

**Design decisions:** asking is a Route Handler, not a Server Action (Actions can't stream for minutes). Housekeeping (create, delete, refresh) is done with Server Actions. A conversation is created on the first question, so there are no empty ones. The model's Markdown is rendered without raw HTML (LLM output is untrusted). Explainer: doc 17.

## Audit: EMP-1017, a real resume outside our sample format (2026-11-05)

**Why it matters:** the 16 sample resumes were all written by us, one page, about 1,000 characters, in one layout. EMP-1017 is a real 3-page resume (6,205 characters) with a categorised skills section, an achievements section and a separate "Key projects" section. The pipeline had never been tested on anything like it.

**Correct:** both jobs, titles and dates (including the typo "Aprl 2018"), total experience 13.8 years, BCA year, contact details removed from chunks.

**Wrong, with the cause in the code:**

| # | What the employee page shows | What the resume says | Cause |
|---|---|---|---|
| 1 | Six "skills" named *Ecommerce & CMS*, *Backend & Full-Stack*, *AI & Automation*, *Frontend*, *Tools*, *Leadership* | These are headings; each lists 5–9 real skills | The model returned one skill per heading with the list as "evidence"; postprocess accepts any name that appears in the text and never splits lists |
| 2 | No Python, Django, FastAPI, Magento, MySQL, PostgreSQL, GraphQL, REST APIs, JavaScript, React, Handlebars, HTML, CSS, Tailwind, Git, OpenAI/Claude APIs, AI chatbots, voice assistants | All listed under Technical skills; Python/Django/FastAPI also in the summary | Consequence of 1: the real skills only survived inside the evidence text |
| 3 | The 6 key projects (Laravel, React.js, MySQL, Stencil, Handlebars, Zoom/Coinbase/Apple Pay APIs, Dymo SDK) don't appear as data | A separate "Key projects" section, undated, with durations | The schema has no projects; the chunker doesn't know the heading "Key projects", so the projects were glued onto the previous job |
| 4 | Search chunks label all 6 projects as "Software Engineer at CIS (2013–2018)", with "Skills used: … Laravel, BigCommerce" | Nothing links the projects to CIS; they're more likely recent | Chunker's job slice runs up to 40 lines until a known heading; "KEY PROJECTS" isn't in the heading list |
| 5 | PHP 5.2 years (CIS only) | "13+ years … PHP, Laravel"; Laravel at Encoresky since 2018 | PHP was rejected for Encoresky because the word isn't in that job's text; `IMPLIED_LANGUAGE` has Python/Java/C# only (no Laravel → PHP). The prompt line asking for these implications is ignored by the code |
| 6 | WooCommerce 13.8 y but WordPress 5.2 y | WooCommerce is a WordPress plugin | No ecosystem implications (WooCommerce → WordPress) |
| 7 | RAG pipelines, n8n, Voiceflow: 8.7 years each | They're in the 2018–present job; RAG didn't exist before 2020, n8n/Voiceflow date from 2019 | A skill gets the whole job's duration; no "can't be older than the technology" cap |
| 8 | "RAG pipelines" as its own skill; AI Agents "no dated job shows it" | The job says "AI Chatbots, Voice Assistants, and RAG pipelines" | Catalogue has no PHP/WordPress/e-commerce/automation entries and no "RAG pipelines" alias; all categories null for this person |
| 9 | MCA without a year | "Graduated: 2010-2013" on the line after a wrapped institution name | `ground_education` needs the model's institution string to match one line exactly; "Indore \| Rajiv" vs "Indore\| Rajiv" and the wrap break it |
| 10 | Summary chunk lists the six headings as skills | — | Consequence of 1; pollutes embeddings and keyword search |

**Found later (doc 18):** the text extraction also deleted R1's line "Tech: Laravel, WordPress, WooCommerce, Bitvavo & Coinbase APIs, Apple Pay" (both copies), because header/footer removal treats any short line seen on 60% of the pages as a page header.

**Design limits it exposed:** one LLM call must return everything within `EXTRACTION_MAX_OUTPUT_TOKENS=2048`. A properly extracted resume like this one (60+ skills with evidence) gets close to that, and a 6–10 page resume would be cut off. Input over 16,000 characters is truncated. The skill catalogue was built around the sample resumes (Python, DevOps, cloud).

## Step 13b: Extraction rebuilt for real resumes

**Why:** the audit of EMP-1017 and the 9 real resumes (doc 18) showed that version 1 only worked on our own one-page samples.

**Built** (details in doc 09, section 13):
- **Text extraction:** `.doc` files read directly; upload limit 25 MB; page-header removal only at page edges (it had deleted real lines); symbol-font bullets.
- **Sections:** `sections.py`, detection by shape plus a list of known names, shared with chunking.
- **The model:** returns structure only (jobs, **projects**, education, title); long resumes are read in parts.
- **Skills:** found by code, a 247-skill catalogue with real-world spellings ("Golang", "Postgres", "Twillo", "MySQ", "Quadrant"), placed per job, project, list or mention. Headings and activities are never stored as skills; "worked with a team who used Camunda" is not usage.
- **Years:** implied use (Laravel → PHP), capped by technology age (RAG ≥ 2020) and by durations written next to a skill. Total years from dated jobs, else as stated.
- **Storage:** projects table; `uses` and `source` per skill (added to existing databases at startup).
- **Matching and search:** project chunks; credit for undated skills by number of projects.
- **Agent:** the profile tool lists projects.
- **Bulk upload:** matches file names without a code by the employee's name.
- **Employee page:** a Projects card, "Years / use" per skill, and a note when experience is stated rather than computed.

**Checked:**
- **Offline test set:** 107/107 (`evaluate_real_resumes --offline`).
- **Original Step 5 checks:** 16/16.
- **The 15 sample resumes re-run through the new code:** every change was checked against the text, and all were corrections:
  - Kubernetes 9.8 → 3.0 ("for the last 3 years").
  - React 8.5 → 1.0 ("React (1 yr)").
  - AKS and vLLM capped by technology age.
  - AWS 2.0 → 7.4 (both jobs use it).
- **End to end in the sandbox:**
  - All 9 files went through the API and the worker to "ready", including the `.doc` and the 12.5 MB `.docx`.
  - An old-schema database was migrated at startup.
  - Harsh is now #2 for the RAG role.
  - The employee page renders the projects.
- **Frontend:** types, lint, 70 unit tests, build.

**Decision (user, 2026-11-05):** identical or tailored resumes across employees are normal in a company, so they are not flagged; a near-duplicate check was built and removed. The focus is correct extraction.

**Findings:**
- A test set of real resumes is what found these bugs; our own samples never could.
- Letting code find skills (dictionary + positions) is more reliable than the model's lists.
- A cleaning step must never delete content.

### Step 13b, part 2: skills without a time period (the evidence ladder)

**Why:** 7 of 9 real resumes give no dates per skill. Their years were empty, so a 5-year React Native developer matched like someone who once used it.

**Built:**
- **Years from the strongest rung available:** dated jobs → written project durations → a stated duration → an **estimate** for core skills of undated resumes (stated total × share of projects; shown "≈", counted at 75% in matching).
- **Caps:** career length, technology age, and durations written right next to the skill.
- **New fields:** level (basic / expert), learning, certified-only, and one duration shared by up to 3 skills in a sentence.
- **Storage:** new columns `years_basis` and `level`, added to existing databases at startup.
- **Display:** the employee page and the agent's profile tool show how sure each number is.

**Checked:**
- Offline 151/151, including a synthetic resume for learning, certified and basic.
- The original 16 Step 5 checks still pass.
- Level detection found "Deep experience in Django" (expert) and "Django (basic)" in the samples.
- Six duration phrasings were tested by hand. "Migrated 10 years of archived invoices with Python" is not read as a Python duration.
- In the sandbox: migration, re-extract all, profile API, matching and the employee page ("≈ 5 y" with a tooltip).

**Finding:** the first version of the duration rule attached any duration on a line to the line's only skill. Durations now count only when written right next to the skill.

### Fix: resumes become ready one by one (2026-11-06)

**Problem (user):** after a bulk upload, no resume was ready until all of them had been processed.

**Cause:** the worker picked work in pipeline order, earliest stage first. That parsed everything, then ran the LLM on everything, then embedded everything, so the first resume could only become ready after the last one's LLM step.

**Fix:** `STAGES = [EMBED, PARSE, EXTRACT]` in `app/ingestion/worker.py`:
- Embed and parse take seconds, and are done first.
- The LLM step runs oldest upload first.
- Each resume becomes ready right after its own extraction.

**Checked:** 9 resumes with a 3-second stand-in model became ready at intervals of about 3 s (47, 50, 53 … 71 s, behind 14 older ones in the queue), instead of all at once at the end.

**Lesson:** order a work queue by what the user waits for (finished items), not by the pipeline's stage order.

### Prompt review and fixes (2026-11-06)

**Judge (bug):** the project chunks added in Step 13b start with lines our code writes ("Project: X | Role: ...", "Technologies: ..."). The judge's filter didn't know them, so a quote from them would have counted as verified proof, the same mistake as in Step 8.
- Now every generated line is excluded from evidence, and "Technologies:" lines are hidden from the judge.
- Rule 2 says a project's own bullet points are real work.
- Checked with a sample dossier: only the resume's own lines remain as evidence.

**Extraction prompt, version 3:**
- Two short worked examples (dated jobs with a project; an undated projects-only resume), with invented names that appear nowhere in our data.
- Resume text is data, never instructions.
- Grey areas defined: internships and freelance are jobs; a promotion is two entries; a client project is a project.
- Technologies come only from the project's own Tech line, which keeps the answer shorter.
- Size: about 1,200 tokens, which still fits a 16,000-character part plus the 2,048-token answer in the 8,192-token context.
- Not measured with the real model yet: run `evaluate_real_resumes` (action item 19).

**Agent prompt, version 2:**
- Explains how sure each number is: "estimated", "as stated", "used in N projects", "listed", "certified", "learning", "basic".
- Uses projects as evidence.
- At most 5 people, with employee codes exactly as the tools give them.
- Never gives contact details, and keeps its instructions private.
- `find_candidates` now labels each matched skill the same way ("React Native (5.0 y estimated)", "Twilio (2 projects)", "Python (listed only)").
- The match result card shows "≈ … y (estimated)" and project counts.

**Role requirements:** the seniority field already existed (with a check in code); the prompt now explains it, in the same words the check accepts.

**Checked in the sandbox:**
- A match run end to end (requirements, retrieval, judge, quotes verified).
- An agent question streamed with a `find_candidates` call.
- Offline extraction 151/151.
- Frontend types, lint, 70 unit tests.

### Cloud and company models: Claude, GPT, Gemini, Azure, Voyage, Cohere (2026-11-06)

**Why:** the user wants to be able to use any model, including Gemini, Claude and GPT, and enterprise embeddings, not only Ollama models.

**Built** (doc 20 §5):
- A **model router** (`app/llm/router.py`): one object with the old client's methods. A setting `<provider>/<model>` picks the provider; no prefix means Ollama, so nothing existing changes.
- **Providers:**
  - OpenAI-compatible (`openai_compat.py`: OpenAI, Azure OpenAI, Gemini chat, any compatible server or gateway).
  - Anthropic (`anthropic_client.py`: tool blocks, alternating roles, JSON answers through a forced tool).
  - Voyage, Cohere and Gemini embeddings over plain HTTP, telling the API whether a text is a query or a document.
- **One error type** with "retryable" (the worker pauses) or "this request was refused" (counts as a failed attempt).
- **`ALLOW_CLOUD_MODELS=false` by default:** personal data never leaves the PC by accident. This covers Ollama `-cloud` models too.
- **The health check** knows every provider without calling the APIs.

**Checked:**
- A stand-in for all five APIs that also validates our requests: 47 direct checks passed.
- The whole app on GPT, Claude and Voyage: re-embed, re-extract, judged match run.
- The agent evaluation gives **identical results on Claude, GPT and Ollama**.
- The block and error paths.

**Found in testing:**
- The newest Anthropic SDK dropped the `temperature` argument, so it is now sent as raw JSON.
- An empty `.env` value followed by a comment was read as that comment.

**Not possible here:** real API calls (no keys). The first real run per provider is the test.

**Review pass:**
- **`EMBED_DIMENSIONS` didn't trigger a re-embed (fixed):** it now does, through a "model@size" signature. Tested: one re-embed, then none.
- **Remote or `-cloud` Ollama models skipped the pulled-models check (fixed).**
- **`$ref`s are now resolved** in schemas sent to OpenAI-compatible services.
- **The dev similarity tool** now embeds the query and the document with their own kinds.
- **The PC's `docs/12` was an older version (fixed):** an earlier delivery had missed it.
- **Byte comparison:** all 262 code files (backend `app`, `scripts`, `evaluation` and frontend `src`) on the PC equal the tested copies.
- **Checks re-run:** provider checks 47/47, extraction 151/151, agent evaluation unchanged.

### Any model from `.env` (2026-11-06)

**Why:** the user wants to try newer models (Qwen 3.5, qwen3-embedding) and to switch any of the three in the future without code changes (doc 20).

**Built:** `app/llm/models.py` holds all model-specific knowledge:
- the embedding prompts of 12 model families, with `.env` overrides for any other;
- `LLM_THINK=off` sends `think:false`, with a one-time retry without the flag for models that reject it;
- `<think>` text is stripped from answers;
- each task's model can be `fast`, `quality` or any model name;
- one ChromaDB collection per embedding model (nomic keeps `resume_chunks`), with automatic re-embedding at startup of resumes made with another model.

Every report and the server log now name the models in use.

**Checked against a stand-in Ollama over HTTP:**
- The think flag in all three modes, plus the retry in normal and streaming calls.
- A switch to `qwen3-embedding:0.6b` + `qwen3.5:4b/9b` by environment variables only: 23 resumes were re-embedded into a 1,024-number collection with the right query prompt. The switch back to nomic worked the same way.

**Finding along the way:** in the real-retrieval test, "Go" ranks Rahul (sample employee, 6.2 dated years) above Vishal (R9, 9 years as stated, undated). That's the evidence ladder working as designed, and it was the same before the depth change. But the test's expected list only has R9, so its MRR shows 0.93. Rahul is a valid answer, so the expected list should include him.

**On the PC:**
- Pull `qwen3.5:4b`, `qwen3.5:9b` and `qwen3-embedding:0.6b`.
- Run the baseline report first.
- Change the `.env` lines, restart, re-extract, then run the report again.

### Step 14c: feedback in the portal (2026-11-06)

**Built** (doc 19, section 10):
- 👍/👎 with reasons and a note on every match result and every assistant answer.
- A `feedback` table: one rating per person per item, the label (role + employee) kept even if the run is deleted, and a snapshot of what was seen.
- An admin Feedback page with counts and filters.
- `export_feedback`, which writes per-role labels for tuning and draft agent test cases from 👎 answers.

**Checked:**
- 24 API checks: permissions, no double votes, 404/409/422 cases, `message_id` in streaming and non-streaming answers, and labels surviving a deleted conversation.
- A browser run on the production build (match card, chat, admin page, filters, reloads).
- The export.
- Frontend checks pass (76 tests).

**Decisions:**
- **Every signed-in user may rate matches;** they are the people who know the candidates. Only admins see everyone's ratings.
- **Agent answers can only be rated by the asker,** because conversations are private.

**To use on the PC:** restart uvicorn (the table is created at startup), then rate as you work. Run `python -m scripts.export_feedback` once there are ratings.

### Step 14a/14b: evaluation (2026-11-06)

**Built** (doc 19):
- `evaluation/agent_cases.json`: 14 cases (single and multi-turn). `scripts/evaluate_agent.py` runs them through the real agent loop with 21 kinds of automatic checks.
- `scripts/evaluate_all.py` runs every suite, writes a report, and flags regressions against each suite's last run.
- Reports are git-ignored (real names).

**Evaluator tested both ways with a stand-in model:**
- Good answers pass (except A09, which needs real embeddings).
- Planted mistakes are all caught (41 failed checks), each with a reason: an invented person, an invented "12 years", reversed order, an email address, the wrong person on the follow-up, the system prompt printed.
- Regression detection was provoked on purpose and reported. A stopped server gives "skipped", not "failed".

**Finding from the first run:**
- `find_candidates` ranked Meera (5.3 y Python) above Ananya (9.3 y), even after the depth fix. The 15% "relevance" (search position) was noise for a bare skill list ("Experience with Python") and outweighed depth.
- **Fix:** without a description, skills alone decide (times the HR factors).
- Python → 9.3, 5.3, 4.4, 2.5. Kubernetes + AWS → Priya (free now) before Fatima (free from 15 Nov).

**On the PC:** `load_real_resumes --wait`, restart the server, then `evaluate_all --note "baseline"` (the agent suite takes about 14 × 1–2 min).

### The agent listed people without the skill (2026-11-06)

**Report:** "find me WordPress developer" answered with Ajay and then Rohan Mehta and Arjun Reddy, who have neither WordPress nor PHP.

**Cause:**
- `find_candidates` returned the top 5 of the fused ranking. Only Ajay had WordPress. The other four came from the meaning and keyword search ("web developer", "experience"), each with `missing: ["WordPress"]`, and the model presented them as candidates.
- The years in that answer ("5.2 y, last used 2018") were copied correctly from the tool. They came from Ajay's old extraction (the conversation is from 30 Oct). After this week's re-extraction his WordPress is 13.8 y, last used 2026. So re-extraction fixed the numbers. The empty candidates were a real bug in the tool.

**Fix:**
- The tool drops people with none of the required skills, from a 4 × wider pool. People whose resume text names the skill are kept and labelled.
- A `note` and a per-person `summary` line go to the model, and prompt v3 says to copy them and never pad the list.

**Checked (copy of the PC database):**
- WordPress returns only Ajay, with the note.
- Kubernetes + AWS returns 6 qualified people (the best shown), and those with only one skill list the other as missing.
- Elementor and Cobol return "nobody has it".
- A non-catalogue term found in the text is kept and labelled.
- Known-skill text checks follow the extraction rules ("we go live" is not Go).

**Then fixed (same day): more years rank higher.** With no minimum years, 2 years counted as "enough", so 2.5 and 9.3 years of Python earned the same credit. The skill credit now includes a depth part, `0.25 × ln(1+y)/ln(11)`, next to "meets the minimum" (0.35); see doc 11.
- "Python" now ranks Ananya 9.3 y > Meera 5.3 y > Kavya 4.4 y > Karthik 2.5 y. Before it was 5.3, 9.3, 2.5, 4.4.
- No evaluation got worse: retrieval R@5 0.83 / MRR 1.00, matching nDCG@5 0.96 / pairs 0.94, real retrieval 7/7, each before and after.

### Match runs listed and judged people without the skill (2026-11-06)

**Report:** a WordPress role, top 3, judge 2. Only Ajay has WordPress, yet Ananya Iyer (no WordPress, no PHP) was #2 with 0.00 and "waiting for the judge". The judge time was wasted on someone everyone could see was wrong. The agent had been fixed for this earlier that day; match runs had not, although the notes suggested both were covered.

**Fix:** match runs use the agent's rule, moved to `app/matching/eligibility.py`: wider pool, keep only people with at least one must-have (skill row or named in the resume text), then score and keep `top_k`. The judge runs only for people with skill evidence; a run with nobody to judge completes at once. The page tells how many people were left out. Details in doc 12 §5.10.

**Checked:** WordPress → Ajay 1.00 and Harsh 0.38 (his resume names WordPress APIs), Ananya and 17 others left out; Rust → empty, completed, no judge; sample roles unchanged at the top; agent evaluation unchanged; frontend check (76 tests) and build pass.

**Lesson:** when one fix applies to two paths (agent and match runs), put the rule in one shared module and test both paths, not just the one in the report.

### Original resumes visible to admins (2026-11-06)

**Question from the user:** where are the current and earlier resumes, and how does an admin see the actual file?

**Finding:**
- Every version was always stored, under `data/uploads/<EMPLOYEE_CODE>/`, and listed under "Resume versions" on the employee page.
- But there was no way to open the file: no endpoint served it. On screens narrower than 1024 px, that card also sits below a long profile.
- A second problem: older versions showed "Searchable", although their chunks are removed from the search indexes when a newer version arrives.

**Built:**
- `GET /api/resumes/{id}/file` (admins only). It serves the exact bytes under the uploaded name: PDFs inline, Word files as a download. It checks that the stored path is inside the upload folder.
- The relay `/bff/resumes/{id}/file`, which passes the cookie to FastAPI as a Bearer token and streams the file back.
- "Open" and "Download" in the employee header (current resume), on every version, and in the `/resumes` list.
- Version numbers and page counts, and the "Older version · not searched" badge.
- The API types were regenerated, which also added the `rerank` signal that the previous step had missed in `schema.d.ts`.

**Checked (copy of the PC database, production build, Playwright):**
- PDF and Word downloads are byte-identical to the originals. The PDF opens in Chromium's viewer.
- After a second version was uploaded, v1 can still be opened and is marked not searched.
- A resource manager sees no buttons and gets 403 on the URL. Logged out, the URL redirects to the login page.
- A missing file gives a clear 404, and a bad id gives 404.
- Frontend checks (types, lint, format) pass, with 72 tests.

**Follow-up worth considering:** `GET /api/resumes/{id}?full_text=true` returns the full extracted text, contact details included, to any signed-in user. If that matters, make it admin-only too (or strip contacts for non-admins).

### Chunking and retrieval upgrades from industry practice (2026-11-06)

**Built** (details in doc 10, section 13):
- **Code-only profile card:** the model-written summary was removed from it.
- **Chunk metadata:** entry, type, name, role and technologies, stored in `resume_chunks.meta` and ChromaDB.
- **Small-to-big dossiers:** the judge gets whole entries, the most relevant first, so long resumes no longer lose their projects.
- **Optional cross-encoder reranker** as a 4th retrieval signal.
- **`evaluate_real_retrieval`:** 7 queries on the real resumes.
- **Fixes:** chunk splitting no longer cuts inside a word; the judge's experience line says when the total is stated.

**Checked:**
- 305/305 merged entries identical to the unsplit text.
- Dossiers built from the database (Ajay: Patrishi Sports included for a React + MySQL role; Mahesh: experience labelled as stated; no generated lines in the evidence).
- Rerank on, off and unavailable.
- The migration adds `resume_chunks.meta`, and every chunk got metadata after re-extraction.
- Retrieval script: hybrid 7/7 hit@3 with stand-in embeddings.
- Offline extraction: 151/151.

**On the PC:**
1. Restart the backend, then **Re-extract all**, so the chunks get the new metadata and card.
2. Run `python -m scripts.load_real_resumes --wait` (server running), then `python -m scripts.evaluate_real_retrieval` (Ollama running), and note the numbers.
3. To try the reranker: `pip install fastembed`, set `RERANK_MODEL=Xenova/ms-marco-MiniLM-L-6-v2`, run with `--compare-rerank`, and keep it only if the numbers improve.

**Fix (same day):** the first run on the PC stopped with `TypeError: OllamaClient.__init__() got an unexpected keyword argument 'timeout'` in `evaluate_real_retrieval` (and in `evaluate_real_resumes` when run with the real model). The parameter is `timeout_seconds`; both scripts now pass it positionally, like `main.py`. It was not caught because the sandbox test replaced `OllamaClient` with a stand-in class. The scripts are now tested with the real client against a stand-in Ollama over HTTP. **Lesson:** test with the real objects and fake only the network.

The same run showed that only R1 (Ajay) was in the database. The new `scripts/load_real_resumes.py` loads R2 to R9, each on its own test employee. R7 and R8 are two versions of Vineet's resume, and one employee has only one current resume, so they need separate employees. It was tested on a copy of the PC database: 8 queued and 1 skipped, a second run skipped all 9, and the worker made all 9 ready. Then `evaluate_real_retrieval` ran with the real client: hybrid 7/7 hit@3, MRR 1.00 with stand-in embeddings. The real numbers come from the PC run.

**Finding:** the judge's dossier cut long resumes at a fixed length in resume order, so relevance never decided what it read. That has been the case since Step 8, and only a long real resume showed it.


## Step 15: production deployment on any cloud (2026-11-11)

**Goal:** be able to run on AWS, Google Cloud, Azure or our own server without changing code: any model provider (Bedrock and Vertex AI added), PostgreSQL + pgvector next to SQLite, files in any bucket, jobs through any queue with separate workers, and Docker. Details: doc 21.

**Built:**
- 15a `bedrock/` (Converse, three structured-output modes) and `vertex/` (Gemini, Claude on Vertex, embeddings).
- 15b Alembic migrations (`0001` baseline, `0002` leases), PostgreSQL full-text with FTS5's BM25, pgvector, `migrate_to_postgres`.
- 15c `app/storage` (local, S3, GCS, Azure Blob) and `migrate_files`.
- 15d `app/jobs`: queues (local, SQS, Pub/Sub, Service Bus), leases, sweeper, heartbeats, `python -m app.worker`.
- 15e Dockerfiles and compose; live/ready probes.
- A pytest suite, 53 tests, run on both databases (51 run on each; the rest are checks for the other database).

**Findings (bugs the tests caught before they reached anyone):**
1. **PostgreSQL ranked the wrong chunk first.** `ts_rank_cd` put "Kubernetes basics." above a chunk naming Kubernetes AND Terraform: it rewards short text and ignores term rarity. Replaced by FTS5's exact BM25 computed in SQL, plus FTS5's word splitting ("node.js" → node js). On a copy of our data: the same people top every match run, top 10 keyword hits identical, 17–18 of 20 keyword ranks equal (the rest are near-ties). Lesson: when you switch a ranking component, compare the rankings, not just "it returns results".
2. **SQLite ignores `VARCHAR(n)`, PostgreSQL refuses the row.** A long LLM-written title would work locally and fail in production. Now text is cut to the column (with a warning) on both.
3. **`now()` on PostgreSQL uses the server's time zone.** Every connection now sets UTC. A test runs with the database's zone set to Asia/Kolkata.
4. **NULLs sort first on PostgreSQL in `DESC`.** Jobs without dates jumped to the top. Fixed with `nulls_last()`.
5. **Claims raced.** The old worker read "the next queued resume" and then updated it, so two workers could take the same one. Claims are now one conditional UPDATE, and a test with 8 simultaneous claims gets exactly one winner.
6. **A storage key `a//b.pdf` passed validation.** S3 treats it as different from `a/b.pdf`. Empty segments are now refused.
7. **A failed upload could delete another upload's file.** Two identical files uploaded at the same moment share a key, and the loser's clean-up removed it. The clean-up now checks first.
8. **Docker: a new volume is owned by root.** Uploads failed in the container. The image now pre-creates its data folders for the app user, and a storage failure is a clear 503, not a 500.
9. **Docker: `public/` doesn't exist in git** (it's empty). The portal image build would have failed on the PC. The Dockerfile creates it.
10. **A stopped judge failed the run.** Now the run is handed over, and another worker completes it with the verdicts already made.

**Verified with real processes:**
- An API and 2 workers on PostgreSQL with SQS and S3 (moto server). A worker was killed with `kill -9` in the middle of an LLM step: its resume returned after the lease ran out, and all 6 resumes became READY.
- A worker stopped mid-judging: another worker finished the run.
- The full compose stack (postgres, migrate, api, worker, portal): upload through the portal, processing in the worker container, `--scale worker=3`.
- The earlier suites are unchanged: provider checks 47/47, agent evaluation 12/14 as before (stand-in limits).

**Fixed in the cross-check (same day), two problems:**

1. **Data loss risk on SQLite (serious).** When a migration makes SQLite rebuild a table, SQLite drops the old table. The app turns foreign keys on for every connection, so dropping `resumes` would have cascade-deleted every chunk, skill and match result. Shown on a copy of the PC data, rebuilding `resumes` left 212 → 0 chunks, 515 → 0 skills and 190 → 0 match results. Today's upgrade (0002) only adds columns, so nothing was rebuilt and no data was lost; a future migration would have done it. `migrate()` now runs migrations with foreign keys off, checks integrity afterwards, and turns them back on. On the same copy, down to 0001 and back up keeps 212/515/190. A regression test fails without the fix. **Lesson:** a migration test must run on a database that has rows in child tables, not only on an empty one.
2. **The tests weren't isolated.** They claimed never to read `backend/.env`, but the shared settings still loaded it. With a real `.env` (a cloud queue, cloud storage, a reranker) the suite stopped before running. The test setup now switches `.env` off for the whole run. It was checked with such a `.env`: every test passed on both databases. **Lesson:** test that the tests are isolated, by running them in a hostile environment.

**Still to do:** SSO, observability (OpenTelemetry, Langfuse), Terraform/Bicep, CI/CD, and a first run against the real Pub/Sub and Service Bus.
