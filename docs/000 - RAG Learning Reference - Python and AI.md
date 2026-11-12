# RAG Talent Matcher: Python & AI Reference

A beginner-friendly reference for the RAG Learning Project (employee–project matching with FastAPI, SQLite, Ollama and ChromaDB).

- **Part A:** the Python concepts used in our code, each with a tiny example.
- **Part B:** the AI vocabulary, each term with what it is, how it works, where we use it, and alternatives.
- **Part C:** every tool we chose, next to its alternatives.
- **Part D:** the enterprise, production-grade stack: what is already industry standard in our build, what large companies use instead, the non-technical enterprise requirements, and the upgrade path.
- **Part E:** findings and lessons learned, step by step, with the real numbers measured on this project.
- **Part F:** troubleshooting: every problem hit so far, its cause and its fix.
- **Part G:** change log of this document.

**How to use this document:** start with **Part 0** for the big picture. Look up unfamiliar words in **Part B**, and Python syntax in **Part A**. When something breaks, check **Part F** first. This document is updated after every step and every new finding.

---

# Part 0: The system at a glance

**Goal:** match current employees to internal project roles, using their resumes, with every recommendation backed by evidence from the resume, running entirely on a local PC.

## 0.1 The two halves of RAG in this project

```
INGESTION (once per resume, in the background)
  upload ─▶ ① validate + store ─▶ ② text ─▶ ③ LLM extracts facts ─▶ ④ chunks ─▶ ⑤ vectors ─▶ READY
            (Step 4)               (Step 4)  (Step 5, qwen2.5)        (Step 6)    (Step 6, nomic)
                                               │                         │            │
                                               ▼                         ▼            ▼
                                         SQLite: profile, jobs,    SQLite: chunk   ChromaDB:
                                         skills with years         rows (truth)    vectors (index)

QUERYING (per project role)
  role text ─▶ requirements ─▶ filters (SQL) + keyword (BM25) + meaning (vectors) ─▶ fusion ─▶ LLM judge ─▶ ranked list with evidence
               (Step 7)        (Step 7)                                               (Step 7)   (Step 8)
```

## 0.2 The resume status pipeline (the worker's queue)

| Status       | Meaning                                                            | Next                   |
| ------------ | ------------------------------------------------------------------ | ---------------------- |
| `queued`     | Uploaded, waiting                                                  | parse                  |
| `parsing`    | Reading text from PDF / DOCX                                       | → `parsed` or `failed` |
| `parsed`     | Text stored, waiting for the LLM                                   | extract                |
| `extracting` | LLM filling the JSON form                                          | → `extracted`          |
| `extracted`  | Profile, jobs, skills saved                                        | embed                  |
| `embedding`  | Chunking and creating vectors                                      | → `ready`              |
| `ready`      | Searchable                                                         | —                      |
| `failed`     | See `error_message` (scanned PDF, corrupt file, 3 failed attempts) | retry                  |

The status is stored in the database, so the queue survives restarts: on startup, anything left in a "working" status (`parsing`, `extracting`, `embedding`) is put back to the status it was waiting in.

## 0.3 Where things live

