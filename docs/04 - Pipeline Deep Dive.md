# 04 · Pipeline Deep Dive: one resume, start to finish

This document follows **one real resume through every stage**, using the actual data stored for **Priya Nair (EMP-1003)**, a fictional DevOps engineer from the sample pack. Her resume is a **two-column PDF** that says "k8s" instead of "Kubernetes", which makes it a good test case.

```
upload ─▶ ① intake ─▶ ② parse ─▶ ③ extract (LLM) ─▶ ④ verify & calculate ─▶ ⑤ save ─▶ ⑥ chunk ─▶ ⑦ embed ─▶ ⑧ index ─▶ READY ─▶ ⑨ search ─▶ ⑩ match a role
status:   queued      parsing→parsed  extracting→                     extracted   embedding→                         ready
```

---

## ① Intake: the upload request (milliseconds)
**Code:** `app/api/resumes.py` → `app/services/resumes.py: add_resume()` → `app/ingestion/storage.py`

| Check / action | Priya's file | Why |
|---|---|---|
| Find the employee from the filename | `EMP-1003_priya_nair.pdf` → `EMP-1003` | Bulk uploads of thousands of files need no clicking |
| Extension allowed? | `.pdf` ✓ | Only PDF and DOCX are accepted |
| Size ≤ 10 MB? | ~3 KB ✓ | Protects disk and memory |
| Magic bytes | starts with `%PDF-` ✓ | The *content* must really be a PDF |
| SHA-256 fingerprint | `0285887c1e55434b…` | Same bytes → same fingerprint |
| Duplicate? | not seen before ✓ | Saves ~1–2 minutes of LLM time per duplicate |
| Save file | `data/uploads/EMP-1003/0285887c1e55434b.pdf` | Our own name, never the uploaded one (path-traversal safety); written to `.part` then renamed (atomic) |
| Older version | marked `is_current = false`, its vectors deleted | Only the latest resume is searchable |
| New database row | status **`queued`** | The queue *is* the database |
| `worker.notify()` | wakes the worker immediately | No waiting for the 5-second poll |

The HTTP response returns now, and everything after this happens in the background.

---

## The worker: how stages are picked
**Code:** `app/ingestion/worker.py`

```
loop:
  _claim(): for stage in [embed, parse, extract]:              ← finish nearly-done resumes first
               oldest current resume with status == stage.waiting?
               → set status = stage.working, attempts += 1, COMMIT (admin sees progress)
  run the stage (outside any database transaction)
  success → next status · file problem → failed · Ollama down → back + wait 30 s · other → retry ×3
  nothing to do → sleep until notify() or 5 s
startup: anything left in parsing/extracting/embedding goes back to queued/parsed/extracted
```

**Why this order:**
- **embed** first: it takes seconds, so a resume is READY right after its own LLM step.
- **parse** next: also seconds, so a broken or scanned file is reported right after upload.
- **extract** last: the slow LLM step, oldest upload first.

The first version ran the stages in pipeline order (parse all, extract all, embed all). With 20 resumes queued, none was ready until the LLM had finished all 20. Measured with a 3-second stand-in model and 9 resumes: they now become ready one by one, about 3 s apart, instead of all together at the end (2026-11-06).

---

## ② Parse: file → clean text (< 1 second)
**Code:** `app/ingestion/text_extraction.py` (run with `asyncio.to_thread`)

1. **PDFium** reads the text of each page in the PDF's **stored order**. For Priya's two-column layout this keeps the sidebar and main column apart. "Sorting top-to-bottom" would have interleaved them line by line.
2. **Cleaning:** Unicode normalisation, `\r\n` → `\n`, bullets → `-`, lone bullets glued to their text, hyphenated words re-joined, page numbers removed, blank lines collapsed.
3. **Scanned check:** fewer than 100 characters per page → `failed` ("needs OCR"). Priya has 985 characters on 1 page, so she passes. The sample scanned resume (EMP-1008) produced 0 characters and was correctly rejected.

