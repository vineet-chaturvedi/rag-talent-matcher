# 12 · Step 8 Explained: Scoring and the LLM Judge

This document explains Step 8 from start to finish: **why** it exists, **what** the user gets, **how** every part works with the AI ideas behind it, **every file**, and **which alternatives** exist up to enterprise level. The code itself is typed in by hand from the chat (learning by building); this document is the reference.

**Read first:** 11 (Step 7 Explained). **Read with:** 03 (AI & RAG Concepts §5.6, §6), 05 (endpoints), 07 (measurements).

---

## 1. Where Step 8 sits: Steps 1 to 7 as one story

| Step | Gave us | Used by Step 8 for |
|---|---|---|
| 1–2 | Local models, FastAPI, the Ollama client with JSON-schema outputs | The judge's LLM call |
| 3 | 12 tables, including **`match_runs`** and **`match_results`** (designed then, empty until now) | Saving every run for audit |
| 4 | Resume text, the background-worker pattern | Background judging, crash recovery |
| 5 | Verified facts: skills with years and last used, jobs, **total experience** | Experience factor, the judge's fact lines |
| 6 | Anonymised **chunks** of original resume text | The judge's evidence and quote checking |
| 7 | Role **requirements**, hybrid **retrieval** (skills + keyword + vector, RRF), availability | The shortlist and its skill score |
| **8** | **Final ranking with reasons**: rule score + LLM judge with verified quotes, saved per run | Steps 10 (agent) and 13 (agent page) show it |

---

## 2. Why we need Step 8

### 2.1 Retrieval finds; it doesn't decide
Step 7's goal was **recall**: get the right people into the top 10. Its order was good but not final, and it deliberately ignored things that matter for staffing:
- **Experience:** Karthik (2.4 years) ranked near Divya (13 years) for a role that asks for "at least 5 years".
- **Availability:** reported, but not used in the order.
- **Location:** not used at all.
- **Reading:** no part of Step 7 actually *reads* a candidate's experience against the role. The skill score counts skills; it can't tell that "rebuilt claims-processing APIs serving 2M requests/day" is strong evidence for a senior backend role.
- **Explanation:** a resource manager needs *why*, with proof, not a number.

### 2.2 What Step 8 is, in one sentence
> **Step 8 turns the retrieval shortlist into a final, explained ranking: a transparent rule score (skills, experience, availability, location) for everyone, plus an LLM judge that reads the top candidates' anonymised resume evidence and assesses each must-have with an exact quote that code verifies, all saved as an auditable match run.**

In RAG terms this is the **"G" (generation)**: the LLM reads the retrieved context and produces an answer (here, a structured assessment), **grounded** in that context with **citations**.

### 2.3 Why two scores, not just the LLM
| | Rule score (code) | LLM judge |
|---|---|---|
| Speed | Milliseconds, for all 10 | ~45–100 s **per person** on this CPU |
| Consistent | Always the same result | Mostly (temperature 0), but sensitive to wording |
| Understands text | No: counts skills and years | Yes: reads what the person actually did |
| Explainable | Every number shown | Strengths, gaps and quotes |
| Can be wrong by | Missing nuance | Inventing, misreading, poor calibration |

Each covers the other's weakness. This is the **retrieve → score → rerank** pattern used by large search and recommendation systems: cheap methods for many items, expensive careful methods for the few that matter.

---

## 3. What it looks like for the user

**Resource manager:**
1. Opens a role, clicks "Find best matches".
2. Immediately sees a ranked list of 10 with scores and the facts behind them: skills matched (direct/implied, years, last used), missing must-haves, availability ("only 50% free; role needs 100%"), location.
3. Over the next few minutes the top 5 fill in with the judge's verdict: per must-have "yes / partly / no" with a **quote from the resume**, up to 3 strengths with quotes, up to 3 gaps, a one-line summary and a rating. Quotes that couldn't be found in the resume are flagged.
4. Can open earlier runs for the same role: what was recommended, when, with which settings.

