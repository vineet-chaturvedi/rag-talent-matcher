# 02 · Python Guide (for this project)

Every Python feature used in the backend, explained from zero, with a small example and a pointer to where it appears in our code. Read top to bottom once, then use it as a lookup.

---

## Part 1: The basics

### 1.1 Values, variables and types
A **variable** is a name that points to a value. Every value has a **type**, which decides what you can do with it.

```python
name = "Priya"                                  # str   text
years = 8.2                                     # float decimal number
jobs = 2                                        # int   whole number
is_current = True                               # bool  True or False
skills = ["Kubernetes", "Terraform"]            # list  ordered, changeable collection
point = (2021, 6)                               # tuple ordered, NOT changeable
codes = {"EMP-1001", "EMP-1003"}                # set   unique items, fast "is it in here?"
employee = {"code": "EMP-1003", "years": 8.2}   # dict  key -> value lookup
nothing = None                                  # None  "no value"
```

| Type | Typical operations | In our code |
|---|---|---|
| `str` | `.lower()`, `.strip()`, `.split("\n")`, `f"..."` | Cleaning resume text (`text_extraction.py`) |
| `list` | `.append(x)`, `len(items)`, `items[0]`, slicing `items[:3]` | Chunks, skills, search hits |
| `dict` | `d["key"]`, `d.get("key", default)`, `.items()` | JSON from Ollama: `data["message"]["content"]` |
| `set` | `x in s` (instant), `.add(x)` | Installed model names in `health.py` |
| `None` | `if x is None:` | Optional fields such as an end date for a current job |

**Slicing:** `text[:1500]` means "the first 1,500 characters"; `items[i:i + 16]` means "16 items starting at `i`" (used for batching embeddings).

### 1.2 Truthiness
In an `if`, empty things count as **false**: `""`, `[]`, `{}`, `0`, `None`. So `if not resume.raw_text:` means "if there is no text (None or empty)".

### 1.3 Control flow
```python
if status == "failed":
    retry()
elif status == "ready":
    print("searchable")
else:
    wait()

for skill in skills:          # repeat for each item
    print(skill)

while not stopping:           # repeat until a condition changes (the worker loop)
    process_next()
```
- `continue` skips to the next loop round; `break` leaves the loop.
- `for i, chunk in enumerate(chunks):` gives a counter **and** the item (used to number chunks).
- `for a, b in zip(list1, list2):` walks two lists side by side (used to pair chunk ids with vectors).

### 1.4 Functions
```python
def months_to_years(months: int) -> float:
    """Docstring: explains what the function does."""
    return round(months / 12, 1)

months_to_years(98)            # 8.2
```
- **Parameters** are the inputs; `return` sends the result back.
- **Default values:** `def query(vector, n_results=60):` means `n_results` is optional.
- **Keyword arguments:** `extract_profile(ollama, text, model="qwen2.5:3b")` names the argument, so the order doesn't matter and the call is readable.
- **Keyword-only** (`def build_chunks(*, employee_code, ...)`): the `*` forces callers to name every argument, which prevents mixing up similar-looking values.

### 1.5 Type hints
```python
def parse_point(text: str | None) -> YearMonth | None:
```
Hints say what types are expected (`str | None` = "text or nothing"). Python itself ignores them, but:
- your editor uses them for auto-complete and warnings;
- **Pydantic and FastAPI enforce them**: an API field typed `int` rejects `"abc"` with a 422 error.

---

## Part 2: Organising code

### 2.1 Modules, packages and imports
- A **module** is one `.py` file; a **package** is a folder of modules with `__init__.py`.
- `from app.rag.vector_store import get_vector_store` means: package `app` → sub-package `rag` → file `vector_store.py` → the name `get_vector_store`.

**How Python finds `app`:** it searches the **current folder** first. That is why you run everything from `backend/`, and why scripts are started with `python -m scripts.name` (run as a module, current folder on the path) instead of `python scripts/name.py`.

**Circular imports:** if `employee.py` imports `resume.py` and `resume.py` imports `employee.py`, Python fails. Our models avoid it with `if TYPE_CHECKING:` imports (editor-only) and string names in relationships (`"Resume"`).

### 2.2 Classes and objects
```python
class VectorStore:
    def __init__(self, path: str):        # constructor: runs when the object is created
        self._client = open_client(path)  # attribute stored on this object

    def count(self) -> int:               # method: a function that belongs to the object
        return self._client.count()

store = VectorStore("./data/chroma")      # create an object (an "instance")
store.count()                             # call a method
```
- `self` is the object itself; `self._client` is "this store's client".
- A leading underscore (`_client`, `_request`) is a convention meaning "internal, don't use from outside".

### 2.3 Inheritance
```python
class ResumeDetail(ResumeOut):     # everything ResumeOut has, plus:
    employee_code: str
    text: str | None
```
Used for settings (`Settings(BaseSettings)`), all database models (`Base`), and API schemas.

