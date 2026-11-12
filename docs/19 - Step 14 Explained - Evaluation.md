# 19 - Step 14 Explained: Evaluation and Tuning

**Read first:** 03 (AI and RAG concepts), 11 (Step 7, retrieval and its metrics), 12 (Step 8, scoring and match metrics), 14 (Step 10, the agent). **Status:** 14a (agent evaluation), 14b (one-command report with regression check) and 14c (👍/👎 feedback in the portal, exported as test data) are built. 14d (tuning weights on labelled data) comes next.

---

## 1. Why this step exists

So far every improvement was checked by hand, one case at a time:
- "Ajay's skills look right now."
- "WordPress only returns Ajay now."
- "Python ranks the 9.3-year person first now."

Each fix was real. But nothing guaranteed that the next fix didn't quietly break an earlier one.

A RAG system has many moving parts: the extraction prompt, the skill catalogue, chunking, three retrieval signals, fusion weights, the rule score, the judge and the agent prompt. A change to any of them can move results somewhere else. Industry practice treats evaluation as part of the product:
- a fixed test set with known right answers;
- run after every change;
- compared with the last run;
- and a change is kept only if nothing got worse.

That is what this step builds.

> **The rule from now on:** before and after any change to prompts, weights, chunking or models, run `python -m scripts.evaluate_all`. The report says what got better and flags anything that got worse.

---

## 2. What is evaluated, and how

| Layer | Question it answers | Script | Metric |
|---|---|---|---|
| Extraction, code only | With correct model answers, does our code (sections, skills, years ladder) produce the right profile? | `evaluate_real_resumes --offline` | share of 151 checks passed |
| Extraction, real model | Does the real model + our code produce the right profile from the 9 real resumes? | `evaluate_real_resumes` | same checks |
| Retrieval, real resumes | Does the right person come up for a role query? | `evaluate_real_retrieval` | hit@3, recall@5, MRR |
| Retrieval, sample roles | Same, on the 3 sample roles with expected people | `evaluate_retrieval` | recall@5, recall@10, MRR |
| Matching | Is the final ranking (rule score) in the right order? | `evaluate_matching --judge-top-n 0` | nDCG@5, MRR, pairwise order |
| **Agent (new)** | Does the chat answer correctly, honestly and safely? | **`evaluate_agent`** | cases and checks passed |
| **Everything (new)** | One command, a saved report, comparison with the last one | **`evaluate_all`** | regressions |

### 2.1 The metrics, in plain words
- **hit@3:** an expected person is in the top 3. Did we find them at all where a manager looks?
- **recall@5:** the share of all expected people in the top 5.
- **MRR (mean reciprocal rank):** 1 ÷ the rank of the first right person, averaged. 1.0 means the right person is always #1; 0.5 means usually #2.
- **nDCG@5:** like MRR but for the whole top 5. Right people near the top count more than right people lower down.
- **pairwise order:** of the pairs "A should rank above B" in the test file, the share in the right order.

---

## 3. 14a: Evaluating the agent

### 3.1 The idea
The agent is the part users talk to, and the part most likely to go wrong quietly. The WordPress answer (doc 07) showed three ways:
- people without the skill were listed;
- the numbers were old;
- the order was off.

A test has to catch all of these **automatically**, on every run.

`evaluation/agent_cases.json` holds 14 test conversations. `scripts/evaluate_agent.py` asks each question through the **real agent loop**, with the same prompt, tools, model and database as the chat page. It records every tool call, tool result and the answer, then checks them.

### 3.2 The checks
**Checks from the test file** (what this question needs):

| Check | Example |
|---|---|
| `tools_any` | "find me a WordPress developer" must call `find_candidates` |
| `must_have_includes` | …and ask for WordPress ("Golang" counts as Go: spellings are normalised) |
| `args` | "from 1 December 2026" → `start_date` 2026-12-01; "Can EMP-1006 start…" → `employee_code` EMP-1006 |
| `mention_all / any / none` | WordPress must name EMP-1017; COBOL must name nobody |
| `first_is_one_of` | Kubernetes + AWS: Priya (EMP-1003) first |
| `first_has_most_years` | Python: the first person has the most Python years among recent users named (read from the database, so it stays right when data changes) |
| `only_people_with_any` | Everyone named has the skill (a skill row, an implied skill, or the resume text) |
| `args_from_previous_first` | "Tell me more about the first person" → the profile of the first person in the previous answer (memory works) |
| `contains_* / not_contains` | The project names are listed; the email address and the system prompt are **not** |
| `no_tools` | Off-topic or injection: answered without tools |

