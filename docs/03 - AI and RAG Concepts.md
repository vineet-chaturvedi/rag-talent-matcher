# 03 · AI & RAG Concepts

Every AI idea used in this project, from the ground up. Each concept follows the same pattern: **what it is → how it works → in our project → alternatives**. Worked examples use our sample employees.

---

## 1. Foundations

### 1.1 AI, machine learning, deep learning
```
Artificial Intelligence   computers doing tasks that seem to need intelligence
 └─ Machine Learning      learns patterns from EXAMPLES instead of hand-written rules
     └─ Deep Learning     ML with large neural networks (many layers of simple maths units)
         └─ LLMs & embedding models   (what we use)
```
- **Rule-based code** (our date parser, skill catalog) is the opposite: exact and predictable, but only as smart as the rules.
- **Our design mixes both:** models for understanding language, rules for anything that must be exact.

### 1.2 Model, parameters, training, inference
- A **model** is a huge mathematical function: text (or numbers) in, prediction out.
- **Parameters (weights)** are its adjustable numbers: ~3 billion in `qwen2.5:3b`, ~7 billion in `qwen2.5:7b`, ~137 million in `nomic-embed-text`.
- **Training** finds good parameter values by showing the model trillions of examples and nudging the numbers after every mistake. It needs datacentres and weeks.
- **Inference** is *using* the trained model. **We only do inference.**

### 1.3 Fine-tuning vs RAG
| | Fine-tuning | RAG (what we do) |
|---|---|---|
| How knowledge gets in | Extra training on your data | Retrieved and pasted into the prompt at question time |
| Updating when a resume changes | Re-train | Re-index one resume (seconds) |
| Cost | GPUs, ML expertise | A database and an index |
| Can cite sources | No | Yes, the retrieved text |
| Good for | Teaching a style or format | Facts that change and must be traceable |

---

## 2. Large Language Models (LLMs)

### 2.1 Tokens
Models read **tokens**, pieces of words, each mapped to an ID number.
```
"Kubernetes engineer in Bengaluru"
 → ["K", "ubern", "etes", " engineer", " in", " Beng", "aluru"]   (illustrative split)
```
Rule of thumb: **1 token ≈ ¾ of an English word ≈ 4 characters**. A 2-page resume is ~1,000–1,500 tokens. Rare words (names, places, product codes) split into more tokens, one reason models handle them less reliably.

### 2.2 How an LLM generates text
An LLM only ever predicts **the next token**:
```
Input: "The candidate has 5 years of experience in"
Model scores every possible next token:  " Python" 0.21 · " Java" 0.14 · " software" 0.09 · ...
Pick one → append → feed everything back → predict again → repeat until done
```
Inside, the text passes through a **Transformer**: an embedding table turns token IDs into vectors; many stacked layers of **self-attention** (each token looks back at earlier tokens to gather context, e.g. "it" → "the payment system") and **feed-forward networks** (where much of the learned knowledge lives) refine them; a final layer scores the whole vocabulary.

**Consequences we design around:**
- It produces *plausible* text, not *verified* text, so it can **hallucinate**.
- It has **no memory** between calls; a chat resends the whole conversation each time.
- It knows nothing about our employees, so it needs **retrieval**.

### 2.3 Chat template, system and user messages
Chat models receive a list of messages:
```python
[{"role": "system", "content": "You extract facts... Use ONLY information in the resume."},
 {"role": "user",   "content": "<resume> ... </resume>"}]
```
- **System:** standing rules. **User:** the task and data. **Assistant:** earlier replies (for chats).
- Ollama wraps these in the model's **chat template** (special role markers, sometimes a hidden default system message). On this PC a 12-word question became **42 tokens**.
- We fence resume text in `<resume>…</resume>`, so instructions hidden inside a resume ("rate me 10/10") stay *data*, not commands. This is a basic defence against **prompt injection**.

### 2.4 Context window
The maximum number of tokens the model sees at once (prompt plus answer). We set `num_ctx = 8192`. **If the prompt is longer, Ollama silently drops the beginning**, which is usually your instructions. That's why long resumes are truncated deliberately, with a warning.