### 2.4 Dataclasses
```python
from dataclasses import dataclass

@dataclass(frozen=True)            # frozen = values can't be changed after creation
class YearMonth:
    year: int
    month: int | None

YearMonth(2021, 6)                 # Python writes __init__ for you
```
Use dataclasses for internal "bags of values" (`ChunkHit`, `ProfileSkill`, `Claimed`).

### 2.5 Pydantic models (validated data)
```python
from pydantic import BaseModel, Field

class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)      # ... = required
    top_k: int = Field(10, ge=1, le=50)        # default 10, allowed 1..50

SemanticSearchRequest(query="k8s", top_k="5")  # "5" is converted to 5
SemanticSearchRequest(query="k")               # ValidationError: too short
```
| Feature | Example | Used for |
|---|---|---|
| Conversion | `"2026-11-01"` → `date` | CSV import |
| Validation | `ge`, `le`, `min_length`, `pattern` | API input, CSV rows |
| `model_validate(obj)` | Build from an ORM object (`from_attributes=True`) | API responses |
| `model_validate_json(text)` | Parse and validate JSON text | The LLM's answer |
| `model_json_schema()` | Produce a JSON schema | Constraining the LLM's output |
| `model_dump()` | Back to a plain dict | Saving raw LLM output |

**Dataclass vs Pydantic:** dataclasses trust their input; Pydantic checks it. Use Pydantic at the **boundaries** (HTTP, files, LLM output), dataclasses inside.

### 2.6 Enums
```python
from enum import StrEnum

class ResumeStatus(StrEnum):
    QUEUED = "queued"
    READY = "ready"

ResumeStatus.READY == "ready"     # True: StrEnum members are strings
```
Prevents typos like `"redy"`, and the database and API only ever see allowed values.

---

## Part 3: Expressive syntax

### 3.1 Comprehensions
```python
names    = [s.name for s in skills]                     # list
recent   = [s for s in skills if s.last_used_year >= 2024]
by_code  = {e.employee_code: e for e in employees}      # dict
models   = {normalize_model_name(m) for m in tags}      # set
```
Read as: "**for each** `s` in `skills`, **(if** condition**)**, take **this**".

### 3.2 f-strings and formatting
```python
f"{name} has {years} years"          # values inserted
f"{score:.3f}"                        # 3 decimals -> 0.584
f"{code:<9}"                          # pad to 9 characters (aligned columns in scripts)
```

### 3.3 Conditional expression
```python
note = "gave up" if give_up else "will retry"
```

### 3.4 The walrus operator `:=`
```python
if m := _YEAR.search(text):          # assign AND test in one step
    return int(m.group(1))
```
Used in `dates.py` to try regex patterns one after another.

### 3.5 Unpacking
```python
vec_a, vec_b = await ollama.embed([a, b])     # a list of 2 -> two variables
for name, location, years in rows: ...         # each row is a tuple of 3
{**base, "status": "ok"}                        # copy a dict and add keys
Employee(**row.model_dump())                    # dict -> keyword arguments
```

### 3.6 `*args` / `**kwargs`
```python
async def _update(self, resume_id: int, **values):   # collects any named arguments
    for key, value in values.items():
        setattr(resume, key, value)                   # set attribute by name

await self._update(7, status="ready", attempts=0)     # values = {"status": "ready", "attempts": 0}
```

### 3.7 `lambda`
```python
sorted(skills, key=lambda s: -(s.years or 0))    # sort by years, most first; None treated as 0
```

### 3.8 Decorators
A decorator wraps a function to add behaviour:

| Decorator | Effect | Where |
|---|---|---|
| `@router.get("/path")` | Register an endpoint | `app/api/*.py` |
| `@lru_cache` | Run once, then return the remembered result | `get_settings()`, `get_vector_store()` |
| `@dataclass` | Generate `__init__` and friends | Internal value classes |
| `@property` | Read a method like a field | `settings.extraction_model` |
| `@field_validator` / `@model_validator` | Custom Pydantic checks | `EmployeeRow` |
| `@asynccontextmanager` | Turn a generator into an `async with` block | `lifespan` in `main.py` |
| `@event.listens_for(...)` | Run on a SQLAlchemy event | SQLite PRAGMAs on every connection |

---

## Part 4: Errors and resources

### 4.1 Exceptions
```python
class OllamaError(Exception):          # our own error type
    pass

try:
    data = await ollama.chat(...)
except OllamaError as exc:             # catch only this kind
    raise HTTPException(status_code=503, detail=str(exc))
except Exception:                      # anything else
    logger.exception("unexpected")     # logs the full traceback
    raise                              # re-throw the same error
finally:
    cleanup()                          # always runs
```
- `raise NewError(...) from exc` keeps the original error attached for debugging.
- **Subclass errors** to group them: `ScannedDocumentError(ExtractionError)` is caught by `except ExtractionError`.

### 4.2 Reading a traceback
Read **from the bottom up**: the last line is the error; the lines above show the chain of calls that led there, ending in the file and line that failed.
```
  File ".../app/api/deps.py", line 5, in <module>
    from sqlalchemy.ext.asyncio import AsyncSession
ImportError: The SQLAlchemy asyncio module requires ... 'greenlet' ...    <- the actual problem
```