**Checks on every answer** (honesty and safety):

| Check | What it catches |
|---|---|
| grounded codes | An employee code that no tool returned: an invented person |
| grounded years | "N years" / "N y" that no tool returned: an invented or rounded number |
| tool order kept | People in a different order than `find_candidates` ranked them |
| at most 5 people | A long list instead of a recommendation |
| no contact details | Email addresses or phone numbers (dates like 2026-12-01 are not phone numbers) |
| no error, not empty | Ollama down, timeouts, crashes |

### 3.3 Why rule checks and not an "LLM judge" of the answers
Tools such as RAGAS or DeepEval often ask a second LLM to grade faithfulness. That is useful for free text, but it is:
- slow on this PC (minutes per answer);
- itself unreliable with small models;
- non-deterministic (the same answer can get different grades).

Our answers are about **checkable facts**: codes, years, skills, order. So the checks compare them with the tool results and the database directly. They are exact, instant and repeatable. An LLM grader would be a later addition for qualities rules can't see, like tone or clarity.

### 3.4 How the evaluator itself was tested
An evaluator that always says PASS is worse than none. It was tested against a stand-in model in two modes:
- **Good mode:** answers built from the tool results. All checks passed, except one search case where the stand-in embeddings don't capture meaning (it needs the real model).
- **Bad mode:** it makes the planted mistakes on purpose:
  - adds a person no tool returned, with "about 12 years";
  - reverses the order;
  - adds an email address;
  - answers the follow-up about the second person;
  - prints the system prompt.

  **Every planted mistake was caught:** 41 failed checks across 10 cases, each with a readable reason, for example `grounded codes: no tool returned ['EMP-1004']`.

### 3.5 What it found straight away
The Python case failed on real data: **Meera (5.3 y) was ranked above Ananya (9.3 y)**, even after the depth fix (doc 11).
- **Cause:** the rule score is 85% skills and 15% "relevance", the position in the keyword and meaning search. For a bare skill list the search text is only "Experience with Python", so that position is noise. It was worth more than the depth difference.
- **Fix:** when the request has no description of the work, `find_candidates` scores on skills alone (times the availability, experience and location factors). With a description, relevance keeps its 15%.
- **Result:** Python → Ananya 9.3, Meera 5.3, Kavya 4.4, Karthik 2.5. Kubernetes + AWS → Priya (free now) before Fatima (free from 15 Nov).

This is exactly why the step exists: the case was written once and then caught a problem nobody had looked for.

---

## 4. 14b: One command, a report, and regressions

`python -m scripts.evaluate_all` runs every suite as its own process, exactly as if you typed its command. It reads the numbers from each output and writes two files:
- `evaluation/reports/all-<date-time>.json`, the full data;
- `evaluation/reports/all-<date-time>.md`, a readable table.

**Regression rule:** every number is "higher is better". For each suite, the numbers are compared with **the most recent report that ran that suite**. A partial run (`--only agent`) doesn't hide older numbers for the other suites. Anything lower by more than 0.005 (rounding) is printed as a `REGRESSION`, and the exit code is 1.

Example output (the regression line was provoked on purpose in testing):
```
- extraction-code: running scripts.evaluate_real_resumes --offline ...
  PASSED  checks_passed_share 1.0  (1 s)
- retrieval-real: ...  PASSED  hybrid_hit@3 1.0  hybrid_R@5 1.0  hybrid_MRR 1.0
- retrieval-samples: ... PASSED hybrid_R@5 0.83  hybrid_R@10 1.0  hybrid_MRR 1.0
- matching-samples: ...  PASSED nDCG@5 0.96  MRR 1.0  pairs 0.94
- agent: ...             PASSED cases_passed_share 1.0  checks_passed_share 1.0

REGRESSIONS (lower than the last report that ran the suite):
  matching-samples nDCG@5: 0.99 -> 0.64 (report of 2026-11-06T07:14:29)
```

- **What it needs:** the server is needed only for the two sample suites (they use the API). It asks for a portal login once, or reads `RTM_EMAIL` / `RTM_PASSWORD`. If the server isn't running, those suites are marked skipped, not failed.
- **`--note "prompt v4"`** records what changed, so the report history reads like a lab notebook.
- **Privacy:** reports contain answers about real employees, so `backend/evaluation/reports/` is git-ignored, like `samples/real/`.

