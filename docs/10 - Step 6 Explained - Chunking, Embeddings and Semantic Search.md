# 10 · Step 6 Explained: Chunking, Embeddings and Semantic Search

This document explains Step 6 from start to finish: **why** it exists (and why Step 5's structured data isn't enough), **what** it gives the user, **how** every part works, with the AI ideas behind it, **every file** that was added or changed, and **which alternatives** exist, from hobby projects to world-class enterprise systems.

**Read first:** 09 (Step 5 Explained). **Read with:** 03 (AI & RAG Concepts, §4–5) for the theory, 04 (Pipeline Deep Dive, stages ⑥–⑨) for Priya's real chunks, 07 for the measured results. Step 7 builds directly on this: document 11.

---

## 1. Where Step 6 sits: Steps 1 to 6 as one story

| Step | What it gave us | What was still missing |
|---|---|---|
| 1 | Python, Node, Ollama and three models on this PC; measured speeds (7B: 7.7 tok/s, 3B: 16.7 tok/s) | Any program |
| 2 | FastAPI server, settings, **the Ollama client** (`/api/chat`, `/api/embed`), health check | Data |
| 3 | 12 database tables: employees, resumes, profiles, skills, **`resume_chunks`**, projects, matches | Content in them |
| 4 | Upload, validation, duplicate check, **text extraction** (`resumes.raw_text`), background worker and queue | Understanding of the text |
| 5 / 5b | The LLM reads each resume once → **structured facts** (jobs, skills with years and evidence), verified by code | **A way to search by meaning**, and a way to keep everything the resume says |
| **6** | **Chunks** of the original text → **vectors** → **ChromaDB**; semantic search endpoint | Combining with facts and keywords → Step 7 |

The worker's stages after Step 6:
```
queued ─parse(4)─▶ parsed ─extract(5)─▶ extracted ─embed(6)─▶ ready
```
A resume is only searchable once it reaches **ready**, after Step 6's stage.

---

## 2. Why we need Step 6

### 2.1 "Step 5 already gives us skills and years. Why chunks, vectors and a vector database?"
This was your question before Step 6, and it's the right one. Step 5's facts are excellent for **exact** questions ("who has Django, how many years, used when?"). But they are a **summary**, and summaries lose things:

| What a resource manager asks | Step 5 facts | Original text |
|---|---|---|
| "Kubernetes, 5+ years" | ✅ skill + years | ✅ |
| "Has worked on **insurance claims** systems" | ❌ domains aren't extracted | ✅ "rebuilt claims-processing APIs" |
| "Has **mentored** junior developers" | ❌ not a skill | ✅ "mentored 4 junior engineers" |
| "Handled **2M requests/day** at low latency" | ❌ numbers aren't kept | ✅ the exact sentence |
| "**Design systems** for the web" | ❌ unless "Storybook" is in the catalog | ✅ "built a React component library…" |
| A skill **not in our catalog** | kept as written, unrelated to similar ones | ✅ in context |

And a person reading a recommendation wants **evidence**: the actual sentence from the resume, not "the AI says so". So we need to keep **the text** and **search it by meaning**.

### 2.2 Why not search the raw text with keywords only?
Because people write the same thing in different words: "container orchestration" vs "k8s"; "on-call" vs "production support"; "design system" vs "component library". Keyword search matches **words**; we also need to match **meaning**. That's what embeddings do.

### 2.3 Why not just give the LLM all resumes and ask?
- 2,000 resumes × ~1,200 tokens = **2.4 million tokens**. Our context window is 8,192.
- Even if it fit, reading it on this CPU (≈ 37 tok/s prefill for the 7B) would take ~18 hours **per question**.
- RAG's whole idea: **retrieve** the few relevant pieces first, then let the LLM read only those.

### 2.4 What Step 6 is, in one sentence
> **Step 6 cuts every resume into small, self-contained, anonymised pieces (chunks), turns each piece into a vector that captures its meaning, stores those vectors in a vector database, and lets us find the employees whose resume pieces are closest in meaning to any question.**

In RAG terms: Steps 4–6 build the **knowledge base and its index**. This is the "**indexing**" half of RAG; Step 7 is "retrieval", Step 8 "generation".

---

## 3. What it looks like for the user

**Admin (end-user view):** nothing to do. After a resume's extraction finishes, the worker automatically chunks and indexes it in about a second; its status goes `extracted → embedding → ready`. `GET /api/resumes/stats` shows `vector_count` (60 for our 14 resumes). `GET /api/resumes/{id}/chunks` shows exactly how a resume was cut, for anyone curious or debugging.