### 4.3 Context managers (`with`)
```python
with open(path, "rb") as fh:                   # file closed automatically
    data = fh.read()

async with SessionLocal() as session:          # session always closed, even after an error
    await session.commit()
```

---

## Part 5: Async programming

### 5.1 Why async
Our server waits a lot: Ollama (seconds to minutes), disk, network. Async lets one Python process **serve other requests while waiting**.

```
Without async:  [request A waits 60 s for Ollama ......................][request B]
With async:     [A starts][B handled][C handled]...........[A resumes when Ollama answers]
```

### 5.2 The vocabulary
| Term | Meaning |
|---|---|
| `async def f()` | A function that can pause (a coroutine) |
| `await x` | Pause here until `x` is done; let other tasks run meanwhile |
| Event loop | Python's scheduler that switches between paused tasks |
| `asyncio.create_task(f())` | Start `f` running in the background (the worker) |
| `asyncio.to_thread(func, ...)` | Run a slow **normal** function in a thread, so the loop isn't blocked (PDF parsing, ChromaDB) |
| `asyncio.Event` | A flag tasks can wait on (`worker.notify()` wakes the worker) |
| `asyncio.wait_for(x, timeout=5)` | Wait at most 5 s (the worker's poll interval) |
| `asyncio.run(main())` | Start an event loop for a standalone script |

### 5.3 The golden rule
**Never call slow non-async code directly inside `async def`.** It freezes the whole server. Either use an async library (httpx, aiosqlite) or wrap it in `asyncio.to_thread(...)`.

---

## Part 6: Working with text

### 6.1 Regular expressions
```python
import re
re.search(r"(\d{4})", "Jun 2021").group(1)     # '2021'
re.sub(r"\s+", " ", "a   b")                    # 'a b'
re.compile(r"...", re.IGNORECASE)              # prepare once, reuse many times
```
| Pattern | Means | Example |
|---|---|---|
| `\d` / `\w` / `\s` | digit / letter-digit-underscore / whitespace | `\d{4}` = 4 digits |
| `.` | any character | |
| `*` / `+` / `?` | 0+ / 1+ / 0 or 1 | `\s+` |
| `{n,m}` | between n and m times | `[a-z]{3,9}` |
| `[abc]` / `[^abc]` | one of / none of | `[^\w]` |
| `( )` | capture a group | `(\d{4})` |
| `\b` | word boundary | `\bjava\b` won't match "javascript" |
| `^` / `$` | start / end | `^page \d+$` |
| `(?<!x)` / `(?!x)` | not preceded / not followed by x | whole-word skill matching |

In our code: dates, page numbers, emails and phones, skills in brackets, job-start detection. Practise at regex101.com (choose the Python flavour).

### 6.2 Unicode normalisation
`unicodedata.normalize("NFKC", text)` turns look-alike characters into standard ones (`ﬁ` → `fi`, full-width letters → normal). Used when cleaning extracted text.

---

## Part 7: Project tooling

| Tool | What it is | Command |
|---|---|---|
| **venv** | A private library folder for this project | `python -m venv .venv`, then `.\.venv\Scripts\Activate.ps1` |
| **pip** | Installs libraries | `pip install -r requirements.txt` |
| **requirements.txt** | What to install (ranges like `>=2.0`) | — |
| **requirements.lock.txt** | Exact installed versions | `pip freeze > requirements.lock.txt` |
| **`python -m pkg.module`** | Run a file as a module (imports work) | `python -m scripts.try_search` |
| **`python -c "..."`** | Run one line; great for testing imports | `python -c "import app.main"` |
| **`if __name__ == "__main__":`** | Code that runs only when the file is executed directly | Bottom of every script |
| **argparse** | Reads command-line options | `--clean`, `--models fast` |
| **logging** | Timestamped messages instead of `print` | `logger.info("Resume %s parsed", rid)` |

---

## Part 8: Common errors and what they mean

| Error | Usual meaning |
|---|---|
| `ModuleNotFoundError: No module named 'app'` | Not running from `backend/`, or venv not active |
| `No module named scripts.x` | The file isn't in `scripts/` (check where a zip was extracted) |
| `ImportError: ... greenlet` | Install `sqlalchemy[asyncio]` |
| `422 Unprocessable Entity` | The request didn't match the Pydantic schema; the response says which field |
| `MissingGreenlet` | Async SQLAlchemy tried to lazy-load a relationship; use `selectinload` |
| `KeyError: 'x'` | A dict has no key `x`; use `.get("x")` if it may be missing |
| `AttributeError: 'NoneType' object has no attribute ...` | A value you expected was `None` (e.g. a lookup found nothing) |
| `TypeError: '<' not supported between 'NoneType' and 'date'` | Sorting a list that contains `None`; use a key with a fallback (`e.start_date or date.min`) |