Result stored in `resumes.raw_text` (excerpt):
```
Priya Nair
DevOps Engineer
Contact
...
Skills
- k8s (EKS)
- Helm
- Terraform
...
Experience
Senior DevOps Engineer, Nimbus Technologies (Sep 2020 – Present)
- Operate 14 EKS clusters (k8s 1.2x) hosting 300+ microservices.
- Wrote reusable Terraform modules for VPC, EKS and RDS; reduced
environment setup from 3 days to 2 hours.
- Set up Prometheus/Grafana monitoring and on-call alerting.
Systems Engineer, Harbor Networks (2018 – 2020)
- Automated Linux server provisioning with Ansible; built Jenkins pipelines.
```
Status → **`parsed`**.

---

## ③ Extract: the LLM fills a form (~90 seconds)
**Code:** `app/extraction/extractor.py`, `prompts.py`, `schema.py`

**The request sent to Ollama** (`POST /api/chat`):
```json
{
  "model": "qwen2.5:7b",
  "messages": [
    {"role": "system", "content": "You extract facts from a resume into JSON. Rules: 1. Use ONLY information written in the resume..."},
    {"role": "user",   "content": "Extract the facts from this resume.\n\n<resume>\nPriya Nair\nDevOps Engineer\n...\n</resume>"}
  ],
  "options": {"temperature": 0.0, "num_ctx": 8192, "num_predict": 2048},
  "format": { "...JSON schema generated from ResumeExtraction..." }
}
```

**Inside Ollama:** tokenise (613 prompt tokens) → prefill → decode **567 tokens at 7.0 tok/s**, each token restricted by the schema's grammar → **90.5 seconds** in total.

**What the model returned** (real, abridged):
```json
{
  "headline": "Senior DevOps Engineer",
  "summary": "Priya Nair is a Senior DevOps Engineer with experience in Kubernetes, Terraform, and CI/CD tools. She specializes in managing EKS clusters and implementing GitOps practices.",
  "experience": [
    {"title": "Senior DevOps Engineer", "company": "Nimbus Technologies", "start": "Sep 2020", "end": "Present",
     "description": "Operate 14 EKS clusters hosting 300+ microservices.",
     "skills_used": ["k8s", "Terraform", "Prometheus", "Grafana", "Bash", "Python"]},
    {"title": "Systems Engineer", "company": "Harbor Networks", "start": "2018", "end": "2020",
     "description": "Automated Linux server provisioning with Ansible; built Jenkins pipelines.",
     "skills_used": ["Ansible", "Jenkins"]}
  ],
  "skills": [{"name": "k8s (EKS)", ...}, {"name": "Helm", ...}, {"name": "Terraform", ...}, {"name": "AWS", ...},
             {"name": "ArgoCD", ...}, {"name": "Jenkins", ...}, {"name": "GitHub Actions", ...}, {"name": "Prometheus", ...},
             {"name": "Grafana", ...}, {"name": "Bash", ...}, {"name": "Python (scripting)", ...}]
}
```
Two things to notice:
- **Bash and Python** were listed under her Nimbus job although that job's text never mentions them. The model copied them from the skills section. This is the over-attribution problem that Step 5b's job-level grounding fixes. Priya's stored data predates 5b, so it still shows Python at 6.2 years; re-extraction will correct it.
- The **summary names her and uses "She"**. Anonymisation later removes the name, but the pronoun reveals gender. That's a fairness gap; the prompt will be changed to ask for a neutral, name-free summary.

Pydantic validates this JSON (`model_validate_json`). If the answer were cut off (`done_reason == "length"`) or invalid, the stage would be retried.

---

## ④ Verify and calculate (milliseconds, plain Python)
**Code:** `app/extraction/postprocess.py`, `dates.py`, `skills.py`

| Sub-step | What happens to Priya's data |
|---|---|
| Dates | "Sep 2020"–"Present" → Sep 2020 to today = **74 months**; "2018"–"2020" → Jul 2018 to Jun 2020 (mid-year rule) = **24 months** |
| Total experience | Spans merged (overlaps counted once): 74 + 24 = 98 months = **8.2 years** |
| Job-level grounding (5b) | Nimbus job text contains k8s, EKS, Terraform, Prometheus, Grafana → kept; **Python and Bash removed** from that job (not in its text) |
| Hallucination check | Every skill's evidence or name must appear in the resume; nothing invented here (`rejected_skills: []`) |
| Normalisation | "k8s (EKS)" → **Kubernetes** + **Amazon EKS**; "Python (scripting)" → **Python** |
| Skills without a job | Python, Bash, AWS, Helm, ArgoCD, GitHub Actions are in the resume but in no job → kept, **years unknown** |
| Years per skill | Kubernetes: Nimbus job only → **6.2 years**, last used **2026**; Jenkins: Harbor job → **2.0 years**, last used **2020** |