**Resource manager (end-user view):** types a question in plain words, e.g. *"container orchestration and infrastructure as code"*, and gets employees ranked by how well their resume **means** that, each with the matching resume passages and a similarity score. No need to guess the exact words a resume used.

**Developer view:** a new worker stage (`embed`), a new package `app/rag/` (chunking, embeddings, vector store, search), the ChromaDB files in `data/chroma/`, two endpoints, a demo script and two maintenance endpoints (`reembed`, `reextract`).

---

## 4. The flow, in the order it runs

### 4.1 Indexing one resume (the worker's embed stage, ~1–2 s)
```
IngestionWorker._claim()            oldest resume with status EXTRACTED → set EMBEDDING, COMMIT
IngestionWorker._embed()
 └─ app/services/indexing.py: index_resume(resume_id)
     1. READ (short session)   resume + employee + profile + experiences + skills    (selectinload: one query per relationship)
     2. CHUNK                  app/rag/chunking.py: build_chunks(...)               pure Python, milliseconds
           ① profile card   from Step 5 facts: headline, total years, summary, skills with years
           ② one chunk per job   that job's ORIGINAL text, found in raw_text by title + company
           ③ "other" chunks      everything not used above (contact, skills list, education, certs)
           each: contextual header first line · anonymised · split if longer than ~1,200 characters
     3. EMBED                  app/rag/embeddings.py: embed_documents(...)
           "search_document: " + chunk text → Ollama /api/embed (16 per call) → 768 numbers each
     4. VECTORS → ChromaDB     app/rag/vector_store.py: replace_resume(...)
           delete this resume's old vectors, add new ones (id, vector, text, metadata)
     5. ROWS → SQLite (one transaction)
           delete old resume_chunks rows, insert new ones (same ids as the vectors), status = READY, COMMIT
errors: Ollama down → back to EXTRACTED, wait 30 s · other → retry ×3 → FAILED · deleted meanwhile → vectors removed
```

### 4.2 Searching (per request, ~50 ms warm)
```
POST /api/search/semantic {"query": "container orchestration", "top_k": 10}
 └─ app/api/search.py → app/rag/search.py: semantic_search()
     1. embed_query()          "search_query: container orchestration" → 768 numbers   (most of the ~50 ms; ~2 s if the model is cold)
     2. ChromaDB query         60 nearest chunks by cosine similarity (HNSW)            (single-digit ms)
     3. validity check (SQL)   keep only chunks of resumes that are CURRENT and READY
     4. group by employee      one person can match through several chunks; best chunk = their score
     5. rank, keep 3 chunks per person as evidence, return JSON with timings
```

### 4.3 Maintenance
- `POST /api/resumes/reembed`: every ready resume back to `extracted` → the worker re-chunks and re-embeds them. Use after changing chunking or the embedding model.
- `POST /api/resumes/reextract`: back to `parsed` → re-extraction (Step 5) **and then** re-embedding automatically.
- Uploading a new version / deleting a resume removes the old vectors (`app/services/resumes.py`).

---

## 5. The AI ideas in Step 6

### 5.1 Embeddings: meaning as numbers
An **embedding model** turns a text into a fixed-length list of numbers, a **vector**. `nomic-embed-text` gives **768 numbers** for any text, short or long. It was trained (contrastive learning, on hundreds of millions of text pairs such as question–answer and title–body) so that texts with **similar meaning** end up with **similar vectors**, and unrelated texts far apart.

**How it works inside (simplified):**
```
"Operate 14 EKS clusters (k8s 1.2x)"
  → tokens  → token embeddings  → 12 Transformer encoder layers (every token attends to every other token,
                                    in both directions: "clusters" learns it's about EKS, not data clusters)
  → one vector per token  → averaged ("mean pooling") → normalised to length 1  → 768 numbers
```
Unlike an LLM, it **doesn't generate** anything: one pass, no token-by-token decoding. That's why embedding a chunk takes milliseconds while extraction takes a minute.

| | nomic-embed-text (ours) | qwen2.5:7b (Step 5) |
|---|---|---|
| Type | Encoder (reads both directions) | Decoder (predicts the next token) |
| Parameters | ~137 million | ~7.6 billion |
| Output | 768 numbers | Text |
| Context | up to 8,192 tokens (v1.5) | 8,192 as we configured it |
| Speed here | a whole search ≈ 50 ms when warm (~2 s cold start) | ~7.7 tokens per second |
| Licence | Apache 2.0 | Apache 2.0 |

**What the 768 numbers mean:** no single number means "Kubernetes"; meaning is spread across all of them (a "distributed representation"). Only **comparisons** between vectors are meaningful.

