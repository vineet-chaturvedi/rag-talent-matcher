# 11 · Step 7 Explained: Hybrid Retrieval

This document explains Step 7 from start to finish: **why** it exists, **what** it does for a user, **how** every part works (with the AI ideas behind it), **every file** that was added or changed, and **which alternatives** exist, from hobby projects to world-class enterprise systems.

**Read first:** 09 (Step 5) and 10 (Step 6 Explained). **Read with:** 03 (AI & RAG Concepts, §5) for the theory, 04 (Pipeline Deep Dive, stage ⑩) for real example data, 05 for the endpoint reference, 07 for the measured results.

---

## 1. Why we need Step 7

### 1.1 Where we were after Step 6
After Steps 4–6 every resume exists in **three forms**:

| Form | Made in | Good at | Bad at |
|---|---|---|---|
| **Structured facts** (skills, years, last used, jobs) in SQLite | Step 5 | Exact questions: "who has Django ≥ 5 years?" | Anything not in the skill catalog; wording; context |
| **Chunks of original text** in SQLite | Step 6 | Evidence a person can read | Nothing by themselves; they need a search |
| **Vectors** (meaning) in ChromaDB | Step 6 | "Similar meaning" ("container orchestration" ≈ "EKS clusters") | Exact rare terms ("k8s", "CKA"), counting years, "always returns someone" |

Step 6's semantic search could answer one free-text question with **one** of these forms. The Step 6 test showed its limits: Priya, the obvious DevOps match, came **second** to Ananya by 0.006 because her resume says "k8s", which the embedding model barely links to "container orchestration".

### 1.2 The real question is not a search box
A resource manager doesn't type a query. They have a **role**: a title, a description, an allocation (100% or 50%), a start date. The real question is:

> *"Of our 2,000 employees, which 15 are worth a closer look for this role?"*

That needs four things Step 6 didn't have:
1. **Understand the role**: turn its free text into requirements (must-have vs nice-to-have skills, years, seniority).
2. **Use all three forms of the resume**, because each covers another's blind spot.
3. **Merge** their opinions into one ranking.
4. **Respect facts from HR**: is the person free, and from when?

### 1.3 What Step 7 is, in one sentence
> **Step 7 turns a project role into structured requirements and finds the most relevant employees by combining three independent searches (structured skills, keywords, meaning) into one ranked shortlist with evidence and availability.**

In RAG terms, this is the **"R" (Retrieval)** done properly. Steps 4–6 built the knowledge base; Step 7 retrieves from it; Step 8 adds the **"G" (Generation)**: an LLM judge that reads the shortlist and explains its verdict.

### 1.4 Why retrieval and judging are separate steps
```
2,000 employees ──Step 7 (≈100 ms, no LLM writing)──▶ top 15 ──Step 8 (LLM, ~1 min each)──▶ ranked with reasons
```
The LLM judge costs ~60 s per person on this PC. Judging 2,000 people would take 33 hours **per role**. Retrieval is the cheap, fast filter that decides who is worth the expensive look. That's why retrieval's goal is **recall** ("never miss the right person"), and Step 8's goal is **precision** ("put them in the right order and explain it"). This *retrieve-then-rerank* pattern is how every large search system works, from Google to LinkedIn Recruiter.

---

## 2. What it looks like for the user

**Resource manager (end-user view):**
1. Creates a project ("Retail Platform Migration") and a role ("DevOps / Platform Engineer", 100%, from 15 Nov).
2. Pastes the role description. Clicks "Analyse". About a minute later sees what the AI understood:
   *Must have: Kubernetes, Terraform, CI/CD, AWS · Nice to have: Helm, ArgoCD, Prometheus, Grafana.*
3. Corrects it if needed (e.g. moves AWS to nice-to-have). The system remembers that a person edited it.
4. Clicks "Find candidates". Instantly sees a list, and for each person:
   - which requirements they meet, **exactly** ("Kubernetes") or **implied** ("Amazon EKS ⇒ Kubernetes"), with years and when last used;
   - which must-haves are **missing**;
   - **quotes** from the resume ("… Skills - [k8s] (EKS) - [Helm] - [Terraform] - [AWS] …");
   - **availability**: "100% free now" or "only 50% free (role needs 100%); available from 1 Jan 2027";
   - optionally only people who are free in time (`only_available`).

(The screens arrive in Steps 11–13; today you use `/docs` or the scripts.)

**Developer view:** seven new endpoints, a new package `app/matching/`, a keyword index inside SQLite, two scripts, and an evaluation that measures quality with numbers.

---

## 3. The flow, in the order it runs