---

## 5. The flow, end to end

```
you change something (prompt, weight, chunk size, model)
        │
        ▼
python -m scripts.evaluate_all --note "what I changed"
        │  for each suite: run the script → read its numbers
        │  agent suite: for each case → run_agent (real loop, real tools, real model)
        │                              → check tool calls, arguments, answer vs tool results and database
        ▼
evaluation/reports/all-<time>.md   + compare each number with its last run
        │
        ├── nothing lower → keep the change
        └── REGRESSION    → look at the failing case in the report, fix or revert
```

---

## 6. Files

| File | What it is |
|---|---|
| `backend/evaluation/agent_cases.json` | 14 test conversations (single and multi-turn) with what each answer must and must not do. Cases on R2–R9 say `requires` and are skipped until `load_real_resumes` has run |
| `backend/scripts/evaluate_agent.py` | Runs each case through `run_agent` with a fresh database session per question (like a chat request); 21 kinds of checks; prints failures with reasons; writes `reports/agent-<time>.json` with every tool call and answer |
| `backend/scripts/evaluate_all.py` | Runs all suites, parses their numbers, writes the JSON + Markdown report, flags regressions per suite |
| `backend/app/agent/tools.py` | `find_candidates`: skills alone decide when the request has no description (finding in 3.5) |
| `.gitignore` | `backend/evaluation/reports/` (answers about real people stay on the PC) |

**Python ideas used:**
- `subprocess.run([sys.executable, "-m", ...])` runs another script with the same Python and venv.
- `re.finditer` and taking the **last** match reads the summary line at the end of an output.
- `dataclasses.replace(weights, skills_share=1.0)` makes a copy of a settings object with one value changed (the original stays as it is).
- An async generator (`async for event in run_agent(...)`) gives the events one by one, exactly as the chat page receives them.

---

## 7. How to run it on the PC

1. Load the real resumes once (server running): `python -m scripts.load_real_resumes --wait`.
2. Restart the server so it has today's code.
3. Run `python -m scripts.evaluate_all --note "baseline"`. This makes the **first real baseline**.
   - The agent suite takes about 14 questions × 1–2 min on CPU.
   - To run only that part: `python -m scripts.evaluate_agent --show`.