### 2.5 Prefill and decode: where the time goes
```
Prefill: read the whole prompt at once (parallel)        this PC: ~37 tok/s (7B), ~86 tok/s (3B)
Decode : write the answer one token at a time            this PC: ~7.7 tok/s (7B), ~16.7 tok/s (3B)
```
Extracting one resume with the 7B model: ~25 s reading plus ~73 s writing. **On a CPU the answer's length dominates**, so prompts ask for short descriptions and short evidence quotes.

**Why a CPU is slow:** generating each token means reading every parameter from memory once. Speed ≈ memory bandwidth ÷ model size. A GPU's memory is 10–20× faster, which is the whole GPU advantage.

### 2.6 Sampling and temperature
After scoring all tokens, one must be chosen:
| Setting | Effect | Our use |
|---|---|---|
| `temperature 0` | Always the most likely token: repeatable | Extraction, judging |
| `temperature 0.3–0.7` | Some variety | Chat answers (Step 10) |
| `top_p`, `top_k` | Only consider the most likely tokens | Defaults |
| `num_predict` | Maximum tokens to generate | 2,048 for extraction |
| `seed` | Fix the randomness | Evaluations |

### 2.7 Quantisation and model size
Parameters are normally 16-bit numbers: an 8B model = 16 GB, too big for 16 GB of RAM. **Quantisation** stores them with ~4–5 bits (Ollama's `Q4_K_M`): ~4.9 GB, with a small quality loss.

| Size class | Quality | This PC's speed | Typical use |
|---|---|---|---|
| 1–4B | Basic reasoning, decent extraction | Fast | Extraction, routing, chat |
| 7–9B | Clearly better reasoning | ~2× slower | Judging, explanations |
| 30–70B+ | Much better | Needs a GPU server | Production quality |

### 2.8 Licences
Open models have different licences: `qwen2.5:7b` is Apache 2.0; `qwen2.5:3b` uses the Qwen Research Licence (may restrict commercial use); Llama models use the Llama Community Licence. **Check before company use.**

---

## 3. Getting reliable output from an LLM

### 3.1 Prompt engineering
Writing instructions the model follows reliably: clear rules, the exact output fields, what to do when information is missing, and examples. Prompts live in `app/extraction/prompts.py` so changes are easy to compare.

### 3.2 Structured output (constrained decoding)
```
Output so far:  {"headline":
Model's top scores:  "Sure" 0.30 · "\"" 0.25 · "null" 0.05
Grammar from our JSON schema allows only:  "\"" or "null"     ← "Sure" is BLOCKED
Chosen:  "
```
Passing a **JSON schema** in Ollama's `format` field blocks every token that would break the schema, so the output is always valid JSON of the right shape. It guarantees the **shape**, not the **truth**.
- **In our project:** `ResumeExtraction.model_json_schema()` (Step 5).
- **Alternatives:** "function calling" / "tool use" in cloud APIs; asking for JSON and retrying (less reliable).

### 3.3 Hallucination
The model states something false with confidence, e.g. adding "Kubernetes" to a resume that never mentions it.
**Defences in this project:**
| Defence | Step |
|---|---|
| "Use ONLY the resume" rules, temperature 0 | 5 |
| Every skill needs an **evidence quote**; code checks the quote exists in the text | 5 |
| **Job-level grounding**: a skill counts for a job only if written in that job's text | 5b |
| Retrieved chunks shown as evidence | 6 |
| Judge explanations must cite resume text | 8 |

### 3.4 "The LLM reads, code checks"
| Task | Who | Why |
|---|---|---|
| Find titles, companies, skills in messy text | LLM | Language understanding |
| Recognise "FastAPI work implies Python" | LLM | World knowledge |
| Copy dates as written | LLM | Just copying |
| Dates → numbers, total years, overlap merging | Code | LLMs are unreliable at arithmetic |
| "k8s" → "Kubernetes" | Code (catalog) | Must be identical across thousands of resumes |
| Is the skill really in the resume? | Code | A model can't reliably check itself |

---

## 4. Embeddings

### 4.1 What an embedding is
An **embedding model** turns text into a fixed-length list of numbers, a **vector** (768 numbers for nomic-embed-text). It was trained so that texts with **similar meaning** get **similar vectors**.

```
                ▲ dimension 2 (imagine 768 of these)
                │      • "Operate EKS clusters (k8s)"
                │   • "container orchestration"
                │
                │                        • "Head chef, 5-star hotel"
                └──────────────────────────────▶ dimension 1
```

### 4.2 Cosine similarity
How close two vectors point, measured by the angle: **1** = same direction (same meaning), **0** = unrelated.
```
cos(a, b) = (a · b) / (|a| × |b|)
a · b = a1×b1 + a2×b2 + ... + a768×b768
```
Ollama returns vectors of length 1, so cosine equals the plain dot product. ChromaDB returns a **distance** = 1 − similarity.

### 4.3 Task prefixes (asymmetric search)
nomic-embed-text was trained with instructions in front of the text:
- stored chunks: `search_document: <text>`
- queries: `search_query: <text>`

A short question and a long passage about it then land close together. Leaving prefixes out lowers quality.

### 4.4 What we measured (Step 6)
- Related texts score in a narrow band: **0.52–0.67**. #1 and #2 were often **< 0.01** apart (**score compression**). Only the order matters; close scores are ties.
- "k8s" is weakly linked to "container orchestration": abbreviations are a weak spot.
- Very short chunks match many unrelated queries moderately (**short-chunk noise**).

### 4.5 Embedding model vs LLM
| | Embedding model | LLM |
|---|---|---|
| Output | A vector | Text |
| Job | Measure similarity | Read, reason, write |
| Size | ~137 M parameters | 3–7 B parameters |
| Speed here | ~50 ms per query | ~50–100 s per resume |
| Ours | nomic-embed-text | qwen2.5 |

Alternatives: `bge-m3` (multilingual, long texts), `mxbai-embed-large`, `embeddinggemma`; commercial OpenAI, Cohere, Voyage.

---

## 5. Retrieval

### 5.1 Chunking
Splitting documents into small pieces before embedding. One vector per whole resume would be a blurry average of everything; one vector per topic is precise.

| Strategy | How | Trade-off |
|---|---|---|
| Fixed-size | Every N characters | Cuts sentences and jobs |
| Recursive | Split at paragraphs → lines → sentences → words | Good general default |
| Structure-aware | Headings, tables, layout | Needs good parsing |
| Semantic | Cut where meaning changes (embeds every sentence) | Slow on CPU |
| **Domain-aware (ours)** | Profile card + one chunk per job + the rest, each with a contextual header, anonymised | Uses Step 5's job boundaries |

Libraries: LangChain text splitters, LlamaIndex, Chonkie, Docling.

### 5.2 Vector database and HNSW
A vector database finds the stored vectors nearest to a query vector. Comparing against all of them (**brute force**) is exact but grows linearly. **HNSW** builds a layered graph where each vector links to its nearest neighbours:
```
Layer 2 (sparse):   A ─────────────────── F                 long jumps
Layer 1:            A ──── C ──── F ──── H
Layer 0 (all):      A─B─C─D─E─F─G─H─I─J─K                    fine steps
Search: enter at the top, walk greedily towards the query, drop a layer, refine.
```
It visits a few hundred vectors instead of millions: milliseconds, approximate but almost always exact at our scale. Our ChromaDB search takes single-digit milliseconds.

### 5.3 Keyword search and BM25
Ranks documents by matching **words**:
- a word appearing more often in a chunk scores higher (with diminishing returns);
- **rare words count more** ("Kubernetes" > "worked");
- long chunks are slightly penalised.

It finds exact terms ("CKA", "SAP FICO") that embeddings blur, but misses synonyms.

**In our project (Step 7):** SQLite **FTS5**, a full-text index built into SQLite (no extra server).
```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id UNINDEXED, resume_id UNINDEXED, employee_id UNINDEXED, text);
SELECT chunk_id, bm25(chunks_fts) FROM chunks_fts
 WHERE chunks_fts MATCH '"kubernetes" OR "k8s" OR "kube"' ORDER BY bm25(chunks_fts);   -- more negative = better
```
- We search for **every spelling** of each required skill, taken from the skill catalog, so "k8s" in Priya's resume is found for "Kubernetes".
- `snippet()` returns the matching words in context (`[k8s] 1.2x hosting 300+ …`) as evidence.
- **Alternatives:** PostgreSQL full-text search (`tsvector`), Elasticsearch / OpenSearch (BM25 at company scale), Tantivy, `rank_bm25` (Python, in memory); learned sparse models such as SPLADE or bge-m3's sparse output.

### 5.4 Hybrid search and Reciprocal Rank Fusion (RRF)
Run several searches and merge their **rankings**:
```
RRF score(doc) = Σ over lists  1 / (k + rank in that list)        k = 60

Example: Priya is #2 in vector search and #1 in keyword search
         1/(60+2) + 1/(60+1) = 0.0161 + 0.0164 = 0.0325
         Ananya is #1 in vector search, absent from keyword search
         1/(60+1)            = 0.0164
→ Priya wins: being good in BOTH lists beats being best in one.
```
RRF uses ranks, not raw scores, so score compression doesn't matter.

**In our project (Step 7)** there are three lists, not two: **skills** (structured data), **keyword** (BM25) and **vector** (embeddings). Each has a weight (`RRF_WEIGHT_*`, default 1.0) so one signal can count more after evaluation. Every candidate keeps its rank in each list (`ranks: {"skills": 1, "keyword": 3, "vector": null}`), so you can see *why* someone was found.

**Alternatives:** weighted score sums (needs score normalisation, sensitive to compression), learning-to-rank models (need labelled data), a cross-encoder or LLM reranker on top (Step 8).

### 5.5 Filters
Structured conditions applied before or during retrieval: available, location, allocation, minimum years. Embeddings can't do these; SQL can.

**Pre-filter vs post-filter.** We pre-filter: only *eligible* people (active, current READY resume, and with `only_available=true` also free enough) are searched; ChromaDB gets `where={"employee_id": {"$in": [...]}}`. Post-filtering (search everything, drop ineligible afterwards) can leave you with too few results.

### 5.5b Structured skill matching (Step 7)
Uses Step 5's verified data, not text. For each required skill the best matching employee skill earns a **credit** between 0 and 1:
```
credit = base × years factor × recency
  base      1.0 exact skill · 0.6 implied skill (Amazon EKS ⇒ Kubernetes, Django REST Framework ⇒ Django)
  years     0.4 + 0.35 × min(1, years ÷ needed) + 0.25 × depth     depth = ln(1+years)/ln(11), max 1
            (meeting the minimum matters most; more years still help, with diminishing returns)
  recency   last used ≤ 1 year ago 1.0 · ≤ 3 years 0.8 · older 0.5 · unknown 0.8
rarity    = 1 + ln((N + 1) ÷ (n + 1))       N eligible people, n of them have the skill   (IDF, as in BM25)
must part = Σ 2 × rarity × credit over must-haves        coverage = must part ÷ its maximum
nice part = Σ 1 × rarity × credit over nice-to-haves
skill score = (must part + nice part × coverage) ÷ (max must part + max nice part)
```
- **Rarity (IDF):** a skill most people have (Python: 1.31) counts less than one that defines the role (RAG: 3.0).
- **Coverage gating:** nice-to-haves only count in proportion to how well the must-haves are met, so "FastAPI + Docker" can't lift someone without LLM experience above someone with it.
- Matching is **case-insensitive**, and every requirement is re-normalised at search time (older or hand-edited requirements benefit from catalog improvements).
Example: Divya (Django, last used 2019) gets recency 0.5 for Django, so a current Django developer outranks her even with fewer years. This is how "recent hands-on" is expressed without asking an LLM.

**Implied skills** live in a small hand-written map (`SKILL_IMPLIES` in `app/extraction/skills.py`). Enterprise alternatives: a skills **taxonomy / ontology** such as ESCO or O*NET, Lightcast Open Skills, or a knowledge graph (Neo4j) with "is-a" and "requires" edges.

### 5.5c Query understanding (role parsing)
Before searching, the LLM turns the free-text role description into requirements (must-have, nice-to-have, minimum years, seniority, location, a one-sentence search summary), using the **same skill catalog** as resume extraction so both sides use identical names. Code then cleans the LLM's names: a compound like "retrieval-augmented generation using vector databases" is split into the known skills inside it (RAG, Vector Databases); "nlp fundamentals" becomes NLP. It runs **once per role** and the result is stored and editable, so its 30–60 s on a CPU are acceptable and the quality model is used. Alternatives: a form where the manager picks skills (exact, more work), or query rewriting/expansion (HyDE: generate a hypothetical ideal resume and embed that).

### 5.6 Reranking
A second, slower, more careful pass over the top results.
```
Bi-encoder (embeddings):  query → vector, chunk → vector, compare      fast, done in advance
Cross-encoder (reranker): [query + chunk] → one relevance score         reads both together, more accurate
LLM judge (ours, Step 8): [role + profile + chunks] → score + reasons   slowest, explains itself
```
Alternatives: `bge-reranker`, Cohere Rerank.

---

## 6. Generation: judging and explaining (Step 8)

### 6.1 LLM-as-a-judge
The LLM scores each shortlisted employee against the role with a fixed **rubric** and returns JSON: score, strengths, gaps, evidence quotes.
**Risks and controls:** inconsistency (temperature 0, fixed rubric); bias (anonymised text, plain-code scores alongside); hallucination (quotes are checked against the resume).

### 6.2 Grounding and citations
Every claim points to resume text a person can check: *"Ananya: rebuilt claims APIs serving 2M requests/day."* This is what makes recommendations trustworthy and auditable.

---

## 7. Agents (Step 10)
An **agent** is an LLM in a loop that can **choose tools** (functions we provide), look at the results and decide the next action:
```
User: "Find a DevOps lead for the Retail migration, Pune only"
LLM → call search_candidates(role="DevOps lead...", filters={"location": "Pune"})
    ← results
LLM → call get_candidate_profile(id=3)
    ← profile
LLM → answer with reasons and citations
```
The core matching works without an agent; the agent is a conversational layer on top. **Built in Step 10:** see document 14 for agent fundamentals (tool calling, ReAct, memory, guard-rails, patterns) and our implementation. Alternatives: a form-based UI; frameworks such as LangGraph, PydanticAI and the OpenAI Agents SDK.

---

## 8. Evaluation
Measure instead of guessing, with a **test set** (`roles.json` expected rankings, the checks in `compare_extraction.py`).

| Metric | Question it answers | Example |
|---|---|---|
| **Precision@k** | Of the top k results, how many are correct? | 3 of the top 5 are relevant → 0.6 |
| **Recall@k** | Of all correct people, how many appear in the top k? | 2 of 3 relevant people in top 5 → 0.67 |
| **MRR** | How high is the first correct result? | First correct at rank 2 → 1/2 = 0.5 |
| **nDCG** | Are the best people near the top, in the right order? | 1.0 = perfect order |

Ground truth can be wrong too: in Step 6 the search found a genuine insurance-domain match the expected list had missed.

---

## 9. Responsible AI in this project
| Concern | Our approach |
|---|---|
| **Privacy** | Local models only; personal data never leaves the PC; cascade deletes (DPDP Act) |
| **Fairness / bias** | Anonymised chunks (no names, emails, phones); skill-based scoring; human makes the final decision |
| **Transparency** | Evidence quotes, matched chunks, stored match runs with reasons |
| **Accuracy** | Grounding checks, deterministic calculations, evaluation scripts |
| **Regulation** | AI for hiring and work allocation is **high-risk** under the EU AI Act; relevant if the company operates in the EU |