### 3.1 Once per role: understand it
```
POST /api/projects/{id}/roles  ──▶ row in project_roles (title, description, allocation, start date)
POST /api/roles/{id}/requirements/parse
   app/api/projects.py: parse_requirements()
     └─ app/matching/requirements.py: parse_role()
          1. build_messages()        system rules + skill catalog names + <role_description> fence
          2. ollama.chat(...)        qwen2.5:7b, temperature 0, JSON schema → ~30-60 s
          3. model_validate_json()   Pydantic checks the shape (else RoleParseError → HTTP 502)
          4. normalise_requirements()  CODE cleans the AI's names: catalog spellings, split compounds,
                                       remove duplicates, must-have wins over nice-to-have
     └─ role.requirements = {...};  fill role.min_experience_years / location if empty;  COMMIT
(PUT /api/roles/{id}/requirements: a person's corrections, normalised the same way, edited_by_user = true)
```

### 3.2 Every search: find candidates (~100 ms)
```
POST /api/roles/{id}/candidates  {"top_k": 15, "only_available": false, "signals": [...]}
   app/api/projects.py: find_candidates()     409 if the role isn't parsed yet
     └─ app/matching/retrieval.py: retrieve_candidates()
          0. normalise requirements again (stored roles get the latest catalog rules) and, unless a person
             edited them, drop years and domains the description doesn't state (ground_in_description)
          1. ELIGIBLE: one SQL query — current + READY resumes of active employees, with their skills
                       check_availability() for each; drop non-fitting people if only_available
          2. ① SKILLS  : skills_signal()     credits per requirement × rarity, gated nice-to-haves  → ranking A
          3. ② KEYWORD : keyword_search()    FTS5 BM25 over chunks for all spellings              → ranking B
          4. ③ VECTOR  : embed_query() + ChromaDB, filtered to eligible employee ids               → ranking C
          5. FUSION    : reciprocal_rank_fusion(A, B, C)  → one score per person
          6. keep each person's rank in every list + evidence; sort; top_k; timings
     └─ CandidatesResponse (JSON)
```

### 3.3 How the data gets there (changes to ingestion)
```
worker: extracted ──▶ embed stage (app/services/indexing.py)
   build_chunks()   now adds "Skills used: Kubernetes, Terraform…" to each job chunk, neutral pronouns
   embed → ChromaDB
   ONE SQLite transaction:  resume_chunks rows  +  chunks_fts rows (keyword index)  +  status = READY
startup (app/main.py): ensure_keyword_index()  creates chunks_fts; rebuilds it if its row count ≠ resume_chunks
delete / new version (app/services/resumes.py): removes old rows from chunks_fts and ChromaDB
```

---

## 4. The AI ideas in Step 7

### 4.1 Query understanding (role parsing)
**What:** turning the user's need into a structured query before searching. Search engines do this constantly (spelling correction, detecting "near me", splitting product and brand).

**How we do it:** the LLM reads the description once and fills a JSON form (`RoleRequirementsLLM`): `seniority`, `must_have[]`, `nice_to_have[]`, `min_total_years`, `location`, `domain[]`, `search_summary`. The **skill catalog names are put into the prompt**, so the model tends to answer with the same names resume extraction uses. Then **code normalises** them anyway, because Step 7b proved models paraphrase: the 7B wrote *"retrieval-augmented generation using vector databases"* instead of "RAG" + "Vector Databases".

**Why an LLM here and not for every search:** it runs **once per role** and the result is **stored**, so 30–60 s is fine, and the quality model can be used. The search itself never waits for an LLM.

**Why the result is editable:** an AI interpretation that decides who gets considered for work must be correctable by a person, and it must be recorded who did what (`parsed_by`, `parsed_at`, `edited_by_user`). That's basic **human oversight**. The EU AI Act lists AI used for employment decisions (recruitment, promotion, allocating tasks) as **high-risk** and requires human oversight for it.

**Code checks the AI's numbers too (`ground_in_description`).** Measured on this PC: for the DevOps role, whose description names **no years at all**, the 7B model wrote "Kubernetes 3 years, Terraform 2, CI/CD 2, AWS 3, 5 years in total" and the domain "cloud". All invented. Now a number of years is kept only if that number is written next to "years" in the role's title or description, and a domain only if its word appears there. This runs when parsing **and** at search time (so already-stored roles are cleaned too), except for requirements a person has edited, which are trusted as they are.

**Alternatives:**
| Option | Pros | Cons |
|---|---|---|
| **Form with a skill picker** (no AI) | Exact, no model needed | More work for the manager; misses nuance in free text |
| **LLM with JSON schema (ours)** | Free text in, structure out; local | Needs normalisation; ~1 min on CPU |
| Cloud LLM function calling (GPT-4-class, Claude) | Better understanding, fast | Data leaves the company (role descriptions are less sensitive than resumes) |
| **HyDE** (Hypothetical Document Embeddings) | Generate an "ideal resume" and embed it: better vector matches | More LLM time; can invent details |
| Query expansion with a taxonomy | Adds synonyms and related skills automatically | Needs a good taxonomy |