| What                       | Where                                                               |
| -------------------------- | ------------------------------------------------------------------- |
| Code                       | `backend/app/` (api, services, ingestion, extraction, rag, db, llm) |
| Settings                   | `backend/.env` (never committed)                                    |
| Database (source of truth) | `backend/data/app.db`                                               |
| Original resume files      | `backend/data/uploads/<EMPLOYEE_CODE>/`                             |
| Vector index (rebuildable) | `backend/data/chroma/`                                              |
| Models                     | Ollama, `D:\OllamaModels` (set in the Ollama app's Settings)        |
| Sample data                | `samples/` (fictional people, `employees.csv`, `roles.json`)        |
| API docs (live)            | http://127.0.0.1:8010/docs                                          |

---

# Part A: Python concepts in our code

### 1. Variables and types

A **variable** is a name for a value. Every value has a **type**:

```python
name = "Priya"          # str   (text)
years = 8.2             # float (decimal number)
jobs = 2                # int   (whole number)
is_current = True       # bool  (True / False)
skills = ["Kubernetes", "Terraform"]           # list  (ordered collection)
employee = {"code": "EMP-1003", "years": 8.2}  # dict  (key -> value lookup)
nothing = None          # None  ("no value")
```

**In our code:** everywhere. JSON from Ollama becomes a dict, so `data["message"]["content"]` means "in the dict, take `message`, then inside it take `content`."

### 2. Functions

A **function** is a named, reusable block of code. It takes **parameters** and **returns** a result:

```python
def months_to_years(months):
    return round(months / 12, 1)

months_to_years(98)   # -> 8.2
```

**In our code:** `dates.py` (`months_to_years`, `parse_point`), `skills.py` (`normalize_skill`), and most other files.

### 3. Type hints

Notes saying what type a parameter or result should be:

```python
def months_to_years(months: int) -> float:
```

`int | None` means "an int, or nothing." Plain Python doesn't enforce them; they help your editor and readers. **FastAPI and Pydantic _do_ use them** to check incoming data, which is why our API rejects `"temperature": "hot"` automatically.

### 4. Classes, objects, methods, `self`

A **class** is a blueprint; an **object** is one thing built from it. A **method** is a function belonging to the class. `self` means "this particular object."

```python
class OllamaClient:
    def __init__(self, base_url):       # runs when an object is created
        self.base_url = base_url        # store a value ON this object

    def describe(self):                 # a method
        return f"Ollama at {self.base_url}"

client = OllamaClient("http://localhost:11434")   # create an object
client.describe()                                 # call its method
```

**In our code:** `OllamaClient`, `IngestionWorker`, `VectorStore`. Each bundles data (URL, settings, a connection) with the actions that use it.

### 5. Inheritance

A class can **build on** another and get all its features:

```python
class Settings(BaseSettings):   # Settings gets BaseSettings' ability to read .env
```

**In our code:** `Settings(BaseSettings)`, every database model `(Base)`, and `ResumeDetail(ResumeOut)`, which is ResumeOut plus a few extra fields.

### 6. Dataclasses

A shortcut for classes that just **hold values**:

```python
@dataclass
class ChunkHit:
    resume_id: int
    text: str
    similarity: float

hit = ChunkHit(resume_id=3, text="...", similarity=0.58)
hit.similarity   # 0.58
```

**In our code:** `ChunkHit`, `ProfileSkill`, `Claimed`, `YearMonth`.

### 7. Pydantic models

Like dataclasses, but they **check and convert** data:

```python
class ChatRequest(BaseModel):
    prompt: str
    temperature: float = Field(0.0, ge=0, le=2)

ChatRequest(prompt="hi", temperature="0.5")   # "0.5" text -> 0.5 number
ChatRequest(prompt="hi", temperature=9)       # error: must be <= 2
```

**In our code:** API requests and responses (`app/schemas/`), the CSV row check (`EmployeeRow`), validating the LLM's JSON (`ResumeExtraction`), and settings (`Settings`). It's the main safety net between the outside world and our code.

### 8. Modules, packages and imports

- A **module** is one `.py` file.
- A **package** is a folder of modules, with an `__init__.py`.
- **Import** means use code from another file:

```python
from app.extraction.dates import months_to_years   # folder app/extraction, file dates.py, function months_to_years
```

`python -m scripts.try_search` runs a file **as a module**, so its imports of `app...` work. It fails if the file isn't actually in `scripts/`.

### 9. Decorators (`@something`)

A line above a function that **adds behaviour** to it:

```python
@router.get("/api/health")      # "call this function when someone visits /api/health"
async def health(): ...

@lru_cache                      # "remember the result; don't recompute it"
def get_settings(): ...
```

Other decorators we use: `@dataclass`, `@property` (lets a method be read like a field: `settings.max_upload_bytes`), `@field_validator` (Pydantic: "run this check on that field").

### 10. Exceptions: `try`, `except`, `raise`

An **exception** is Python's way of signalling an error. `raise` throws one; `try/except` catches it:

```python
try:
    data = await ollama.chat(...)
except OllamaError as exc:               # Ollama was down
    raise HTTPException(503, str(exc))   # tell the browser "service unavailable"
```

We also **define our own** exception types (`OllamaError`, `ExtractionError`, `InvalidFileError`), so each kind of failure can be handled differently. The worker's three failure rules (Step 5) are built entirely on this.

### 11. Context managers (`with`)

`with` sets something up and **guarantees cleanup**, even if an error happens:

```python
async with SessionLocal() as session:   # open a database session
    ...                                 # use it
# here the session is ALWAYS closed
```

Also used for files (`with open(...)`) and HTTP clients.

### 12. `async` / `await` and the event loop

Some operations are **slow waits**: Ollama answering (60 seconds), the disk, the network. With `async`, Python can **do other work while waiting**:

```python
async def handler():
    answer = await ollama.chat(...)   # pause HERE; meanwhile serve other requests
```

- `async def` makes a function that can pause.
- `await` is where it pauses.
- The **event loop** is Python's scheduler that switches between paused tasks.
- `asyncio.create_task()` starts something running in the background (our worker).
- `asyncio.to_thread()` runs a slow **non-async** function (PDF reading, ChromaDB) in a separate thread, so it doesn't freeze the event loop.

### 13. Comprehensions

A one-line way to build lists, dicts and sets:

```python
names = [s.name for s in skills]                    # list of every skill's name
long_ones = [s for s in skills if s.years > 3]      # with a filter
by_code = {e.employee_code: e for e in employees}   # dict: code -> employee
```

Read them as "for each `s` in `skills`, take `s.name`."

### 14. f-strings

Text with values inserted: `f"{years} years"` becomes `"8.2 years"`.

### 15. Regular expressions (`re`)

A mini-language for **finding text patterns**:

```python
re.search(r"(\d{4})", "Jun 2021")   # finds 4 digits in a row -> "2021"
```

| Pattern | Means             |
| ------- | ----------------- |
| `\d`    | a digit           |
| `{4}`   | exactly 4 of them |
| `\s`    | a space           |
| `+`     | one or more       |
| `( )`   | capture this part |
| `\b`    | a word boundary   |

**In our code:** dates (`dates.py`), emails and phones (anonymisation), skills in brackets, page numbers. Test patterns at regex101.com.

### 16. `*args` and `**kwargs`

- `**values` collects named arguments into a dict, so `_update(id, status="ready", attempts=0)` gives `values = {"status": "ready", "attempts": 0}`.
- `Employee(**row)` does the reverse: it spreads a dict into named arguments.

### 17. `lambda`

A tiny unnamed function, usually for sorting:

```python
sorted(skills, key=lambda s: s.years)   # "sort skills by their years"
```

### 18. Enums

A fixed set of allowed values: `ResumeStatus.READY`. Typos become impossible.

### 19. `if __name__ == "__main__":`

"Run this only when the file is executed directly, not when it's imported." Every script in `scripts/` ends with it.

### 20. Virtual environment, pip and requirements

- **pip** installs libraries.
- A **venv** (`.venv`) is a private library folder for one project.
- `requirements.txt` lists what to install.
- A **library** (package) is code someone else wrote: FastAPI, SQLAlchemy, ChromaDB.

---

# Part B: AI and RAG vocabulary

For each term: **what it is**, **how it works**, **in our project**, and **alternatives**.

### Artificial intelligence, machine learning, deep learning

- **What:** AI is computers doing tasks that seem to need intelligence. **Machine learning** is the kind of AI that _learns patterns from examples_ instead of following hand-written rules. **Deep learning** is machine learning with large **neural networks** (many layers of simple maths units).
- **In our project:** both models (qwen and nomic) are deep-learning models. Our date parser and skill catalog are **rule-based**, the opposite of ML: exact, predictable, but only as smart as the rules we write.

### Model, parameters (weights)

- **What:** a model is a giant mathematical function. **Parameters** are its billions of adjustable numbers.
- **How:** during training, the parameters are nudged billions of times until the outputs are good. After training they're frozen and stored in a file (the 4.7 GB download).
- **In our project:** `qwen2.5:3b` has ~3 billion parameters; `qwen2.5:7b` has ~7 billion. More parameters usually means smarter but slower.

### Training vs inference

- **Training:** _creating_ the model (weeks on thousands of GPUs). **Inference:** _using_ it to produce an answer.
- **In our project:** inference only. RAG gives the model new knowledge **at question time**, so no training is needed.
- **Alternative:** **fine-tuning**, extra training on your own data. It's more expensive, and it doesn't keep up when resumes change daily. RAG does.

### LLM (Large Language Model)

- **What:** a model trained to **predict the next token** of text.
- **How:** it reads your input, scores every possible next token, picks one, adds it, and repeats.
- **In our project:** qwen2.5 reads resumes (Step 5), will judge candidates (Step 8) and will power the agent (Step 10).
- **Alternatives:** Llama 3.x, Gemma, Mistral, Phi, Granite (local); GPT, Claude, Gemini (cloud). Cloud models are smarter and faster, but resumes would leave your machine.

### Token, tokenizer

- **What:** the pieces of text a model reads, roughly 3/4 of a word each. The **tokenizer** converts text to token IDs.
- **In our project:** speed is measured in tokens/second, and limits like `num_predict` count tokens.

### Context window

- **What:** the maximum number of tokens the model can look at once (input plus output).
- **In our project:** `LLM_NUM_CTX=8192`. If a prompt is too long, the start is cut off silently, which is why we truncate long resumes.

### Prompt; system and user messages

- **What:** the input text. The **system** message holds standing rules ("Use ONLY information in the resume"). The **user** message holds the actual task and data.
- **In our project:** `prompts.py`. **Prompt engineering** means writing these instructions carefully.

### Temperature (and sampling)

- **What:** how randomly the next token is chosen. 0 always picks the most likely token (repeatable); higher values are more varied.
- **In our project:** 0 for extraction (same resume gives the same profile every time).

### Hallucination

- **What:** the model confidently writes something false, because it generates _plausible_ text, not _checked_ text.
- **In our project:** the evidence check (Step 5), job-level grounding (Step 5b) and citations (Step 8) all exist because of this.

### Structured output (constrained decoding)

- **What:** forcing the model's output to match a JSON schema.
- **How:** at each step, tokens that would break the schema are blocked.
- **In our project:** Ollama's `format` parameter (Step 5).
- **Alternatives:** asking for JSON and retrying on errors (less reliable); "function calling" or "tool use" in cloud APIs (the same idea).

### Embedding

- **What:** text turned into a list of numbers (768 for nomic) that represents its **meaning**.
- **How:** a separate, smaller model trained so that texts with similar meaning get similar numbers.
- **In our project:** every chunk and every search query (Step 6).
- **Alternatives:** `bge-m3` (multilingual, longer texts), `mxbai-embed-large`, `embeddinggemma`, and cloud embeddings (OpenAI, Voyage, Cohere).

### Vector, dimensions

- **What:** a vector is a list of numbers; the **dimensions** are how many numbers (768).
- **Picture:** a point in space. Similar meanings are nearby points.

### Cosine similarity

- **What:** a measure of how similar two vectors are, by the angle between them. 1 means the same direction, 0 means unrelated.
- **In our project:** the `score` in search results; `cosine_similarity()` in `dev.py`.
- **Alternatives:** dot product (identical for normalised vectors), Euclidean distance.

### Embedding model vs LLM

|                | Embedding model      | LLM                                    |
| -------------- | -------------------- | -------------------------------------- |
| Output         | Numbers (a vector)   | Text                                   |
| Job            | Measure similarity   | Read, reason, write                    |
| Size and speed | Small, fast (~50 ms) | Big, slow (~50+ s per resume on a CPU) |
| Ours           | nomic-embed-text     | qwen2.5                                |

### Chunking

- **What:** splitting documents into smaller pieces before embedding them.
- **Why:** one vector per small topic is precise; one vector per whole document is a blurry average.
- **In our project:** profile card, one chunk per job, everything else (`chunking.py`).
- **Alternatives:** fixed-size, recursive, semantic and layout-aware chunking (LangChain text splitters, Chonkie, Docling HybridChunker).

### Vector database

- **What:** a database specialised in "find the stored vectors nearest to this one," fast.
- **In our project:** ChromaDB, in `data/chroma/`.
- **Alternatives:** Qdrant (also runs embedded), **pgvector** (vectors inside PostgreSQL, so one database for everything), FAISS (a library, not a database), Milvus, Weaviate, LanceDB.

### ANN and HNSW

- **What:** **approximate nearest neighbour** search finds the nearest vectors without comparing against all of them. **HNSW** is the most popular method: a layered graph of "neighbour" links that the search hops through, like motorways, then main roads, then streets.
- **In our project:** inside ChromaDB, automatically.
- **Alternatives:** brute force (exact, fine for small data), IVF, product quantisation (for billions of vectors).

### RAG (Retrieval-Augmented Generation)

- **What:** **retrieve** the relevant information from your data first, then let the LLM **generate** an answer using it.
- **Why:** the LLM doesn't know your employees, can't read 2,000 resumes at once, and hallucinates without evidence.
- **In our project:** the whole system. Steps 4–6 build the knowledge base, Step 7 is retrieval, Step 8 is generation.
- **Alternatives:** fine-tuning (expensive and stale); stuffing everything into a long context (too slow on CPU); plain SQL filters without AI (no understanding of meaning).

### Semantic search vs keyword search

- **Semantic** matches meaning: "container orchestration" finds "k8s clusters." It's weak on exact rare terms.
- **Keyword** matches exact words: it finds "SAP FICO" precisely, but misses synonyms.
- **In our project:** semantic search in Step 6, keyword search in Step 7.

### BM25

- **What:** the classic keyword-ranking formula used by search engines.
- **How:** a document scores higher when it contains the query words often, and **rare words count more** than common ones ("Kubernetes" matters more than "worked"). Very long documents are slightly penalised.
- **In our project:** Step 7, using SQLite's built-in **FTS5** full-text search.
- **Alternatives:** Elasticsearch/OpenSearch, Tantivy, the `rank-bm25` Python library.

### Hybrid search and RRF (Reciprocal Rank Fusion)

- **Hybrid** means running several searches (semantic plus keyword) and combining them.
- **RRF** is a simple way to combine rankings: each result gets `1 / (60 + its rank)` from each list, added together. Something ranked well in **both** lists wins. It uses ranks, not raw scores, which is useful because similarity scores are squeezed together.
- **In our project:** Step 7.
- **Alternatives:** weighted score averaging, or learning-to-rank (trained on past decisions).

### Reranking

- **What:** a second, more careful pass that re-orders the top results from retrieval.
- **In our project:** Step 8, where the LLM judges the top 5.
- **Alternatives:** **cross-encoder rerankers** such as `bge-reranker`. These are small models that read query and text _together_ and give a relevance score: much faster than an LLM, but with no written explanation.

### LLM-as-a-judge

- **What:** using an LLM to score something against a rubric, with reasons.
- **In our project:** Step 8: "score this employee 0–100 for this role; list strengths, gaps and evidence quotes."
- **Risks:** inconsistency and bias. We handle them with temperature 0, a fixed rubric, anonymised text and plain-code scores alongside.

### Grounding and citations

- **What:** tying every claim to real source text, so it can be checked.
- **In our project:** evidence quotes (Step 5), job grounding (Step 5b), matched chunks (Step 6), citations in explanations (Step 8).

### Agent and tools

- **What:** an LLM that can **decide which functions ("tools") to call**, look at the results and continue, in a loop. For example: "search candidates", then "filter to Pune", then "compare #1 and #2."
- **In our project:** Step 10, the conversational layer on top of the search.
- **Alternatives:** a fixed form-based UI (simpler, predictable); frameworks like LangGraph, the OpenAI Agents SDK or PydanticAI.

### Quantisation

- **What:** storing model parameters with fewer bits (e.g. 4 instead of 16), so models fit in RAM and run faster, at a small cost in quality.
- **In our project:** Ollama's models are already 4-bit quantised (`Q4_K_M`).

### Evaluation

- **What:** measuring quality with a test set and metrics instead of judging by feel.
- **In our project:** `compare_extraction.py` (Step 5), the expected rankings in `roles.json`, and Step 14 (precision@k: "how many of the top k are correct?").

### Structured extraction

- **What:** using an LLM to turn free text into fixed fields (a "form"): titles, dates, skills with evidence.
- **Why:** embeddings can't count years or compare numbers; structured fields can be filtered and sorted with SQL.
- **In our project:** Step 5 (`app/extraction/`). The LLM **copies and labels**; code **calculates and checks**.
- **Alternatives:** rule-based parsers (fragile on varied layouts), commercial resume parsers (Affinda, Sovren/Textkernel, Daxtra).

### Normalisation (canonical names)

- **What:** mapping many spellings of the same thing to one name: "k8s", "K8s (EKS)", "kubernetes" all become **Kubernetes**.
- **In our project:** the skill `CATALOG` in `skills.py`. Unknown skills are kept as written; add aliases over time.
- **Alternatives:** skill taxonomies such as ESCO or O\*NET, or embedding-based matching of skill names.

### Grounding (evidence check) and job-level grounding

- **Grounding:** a skill is kept only if its name or quoted evidence really appears in the resume text. This catches invented skills.
- **Job-level grounding (Step 5b):** a skill counts towards a job's duration only if it is written in **that job's own part** of the resume. This catches the LLM copying the skills section into every job.
- **Why it matters:** without it, "Django, 13.3 years, last used 2026" for someone who stopped coding in 2019.

### Prefill and decode

- **Prefill:** the model reads the whole prompt at once (fast, parallel). Measured: ~37 tokens/s (7B) and ~86 tokens/s (3B) on this PC.
- **Decode:** the model writes the answer one token at a time (slow). Measured: ~7.7 tokens/s (7B) and ~16.7 tokens/s (3B).
- **Lesson:** on a CPU, **output length dominates time**, so prompts ask for short descriptions and short evidence.

### `num_ctx` and `num_predict`

- **`num_ctx`:** the context window Ollama allocates (we set 8192). Too small means the start of the prompt is silently dropped.
- **`num_predict`:** the maximum number of tokens to generate (we set 2048 for extraction). It stops runaway output; `done_reason="length"` reveals a cut-off answer.

### Task prefixes (asymmetric embeddings)

- **What:** some embedding models were trained with instructions in front of the text. nomic-embed-text expects `search_document: ` for stored text and `search_query: ` for questions.
- **Why:** a short question and a long passage _about_ it then land close together. Leaving prefixes out lowers search quality.
- **In our project:** `app/rag/embeddings.py`.

### Contextual chunk header

- **What:** a line added at the start of every chunk saying whose it is and what it is: `Employee EMP-1003 | Experience | Senior DevOps Engineer at Nimbus Technologies (2020 - present)`.
- **Why:** a chunk retrieved alone still makes sense, both to the embedding model and to the LLM judge.

### Anonymisation (pseudonymisation)

- **What:** replacing personal identifiers with placeholders: `[name]`, `[email]`, `[phone]`.
- **Why:** fairness (matching should never be influenced by a name) and privacy (less personal data in the index).
- **In our project:** `anonymize()` in `chunking.py`, applied before embedding.
- **Enterprise alternative:** Microsoft Presidio or cloud DLP services.

### Source of truth vs index

- **Source of truth:** the authoritative copy of data (SQLite `resume_chunks`). **Index:** a derived structure for fast lookup (ChromaDB vectors).
- **Rule:** an index can always be rebuilt from the source of truth (`POST /api/resumes/reembed`), never the other way round.

### Idempotent

- **What:** an operation that gives the same result whether it runs once or several times.
- **In our project:** re-extraction replaces the old profile; re-embedding deletes a resume's old vectors before adding new ones. Retries after a crash therefore never create duplicates.

### Upsert

- **What:** "update if it exists, insert if it doesn't." The HR CSV import upserts employees by `employee_code`.

### Batching

- **What:** sending many items in one request instead of one request each. Embeddings are sent 16 chunks per call.

### Cold start and `keep_alive`

- **What:** the first request to a model loads it from disk into RAM (measured: ~2 s for nomic-embed-text, 4–10 s for the qwen models). Ollama keeps a model loaded for 5 minutes after its last use (`keep_alive`), so later requests are fast.

### Score compression

- **What:** embedding similarities for related documents cluster in a narrow band. Measured here: 0.52–0.67, with #1 and #2 often less than 0.01 apart.
- **Consequence:** absolute scores mean little; only the order matters, and close scores are effectively ties. This is why rank-based fusion (RRF) is preferred over score thresholds.

### Short-chunk noise ("hubness")

- **What:** very short chunks ("ASP.NET MVC applications on-premise.") have vague vectors that sit moderately close to many queries and appear in unrelated results.
- **Fixes:** enrich chunks with context (e.g. the job's normalised skills), merge tiny chunks, and combine vector search with other signals.

### Ground truth and test set

- **What:** the correct answers, decided by humans, used to measure the system (`roles.json` expected rankings, the checks in `compare_extraction.py`).
- **Lesson from Step 6:** ground truth can itself be incomplete. Rohan genuinely worked for an insurance client, which the expected list had missed.

### Pipeline / state machine

- **What:** work broken into ordered stages, with each item's current stage recorded. See Part 0.2.

---

# Part C: Our choices and their alternatives

| Part                    | We use                                 | Main alternatives                                                       | Why ours (for now)                                                  |
| ----------------------- | -------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Web API framework       | **FastAPI**                            | Flask (simpler, not async by default), Django (big, batteries included) | Async (needed for slow LLM calls), automatic validation and `/docs` |
| Web server              | **Uvicorn**                            | Hypercorn, Gunicorn plus Uvicorn workers                                | FastAPI's standard partner                                          |
| Relational database     | **SQLite**                             | PostgreSQL, MySQL                                                       | Zero install, one file; switch to PostgreSQL for many users         |
| ORM                     | **SQLAlchemy 2 (async)**               | SQLModel, Django ORM, Tortoise, raw SQL                                 | The industry standard; works with any database                      |
| Settings                | **pydantic-settings**                  | python-dotenv, dynaconf                                                 | Typed and validated                                                 |
| PDF text                | **pypdfium2**                          | PyMuPDF (AGPL licence), pdfplumber, pypdf, Docling                      | Fast, accurate, permissive licence                                  |
| Word text               | **python-docx**                        | docx2txt, mammoth, Docling                                              | Reads tables in order                                               |
| Background jobs         | **Our own worker** (database as queue) | Celery, RQ, Arq, Dramatiq (with Redis)                                  | No extra server; survives restarts; easy to read                    |
| Local LLM runner        | **Ollama**                             | LM Studio (GUI), llama.cpp (raw engine), vLLM (needs a GPU)             | Easiest install, simple REST API                                    |
| LLM                     | **qwen2.5:3b / 7b**                    | llama3.2:3b, llama3.1:8b, gemma, granite, phi                           | Good JSON reliability; licence check needed for the 3B              |
| Embeddings              | **nomic-embed-text**                   | bge-m3, mxbai-embed-large, embeddinggemma                               | Small, fast, proven for RAG                                         |
| Chunking                | **Our own**                            | LangChain splitters, Chonkie, Docling                                   | Uses job structure from Step 5                                      |
| Vector database         | **ChromaDB**                           | Qdrant, pgvector, FAISS, LanceDB, Milvus                                | Embedded, no server, simple API                                     |
| Keyword search (Step 7) | **SQLite FTS5**                        | Elasticsearch, OpenSearch, rank-bm25                                    | Already inside SQLite                                               |
| RAG framework           | **None** (our own code)                | LangChain, LlamaIndex, Haystack                                         | You see and understand every step; add a framework later if wanted  |
| Frontend (Step 11)      | **Next.js**                            | React + Vite, Vue/Nuxt, SvelteKit                                       | Your choice; widely used                                            |

---

# Part D: Enterprise, production-grade stack

There is no single "best" tool for every company. The right choice depends on scale, budget, cloud provider and compliance rules. The options below are the **widely adopted, production-proven** choices large organisations use today. Our learning build was chosen for three constraints (learn the concepts clearly, run on a 16 GB CPU laptop, keep resumes private). The _architecture_ is already enterprise-grade; some _components_ are prototype-grade and get swapped before going live.

## D1. Already industry standard in our build

| Part                 | Our choice                                                                                                | Standing                                                                                |
| -------------------- | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Backend language     | **Python**                                                                                                | The default language for AI/ML systems                                                  |
| API framework        | **FastAPI**                                                                                               | Among the most widely used Python API frameworks; used in production by large companies |
| Data validation      | **Pydantic**                                                                                              | The standard; FastAPI, LangChain and the OpenAI SDK are built on it                     |
| ORM                  | **SQLAlchemy 2**                                                                                          | The most established Python ORM                                                         |
| Frontend             | **Next.js**                                                                                               | One of the most popular React frameworks                                                |
| Version control      | **Git**                                                                                                   | Universal                                                                               |
| Retrieval design     | Structured extraction, then hybrid search (vector + BM25), then fusion, then LLM reranking with citations | What serious RAG systems use; most tutorials only do "vector search, then LLM"          |
| Engineering patterns | Database as source of truth, idempotent re-indexing, grounding checks, evaluation scripts, crash recovery | The habits that separate production systems from demos                                  |

## D2. Learning choice vs enterprise production choice

| Layer                  | Ours (learning)                    | Enterprise production choice                                                                                                                                                                                    | Why we didn't start there                                          |
| ---------------------- | ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Relational database    | SQLite                             | **PostgreSQL**, usually managed (AWS RDS / Aurora, Azure Database for PostgreSQL, Google Cloud SQL)                                                                                                             | Needs a server or Docker; SQLite works for one user                |
| Vector search          | ChromaDB (embedded)                | **pgvector** inside PostgreSQL (one database for everything), **Qdrant**, **Elasticsearch / OpenSearch** (vectors + BM25 in one engine), or managed: **Azure AI Search**, **Pinecone**, Vertex AI Vector Search | Chroma needs no server; ideal for learning                         |
| Keyword search         | SQLite FTS5                        | **Elasticsearch / OpenSearch**, or PostgreSQL full-text search                                                                                                                                                  | Same reason                                                        |
| File storage (resumes) | Local `data/uploads/` folder       | **Object storage**: AWS S3, Azure Blob Storage, Google Cloud Storage (MinIO on-premise), encrypted, with lifecycle rules                                                                                        | Local disk is fine on one PC                                       |
| Document parsing / OCR | pypdfium2 + python-docx; no OCR    | **Azure AI Document Intelligence**, **AWS Textract**, Google Document AI; open source: **Docling**, Unstructured, Tesseract / PaddleOCR                                                                         | Cloud services send data out; open-source OCR needs extra installs |
| Background jobs        | Our own worker (database as queue) | **Celery** or **RQ** with Redis / RabbitMQ; **Temporal** for long, multi-step workflows; cloud queues (AWS SQS, Azure Service Bus)                                                                              | No extra servers; you can read every line                          |
| LLM serving            | Ollama on a CPU                    | **vLLM** or Hugging Face **TGI** on **GPU servers**; or **managed APIs** under an enterprise agreement: **Azure OpenAI**, **AWS Bedrock**, **Google Vertex AI** (data not used for training, regional hosting)  | No GPU; everything stays on the laptop                             |
| LLM gateway            | Direct calls to one model          | **LiteLLM** or a cloud API gateway: one API for many models, with retries, fallbacks, rate limits and cost tracking                                                                                             | One model, one user                                                |
| LLM                    | qwen2.5 3B / 7B                    | Larger open models (30–70B class) on GPUs, or frontier models through managed APIs                                                                                                                              | 3–7B is what a 16 GB CPU can run                                   |
| Embeddings             | nomic-embed-text                   | **bge-m3**, **e5**, or commercial: OpenAI, Cohere, Voyage                                                                                                                                                       | Small and fast on CPU                                              |
| Reranking              | LLM judge (Step 8)                 | Cross-encoders (**bge-reranker**, **Cohere Rerank**) before the LLM judge: faster and cheaper                                                                                                                   | Fewer moving parts while learning                                  |
| Caching                | None                               | **Redis** for repeated queries, embeddings and sessions                                                                                                                                                         | Not needed for one user                                            |
| Authentication         | JWT built ourselves (Step 9)       | **SSO** with the company identity provider (**Microsoft Entra ID**, **Okta**) via OIDC / SAML, plus role-based access control (RBAC)                                                                            | Needs the company's identity setup                                 |
| Secrets                | `.env` file                        | **Azure Key Vault**, **AWS Secrets Manager**, **HashiCorp Vault**                                                                                                                                               | Fine on a laptop                                                   |
| Packaging & deployment | `uvicorn` on a PC                  | **Docker** images on **Kubernetes** (AKS / EKS / GKE) or a managed container service (Azure Container Apps, AWS ECS, Cloud Run)                                                                                 | Not needed to learn RAG                                            |
| Infrastructure         | Manual                             | **Infrastructure as Code**: Terraform, Bicep, Pulumi                                                                                                                                                            | Same                                                               |
| CI/CD                  | Manual git commits                 | **GitHub Actions**, GitLab CI, Azure DevOps: tests, linting and evaluations on every change                                                                                                                     | Same                                                               |
| Code quality           | Manual                             | **pytest** (tests), **ruff** (linting/formatting), **mypy** (type checking), pre-commit hooks                                                                                                                   | Added in hardening                                                 |
| Observability          | Log lines                          | **OpenTelemetry** traces, **Prometheus + Grafana** metrics, central logs (ELK, Azure Monitor, CloudWatch), LLM tracing (**Langfuse**, LangSmith)                                                                | Later concern                                                      |
| RAG / LLM evaluation   | Our own scripts                    | Our scripts **plus** **Ragas**, **DeepEval** or promptfoo, run in CI on a fixed test set                                                                                                                        | Learn the idea first                                               |
| PII protection         | Regex anonymisation                | **Microsoft Presidio** or cloud DLP services for detecting and masking personal data                                                                                                                            | Regex is enough for the samples                                    |
| Guardrails             | Grounding checks                   | Input / output filters (e.g. NeMo Guardrails, Guardrails AI, cloud content safety) against prompt injection and data leakage                                                                                    | Small internal tool                                                |

## D3. Enterprise requirements beyond technology

For an HR system, these matter as much as the tools:

- **Data protection:** India's **DPDP Act** (purpose limitation, consent, retention limits, deletion on request). Our delete cascades and local-only processing help.
- **Fairness and human oversight:** anonymise what the AI sees, keep a human as the final decision maker, and test rankings for bias. If the company also operates in the EU, the **EU AI Act** classifies AI used for recruitment and work allocation as **high-risk**, which brings documentation, risk management, bias testing and human-oversight obligations.
- **Audit trail:** who searched, who was shortlisted, and why. Our stored match runs with evidence are designed for this.
- **Access control:** only authorised people see resumes (least privilege), and every access is logged.
- **Security reviews:** penetration testing, dependency scanning (e.g. Dependabot, Snyk), and licence checks (we already avoided AGPL PyMuPDF and noted the Qwen 3B licence).
- **Reliability:** backups and restore tests, defined uptime targets, and monitoring alerts.

## D4. Reference production architecture

```
Users ──SSO (Entra ID / Okta)──▶ Next.js frontend ──▶ API gateway ──▶ FastAPI (Docker, Kubernetes, several replicas)
                                                                         │
           ┌─────────────────────────────┬───────────────────────────────┼──────────────────────────┐
           ▼                             ▼                               ▼                          ▼
  PostgreSQL + pgvector          Object storage (S3 / Blob)        Job queue (Celery/Temporal)   LLM gateway (LiteLLM)
  (profiles, chunks, vectors,    (original resumes, encrypted)     → ingestion workers          → vLLM on GPUs, or
   audit log, FTS / BM25)                                            parse / extract / embed       Azure OpenAI / Bedrock
           │
  Observability: OpenTelemetry · Prometheus/Grafana · Langfuse      Secrets: Key Vault / Secrets Manager
  Quality: pytest · Ragas/DeepEval in CI                             Infra: Terraform · GitHub Actions
```

## D5. Upgrade path from our build

Each outside dependency sits behind **one adapter file**, so moving up is cheap:

| To switch to…              | Change                                                                                       |
| -------------------------- | -------------------------------------------------------------------------------------------- |
| PostgreSQL                 | `DATABASE_URL=postgresql+asyncpg://...` and install the driver; add Alembic migrations       |
| pgvector or Qdrant         | Rewrite `app/rag/vector_store.py` only                                                       |
| A GPU server with vLLM     | `app/llm/ollama_client.py` (vLLM speaks an OpenAI-compatible API) plus model names in `.env` |
| Azure OpenAI / AWS Bedrock | Replace the internals of `app/llm/ollama_client.py`; nothing else changes                    |
| Celery / Temporal          | Replace `app/ingestion/worker.py`; the stage functions stay the same                         |
| Object storage             | Replace `app/ingestion/storage.py` save / delete functions                                   |
| SSO                        | Replace the token check in `app/api/deps.py` (Step 9) with OIDC validation                   |

Plan: finish the learning build (Steps 7–14), then a final **Production upgrade** step covering PostgreSQL + pgvector, Docker, SSO-ready auth, observability and evaluation in CI.

---

# Part E: Findings and lessons learned (by step)

Measured on this project's PC: Windows, 16 GB RAM, no NVIDIA GPU (CPU-only inference), Python 3.13, Ollama 0.40.

## Step 1: Environment and models

| Measurement       | qwen2.5:3b        | qwen2.5:7b       |
| ----------------- | ----------------- | ---------------- |
| Size on disk      | 1.9 GB            | 4.7 GB           |
| Load time (cold)  | 4.1 s             | 10.2 s           |
| Prefill (reading) | 85.7 tokens/s     | 36.7 tokens/s    |
| Decode (writing)  | **16.7 tokens/s** | **7.7 tokens/s** |

- **Lesson:** on a CPU, speed is roughly _memory bandwidth ÷ model size_. The 7B is ~2.4× bigger and ~2.2× slower.
- **Lesson:** a 12-word prompt became 42 tokens: every chat message is wrapped in the model's chat template (role markers plus a hidden default system message).
- **Licence findings:** `qwen2.5:3b` is under the Qwen **Research** Licence (may restrict commercial use); `qwen2.5:7b` is Apache 2.0. Check licences before company use.
- nomic-embed-text produces **768** numbers per text, normalised to length 1.

## Step 3: Database

- 12 tables created. The seed script proved `PRAGMA foreign_keys=ON` works: deleting 2 employees made SQLite remove their 2 resumes, 5 skill links and 1 experience automatically (`ON DELETE CASCADE`), while the shared `skills` catalogue stayed.
- **Lesson:** SQLite ignores foreign keys unless `PRAGMA foreign_keys=ON` is set on **every** connection; without it cascades silently do nothing.

## Step 4: Resume intake

- Imported **16** employees; **15** resumes uploaded; **14** parsed; **1** correctly rejected as a scanned image (0 characters extracted).
- Re-uploading the same files: **15 duplicates rejected** by SHA-256 fingerprint.
- **Two-column PDF:** sorting text "top-to-bottom, left-to-right" mixed the columns line by line; the PDF's own stored order kept them intact. Use stored order.
- **DOCX tables:** reading only paragraphs silently drops tables (where skills often are); read paragraphs and tables in document order.
- **Licence finding:** PyMuPDF is AGPL; we chose pypdfium2 (Apache-2.0/BSD) with equal results.

## Step 5: Structured extraction

| Model                | Checks passed | Avg time / resume | 2,000 resumes |
| -------------------- | ------------- | ----------------- | ------------- |
| qwen2.5:3b (fast)    | 13/14         | 50 s              | ~28 hours     |
| qwen2.5:7b (quality) | 13/14         | 101 s             | ~56 hours     |

- **Decision:** the **fast** model for extraction (same accuracy on our checks, half the time). Swap to a commercially licensed 3B (e.g. `llama3.2:3b`) for company use and re-run the comparison.
- **Time split (7B, one resume):** ~25% reading the prompt, ~75% writing the answer; post-processing and saving take milliseconds.
- **Finding:** both models copied skills from the skills section into **every** job, inflating years (Divya: Django 13.3 years, last used 2026; Neha: AngularJS 10.3 years). Hidden inside "passing" results too (Priya: Python/Bash 6.2 years).
- **Fix (Step 5b):** job-level grounding; skills removed from jobs are kept without years if mentioned elsewhere; stated durations ("React (1 yr)") cap years. Stand-in test: 16/16.
- **Lesson:** division of labour. The LLM reads and labels; deterministic code verifies, normalises and calculates.
- **Lesson:** a skill-years number derived from job dates is an **upper bound**; treat it as such in scoring.

## Step 6: Chunking, embeddings and semantic search

- 7 test queries written _without the resumes' words_: the expected person was in the top 3 for **7/7** and at #1 for **5/7**.
- Scores ranged **0.52–0.67**; #1 vs #2 often differed by < 0.01 (score compression).
- First query **2,014 ms** (embedding model cold start), then **~50 ms** per search; ChromaDB itself takes single-digit milliseconds.
- **Weaknesses found:** short chunks appear in unrelated results; "k8s" is weakly linked to "container orchestration" by the embedding model; vector search always returns _someone_, even for skills nobody has.
- **Planned fixes (Step 7):** enrich experience chunks with the job's normalised skills; hybrid retrieval (BM25 + vectors + structured skills) with rank fusion; role parsing that maps descriptions to catalog skills; SQL filters for availability and location.
- **Lesson:** pure vector search is good, not sufficient for ranking people. Each retrieval method covers another's blind spot.

---

# Part F: Troubleshooting (problems hit so far)

| Symptom                                                                                  | Cause                                                                                                                                                       | Fix                                                                                                                                                                       |
| ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[WinError 10013] An attempt was made to access a socket...` when starting Uvicorn       | Windows reserves port ranges (Hyper-V / WSL / Docker via the `winnat` service); port 8000 was inside one                                                    | Use another port: `--port 8010`. Check reserved ranges: `netsh interface ipv4 show excludedportrange protocol=tcp`                                                        |
| `Could not import module "app.main"`                                                     | `main.py` missing, in the wrong folder, or saved as `main.py.txt` (Explorer hides extensions)                                                               | List real names with `Get-ChildItem -Recurse -File`; turn on _File name extensions_ in Explorer; create files in the IDE. Test imports with `python -c "import app.main"` |
| `/api/health` shows `degraded`, all models `installed: false`                            | Ollama was looking in an empty model folder: `setx OLLAMA_MODELS` was run while Ollama was running, and the Ollama app has its own _Model location_ setting | Set _Model location_ to `D:\OllamaModels` in the Ollama app, restart Ollama, remove the env var, check with `ollama list`                                                 |
| Folder size shows 6.41 GB, not 6.9                                                       | PowerShell's `1GB` is a binary gigabyte (1,073,741,824 bytes)                                                                                               | Not a problem; units differ                                                                                                                                               |
| Prompt starts in `C:\WINDOWS\system32`                                                   | PowerShell running as Administrator                                                                                                                         | Use the IDE's terminal (Terminal → New Terminal), or turn off "Run as administrator" in the shortcut / Windows Terminal profile                                           |
| `The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed` | Newer SQLAlchemy makes greenlet optional                                                                                                                    | Use `sqlalchemy[asyncio]` in `requirements.txt`, then `pip install -r requirements.txt`                                                                                   |
| `No module named scripts.try_search`                                                     | The zip was extracted into a new sub-folder instead of over the project                                                                                     | From the project root: `Expand-Archive -Path <zip> -DestinationPath . -Force`, or `robocopy <extracted>\backend . /E`                                                     |
| A long LLM extraction restarts from scratch                                              | `--reload` restarts the server whenever a `.py` file is saved, cancelling the running LLM call                                                              | Run long jobs without `--reload`: `uvicorn app.main:app --port 8010`                                                                                                      |
| A resume stays `parsed` with "Waiting for Ollama"                                        | Ollama not running                                                                                                                                          | Start Ollama; the worker retries every 30 s without using up attempts                                                                                                     |
| `MissingGreenlet` error (async SQLAlchemy)                                               | A relationship was accessed that wasn't loaded in the query                                                                                                 | Load it with `selectinload(...)`, or `await session.refresh(obj)` after commit                                                                                            |

---

# Part G: Change log of this document

| Date       | Change                                                                                                                                                                                         |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-10-27 | Created: Parts A (Python), B (AI vocabulary), C (choices vs alternatives)                                                                                                                      |
| 2026-10-27 | Added Part D (enterprise, production-grade stack)                                                                                                                                              |
| 2026-10-27 | Added Part 0 (system overview, status pipeline, where things live), 18 new Part B terms from Steps 4–6, Part E (findings with measured numbers), Part F (troubleshooting), Part G (change log) |