### 5.2 Cosine similarity
How close two vectors point, measured by the angle between them:
```
cos(a, b) = (a · b) ÷ (|a| × |b|)          1 = same direction, 0 = unrelated, −1 = opposite
a · b = a1×b1 + a2×b2 + … + a768×b768
```
Ollama returns vectors of length 1, so cosine is just the dot product. ChromaDB reports **distance = 1 − similarity**; our code converts it back.

**What we measured:** related texts score in a narrow band (**0.52–0.67**); #1 and #2 were often **< 0.01** apart. This is **score compression**: absolute values say little, only the **order** matters. (It's why Step 7 fuses by rank, not by score.)

### 5.3 Task prefixes: asymmetric search
nomic-embed-text was trained with an instruction in front of each text:
- stored chunks: `search_document: <text>`
- questions: `search_query: <text>`

A short question and a long passage that answers it are different kinds of text; the prefixes teach the model to map them to the same place. Leaving them out lowers search quality noticeably (you can compare with `/api/dev/similarity`, `use_prefixes`).

### 5.4 Chunking: why pieces, and why our pieces
**One vector per whole resume** would be an average of a DevOps job, a Java job, education and contact details: a blurry point that matches nothing sharply. **One vector per topic** is precise. The chunk is the unit of **search** and of **evidence**.

**Size trade-off:**
| Too small (one line) | Right (~300 tokens, one topic) | Too large (whole resume) |
|---|---|---|
| Loses context ("led the migration": of what?) | One job or section with its context | Several topics averaged together |
| Matches many queries a little (noise) | Clear meaning, readable as evidence | Matches nothing strongly; long to read |

**Our strategy: domain-aware chunking.** We know what a resume is made of, and Step 5 already found the jobs. So instead of cutting every N characters:
1. **Profile card**: built from Step 5's facts: headline, total years, summary, skills with years. One chunk that represents the whole person.
2. **One chunk per job**, using the job's **original text** from the resume (located by its title and company), never cut mid-job unless it's longer than the limit.
3. **Other**: everything not used above, so **nothing from the resume is lost**.
Long pieces are split at line boundaries with **overlap** (~150 characters repeated), so a sentence cut at the border is still whole in one of the two pieces.

### 5.5 Contextual headers
Every chunk starts with one line saying what it is:
```
Employee EMP-1003 | Experience | Senior DevOps Engineer at Nimbus Technologies (2020 - present)
- Operate 14 EKS clusters (k8s 1.2x) hosting 300+ microservices. ...
```
Without it, the bullet list alone doesn't say whose job, which role, or when. With it, the chunk makes sense **on its own**: to the embedding model (better vector) and to a person or LLM reading it later. Anthropic published this idea as **contextual retrieval** (2024): prepending context to each chunk reduced retrieval failures substantially in their tests. We do a cheap version from data we already have; they generate the context with an LLM. (Step 7 added a second line, `Skills used: …`.)

### 5.6 Anonymisation: privacy and fairness by design
Before indexing, names, emails and phone numbers are replaced (`[name]`, `[email]`, `[phone]`); since Step 7 also gendered pronouns. Two reasons:
- **Privacy:** the search index and anything that reads it (the Step 8 judge) don't need to know who someone is to judge their experience.
- **Fairness:** names can signal gender, ethnicity or religion; models can be biased by them. Matching should be about skills and experience. The employee is linked through **metadata** (`employee_id`), not through text.

### 5.7 Vector database, nearest-neighbour search and HNSW
A **vector database** stores vectors with their ids, text and metadata, and answers: *"which stored vectors are nearest to this one?"*

- **Brute force** (compare against every vector) is exact but grows linearly: fine for 60 chunks, slow for 50 million.
- **Approximate nearest neighbour (ANN)** indexes trade a tiny bit of accuracy for huge speed. ChromaDB uses **HNSW** (Hierarchical Navigable Small World graphs):
```
Layer 2 (few nodes):  A ─────────────── F                    long jumps across the space
Layer 1:              A ──── C ──── F ──── H
Layer 0 (all nodes):  A─B─C─D─E─F─G─H─I─J─K                   short steps between close neighbours
Search: start at the top layer, walk greedily towards the query, go down a layer, refine, repeat.
```
It visits a few hundred vectors instead of millions → milliseconds. Settings: `space = cosine` (how distance is measured); defaults for graph size and search depth are fine at our scale.

**Metadata** stored with each vector (`resume_id`, `employee_id`, `employee_code`, `section`, `chunk_index`, `embedding_model`) allows **filtering** (Step 7 searches only eligible employees) and **tracing** a hit back to the database.