### 4.2 Hybrid search: why three signals
No single method is good at everything:

| Example | Skills (structured) | Keyword (BM25) | Vector (meaning) |
|---|---|---|---|
| Resume says "k8s", role says "Kubernetes" | ✅ catalog maps it | ✅ all spellings searched | ⚠️ weak link |
| Role says "design systems", resume "component library" | ❌ not in catalog | ❌ different words | ✅ similar meaning |
| Rare exact term "CKA" or "SAP FICO" | only if in catalog | ✅ rare words score high | ⚠️ blurred |
| "at least 5 years of Django", "used recently" | ✅ years and last-used year | ❌ | ❌ |
| Domain "insurance claims" | ❌ | ✅ | ✅ |

Each signal makes **different mistakes**. When they're combined, a person found by **several** signals rises, and one signal's mistake is outvoted by the others. This is the same reason a hiring panel has several interviewers.

### 4.3 Signal ①: structured skill matching
Uses Step 5's verified facts (`resume_skills`: skill, years, last used year, evidence quote).

**For each requirement, find the employee's best matching skill** (`_best_match`):
- **direct** match: the same canonical name (case-insensitive);
- **implied** match: a skill that implies the requirement (`SKILL_IMPLIES`: Amazon EKS ⇒ Kubernetes and AWS; Django REST Framework ⇒ Django; vLLM ⇒ LLMs).

**Give it a credit between 0 and 1** (`_credit`):
```
credit = base × years factor × recency
  base      1.0 direct · 0.6 implied
  years     0.4 + 0.35 × min(1, years ÷ needed) + 0.25 × depth(years)
            needed = the role's min_years, else 2;  depth = ln(1 + years) ÷ ln(11), at most 1 (full at 10 years)
            unknown years → by projects (0.6 … 0.9), see doc 09 §13.6
  recency   last used ≤ 1 year ago 1.0 · ≤ 3 years 0.8 · older 0.5 · unknown 0.8
```
**Depth (2026-11-06).** The years factor used to stop growing once the minimum was met. With no minimum (2 years assumed), 2.5 and 9.3 years of Python earned the same credit, so the search order decided who came first, and the agent ranked a 2.5-year Python developer above a 9.3-year one.
- The factor now has two parts. **Meeting the minimum** stays the larger part (0.35): it is what the role asks for.
- **Depth** (0.25) keeps rewarding more years, with diminishing returns: going from 2 to 4 years counts more than going from 8 to 10.
- With no minimum stated, the years factor is 2 y → 0.87, 5 y → 0.94, 9.3 y → 0.99. With a 5-year minimum, 3 y → 0.75 and 5 y → 0.94.
- On the PC database, "Python" now ranks 9.3 y > 5.3 y > 4.4 y > 2.5 y (availability can still move someone down).
- Checked: `evaluate_retrieval` (R@5 0.83, R@10 1.00, MRR 1.00), `evaluate_matching` (nDCG@5 0.96, pairs 0.94) and `evaluate_real_retrieval` (hybrid 7/7) are unchanged. Their roles state minimum years, so the change mostly affects open "find a Python developer" questions.
- Experience in a framework counts for its language in two places. Extraction gives the language the framework's job years (a Django job also counts as Python use). At match time, a framework can stand in for a required skill it implies (implied match, base 0.6).
Examples:
- Priya, Kubernetes, 6.2 years, last used 2026 → 1.0 × (0.4 + 0.35 + 0.25 × 0.83) × 1.0 = **0.96**.
- Divya, Django, last used 2019 → recency 0.5, so at most **0.5**: "hands-on long ago" counts less than "hands-on now".
- Siddharth, AKS for a Kubernetes requirement → implied, 0.6 × … ≈ **0.6**.

**Weight each requirement by rarity** (`rarity_weight`, Step 7b):
```
rarity = 1 + ln((N + 1) ÷ (n + 1))       N = eligible people, n = people who have that skill
```
This is **IDF** ("inverse document frequency"), the core idea of BM25, applied to skills. With 14 people: Python (most have it) → 1.31; RAG (one person) → 3.0. A skill that *defines* the role counts more than a skill everybody has.

**Combine, with nice-to-haves gated by must-haves** (Step 7b):
```
must part  = Σ 2 × rarity × credit      (must-haves count double)
nice part  = Σ 1 × rarity × credit
coverage   = must part ÷ maximum possible must part
skill score = (must part + nice part × coverage) ÷ (max must part + max nice part)
```
Without the gate, Rohan (Python + FastAPI + Docker, no LLM experience) outranked Fatima (LLM serving) for the GenAI role, the exact trap in `roles.json`. Nice-to-haves now only count as far as the core of the role is met.