---

## ⑤ Save (one transaction)
**Code:** `app/services/profiles.py: save_profile()`

```
DELETE old profile / experiences / skill links for this resume       (re-runs never duplicate)
INSERT resume_profiles   headline, summary, total_experience_years=8.2, raw_extraction={llm_output, rejected, warnings, stats}
INSERT experiences ×2    (Senior DevOps Engineer, Nimbus, 2020-09-01, current) · (Systems Engineer, Harbor, 2018, 2020)
SELECT/INSERT skills     shared catalogue, case-insensitive (one query)
INSERT resume_skills     (Kubernetes, 6.2, 2026, "k8s (EKS)") · (Terraform, 6.2, 2026, ...) · ...
UPDATE resumes           status = extracted, attempts = 0
COMMIT
```

---

## ⑥ Chunk (milliseconds)
**Code:** `app/rag/chunking.py`

Priya's resume becomes **4 chunks** (real, stored data):

*(The chunks below are from Step 6, before re-extraction. Since Step 7 the summary is neutral ("A platform engineer with extensive experience in Kubernetes, AWS, and CI/CD pipelines…"), Python has no years, and each job chunk has a `Skills used:` line. All 14 resumes now give 58 chunks.)*

**Chunk 0, profile card** (built from step ⑤'s data, ~120 tokens)
```
Employee EMP-1003 | Profile
Senior DevOps Engineer with 8.2 years of total experience.
[name] is a Senior DevOps Engineer with experience in Kubernetes, Terraform, and CI/CD tools. ...
Skills: Kubernetes (6.2 years), Terraform (6.2 years), ..., Ansible (2.0 years), Jenkins (2.0 years), AWS, Amazon EKS, ArgoCD, ...
```
**Chunk 1, experience** (the job's original text, ~98 tokens)
```
Employee EMP-1003 | Experience | Senior DevOps Engineer at Nimbus Technologies (2020 - present)
Senior DevOps Engineer, Nimbus Technologies (Sep 2020 – Present)
- Operate 14 EKS clusters (k8s 1.2x) hosting 300+ microservices.
- Wrote reusable Terraform modules for VPC, EKS and RDS; reduced environment setup from 3 days to 2 hours.
- Set up Prometheus/Grafana monitoring and on-call alerting.
```
**Chunk 2, experience** (~51 tokens): the Harbor Networks job.

**Chunk 3, other sections** (~143 tokens): contact (anonymised to `[name]`, `[email]`, `[phone]`), skills list, certifications, education, profile paragraph.

**Design choices visible here:**
- Each job is one chunk, cut at real job boundaries, never mid-job.
- The **contextual header** (first line) makes every chunk understandable on its own.
- Nothing from the resume is lost: everything outside jobs goes into the "other" chunk.
- Names, emails and phones are replaced before indexing; since Step 7 also gendered pronouns (she/he → they, her/his → their).
- **Since Step 7** each experience chunk carries a `Skills used:` line with the **normalised** skills found in that job's own text, so "k8s" is also indexed as "Kubernetes":
```
Employee EMP-1003 | Experience | Senior DevOps Engineer at Nimbus Technologies (2020 - present)
Skills used: Kubernetes, Grafana, Prometheus, Terraform, Amazon EKS
Senior DevOps Engineer, Nimbus Technologies (Sep 2020 – Present)
- Operate 14 EKS clusters (k8s 1.2x) hosting 300+ microservices. ...
```

---

## ⑦ Embed (~1 second)
**Code:** `app/rag/embeddings.py`

All 4 chunks go to Ollama in one batched call to `POST /api/embed`, each prefixed with `search_document: `. Each comes back as **768 numbers**.

---

## ⑧ Index (milliseconds, two stores)
**Code:** `app/services/indexing.py`, `app/rag/vector_store.py`

```
1. ChromaDB: delete vectors where resume_id = 3, then add 4 (id, vector, text, metadata)
      metadata = {resume_id: 3, employee_id: 3, employee_code: "EMP-1003", section, chunk_index, embedding_model}
2. SQLite (one transaction): replace resume_chunks rows (same ids),
      replace chunks_fts rows (keyword index, Step 7), status = ready, COMMIT
```
ChromaDB is written first: if SQLite then fails, the retry replaces the vectors (idempotent). SQLite stays the **source of truth**; ChromaDB can be rebuilt from it at any time.

Across all 14 sample resumes: **60 chunks** indexed.

---

## ⑨ Search (≈ 50 ms when warm)
**Code:** `app/rag/search.py`

```
"container orchestration and infrastructure as code"
 → embed with "search_query: " prefix                     (first call ~2 s: model cold start)
 → ChromaDB: 60 nearest chunks                             (single-digit ms)
 → keep chunks of current + ready resumes
 → group by employee: score = best chunk, keep 3 as evidence
 → ranked list
```
Real result: **#1 Ananya 0.584, #2 Priya 0.578, #3 Siddharth 0.562**. Priya should be first, and lost by 0.006 because:
- her strongest chunk says "k8s", which the embedding model barely links to "container orchestration";
- scores are compressed, so tiny differences decide the order.

**Step 7 fixes this** with skill-enriched chunks, keyword search, structured skill matching and rank fusion (stage ⑩).

---

## ⑩ Match a role: hybrid retrieval (Step 7)
**Code:** `app/api/projects.py` → `app/matching/requirements.py` → `app/matching/retrieval.py`

Example role from `samples/roles.json`: **DevOps / Platform Engineer (Kubernetes)**, 100%, from 15 Nov 2026.
> "Platform engineer to migrate 60 services to Kubernetes on AWS. Must have hands-on Kubernetes in production, Terraform, CI/CD pipelines and AWS. Nice to have: Helm, ArgoCD, Prometheus/Grafana monitoring…"

**10a. Parse the role once (LLM, ~30–60 s, stored)**. What qwen2.5:7b really returned on this PC (abridged):
```json
{"seniority": "mid",
 "must_have":    [{"name": "Kubernetes", "min_years": 3.0}, {"name": "Terraform", "min_years": 2.0},
                  {"name": "CI/CD", "min_years": 2.0, "as_written": "ci/cd pipelines"}, {"name": "AWS", "min_years": 3.0}],
 "nice_to_have": [{"name": "Helm"}, {"name": "ArgoCD"}, {"name": "Prometheus"}, {"name": "Grafana"}],
 "min_total_years": 5.0, "domain": ["cloud"],
 "search_summary": "A mid-level platform engineer with extensive experience in Kubernetes, Terraform, and CI/CD pipelines, and a strong background in AWS. ...",
 "parsed_by": "qwen2.5:7b", "edited_by_user": false}
```
⚠️ **The description names no years at all**: every `min_years` and the `min_total_years: 5` were **invented** by the model, and "cloud" isn't a word in the description. Code now checks this (`ground_in_description`): a number of years is kept only if it's written next to "years" in the role text, and a domain only if the word appears in it. After that check, all of these become `null` and `domain` becomes `[]`.

Code also normalises every name through the skill catalog (same names as resumes), splits compound names, removes duplicates (a skill in both lists stays must-have) and fills the role's `min_experience_years` and `location` if they were empty.

**10b. Who is eligible:** active employees with a current READY resume (14 here). Each gets an availability verdict, e.g. Priya: *"100% free now (role needs 100%)"*; Fatima: *"only 50% free (role needs 100%)"*. With `only_available=true` people who don't fit are removed before searching.

**10c. Three signals, each a ranking of employees**

| Signal | Input | How | Priya |
|---|---|---|---|
| ① skills | Step 5 data | must/nice credits (exact or implied, years, recency) × rarity | #1, skill score 0.648 |
| ② keyword | all catalog spellings of the required skills: `"kubernetes" OR "k8s" OR "kube" OR "terraform" OR "hashicorp terraform" OR "ci/cd" OR … OR "aws" OR "amazon web services" OR "helm" OR …` | FTS5 BM25 over chunks, best chunk per person | #1, snippet `… Skills - [k8s] (EKS) - [Helm] - [Terraform] - [AWS] - [ArgoCD] …` |
| ③ vector | `search_query: <summary> Key skills: Kubernetes, Terraform, …` | ChromaDB, 80 nearest chunks, eligible only | #1 |

**10d. Fuse with RRF (k = 60):** Priya = 1/61 + 1/61 + 1/61 = **0.0492**. Someone #2 in one list only gets 1/62 = 0.0161.

**10e. Response** (abridged; the user's real data after re-extraction, skills and keyword signals; vector values are left out because they were computed on the user's PC):
```json
{"rank": 1, "employee_code": "EMP-1003",
 "ranks": {"skills": 1, "keyword": 1, "vector": 1}, "skill_score": 0.648,
 "must_matched": [
   {"required": "Kubernetes", "matched_with": "Kubernetes", "direct": true,  "years": 6.2, "last_used_year": 2026, "credit": 1.0, "weight": 2.099},
   {"required": "Terraform",  "matched_with": "Terraform",  "direct": true,  "years": 6.2, "last_used_year": 2026, "credit": 1.0, "weight": 2.386},
   {"required": "CI/CD",      "matched_with": "Jenkins",    "direct": false, "years": 2.0, "last_used_year": 2020, "credit": 0.3, "weight": 2.386},
   {"required": "AWS",        "matched_with": "Amazon EKS", "direct": false, "years": 6.2, "last_used_year": 2026, "credit": 0.6, "weight": 2.099}],
 "must_missing": [],
 "keyword_snippets": ["… Skills - [k8s] (EKS) - [Helm] - [Terraform] - [AWS] - [ArgoCD] - Jenkins - GitHub Actions - [Prometheus] - [Grafana] …",
                      "… A platform engineer with extensive experience in [Kubernetes], [AWS], and [CI/CD pipelines], specializing in production …"],
 "availability": {"status": "available", "free_percent": 100, "fits": true, "note": "100% free now (role needs 100%)"}}
```
Things to notice:
- **CI/CD via Jenkins** (implied, last used 2020 → credit 0.3). Her GitHub Actions has unknown years (0.6 × 0.6 × 0.8 = 0.29), so Jenkins wins by a hair.
- **AWS via Amazon EKS** (implied, 0.6) beats her direct "AWS" skill, because that has unknown years (1.0 × 0.6 × 0.8 = 0.48). Known facts beat unknown ones; this is a formula choice worth revisiting in Step 8.
- The `evidence` stored for Jenkins and GitHub Actions in Step 5 is a Terraform sentence: the model attached a wrong quote, and the Step 5 check accepted it because the skill's **name** appears elsewhere in the resume. Step 8's judge must verify that quotes really support the skill.

Total time ≈ 100 ms (one query embedding + SQL); no LLM writing at search time. Ordering with judgement and explanations is Step 8.

---

## Time budget for one resume (this PC)

| Stage | Time | Share |
|---|---|---|
| ① Intake | ~10 ms | — |
| ② Parse | < 1 s | ~1% |
| ③ Extract: prefill (~600 tokens) | ~15–25 s | ~25% |
| ③ Extract: decode (~570 tokens) | ~65–80 s | ~73% |
| ④–⑤ Verify, calculate, save | ~50 ms | — |
| ⑥–⑧ Chunk, embed, index (vectors + keyword index) | ~1–2 s | ~1% |
| **Total** | **~1.5 minutes (7B) · ~50 s (3B)** | |

**For 2,000 resumes:** ~56 hours with the 7B, ~28 hours with the 3B. An overnight batch for the first load; then minutes per day for new uploads.

---

## Failure handling at every stage

| Stage | What can go wrong | Result |
|---|---|---|
| Intake | Wrong type, fake content, too big, duplicate, unknown employee code | Immediate error in the upload response; nothing saved |
| Parse | Scanned image, corrupt or password-protected file | `failed` with a clear message (permanent; retrying won't help) |
| Extract | Ollama not running | Back to `parsed`, attempt not counted, retry every 30 s |
| Extract | Answer cut off or invalid JSON | Retry up to 3 times, then `failed` |
| Embed | Ollama not running | Back to `extracted`, retry every 30 s |
| Any | Server stopped mid-stage | Put back on next startup; nothing lost |
| Any | Resume deleted while being processed | Result discarded; vectors removed |