**Developer:** three endpoints, a run that continues in the background, and an evaluation script that measures the final order (nDCG, MRR, pair order).

---

## 4. The flow, in the order it runs

```
POST /api/roles/{id}/match  {"top_k": 10, "judge_top_n": 5, "only_available": false}
 └─ app/api/matching.py: start_match()                         404 no role · 409 not parsed · 503 Ollama down
     └─ app/matching/runner.py: create_match_run()             ~0.1 s, inside the request
          1. effective_requirements(role)    normalised + grounded (years, domains, seniority)
          2. retrieve_candidates()           Step 7, a wider pool: max(4 × top_k, 20) people
          3. keep_qualified()                only people with AT LEAST ONE must-have (eligibility.py, §5.10);
                                             the others are counted (settings.excluded_without_must_haves)
          4. total years per candidate       one SQL query (Step 5's resume_profiles)
          5. score_candidates()              rule score for each (scoring.py), sorted, best top_k kept
          6. save MatchRun (status RUNNING, settings: weights, models, requirements, timings, qualified, excluded)
             + MatchResults (rank, rule score, breakdown, facts, judge_status pending / not_requested)
             judge_status "pending" only for the top judge_top_n WITH skill evidence (skills > 0 or named in text)
             nobody pending → the run is COMPLETED at once, no background task
     └─ asyncio.create_task(judge_run(...))   background; reference kept in app.state.match_tasks
     └─ reply 202 with the run (results already ranked by the rule score)

background: runner.judge_run(run_id)
   for each pending result, best first:
     1. _dossier_for()     fact lines (total years, jobs) + the resume's chunks, ≤ 6,000 characters,
                           "Employee EMP-1003 |" removed; evidence = original resume lines only
     2. judge_candidate()  qwen2.5 + JSON schema, temperature 0                ~45–100 s on this CPU
     3. verify()           every quote checked against the evidence; "yes" without proof → "partly";
                           judge score computed by code from the must-have verdicts
     4. final = 0.6 × rule score + 0.4 × judge score;  COMMIT  (progress visible while it runs)
   re-rank the judged top 5 by final score (others keep their places); status COMPLETED
   errors: one candidate fails → judge_status "failed", the run continues · anything else → run FAILED
   server stops → task cancelled → run FAILED "start a new run" · next startup: leftover RUNNING → FAILED

GET /api/match-runs/{id}          poll: status, judged / to_judge, results
GET /api/roles/{id}/match-runs    history
```

---

## 5. The AI ideas in Step 8

### 5.1 A transparent rule score with multiplicative factors
```
fit        = 0.85 × skills + 0.15 × relevance
rule score = fit × experience factor × availability factor × location factor
factor     = floor + (1 − floor) × component            component between 0 and 1
```
| Component | How it's computed | Floor | Effect |
|---|---|---|---|
| skills | Step 7's skill score (coverage × rarity × years × recency) | — | The core of fit |
| relevance | Position in Step 7's fused ranking: 1 for first, 0 for last | — | Text evidence (keywords, meaning) as a tie-breaker |
| experience | total years ÷ required years (max 1); unknown → 0.5; no requirement → 1 | 0.6 | 2.4 of 5 years → × 0.79 |
| availability | fits now 1.0 · fits before start 0.9 · else 0.8 × free share; on leave 0 | 0.7 | Siddharth (30% free, needs 100%) → × 0.77 |
| location | same city or role has none → 1 · other city / unknown → 0.5 | 0.9 | Bengaluru for a Pune role → × 0.95 |

**Required years:** the role's stated minimum, or, if only a seniority is **stated**, its usual years (junior 0, mid 3, senior 5, lead 7, principal 10).

**Why multiply, not add?** We tried a weighted sum first (skills 55%, experience 15%, relevance 15%, availability 10%, location 5%). Measured problem: everyone who is free, local and experienced collected ~45% of the points **without any relevant skill**, so a data scientist landed between expected backend candidates. With factors, HR facts can only **reduce** a skills-based fit, never create one. A free Java developer is still not a DevOps candidate.