**Why structured matching at all, when we have vectors?** It's the only signal that understands **years**, **recency** and **implications**, and it's fully **explainable**: "Kubernetes ✓ (via Amazon EKS, 6 years, used 2026)".

### 4.4 Signal ②: keyword search with BM25 (SQLite FTS5)
**Inverted index:** instead of storing "chunk → words", FTS5 stores "word → which chunks contain it, and where":
```
"terraform" → chunk 3_1 (pos 14, 22), chunk 13_2 (pos 5), chunk 12_1 (pos 9)
"k8s"       → chunk 3_1 (pos 8), chunk 14_2 (pos 31)
```
A query only touches the lists of its own words: milliseconds even for millions of chunks.

**BM25 score** for a chunk, summed over the query words it contains:
```
              IDF(word) × tf × (k1 + 1)
score = Σ  ─────────────────────────────────────────        k1 ≈ 1.2, b ≈ 0.75
           tf + k1 × (1 − b + b × chunk length ÷ average length)
```
- **tf** (term frequency): the word appears more often → higher, with **diminishing returns** (saying "Kubernetes" 10 times isn't 10× better).
- **IDF**: a rare word ("terraform") counts far more than a common one ("experience").
- **Length normalisation**: a long chunk that mentions a word once is less focused than a short one.

SQLite's `bm25()` returns the score **negated** (more negative = better), so we `ORDER BY score` ascending.

**What we send:** every spelling of every required skill from the catalog, plus domains, each as a quoted phrase joined by OR:
```
"kubernetes" OR "k8s" OR "kube" OR "terraform" OR "hashicorp terraform" OR "ci/cd" OR "continuous integration" OR … OR "aws" OR "amazon web services" OR "helm" OR …
```
Quoting makes FTS5 treat each one literally (no accidental operators) and match multi-word phrases. The `unicode61` tokenizer lowercases and splits on punctuation, so "CI/CD" matches "ci cd" too.

Only the spellings of the **required** skills are searched, not of skills that imply them: "eks" is not a Kubernetes spelling, so a resume that only says "EKS" is found by the skills signal (EKS ⇒ Kubernetes), not by keywords.

**Evidence:** `snippet()` returns ~16 words around the match with brackets. Real example for Priya: `… Skills - [k8s] (EKS) - [Helm] - [Terraform] - [AWS] - [ArgoCD] - Jenkins …`.

**One person, many chunks:** results are chunks; we keep each person's **best** chunk position as their rank, and their first two snippets as evidence.

### 4.5 Signal ③: vector search (from Step 6, now filtered)
The query text is `search_summary + "Key skills: …"` (the must-haves), embedded with the `search_query:` prefix. ChromaDB returns the 80 nearest chunks, **only from eligible employees**: `where={"employee_id": {"$in": [ids]}}`. Each person's best chunk decides their rank; two chunks are kept as evidence.

**Pre-filtering vs post-filtering:** filtering *during* the search (pre) guarantees the 80 results are all usable. Searching everyone and dropping ineligible people *afterwards* (post) can leave you with almost nothing when most people are busy.

### 4.6 Fusion: Reciprocal Rank Fusion (RRF)
The three signals produce numbers on **incompatible scales**: BM25 −8.1, cosine 0.58, skill score 0.71. Adding them would be meaningless. RRF ignores the numbers and uses **positions**:
```
RRF(person) = Σ over signals   weight ÷ (k + rank in that signal)       k = 60, weight = 1.0

Priya, DevOps role: #1 skills, #1 keyword, #1 vector → 1/61 + 1/61 + 1/61 = 0.0492
Someone #1 in only one list                          → 1/61              = 0.0164
```
- Being **good in several lists** beats being **best in one**.
- **k = 60** (from the original 2009 paper by Cormack, Clarke and Büttcher) flattens the curve, so #1 vs #2 in one list matters little; agreement between lists matters a lot.
- **Weights** (`RRF_WEIGHT_*`) let one signal count more once evaluation shows it's more reliable. We keep 1.0: three roles are too few to tune on.
- RRF is **robust to score compression** (Step 6 found cosine scores bunched in 0.52–0.67).

RRF is what major search platforms ship as their default hybrid method: Elasticsearch (RRF retriever), OpenSearch, Azure AI Search, Qdrant and MongoDB Atlas all offer it.

### 4.7 Availability: facts, not AI
`check_availability()` uses HR data only:
- **free now** if `100 − allocation_percent ≥ role.allocation_percent` and not on leave;
- **free later** if `available_from ≤ role.start_date`.
It produces a readable note and a `fits` flag. Retrieval **reports** availability (and filters with `only_available`); Step 8 will **weigh** it in the final score.

### 4.8 Recall vs precision, and how we measure them
- **Recall@k:** of the people who *should* be found, how many are in the top k? `2 of 2 in top 5 → 1.0`.
- **MRR** (mean reciprocal rank): 1 ÷ the rank of the first right person. `first right person at #2 → 0.5`.
- **Ground truth:** `samples/roles.json` lists the expected people per role, written *before* building, with deliberate **traps** (people who look right but aren't).

`evaluate_retrieval.py` runs hybrid and each signal **alone** (an "ablation study"), so we see what each signal contributes.

**Lesson from Step 7b:** perfect averages (recall@5 = 1.00) hid a real ranking error (the GenAI trap). Always read the top-5 lists, not only the averages.

### 4.9 "The LLM reads, code checks" again
The same principle as Step 5, applied to the role side:
| Task | Who |
|---|---|
| Understand "hands-on Kubernetes in production" is a must-have | LLM |
| Map it to the catalog name "Kubernetes" | Code (catalog lookup, phrase splitting) |
| Decide whether an employee has it, how long, how recently | Code (Step 5 facts) |
| Count, weight, fuse, filter | Code |

The only AI calls in Step 7 are **one LLM call per role** and **one embedding per search**.

---

## 5. The files, one by one

### 5.1 `app/matching/requirements.py` (new): understanding the role
**Purpose:** free-text role → structured, normalised requirements.

**What's inside:**
| Piece | What it does |
|---|---|
| `RequiredSkillLLM`, `RoleRequirementsLLM` | Pydantic classes describing the JSON the LLM must return. `seniority` is a `Literal[...]`, so only the six allowed words are accepted |
| `ROLE_SCHEMA` | `RoleRequirementsLLM.model_json_schema()`: sent to Ollama's `format`, so decoding is **constrained** to this shape |
| `SYSTEM_PROMPT` | The rules: only what the description says; how to tell must from nice; the **catalog names**; one short skill per item; no names in the summary |
| `build_messages()` | System + user message; the description is fenced in `<role_description>` so instructions inside it stay data (prompt-injection defence) |
| `canonical_skills()` | One written requirement → canonical names: "k8s" → Kubernetes; "…using vector databases" → RAG, Vector Databases; unknown → kept |
| `normalise_skill_list()`, `normalise_skill_sections()` | Apply that to lists, merge duplicates case-insensitively, a skill in both lists stays must-have |
| `ground_in_description()` | Drops invented numbers and domains: years only if written next to "years" in the role text; domains only if their word appears in it |
| `parse_role()` | The async LLM call: temperature 0, `num_predict` 1024, checks `done_reason == "length"` (cut off), validates JSON, normalises, grounds, logs |
| `search_terms()` | Builds the keyword-search terms: every spelling of every skill + domains |
| `vector_query()` | Builds the vector-search text: summary + "Key skills: …" |

**Why separate from retrieval:** parsing is slow and happens once; retrieval is fast and happens often. Different reasons to change, different files.

### 5.2 `app/matching/retrieval.py` (new): the heart of Step 7
**Purpose:** role requirements → ranked candidates with evidence.

| Piece | What it does |
|---|---|
| `SkillMatch`, `Availability`, `Candidate` | Dataclasses: plain containers for results. `Candidate.ranks` holds the person's rank in each signal (`None` = not found by it) |
| `check_availability()` | HR facts → `fits` + note (§4.7) |
| `_credit()` | One skill vs one requirement → 0..1 (§4.3) |
| `_best_match()` | Best of the employee's skills for one requirement, direct or implied |
| `rarity_weight()` | IDF for skills |
| `skills_signal()` | Two passes: first find all matches and count how many people have each skill (for rarity), then score everyone, filling `must_matched`, `must_missing`, `nice_matched` |
| `reciprocal_rank_fusion()` | §4.6, ~6 lines |
| `retrieve_candidates()` | The pipeline in §3.2: eligibility query (with `selectinload`, resumes, employees, skill links and skill names come in 4 queries instead of one per person), three signals, fusion, timings (`skills_ms`, `keyword_ms`, `vector_ms`, `found_by`) |

**Why the `signals` parameter:** so evaluation can switch signals off one at a time (ablation), and so a slow or broken signal can be disabled without code changes.

**Why ChromaDB runs in `asyncio.to_thread`:** ChromaDB's client is synchronous; running it in a thread keeps the server responsive to other requests.

### 5.3 `app/rag/keyword_index.py` (new): BM25 inside SQLite
**Purpose:** the keyword index and its search.

| Piece | What it does |
|---|---|
| `_CREATE` | `CREATE VIRTUAL TABLE chunks_fts USING fts5(...)`: a **virtual table** looks like a table but is backed by FTS5's inverted index. Ids are `UNINDEXED` (stored, not searchable) |
| `ensure_keyword_index()` | At startup: create the table; if its row count differs from `resume_chunks`, **rebuild** from it (one `INSERT … SELECT`) |
| `replace_resume_rows()` / `delete_resume_rows()` | Keep the index in step with chunks; called **inside the caller's transaction** |
| `build_match_query()` | Terms → `"a" OR "b" OR …` (quoted, de-duplicated) |
| `keyword_search()` | `MATCH`, `bm25()`, `snippet()`, limited to eligible `resume_id IN (...)` using `bindparam(expanding=True)` |

**Why inside the same transaction:** chunks and their keyword rows are committed together, or not at all, so the two can never disagree. (ChromaDB is a separate store, so there we rely on idempotent re-runs instead.)

**Why FTS5 and not Elasticsearch:** it's already inside SQLite: no server to install, run or secure. At 2,000 resumes (~9,000 chunks) it answers in milliseconds. `IS_SQLITE` checks keep the code safe if the database is switched to PostgreSQL (Step 15 would use PostgreSQL's own full-text search).

### 5.4 `app/api/projects.py` (new): the HTTP layer
Seven endpoints (full reference in document 05):
`POST/GET /api/projects`, `POST /api/projects/{id}/roles`, `GET /api/roles/{id}`, `POST /api/roles/{id}/requirements/parse`, `PUT /api/roles/{id}/requirements`, `POST /api/roles/{id}/candidates`.

**Responsibilities:** HTTP only: find the role (404), translate errors into status codes (Ollama down → 503, unusable LLM answer → 502, not parsed → 409), call the matching layer, and convert dataclasses into response models. No matching logic lives here (layering, document 01 §2).

**Small but important details:** `parse` fills the role's `min_experience_years` and `location` **only if empty** (never overwrites a person's input); `PUT` keeps `parsed_by` and the title, normalises names and sets `edited_by_user`.