### 5.8 Source of truth vs index
**SQLite** (`resume_chunks`) holds the chunk text, with the **same ids** as the vectors. **ChromaDB** is an **index**: a fast, derived copy that can always be rebuilt (`reembed`). This means:
- we can change chunking or the embedding model freely and rebuild;
- if ChromaDB were lost or corrupted, nothing is lost;
- the validity check in search (current + ready) uses SQLite, so a stale vector can never surface an old resume.

**Write order:** ChromaDB first, then SQLite with `status = READY`. If SQLite fails, the status is still `EMBEDDING`, the stage is retried, and `replace_resume` (delete, then add) makes the retry safe: it's **idempotent**.

**Embedding model consistency:** vectors from different models live in different "spaces" and can't be compared. Each chunk records `embedding_model`; changing the model means `reembed` everything.

### 5.9 Group by person
Search returns **chunks**; users want **people**. One person can match through several chunks (a job and their profile card). We keep the **best chunk's** similarity as the person's score and up to **3 chunks** as evidence. (Alternatives: sum or average of top chunks; Step 7 instead fuses ranks.)

### 5.10 What semantic search can't do (and why Step 7 exists)
Measured in Step 6:
- **Abbreviations:** "k8s" is weakly linked to "container orchestration": Priya lost #1 by 0.006.
- **Short chunks are noisy:** they match many queries a little.
- **It always returns someone:** even for a skill nobody has, the nearest vector exists.
- **No numbers or rules:** it can't count years, check recency or availability.
- **Compressed scores:** hard to set a threshold.
These are exactly what Step 7's keyword search, structured matching and rank fusion fix.

---

## 6. The files, one by one

### 6.1 `app/rag/chunking.py` (new): cutting a resume into pieces
**Purpose:** resume text + Step 5 facts → a list of `ChunkDraft(section, text)`. **Pure functions:** no database, no Ollama, so they're easy to read and test.