**Why floors?** A factor of 0 would delete people from the list entirely. Floors keep them visible but lower, because a human may know something the data doesn't ("the current project ends early").

### 5.2 Grounding seniority (and why "mid" broke)
Seniority is used for required years only if it is **stated**. The DevOps role description says "Start mid-November"; a first version matched the word "mid" and invented a 3-year requirement. Plain "mid" was removed: only "mid level" or "intermediate" count. Small words are dangerous in text matching.

### 5.3 LLM-as-a-judge
An LLM evaluating something against criteria. It is widely used (evaluating chatbot answers, ranking search results, reviewing code) because it can **read**. Known risks and our controls:

| Risk | Our control |
|---|---|
| **Hallucination**: claims experience that isn't there | Every claim needs a quote; code verifies quotes; "yes" without a verified quote counts as "partly" |
| **Poor calibration**: "78/100" means little and varies | The model gives categories (yes / partly / no); **code computes the score**: yes = 1, partly = 0.5, no = 0, averaged over must-haves |
| **Inconsistency** | Temperature 0, fixed rubric, fixed schema |
| **Bias** (names, gender, origin) | No name, email, phone, employee code, pronouns, location or availability in the dossier; rule 7 tells it to judge only the work |
| **Position / verbosity bias** | One candidate per call (no comparison between candidates in one prompt); short, structured answers |
| **Prompt injection** in a resume | The dossier is fenced in `<candidate>`; output constrained to the schema |
| **Skipped or renamed requirements** | Code follows **its own** must-have list, matching names while ignoring case and brackets ("Python (5.0+ years)" = "Python"), falling back to position when the counts match; anything still unassessed counts as "no" with a note. The model's raw answer is stored (`llm_output`) |

### 5.4 Citations that are checked (grounded generation)
A citation is only useful if it's real. The judge must quote; `verify()` checks every quote against the **evidence text** with the same near-exact matcher as Step 5 (`appears_in`, ≥ 80% of the quote found contiguously).

**What counts as evidence:** only the **original resume text**. Not chunk headers or "Skills used:" lines (written by our code), not the "Total experience" / "Jobs" fact lines. Otherwise the system would be quoting itself as proof. The judge still **sees** those lines for orientation, but can't use them as evidence.

**"Skills used:" lines are also left out** (second real run: the judge quoted them for Kavya, 3 of 8 quotes verified).

**The profile card is left out of the dossier entirely** (since the first real run): it contains Step 5's LLM-written summary, and the judge preferred quoting its paraphrases ("Adept in Java, Spring Boot, Kafka…") over the resume's own words ("Moved services from VMs to Kubernetes in 2023"). Those quotes could never verify, so Vikram got 0 of 4 verified.

This also addresses journal item 11 (wrong Step 5 evidence quotes) at the point where it matters: a recommendation is only "proved" by the person's own words.

### 5.5 Structured output again
Same technique as Steps 5 and 7: a Pydantic class (`JudgeVerdictLLM`) → JSON schema → Ollama's grammar-constrained decoding. `Field(max_length=3)` becomes `maxItems: 3` in the schema, so the model physically can't write a fourth strength. Shorter answers are also faster on a CPU (decode dominates).

### 5.6 Combining the scores and re-ranking only the top N
`final = (1 − w) × rule + w × judge`, with `w = 0.4`. Then **only the judged top 5 are re-sorted** among themselves; positions 6–10 keep their rule order. Why: judge scores and rule scores have different scales. In a first version the whole list was re-sorted, and judged candidates fell *below* unjudged ones simply because judge scores ran lower. "Rerank the top N" is the standard pattern for exactly this reason.