### 5.5 `app/schemas/project.py` (new): the API's shapes
Pydantic models for input (`ProjectCreate`, `RoleCreate`, `CandidatesRequest` with `top_k` 1–100, `only_available`, `signals`) and output (`RoleOut`, `ProjectOut`, `Requirements`, `CandidateOut`, `SkillMatchOut`, `AvailabilityOut`, `ChunkEvidence`, `CandidatesResponse`). They validate input (e.g. `allocation_percent` 1–100, description ≥ 20 characters → else 422) and generate the `/docs` page. `from_attributes=True` lets them be built straight from database objects.

### 5.6 Changed files
| File | Change | Why |
|---|---|---|
| `app/extraction/skills.py` | `CI/CD` and `LLM evaluation` in the catalog; `SKILL_IMPLIES` + `implied_by()` (case-insensitive); `skills_in_phrase()` | Implied skills for matching; recognise known skills inside long phrases |
| `app/extraction/postprocess.py` | `normalize_for_match` (public name for the text normaliser) | Reused by chunking to find a job's skills in its text |
| `app/extraction/prompts.py` | Summary without name or gendered words, starting with the job title | Fairness: the Step 8 judge must not see gender |
| `app/rag/chunking.py` | `Skills used: …` line in each job chunk (only skills found in that job's text, via `ground_job_skills`); pronoun neutraliser in `anonymize()` | Keyword and vector search find "k8s" as Kubernetes; safety net for old summaries |
| `app/services/indexing.py` | Writes keyword rows in the same transaction as chunks | Index consistency |
| `app/services/resumes.py` | Deletes keyword rows on new version / delete | No stale search results |
| `app/config.py` | Step 7 settings + `role_parse_model` property | Tunable without code changes |
| `app/main.py` | Registers the router; `ensure_keyword_index()` at startup; version 0.6.0 | Wiring |
| `.env.example` | `EXTRACTION_MODEL_ROLE=fast` + Step 7 block | Documented settings |

### 5.7 Scripts
- **`scripts/load_roles.py`**: reads `samples/roles.json`, creates projects and roles **through the real API** (like the future frontend will), reuses existing ones by name (**idempotent**: safe to run again), parses requirements (`--reparse` to redo) and prints what the AI understood.
- **`scripts/evaluate_retrieval.py`**: for each role, calls `/candidates` four times (hybrid, skills, keyword, vector), computes recall@5, recall@10, MRR, shows the ranks of the expected people and the top 5, then averages. This is our **regression test** for search quality: after any change, run it and compare.

---

## 6. Python you'll meet in Step 7

| Code | Meaning |
|---|---|
| `@dataclass class Candidate: ranks: dict = field(default_factory=lambda: {...})` | A class that just holds data. `default_factory` creates a **new** dict per object (a shared default dict would be a classic bug) |
| `Literal["junior", "mid", ...]` | The value must be one of these exact strings |
| `float \| None` | "a float, or nothing" (optional value) |
| `{**requirements, "must_have": must}` | Copy a dict and override one key |
| `sorted(..., key=lambda c: -c.skill_score)` | Sort by a computed value, highest first |
| `dict.get("must_have", [])` | Read a key, with a default if missing |
| `next((x for x in items if cond), None)` | First matching item, or `None` |
| `enumerate(ids, start=1)` | Loop with a counter starting at 1 (ranks) |
| `text("... :q ...").bindparams(bindparam("ids", expanding=True))` | Raw SQL with **safe parameters**; `expanding` turns a list into `IN (?, ?, ?)`. Never paste user text into SQL yourself (SQL injection) |
| `await asyncio.to_thread(func, args)` | Run blocking code in a thread without freezing the server |
| `math.log(x)` | Natural logarithm (used for rarity) |
| `argparse.ArgumentParser` | Command-line options (`--reparse`, `--base-url`) |
| `httpx.Client(...).post(...).raise_for_status().json()` | Call our API from a script; stop with an error on 4xx/5xx |

---

## 7. Alternatives, industry standards and enterprise options

### 7.1 Component by component
| Component | Ours (learning, one PC) | Common production choice | World-class / enterprise scale |
|---|---|---|---|
| Role understanding | Local LLM + JSON schema + catalog normalisation | Hosted LLM with function calling; structured form as fallback | Skills-inference models trained on millions of job posts (LinkedIn, Eightfold, Workday Skills Cloud) |
| Skills vocabulary | Hand-written `CATALOG` + `SKILL_IMPLIES` (~120 skills) | Open taxonomies: **ESCO** (EU, ~13,900 skills), **O*NET** (US), **Lightcast Open Skills** | Company skills ontology / **knowledge graph** (Neo4j, Amazon Neptune) with "is-a", "requires", "related-to" edges, curated by a team |
| Keyword search | SQLite FTS5 (BM25) | **PostgreSQL full-text search** (`tsvector`, `ts_rank`) or **OpenSearch / Elasticsearch** | Elasticsearch / OpenSearch / **Vespa** / Solr clusters; learned sparse retrieval (**SPLADE**, ELSER, bge-m3 sparse) |
| Vector search | ChromaDB (embedded) | **pgvector** in PostgreSQL, **Qdrant**, Weaviate | Milvus, Vespa, Pinecone, Elasticsearch/OpenSearch k-NN, with replicas and sharding |
| Fusion | RRF, k = 60, equal weights | RRF (built into Elasticsearch, OpenSearch, Azure AI Search, Qdrant, MongoDB Atlas) or normalised weighted sum (Weaviate's default "relative score fusion") | **Learning-to-rank** (LambdaMART / XGBoost) trained on recruiters' past decisions |
| Reranking | — (Step 8: LLM judge) | Cross-encoder (`bge-reranker`, Cohere Rerank) on top 50–100 | Cross-encoders + LLM rerankers + business rules, A/B-tested |
| Availability | Two HR fields | HRIS integration (Workday, SAP SuccessFactors, Oracle HCM) | Live resource-management systems (allocations by week, bookings, PTO calendars) |
| Evaluation | 3 roles, recall@k, MRR | 50–200 labelled roles, nDCG, regression suite in CI | Offline metrics + online A/B tests + human review panels + **bias audits** |

### 7.2 Complete products that do this
Internal talent marketplaces: **Eightfold AI**, **Gloat**, **Workday Skills Cloud / Talent Marketplace**, **SAP SuccessFactors Opportunity Marketplace**, **Beamery**, **Fuel50**. Resource-management tools for services firms: **Kantata**, **Float**, **Planview**. They use the same building blocks at much larger scale: skills inference, a skills ontology, hybrid retrieval, ranking models and availability from HR systems. Building it yourself teaches you what's inside them and keeps the data local.

### 7.3 What "enterprise grade" adds beyond the algorithm
| Area | What it means here |
|---|---|
| **Scale** | Indexes as services (not files), incremental updates, sharding past ~10 M chunks, caching of query embeddings |
| **Latency budgets** | e.g. p95 < 300 ms for retrieval, measured per signal (our `timings` are the start) |
| **Security** | Permission filters inside the search ("this manager can see only these departments"), audit logs, encryption at rest (Step 9, 15) |
| **Explainability** | Every result shows why: matched requirements, evidence, per-signal ranks (we have this) |
| **Fairness & compliance** | Anonymised text, no protected attributes in scoring, regular **adverse-impact checks**; the EU AI Act lists AI for employment decisions, including task allocation and promotion, as **high-risk**; New York City's Local Law 144 requires bias audits for automated tools used in hiring and promotion decisions |
| **Human oversight** | Editable AI interpretations, human makes the final choice (we have this) |
| **Evaluation as a process** | A growing labelled set, run on every change; dashboards over time (Step 14) |
| **Feedback loop** | Record who was finally chosen; use it to tune weights or train a ranking model |

### 7.4 Why we chose what we chose
- **Everything local and in-process** (SQLite FTS5, ChromaDB, Ollama): no servers to run, data never leaves the PC, ideal for learning and for thousands of resumes.
- **RRF over weighted sums:** no score normalisation, robust, the industry default; weights stay available.
- **Hand-written catalog over ESCO:** small, readable, tuned to our samples. ESCO is the upgrade path when the catalog gets too big to maintain.
- **Structured matching as a first-class signal:** in staffing, years and recency matter; text search can't count them.
- **Recall first, judge later:** keeps every search fast and puts the expensive LLM where it adds the most.

---

## 8. Limitations to know about
- **Keyword search uses only the required skills' own spellings**, not those of implied skills (EKS for Kubernetes); the skills signal covers that.
- **An implied skill with known years can beat a direct one with unknown years** (Priya's AWS: 0.6 via Amazon EKS vs 0.48 direct). A deliberate formula choice: known facts count more than unknown ones; revisit in Step 8.
- **The parser can turn sub-points into skills** ("query tuning", "indexing" for the Django role) and copy one stated number onto every skill ("5 years" on Python, Django, PostgreSQL…). Grounding keeps the 5 because it is written; a person can correct it with `PUT`.
- **Step 5 evidence quotes can be wrong** (Jenkins' stored evidence is a Terraform sentence): the skill counts because its name is in the resume. Step 8 must verify quotes.
- **The catalog is only as good as its entries:** an unknown skill matches only exactly (case-insensitive) and through keyword/vector search.
- **Years are an upper bound** (from Step 5's job dates).
- **Minimum total years and seniority are not used in retrieval yet**: Karthik (1.5 y) ranks above Divya for a 5-year role. Step 8 adds this.
- **Three roles are a tiny test set:** recall@10 is almost automatically 1.0 with 15 people; read the ranks and top-5 lists.
- **FTS5 is SQLite-only:** moving to PostgreSQL means switching the keyword index to PostgreSQL full-text search (planned in Step 15).
- **Vector search depends on the wording of chunks:** Fatima's MLOps text is only a partial match for "RAG engineer", which is correct, but shows why the other signals are needed.

---

## 9. Try it yourself
With the server running (`uvicorn app.main:app --port 8010`):
```powershell
# Every role and its parsed requirements
Invoke-RestMethod http://127.0.0.1:8010/api/projects | ConvertTo-Json -Depth 6

# Candidates for the DevOps role, only people who are free in time
$body = '{"top_k": 5, "only_available": true}'
Invoke-RestMethod -Method Post http://127.0.0.1:8010/api/roles/2/candidates -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 6

# One signal alone, to see what it contributes
$body = '{"top_k": 5, "signals": ["keyword"]}'
Invoke-RestMethod -Method Post http://127.0.0.1:8010/api/roles/2/candidates -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 6
```
Experiments worth doing:
1. Set `RRF_WEIGHT_VECTOR=2.0` in `.env`, restart, run `evaluate_retrieval`: what moves?
2. In `/docs`, `PUT` the GenAI role's requirements with "Docker" moved to must-have: who rises?
3. Add your own role to `samples/roles.json` with an expected ranking, then `load_roles` and `evaluate_retrieval`.

---

## 10. Glossary for this step
| Term | Meaning |
|---|---|
| **Retrieval** | Finding the candidate items worth a closer look |
| **Hybrid search** | Combining several retrieval methods |
| **Signal** | One independent source of ranking evidence (skills, keyword, vector) |
| **Inverted index** | word → list of documents containing it |
| **BM25** | Classic keyword ranking formula: term frequency with diminishing returns × rarity (IDF) × length normalisation |
| **IDF** | Inverse document frequency: rare terms count more |
| **FTS5** | SQLite's built-in full-text search engine |
| **RRF** | Reciprocal Rank Fusion: merge rankings by Σ 1/(k + rank) |
| **Pre-filtering** | Restricting the search to eligible items while searching |
| **Query understanding** | Turning the user's request into a structured query |
| **Taxonomy / ontology** | A structured vocabulary of skills and how they relate |
| **Recall@k / MRR** | "How many right people in the top k" / "how high the first right person is" |
| **Ablation** | Turning parts off one at a time to measure their contribution |
| **Retrieve-then-rerank** | Fast, broad search first; slow, careful judging of the shortlist second |