| Piece | What it does |
|---|---|
| `JobInfo`, `ChunkDraft` | Dataclasses: a job's facts; a chunk's section and text. `token_estimate` = characters ÷ 4 (Step 1's rule of thumb) |
| `_HEADING` | Regular expression for section headings (EDUCATION, SKILLS, …): a job chunk stops there |
| `_EMAIL`, `_PHONE`, `anonymize()` | Replace emails, phones, the full name and each name part (≥ 3 letters), and gendered pronouns |
| `split_text()` | Splits long text at **line boundaries** into ≤ `max_chars` pieces with ~`overlap` characters carried over; hard-cuts a single enormous line |
| `_period()` | "2020 - present": years only, because "2018" in a resume is stored as 1 Jan 2018 and months would mislead |
| `_find_job_lines()` | Finds where each job starts in the raw text: company on a line with the title on the same or a neighbouring line; falls back to the company alone; searches after the previous job first (resumes list jobs in order) |
| `build_chunks()` | ① profile card ② one chunk per located job (until the next job, a heading, or 40 lines) ③ the remaining lines as "other". Falls back to Step 5's job description if a job can't be located |

**Why it relies on Step 5:** the profile card comes from Step 5's facts, and job boundaries come from Step 5's list of jobs. Steps build on each other.

### 6.2 `app/rag/embeddings.py` (new): text → vectors
Two functions and two constants:
- `embed_documents()`: adds `search_document: `, sends chunks in **batches** of `EMBED_BATCH_SIZE` (16) per HTTP call (one call per chunk would be much slower).
- `embed_query()`: adds `search_query: `, one text.
**Why a separate file:** the prefixes are a property of *this* model; if we switch models (e.g. to `bge-m3`, which uses different instructions), only this file changes.

### 6.3 `app/rag/vector_store.py` (new): the ChromaDB adapter
| Piece | What it does |
|---|---|
| `ChunkHit` | One search result: ids, section, text, similarity |
| `VectorStore.__init__` | `PersistentClient(path=data/chroma, anonymized_telemetry=False)`: data on disk, no usage data sent; collection with `embedding_function=None` (we bring our own vectors from Ollama) and cosine HNSW |
| `replace_resume()` | Delete this resume's vectors, add the new ones: idempotent |
| `delete_resume()` | Remove a resume's vectors |
| `query()` | Nearest `n_results` vectors (optionally with a `where` filter), converts distance to similarity |
| `get_vector_store()` | `@lru_cache`: one shared instance for the whole process (opening ChromaDB isn't free) |

**Why an adapter:** it's the **only** file that knows ChromaDB. Moving to Qdrant or pgvector means rewriting this one file; nothing else changes (document 01, "one adapter per outside system").

**Why `asyncio.to_thread` around its calls:** ChromaDB's API is synchronous; calling it directly would freeze the server for every other request while it works.

### 6.4 `app/rag/search.py` (new): semantic search
`semantic_search()` performs §4.2: embed, query a pool of 60 chunks, keep valid ones (two SQL queries), group by employee, rank, time each phase. `EmployeeMatch` holds a person, their score and their evidence chunks.

### 6.5 `app/services/indexing.py` (new): indexing one resume
`index_resume()` performs §4.1 with three deliberate design choices:
1. **Short database sessions:** read, close; chunk and embed (slow) **outside** any transaction; open a new session to write. Long transactions would lock SQLite for other requests.
2. **Order of writes:** ChromaDB first, SQLite + READY last (§5.8).
3. **Deleted meanwhile?** If the resume vanished during embedding, its new vectors are removed again.
Also: `requeue_for_embedding()` (used by `reembed`) and `chunks_of()` (used by the chunks endpoint).

### 6.6 `app/api/search.py` and `app/schemas/search.py` (new)
- `POST /api/search/semantic`: validates `{"query": 2–2000 chars, "top_k": 1–50}`, calls the search, returns 503 if Ollama is down.
- `GET /api/resumes/{id}/chunks`: shows a resume's chunks (section, token estimate, model, text).
- Schemas: `SemanticSearchRequest`, `MatchedChunk`, `EmployeeResult`, `SemanticSearchResponse`.

### 6.7 Changed files
| File | Change | Why |
|---|---|---|
| `app/ingestion/worker.py` | Third stage `embed` (EXTRACTED → EMBEDDING → READY); crash recovery puts EMBEDDING back to EXTRACTED | Indexing runs automatically after extraction |
| `app/api/resumes.py` | `POST /reembed`, `vector_count` in stats | Maintenance and visibility |
| `app/services/resumes.py` | New version / delete → old vectors removed; when the current version is deleted, the newest remaining one is re-indexed | Only current resumes searchable |
| `resume_chunks` table (`ResumeChunk`, designed in Step 3) | Filled for the first time: `id` (= vector id), `section`, `chunk_index`, `text`, `token_count`, `embedding_model` | Source of truth for the index |
| `app/config.py`, `.env` | `CHROMA_DIR`, `CHROMA_COLLECTION`, `CHUNK_MAX_CHARS`, `CHUNK_OVERLAP_CHARS`, `EMBED_BATCH_SIZE`, `ANONYMIZE_CHUNKS` | Tunable without code changes |
| `app/main.py` | Opens the vector store at startup, logs its count | Fails early if ChromaDB is broken |
| `requirements.txt` | `chromadb` | The vector database |

### 6.8 `scripts/try_search.py` (new)
Seven demo queries written **without the resumes' words** ("container orchestration" for a resume that says "k8s"), each with the person expected near the top. Prints the top 3, scores and the best chunk. Our first, informal evaluation of meaning-based search: 7/7 expected in the top 3, 5/7 at #1.

---

## 7. Python you'll meet in Step 6

| Code | Meaning |
|---|---|
| `re.compile(r"...", re.IGNORECASE)` | A **regular expression**: a pattern for finding text (emails, phones, headings) |
| `re.sub(pattern, replacement, text)` | Replace every match |
| `rf"\b{re.escape(part)}\b"` | Raw f-string pattern; `\b` = word boundary; `re.escape` makes a name safe inside a pattern |
| `@dataclass` + `@property` | A data class with a computed field (`token_estimate`) |
| `for i in range(0, len(texts), batch_size): texts[i:i + batch_size]` | Process a list in batches |
| `dict.setdefault(key, default)` | Get the value, or insert the default first (grouping chunks by employee) |
| `zip(a, b, c)` | Walk several lists in step (ids, texts, metadata, distances) |
| `@lru_cache` | Remember a function's result: here, one shared vector store |
| `uuid.uuid4()` | A random unique id, used for both the chunk row and its vector |
| `await asyncio.to_thread(f, ...)` | Run blocking code without freezing the server |
| `time.perf_counter()` | Precise timer for the `timings` |
| `selectinload(Resume.skills).selectinload(ResumeSkill.skill)` | Load related rows in a few queries instead of one per row |
| `(lambda t: anonymize(t, name)) if flag else (lambda t: t)` | Choose a small function once, use it many times |

---

## 8. Alternatives, industry standards and enterprise options

### 8.1 Component by component
| Component | Ours (learning, one PC) | Common production choice | World-class / enterprise scale |
|---|---|---|---|
| **Chunking** | Domain-aware (profile + per job + rest), contextual headers, overlap | LangChain / LlamaIndex recursive splitters; layout-aware parsing (**Docling**, Unstructured) | Structure + semantic chunking, LLM-generated chunk context (contextual retrieval), parent–child ("small-to-big") retrieval |
| **Embedding model** | `nomic-embed-text` (local, 768-d, Apache 2.0) | `bge-m3` (multilingual, dense + sparse), `mxbai-embed-large`, `embeddinggemma`, `snowflake-arctic-embed`; hosted OpenAI `text-embedding-3`, Cohere Embed, Voyage, Google | Domain-fine-tuned embeddings trained on the company's own matches; multi-vector models (**ColBERT**) |
| **Vector database** | ChromaDB embedded in the process | **pgvector** (inside PostgreSQL), **Qdrant**, Weaviate | Milvus / Zilliz, Pinecone, Vespa, Elasticsearch / OpenSearch k-NN, with replicas, sharding, backups |
| **Index type** | HNSW (cosine) | HNSW | HNSW + quantisation (PQ, binary) to fit billions of vectors in memory; DiskANN; IVF |
| **Anonymisation** | Regex for email/phone + name parts + pronouns | NER-based PII detection (**Microsoft Presidio**, spaCy) | PII services (AWS Comprehend, Google DLP) + policy engines + audit |
| **Index freshness** | Worker stage after extraction | Message queue (Celery/RQ, Redis, RabbitMQ) | Event streaming (Kafka) + change-data-capture from the HR system |
| **Evaluation** | 7 demo queries | Labelled query sets, recall@k / nDCG in CI | Continuous offline + online evaluation, embedding drift monitoring |

**How to choose an embedding model:** the **MTEB** leaderboard (Massive Text Embedding Benchmark) compares models on retrieval tasks; then test the top few **on your own data**, because benchmark rankings don't always transfer. Consider size (speed on your hardware), languages, context length, licence and whether it runs locally.

**How to choose a vector database:**
| Situation | Good choice |
|---|---|
| Learning, one machine, < 1 M vectors | ChromaDB (ours), LanceDB, FAISS |
| Already on PostgreSQL, < ~10 M vectors | **pgvector**: one database, transactions with your data, SQL filters (our Step 15 plan) |
| Dedicated, fast, rich filtering | Qdrant, Weaviate |
| Billions of vectors | Milvus, Vespa, managed Pinecone |
| Already running Elasticsearch/OpenSearch | Their built-in vector search, keyword and vector in one engine |

### 8.2 What "enterprise grade" adds
| Area | What it means here |
|---|---|
| **Versioned indexes** | Build a new index with a new model/chunking next to the old one, evaluate, then switch ("blue–green re-indexing") |
| **Metadata and access control** | Department / region / permission metadata on every vector, enforced in every query |
| **Right to be forgotten** | Deleting a person removes their vectors everywhere, verifiably (we do this via cascade + `delete_resume`) |
| **Monitoring** | Index size, query latency (p50/p95), empty-result rate, embedding service health |
| **Cost and capacity** | GPU or hosted embedding for bulk loads; quantisation for memory |
| **Data residency** | Where vectors live matters: vectors can leak information about the original text, so they're personal data too |

### 8.3 Why we chose what we chose
- **nomic-embed-text:** small enough to be fast on a CPU, long context, good retrieval quality, Apache 2.0, available in Ollama.
- **ChromaDB embedded:** no server, a `pip install`, files on disk, metadata filters; ideal for learning and for thousands of resumes. pgvector is the upgrade path.
- **Domain-aware chunking:** we already know the jobs from Step 5, so cutting at real job boundaries is better than any generic splitter.
- **SQLite as source of truth:** the index is disposable, so we can experiment freely.

---

## 9. What we measured (Step 6)
- 14 resumes → **60 chunks** (Priya: 4). After the Step 7 re-extraction: 58 chunks.
- Indexing: ~1–2 s per resume (embedding ~1 s).
- 7 demo queries without the resumes' words: expected person in the **top 3 for 7/7**, **#1 for 5/7**.
- Similarity scores 0.52–0.67; #1 vs #2 often < 0.01 apart.
- First query **2,014 ms** (model cold start), then **~50 ms**.
- Found: a genuine insurance-domain match missing from our own expected list (ground truth needs care too); pronouns in summaries reveal gender (fixed in Step 7).

---

## 10. Limitations to know about
- **Job location by title + company** can fail on unusual layouts; the chunk then falls back to Step 5's short description.
- **Regex anonymisation** misses names of other people mentioned in a resume (a manager's name) and unusual phone formats; NER-based tools do better.
- **Pronoun replacement** can break grammar ("They specializes"); the real fix is the neutral-summary prompt (Step 7).
- **One language:** nomic-embed-text is English-focused; multilingual resumes need `bge-m3` or similar.
- **The profile card is capped at twice the chunk limit** (2,400 characters): very long skill lists are cut off at the end.

---

## 11. Try it yourself
With the server running:
```powershell
# How resume 3 (Priya) was chunked
Invoke-RestMethod http://127.0.0.1:8010/api/resumes/3/chunks | ConvertTo-Json -Depth 4

# A meaning-based search
$body = '{"query": "people who mentored junior engineers", "top_k": 5}'
Invoke-RestMethod -Method Post http://127.0.0.1:8010/api/search/semantic -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 5

# Same meaning, different words: compare the scores
python -m scripts.try_search "kubernetes"
python -m scripts.try_search "container orchestration"

# Prefixes on vs off (dev endpoint)
$body = '{"text_a": "container orchestration", "text_b": "Operate 14 EKS clusters (k8s)", "use_prefixes": true}'
Invoke-RestMethod -Method Post http://127.0.0.1:8010/api/dev/similarity -ContentType 'application/json' -Body $body
```
Experiments worth doing:
1. Set `CHUNK_MAX_CHARS=400`, restart, `POST /api/resumes/reembed`, run `try_search`: are results noisier?
2. Set `ANONYMIZE_CHUNKS=false`, re-embed, and look at `/api/resumes/3/chunks`: names, emails and phones are back in the indexed text, where they can influence search and the Step 8 judge. That's why anonymisation is on by default. (Set it back and re-embed afterwards.)

---

## 12. Glossary for this step
| Term | Meaning |
|---|---|
| **Chunk** | A small, self-contained piece of a document; the unit of search and evidence |
| **Chunking strategy** | How documents are cut: fixed size, recursive, structure-aware, semantic, domain-aware |
| **Overlap** | Text repeated between neighbouring chunks so nothing is cut in half |
| **Contextual header** | A first line saying what the chunk is and whose it is |
| **Embedding** | A vector of numbers representing a text's meaning |
| **Encoder** | A Transformer that reads text in both directions to produce embeddings (vs a decoder that generates text) |
| **Mean pooling** | Averaging token vectors into one vector for the whole text |
| **Dimension** | How many numbers a vector has (768 here) |
| **Cosine similarity** | Closeness of two vectors by angle: 1 same, 0 unrelated |
| **Task prefix** | An instruction (`search_query:` / `search_document:`) the embedding model was trained with |
| **Vector database** | Stores vectors + metadata and finds the nearest ones |
| **ANN / HNSW** | Approximate nearest-neighbour search / the layered graph index that makes it fast |
| **Metadata filter** | Restricting a vector search by fields such as `employee_id` |
| **Source of truth** | The authoritative data (SQLite); indexes are rebuildable copies |
| **Idempotent** | Running it twice gives the same result as once |
| **Score compression** | Similar texts all scoring in a narrow band, so only order matters |
| **Indexing** | Preparing the knowledge base for search: chunk, embed, store |

## 13. How chunks are made and stored now, and how industry does it (2026-11-06)

### 13.1 What gets chunked
We chunk the **original resume text**, not the AI's answer. The AI's structure (jobs, projects) is only used to know where each entry starts and to write a short label line on top.

```
upload ──▶ original file kept on disk (data/uploads/) ──▶ resumes.raw_text (cleaned, nothing deleted)
                                                               │
     AI structure + code (Step 5) ─▶ profile tables            │
                                         │                     ▼
                                         └──▶ rag/chunking.py: one entry per job, project and section,
                                              each = a label line our code writes + the ORIGINAL text;
                                              long entries split at ~1,200 chars (150 overlap, at spaces)
                                              + one profile card: facts computed by code, labelled as such
                                                               │
                        resume_chunks (text + meta) · ChromaDB (vector + meta fields) · FTS5 (BM25)
```

**Chunk metadata** (new): every chunk stores which entry it belongs to (`entry`: "job-0", "project-3", "section-2"), its type, name, role and technologies.
- These are real fields in ChromaDB and in `resume_chunks.meta` (JSON), not only text inside the chunk.
- Existing databases get the column at startup. Chunks made before this change have no metadata until the resume is re-extracted or re-embedded.

**Profile card:** facts our code computed (title, total years and how they were found, skills with years or project counts).
- The model-written summary was removed from it, because a paraphrase can drift from the resume.
- The resume's own summary section is indexed as its own chunk.

### 13.2 What the industry does, and where we stand

| Practice | Who recommends it | Here |
|---|---|---|
| Keep the original text as the source of truth; add generated fields beside it, never instead | Microsoft, RAG enrichment phase | ✅ Original text in chunks; judge quotes checked against it only |
| Chunk by document structure (headings, sections), keep the headers with each chunk | Azure AI Search (Document Layout, `header_1…3`, parent id); Pinecone | ✅ Sections, jobs and projects (`sections.py`); header line + `entry` metadata |
| Prepend context to every chunk before embedding AND BM25 | Anthropic, Contextual Retrieval (−49% retrieval failures) | ✅ Done by code (person, job, dates, project, role, technologies), no LLM cost |
| Rerank the shortlist with a cross-encoder | Anthropic (−67% with reranking) | ✅ Optional 4th signal (`RERANK_MODEL`), off until measured on your data |
| Small-to-big: search small chunks, give the reader the whole parent | LangChain ParentDocumentRetriever; Azure parent/child | ✅ The judge gets whole jobs/projects, the most relevant first |
| Structured data for matching, text for evidence; the LLM explains computed scores | JobMatchAI (2026) | ✅ Rule score + judge with verified quotes |
| A skills taxonomy for related skills | JobMatchAI (ESCO) | ❌ Our `SKILL_IMPLIES` has about 40 links (next step) |
| Measure retrieval on your own data | All of them | ✅ `scripts/evaluate_real_retrieval.py` (7 queries on the real resumes) |

### 13.3 Small-to-big for the judge
- **Before:** the judge got chunks in resume order until 6,000 characters. On a long resume the projects at the end were cut off, however relevant they were.
- **Now:** the chunks of each entry are joined back into the whole job or project. The repeated header lines and overlap are removed, and the result matches the unsplit entry exactly (305/305 entries checked, 7 resumes × 4 chunk sizes).
- **When not everything fits:** the entries that mention the role's skills most are chosen (must-have = 2 points, nice-to-have = 1), then shown in resume order.
- **Example:** for a React + MySQL role, Ajay's dossier now contains the Patrishi Sports project (React, MySQL) instead of only his first job.
- **Also fixed:** the dossier said "Total experience (calculated from job dates)" even when the total was the resume's own claim. It now says so.

### 13.4 The reranker (optional)
- **What:** `app/rag/reranker.py` uses fastembed, which is ONNX and needs no PyTorch.
  - Suggested model: `Xenova/ms-marco-MiniLM-L-6-v2`, about 80 MB, downloaded from Hugging Face on first use into `data/models/`.
  - It re-scores the best 8 chunks of the 30 best-fused people against the role summary, and their best score becomes a 4th ranking.
- **Safety:** if fastembed is missing or the model can't load, one warning is logged and matching continues without it. A failed download costs about 30 s once.
- **Turn it on:**
  1. `pip install fastembed`
  2. Set `RERANK_MODEL=Xenova/ms-marco-MiniLM-L-6-v2` in `.env`.
  3. Run `python -m scripts.evaluate_real_retrieval --compare-rerank`.
  4. Keep it on only if hit@3 / MRR improve.
- **Tested in the sandbox** (no Hugging Face access there): the wiring with a stand-in scorer (150 chunks for 23 people, fused as a 4th signal); "unavailable" gives exactly the same ranking as "off"; and the real fastembed library with a blocked download returns cleanly.

### 13.5 Measuring retrieval on the real resumes
`python -m scripts.evaluate_real_retrieval` runs 7 role queries. Examples: React Native → R6, Golang → R9, PHP/WooCommerce → R1, Python + RAG → R2, MERN → R4/R5/R7/R8, Next.js + TypeScript → R3, AWS serverless → R2.
- Each query is run with all signals together and with each signal alone; the script reports hit@3, R@5 and MRR.
- The resumes are found by file hash, so they can be uploaded under any employee. Needs Ollama running; no server needed.
- **Sandbox run** (stand-in embeddings, so the vector column means nothing there): hybrid 7/7 hit@3, MRR 0.93; skills 7/7; keyword 5/7.
- The real numbers come from the PC.

**Sources:** [Anthropic: Contextual Retrieval](https://www.anthropic.com/research/contextual-retrieval) · [Microsoft: RAG enrichment phase](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-enrichment-phase) · [Microsoft: chunk by document layout](https://learn.microsoft.com/en-us/azure/search/search-how-to-semantic-chunking) · [Pinecone: chunking strategies](https://www.pinecone.io/learn/chunking-strategies) · [LangChain: ParentDocumentRetriever](https://reference.langchain.com/python/langchain-classic/retrievers/parent_document_retriever/ParentDocumentRetriever) · [JobMatchAI (arXiv 2603.14558)](https://arxiv.org/pdf/2603.14558)