### 5.7 Long-running AI work: background tasks and their life cycle
Judging 5 people takes minutes; an HTTP request shouldn't wait that long (browsers and proxies time out). So:
- the request creates the run, starts an **asyncio task**, and answers **202 Accepted** immediately;
- the task commits after every candidate, so polling shows progress (`judged` / `to_judge`);
- a reference to the task is kept in `app.state.match_tasks` (Python may otherwise garbage-collect a running task);
- on shutdown, tasks are **cancelled** and their runs marked failed; at startup, leftover RUNNING runs are marked failed. A run is never stuck "running" forever.

### 5.8 Measuring the final order: nDCG, MRR, pair order
- **nDCG@5** (normalised discounted cumulative gain): each expected person has a **gain** (the first expected is worth most); gains lower in the list are **discounted** by log2(position + 1); divided by the best possible. 1.0 = the expected people at the top in the expected order.
- **MRR:** 1 ÷ rank of the first expected person.
- **Pair order:** of all pairs in the expected list (A should be above B), the share in the right order.
Retrieval was measured by **recall** (who's in); the final ranking by **order**.

### 5.10 Who counts as a candidate (2026-11-06)
**Report:** a WordPress role, top 3, judge 2. Only Ajay has WordPress. The run still listed Ananya Iyer at #2 with a 0.00 score and "0 of 2 must-haves", and sent her to the judge: minutes of model time for someone with neither WordPress nor PHP.

**Cause:** retrieval fuses three signals, and the meaning and keyword searches always find *someone* ("developer", "web"). The run took retrieval's top `top_k` as they came, and judged the first `judge_top_n` of them, whatever their skills. The agent's `find_candidates` had already been fixed for this (doc 14); match runs had not.

**Fix** (`app/matching/eligibility.py`, shared by match runs and the agent, so both follow one rule):
- Retrieve a wider pool, `max(4 × top_k, 20)`, so qualified people aren't crowded out.
- Keep a person only if they have **at least one must-have**: a skill row (directly or through a related skill), or the skill **named in their resume text** (a skill extracted before the catalogue knew it). Known skills are checked with the extraction rules, so "we go live" is not Go.
- Then score and keep the best `top_k`. A role without must-haves keeps everyone.
- The judge runs only for people with skill evidence. If nobody needs judging, the run is completed at once.
- The run records `qualified` and `excluded_without_must_haves`. The page says: "18 people also came up in the search but have none of the must-have skills, so aren't listed or sent to the judge." If nobody qualifies: "Nobody has any of the must-have skills …", with no judge call.
- A must-have found only in the text shows as "named in the resume text (no years on the profile)" (`facts.named_in_text`).

**Checked (copy of the PC database, stand-in models):** WordPress (top 3, judge 2) → Ajay (1.00) and Harsh (0.38, his resume says "integrates multiple WordPress APIs"), both judged; Ananya and 17 others left out. Rust → no results, completed at once, no judge. The three sample roles: same people at the top (Django 0 left out, Kubernetes 6, RAG 7). Agent evaluation unchanged (12/14 with the stand-in).

**Old runs keep their results** (they are an audit record); start a new run to see the change.

### 5.9 Saving runs: audit and reproducibility
Each run stores its **settings** (weights, floors, judge model, embedding model, RRF k, the exact requirements used, retrieval timings) and each result its **breakdown** and **explanation**. Months later, anyone can answer "why was Priya recommended over Fatima on 28 October?", even after weights or models change. For AI that influences people's work, this is what auditors and regulators expect.

---

## 6. The files

| File | New / changed | Purpose |
|---|---|---|
| `app/matching/scoring.py` | new | Rule score: components, factors, required years, breakdown |
| `app/matching/judge.py` | new | Judge schema, prompt, dossier, quote verification, code-computed judge score |
| `app/matching/runner.py` | new | A match run: create (sync), judge (background), fail/recover |
| `app/matching/eligibility.py` | new (2026-11-06) | Who counts as a candidate: at least one must-have; pool size; text check (§5.10) |
| `app/schemas/matching.py` | new | `MatchRequest`, `MatchRunOut`, `MatchResultOut`, `MatchRunSummary` |
| `app/api/matching.py` | new | `POST /api/roles/{id}/match`, `GET /api/match-runs/{id}`, `GET /api/roles/{id}/match-runs` |
| `scripts/evaluate_matching.py` | new | nDCG@5, MRR, pair order per role, with a score table |
| `app/matching/requirements.py` | changed | Seniority grounding; `effective_requirements(role)` |
| `app/config.py` | changed | Step 8 settings; `judge_model`, `score_weights` properties |
| `app/main.py` | changed | Router; recover interrupted runs; track/cancel judge tasks; version 0.7.0 |
| `.env` / `.env.example` | changed | Step 8 settings block |

No database change: `match_runs` and `match_results` were designed in Step 3 for exactly this.

### 6.1 Each file: where it sits in the flow, what goes in, what comes out

```
 user clicks "Find best matches"
        │
 ① api/matching.py ──────────── start_match()            HTTP in: role id + {top_k, judge_top_n, only_available}
        │                                                 HTTP out: 202 + the run (results ranked by rule score)
 ② matching/runner.py ───────── create_match_run()       orchestrates the quick part
        ├─ ③ matching/requirements.py  effective_requirements()   in: stored role → out: cleaned requirements
        ├─ (Step 7) matching/retrieval.py retrieve_candidates()    in: role → out: top 10 Candidates
        ├─ ④ matching/scoring.py       score_candidates()         in: Candidates + years → out: (candidate, breakdown) sorted
        └─ saves MatchRun + MatchResults (database, Step 3 tables)
        │
 ⑤ main.py keeps the background task ── runner.judge_run()       for each of the top N:
        ├─ runner._dossier_for()      in: resume id → out: (dossier text, evidence text)
        ├─ ⑥ matching/judge.py judge_candidate()  in: role + dossier → LLM → out: verified verdict + judge score
        └─ saves after each candidate; re-ranks the top N; status COMPLETED
        │
 ⑦ api/matching.py ──────────── get_match_run()           HTTP out: the run with results (polled by the UI)
 ⑧ schemas/matching.py ───────── the JSON shapes of ① and ⑦
 ⑨ config.py / .env ──────────── every weight, floor, model choice and limit
 ⑩ scripts/evaluate_matching.py  in: roles.json answer key → out: nDCG@5, MRR, pair order, score table
```

| File | Job in one line | Input → output | Why it's a separate file |
|---|---|---|---|
| `api/matching.py` | The HTTP door: validate, start, show | role id + request → 202 run / run JSON / history | HTTP concerns only (status codes, polling); no business logic |
| `schemas/matching.py` | The contract with the frontend | Python objects ↔ JSON | The API shape can stay stable while internals change |
| `matching/runner.py` | Conductor of one match run | role → saved run; run id → judged run | Orchestration and life cycle (background, failure, recovery) in one place |
| `matching/requirements.py` (changed) | What the role really asks for | stored requirements → normalised + grounded requirements | Shared by retrieval, scoring and the judge, so all use the same version |
| `matching/scoring.py` | The transparent rule score | candidates + total years → breakdown + rule score | Pure maths: easy to read, test and tune; no database, no AI |
| `matching/judge.py` | The AI reader and its fact-checker | role + dossier → verdict with verified quotes + judge score | The only Step 8 code that talks to the LLM; prompt and checks together |
| `config.py` (changed) | Every setting with a default | `.env` → `settings.judge_model`, `settings.score_weights` | Tune without code changes; recorded in each run |
| `main.py` (changed) | Start-up and shut-down | registers routes; recovers runs; cancels tasks | The app's life cycle lives in one place |
| `scripts/evaluate_matching.py` | The quality check | roles.json → metrics table | Proves changes help instead of guessing |

### 6.2 The developer flow vs the end-user flow

| Moment | End user (resource manager) sees | Developer / system does |
|---|---|---|
| Click "Find best matches" | A list appears in about a second | `POST /match` → retrieval + rule score → save → 202 |
| First seconds | 10 people with skills matched/missing, availability, location, a score | `explanation.facts` and `score_breakdown` from the saved results |
| Next minutes | The top 5 fill in one by one: yes/partly/no per must-have with quotes, strengths, gaps, rating | Background `judge_run`: dossier → LLM → verify → commit; UI polls `GET /match-runs/{id}` |
| A quote can't be found | It is marked "unverified"; a "yes" shows as "partly" | `verify()` downgraded it; counted in `quotes_verified / quotes_total` |
| Judging finished | Final order of the top 5 | Re-rank of the judged top N; status COMPLETED |
| Server restarted mid-run | "This run was interrupted; start a new run" | `recover_interrupted_runs()` at startup |
| Weeks later: "why was Priya suggested?" | The old run, unchanged, with its reasons | `GET /roles/{id}/match-runs` + stored settings, breakdowns and verdicts |

---

## 7. Python you'll meet in Step 8

| Code | Meaning |
|---|---|
| `asyncio.create_task(coro, name=...)` | Start a coroutine running in the background, without waiting for it |
| `task.add_done_callback(set.discard)` | Run a function when the task finishes (here: forget it) |
| `task.cancel()` + `except asyncio.CancelledError: ...; raise` | Stop a task; clean up, then let the cancellation continue |
| `await asyncio.gather(*tasks, return_exceptions=True)` | Wait for several tasks; collect errors instead of stopping at the first |
| `status_code=202` | HTTP "Accepted": the work continues after the reply |
| `explanation = dict(result.explanation)` | A **new** dict: SQLAlchemy only notices a JSON column changed when it's re-assigned |
| `db.get(..., populate_existing=True)` | Re-read from the database even if the object is already in the session |
| `Field(max_length=3)` on a list | At most 3 items (also becomes `maxItems` in the JSON schema) |
| `{**breakdown, "judge_score": x}` | Copy a dict and add/override a key |
| `sorted(top, key=lambda r: -r.final_score)` | Sort descending by a computed value |
| `math.log2(i + 2)` | The position discount in nDCG |
| `print(..., end="\r", flush=True)` | Overwrite the same terminal line (progress display) |
| `@property` with an import inside | Lazy import to avoid a **circular import** (config ↔ scoring) |

---

## 8. Alternatives, industry standards and enterprise options

| Part | Ours | Common production choice | Enterprise / world-class |
|---|---|---|---|
| Ranking function | Hand-tuned rule score with factors | Weighted scoring tuned on labelled data | **Learning-to-rank** (LambdaMART, XGBoost ranker) trained on past staffing outcomes; constraints for fairness |
| Reranker | LLM judge (qwen2.5 local) | **Cross-encoder rerankers** (`bge-reranker-v2`, Cohere Rerank, Jina Reranker): fast, score only | LLM rerankers + cross-encoders + business rules, A/B tested |
| Judge model | 7B (or 3B) on CPU | Hosted frontier models via API; fine-tuned 7–8B on GPU | Ensembles / several judges with agreement checks; human review for close calls |
| Citations | Quote + near-exact match check | Span-level citations (character offsets) | Citation verification models (entailment / NLI checks that the quote *supports* the claim) |
| Background work | asyncio task in the web process | Task queue (**Celery**, RQ, **Arq**, Dramatiq) with Redis/RabbitMQ | Workflow engines (**Temporal**, Airflow) with retries, timeouts, observability |
| Progress | Polling | Server-Sent Events / WebSockets | Event streams to many clients |
| Evaluation | 3 roles: nDCG, MRR, pair order | 50–200 labelled roles in CI; LLM-judge agreement with humans (Cohen's kappa) | Offline + online metrics, recruiter feedback loops, bias audits |
| Audit | `match_runs.settings`, breakdowns | Immutable audit log, model registry | Model cards, decision logs for regulators (EU AI Act high-risk obligations) |

**Products that do this end to end:** Eightfold AI, Gloat, Workday Talent Marketplace, SAP SuccessFactors Opportunity Marketplace, Beamery. They combine skills inference, retrieval, learned ranking and increasingly LLM explanations, at much larger scale.

**What "enterprise grade" adds here:**
- human-in-the-loop decisions (the system recommends; a person decides and records why);
- a feedback loop (who was actually staffed, and how it went) to tune or train the ranker;
- fairness monitoring of outcomes across groups (adverse-impact ratios), not only removing names;
- judge-quality monitoring (share of verified quotes, agreement with human reviewers);
- cost and latency budgets per run (GPU serving makes the judge take seconds, not minutes).

---

## 9. Limitations to know about
- **Judge speed:** ~45 s (3B) to ~100 s (7B) per candidate on this CPU, so 4–8 minutes per run of 5.
- **Quote verification checks presence, not support:** a real quote about Terraform used as proof for Kubernetes would still pass. An entailment check (does the quote support the claim?) is the enterprise upgrade.
- **The judge only sees ~6,000 characters:** very long resumes are cut; the profile card and recent jobs come first.
- **Hand-set weights and floors** (0.85 / 0.6 / 0.7 / 0.9 / 0.4): reasonable, but 3 roles are too few to tune them; collect labelled roles first (Step 14).
- **Judgement calls:** Divya (13 years, Django until 2019, now a manager) vs Karthik (current Django, 2.4 of 5 years) tie on the rule score (0.20 each). In the real run the judge settled it (Divya "partial", Karthik "weak: lacks the required years"), matching the expected order. Still, it's a staffing decision; the system explains rather than decides.
- **One must-have is enough to be listed:** someone with PHP but no WordPress is still listed (lower) for a "WordPress + PHP" role, and judged if in the top N. That's on purpose: partial fits are often worth a look. To require every must-have, the rule in `eligibility.py` is the one place to change.
- **Background tasks live in the web process:** if it stops, running judgements are lost (marked failed, start again). A task queue fixes this at scale.

---

## 10. Try it yourself
```powershell
# Rule score only (seconds) and with the judge (minutes)
python -m scripts.evaluate_matching --judge-top-n 0
python -m scripts.evaluate_matching

# One run by hand
$run = Invoke-RestMethod -Method Post http://127.0.0.1:8010/api/roles/2/match -ContentType 'application/json' -Body '{"top_k": 10, "judge_top_n": 3}'
Invoke-RestMethod http://127.0.0.1:8010/api/match-runs/$($run.id) | ConvertTo-Json -Depth 8
```
Experiments:
1. `JUDGE_MODEL_ROLE=fast` vs `quality`: compare time, nDCG and verified quotes.
2. `SCORE_EXPERIENCE_FLOOR=0.4`: does Divya move above Karthik? Is that what you want?
3. Run the same role twice: are the judge verdicts identical (temperature 0)?

---

## 11. Glossary
| Term | Meaning |
|---|---|
| **Rule score** | A score computed by code from explicit formulas |
| **Factor / floor** | A multiplier between `floor` and 1 that can only lower a score |
| **LLM-as-a-judge** | An LLM assessing something against a rubric |
| **Rubric** | The fixed criteria the judge applies (here: each must-have, yes/partly/no) |
| **Calibration** | Whether a model's numbers mean what they say (LLM scores often don't) |
| **Citation verification** | Checking that a quoted source really says it |
| **Rerank top N** | Re-sort only the best N with a slow, careful method |
| **Match run** | One saved execution of matching for a role, with settings and results |
| **202 Accepted** | The server accepted the work and will finish it later |
| **nDCG** | Ranking quality: right people near the top, in the right order |
| **Learning-to-rank** | A model trained to order items from past examples |
| **Cross-encoder** | A model that reads query and document together and outputs a relevance score |