4. Once in a while, add `--with-model-extraction` (about 10 minutes; stop the server first so the CPU isn't shared).

---

## 8. Alternatives, from hobby to enterprise

| Level | How teams evaluate RAG and agents |
|---|---|
| Hobby | Try a few questions by hand after a change |
| **This project** | Fixed test sets per layer, rule-based checks against tool results and the database, a saved report per run, automatic regression flags |
| Team | The same in CI on every pull request, often with **promptfoo** (YAML test cases, assertions, side-by-side model and prompt comparison), **DeepEval** or **RAGAS** (faithfulness, answer relevance, context precision and recall, scored by an LLM) |
| Enterprise | Observability with tracing of every production request (**LangSmith**, **Arize Phoenix**, **Langfuse**), datasets grown from real user questions and thumbs up/down, human review queues, online A/B tests of prompts and models, dashboards and alerts on quality over time |

Our checks are close to promptfoo-style assertions, written in Python against our own data. Moving to such a tool later would mainly mean exporting `agent_cases.json`.

---

## 9. Limitations (honest list)

- **Small test sets:** 14 agent cases, 7 + 3 retrieval roles and 9 real resumes. Enough to catch breakage, too few to *tune* weights without overfitting. That needs 14c.
- **Rule checks can't judge quality of wording**, only facts, order and safety. "Is this a helpful answer?" still needs a person (or later an LLM grader).
- **Expectations depend on the data:** if HR data changes (someone becomes busy), an expectation like "Priya first" may legitimately change. Checks that read the database (`first_has_most_years`, `only_people_with_any`) stay right automatically, but fixed codes don't.
- **Small models are not fully deterministic** even at temperature 0, so a case can fail once and pass on a second run. Repeated failures are what count.
- **The meaning-search case (A09)** could only be verified with the real embedding model, on the PC.

---

## 10. 14c: Feedback from the people who use it

### 10.1 Why
The test sets in sections 2–4 were written by us: 14 agent questions, 10 roles. Real quality is decided by the resource managers who know the people. They can tell at a glance "Kavya only has 2 years of RAG, she's not senior enough", which no rule can.

Every 👍 or 👎 they give is a **labelled example**, and real use is the only way to get hundreds of them. Industry practice is the same: thumbs up/down in ChatGPT, "was this helpful?" in search engines, relevance judgements in enterprise search.

### 10.2 What the user sees
- **On every candidate card** of a match run: "Was this right? 👍 👎".
  - 👍 saves at once.
  - 👎 saves at once and opens a short form: a reason from a fixed list (lacks a key skill, not enough experience, not really available, the profile is wrong, should rank higher, should rank lower, something else) and an optional note.
  - Pressing the same thumb again takes the rating back.
  - The card also shows the team's count ("Team: 2 👍 · 1 👎").
- **Under every assistant answer:** the same thumbs, with answer reasons (named the wrong people, missed someone who fits, wrong years, dates or availability, misunderstood the question, too long or unclear).
- **Admins: a new Feedback page** (`/feedback`).
  - Counts for matches and answers, filters (what was rated, 👍 or 👎), and one row per rating with its reason, note, who and when.
  - For a match: the employee, the role, the rank and score at the time, and a link to the run. For an answer: the question, and the answer itself.

### 10.3 How it is stored (`feedback` table)
| Column | Why |
|---|---|
| `user_id`, `target`, `rating`, `reason`, `comment` | Who said what. One rating per person per item (a unique constraint): rating again **changes** it, so nobody can vote twice |
| `match_result_id`, `match_run_id` | Which result it was. `SET NULL` if the run is deleted |
| `role_id`, `employee_id` | **The label itself:** "for this role, this person is / isn't a match". It survives re-running or deleting the run |
| `agent_message_id` | Which answer. Only the asker can rate it (someone else's answer → 404) |
| `context` (JSON) | A **snapshot** of what the person saw: rank, scores and requirements, or the question, the answer and the tools used. The label stays understandable after the conversation is deleted |

The table is created automatically at startup (`create_all`), so no migration step is needed.

### 10.4 From clicks to test data
`python -m scripts.export_feedback` reads the table and writes two files (git-ignored):
- **`feedback-labels-<time>.json`:** per role, who is `good`, `not_good` or `disputed` (votes are added up; a tie is disputed), with reasons and notes. This is the labelled set for 14d.
- **`agent-cases-from-feedback-<time>.json`:** every 👎 answer as a **draft agent test case**, in the format of `agent_cases.json`. It contains the question, what the agent answered and which tools it used, the reason, and a suggestion for the check (for example "missed someone → add the missing person to `mention_all`"). A person finishes the expectation and copies it in, so the same mistake is caught by `evaluate_agent` from then on.

### 10.5 Tested
**API (24 checks on a copy of the PC database):**
- Rating, changing a rating (no duplicate) and taking it back.
- Team counts, and each person sees their own rating.
- Wrong values are refused (422); an unknown result returns 404.
- The answer event carries `message_id`, in streaming and non-streaming mode.
- Rating someone else's answer returns 404; a tool message can't be rated (409).
- The admin list and its filters work; a resource manager gets 403.
- The label survives deleting the conversation.

**Browser (production build):**
- 👎 → reason + note → saved; after a reload the right thumbs are still pressed.
- Toggling a rating off works.
- An assistant answer is rated and still shown after a reload.
- The admin page shows both kinds of rating, and its filters work.
- A resource manager has no Feedback menu item.
- No errors in the browser console.

**Export:** 4 labelled people (1 good, 2 not good, 1 disputed) and 2 draft cases, from the test votes.

**Small thing seen:** a brand-new conversation reloads once just after the first answer (the page moves to its own address). A 👎 pressed in that second is saved, but its reason form closes. The thumb stays pressed, with an "add a reason" link.

---

## 11. What comes next in Step 14

- **14d: tuning on labels.** With 30–50 labelled roles from 14c, sweep the RRF weights, the score weights and the depth share. Keep a setting only if it improves the numbers on roles that were held out of the tuning.

---

## Glossary

- **Test set / golden set:** questions with known right answers, kept fixed so runs can be compared.
- **Regression:** something that worked before and is worse now.
- **Grounded:** every fact in the answer can be found in what the tools returned.
- **Deterministic check:** gives the same verdict every time for the same answer (a rule), unlike an LLM grader.
- **Baseline:** the first report all later reports are compared with.
- **Overfitting:** tuning so closely to a few test cases that the system gets worse on everything else.
