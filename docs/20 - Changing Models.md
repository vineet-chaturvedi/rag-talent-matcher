# 20 - Changing Models

**Read first:** 03 (AI and RAG concepts), 06 (technology choices). **Built:** 2026-11-06.

**In one sentence:** every model the system uses is chosen in `backend/.env`: a local Ollama model, or a cloud or company model (Claude, GPT, Gemini, Azure OpenAI, Voyage, Cohere, any OpenAI-compatible server). To try one, change one line, restart the server, and measure. No code changes.

**The form of a model setting:** `<provider>/<model>`, for example `anthropic/claude-sonnet-4-5`. Without a provider in front it is an Ollama model (`qwen3.5:9b`), so all existing settings keep working. Section 5 has the providers.

---

## 1. The three kinds of model

| Kind | `.env` line | What it does | Used by |
|---|---|---|---|
| **Embedding model** | `EMBED_MODEL` | Turns text into a list of numbers (a vector), so "meaning" can be compared | Search, matching (vector signal), the agent's `search_employees` |
| **Fast LLM** | `FAST_LLM_MODEL` | The quick chat model | Whichever tasks say `fast` |
| **Quality LLM** | `QUALITY_LLM_MODEL` | The careful chat model | Whichever tasks say `quality` |

Each **task** chooses its LLM:

| Task | `.env` line | Value |
|---|---|---|
| Reading resumes (extraction) | `EXTRACTION_MODEL_ROLE` | `fast`, `quality` **or any Ollama model name** |
| Reading role descriptions | `ROLE_PARSE_MODEL_ROLE` | same |
| The LLM judge | `JUDGE_MODEL_ROLE` | same |
| The staffing assistant | `AGENT_MODEL_ROLE` | same |

So you can try a model on one task only, for example `AGENT_MODEL_ROLE=gemma4:e4b`, while everything else stays as it is.

There is also an optional fourth model, the **reranker** (`RERANK_MODEL`, doc 10 §13). It runs inside Python, not in Ollama.

---

## 2. How to switch (the routine)

```powershell
# 1. Get the model (it goes to D:\OllamaModels, the folder set in the Ollama app)
ollama pull qwen3.5:9b

# 2. Measure the current models first, if there's no recent report yet
python -m scripts.evaluate_all --note "before: qwen2.5"

# 3. Change backend\.env, e.g.
#    QUALITY_LLM_MODEL=qwen3.5:9b
# 4. Restart uvicorn. The log line "Models: ..." shows what is now in use.
# 5. If the model reads resumes (extraction), click "Re-extract all" on the Resumes page.
# 6. Measure again and compare (regressions are flagged)
python -m scripts.evaluate_all --note "after: qwen3.5:9b"
```

- **Seeing what's in use:** the dashboard's health card shows every model and whether it's installed.
- **Reports:** each evaluation report records the models that produced its numbers.

**Keep or go back?** Keep the new model if no number got worse (or a small loss buys a big gain) **and** the time per answer is acceptable on the PC. Otherwise change the line back and restart: nothing else has to be undone.

---

## 3. What differs between models, and how the code handles it

All model-specific knowledge lives in **one file, `backend/app/llm/models.py`**. The rest of the code only says "the embedding model" or "the agent model".

### 3.1 Embedding prompts
Retrieval embedding models were trained with a fixed text in front of the **query**, and some in front of the **document** too. Leaving it out quietly lowers search quality.

| Model | Query | Stored text |
|---|---|---|
| nomic-embed-text | `search_query: …` | `search_document: …` |
| qwen3-embedding | `Instruct: Given a job role description, retrieve resume passages of employees who match it` + new line + `Query: …` | as is |
| embeddinggemma | `task: search result \| query: …` | `title: none \| text: …` |
| mxbai-embed-large, bge-large, snowflake-arctic-embed | `Represent this sentence for searching relevant passages: …` | as is |
| snowflake-arctic-embed2 | `query: …` | as is |
| e5, multilingual-e5 | `query: …` | `passage: …` |
| bge-m3, granite-embedding, all-minilm | as is | as is |

**A model that isn't in the table:**
1. The server log warns: `Embedding model X is not in app/llm/models.py ...`.
2. Look up the model's card on ollama.com or Hugging Face for its query instruction.
3. Put it in `.env`, with `{text}` where the text goes:
   ```
   EMBED_QUERY_TEMPLATE=query: {text}
   EMBED_DOCUMENT_TEMPLATE=passage: {text}
   ```
   An empty line means "use the table". Write `{text}` alone for "no prompt at all".

### 3.2 Vector size: why each embedding model gets its own index
- **The problem:** models make vectors of different lengths, for example nomic 768, qwen3-embedding:0.6b 1024, qwen3-embedding:8b 4096. Even at the same length, two models' numbers mean different things.
  - So vectors of two models can never be compared or stored together.
  - ChromaDB would refuse a 1024-number vector in a 768 collection.
- **The solution:**
  - **One ChromaDB collection per embedding model.** nomic keeps the original name `resume_chunks`, so existing data stays valid. Every other model gets `resume_chunks__<model>`, e.g. `resume_chunks__qwen3-embedding-0-6b`.
  - **Automatic re-embedding at startup.** Every chunk row records which model embedded it (`resume_chunks.embedding_model`). At startup the server queues every current resume whose chunks were made with a different model, and the worker re-embeds them in the background. The log says how many were queued, and it takes minutes. Turn this off with `AUTO_REEMBED_ON_MODEL_CHANGE=false` and use the **Re-embed** button instead.
  - **Switching back** to the old model re-embeds again, so the chunk records match. The old collection is kept on disk; vectors of deleted or replaced resumes in it are never shown, because search keeps only chunks of current, ready resumes.
- **While re-embedding runs:** matching still works through skills and keywords. The meaning signal fills in as resumes finish.

### 3.3 "Thinking" (reasoning models)
Newer chat models (qwen3, qwen3.5, deepseek-r1, gpt-oss, …) can write out step-by-step reasoning before the answer. It can help on hard questions, but on a CPU it multiplies the time per answer several times.

| `LLM_THINK` | Effect |
|---|---|
| `off` (default) | Ollama is asked to skip thinking (`"think": false`) |
| `on` | Always think (try it for the judge if you have time to spare) |
| `default` | Send nothing; the model does what it does by default |

Models without thinking:
- **If a model rejects the flag:** the client asks again without it and remembers that model, so only one extra request is ever made.
- **If a model writes `<think>…</think>` into its answer anyway:** that part is removed, from normal answers and from the assistant's final answer.

### 3.4 Things that stay the same for every model
- **Structured output (JSON schema):** Ollama enforces it for any model, so extraction and judging can't produce broken JSON.
- **Tool calling** (the assistant) needs a model that supports tools. On ollama.com these models carry a **tools** label.
- **`LLM_NUM_CTX=8192`** is sent with every request, so the Ollama app's context slider doesn't matter.

---

## 4. Choosing a model for this PC (16 GB RAM, no GPU)

A rough rule: a model needs about its download size in RAM, plus 1–2 GB. Speed on a CPU drops roughly in proportion to size (doc 07, Step 1).

| Use | Try | Size | Note |
|---|---|---|---|
| Fast LLM | `qwen3.5:4b` | ~3 GB | Apache 2.0. Strong at JSON. Replaces `qwen2.5:3b` (whose licence isn't for company use) |
| Quality LLM | `qwen3.5:9b` | ~6 GB | Apache 2.0. Probably a bit slower than `qwen2.5:7b`: measure |
| Alternatives | `gemma4:e4b`, `phi-4-mini` | 3–4 GB | Both do tool calling; good second opinions |
| Embeddings | `qwen3-embedding:0.6b` | ~0.6 GB | Higher retrieval scores than nomic (MTEB 64.3 vs 62.3), multilingual |
| Too big here | 27B+ models, `gpt-oss-20b` | 13 GB+ | Fit badly, or far too slow per answer |

**Before company use:** check each model's licence. Apache 2.0 and MIT are the safest.

---

## 5. Cloud and company models (Claude, GPT, Gemini, Azure, Bedrock, Vertex AI, Voyage, Cohere, gateways)

### 5.1 The providers
| Prefix | Chat | Embeddings | Service | `.env` settings |
|---|---|---|---|---|
| *(none)* or `ollama/` | ✓ | ✓ | Ollama on this PC (default) | `OLLAMA_BASE_URL` |
| `openai/` | ✓ | ✓ | OpenAI | `OPENAI_API_KEY` (`OPENAI_BASE_URL` optional) |
| `azure/` | ✓ | ✓ | Azure OpenAI; the name is your **deployment** name | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION` |
| `anthropic/` | ✓ | – | Anthropic (Claude) | `ANTHROPIC_API_KEY` |
| `gemini/` | ✓ | ✓ | Google Gemini (AI Studio key) | `GEMINI_API_KEY` |
| `bedrock/` | ✓ | ✓ | **Amazon Bedrock** (Step 15): Claude, Llama, Mistral, Nova, DeepSeek … through the Converse API; Titan and Cohere embeddings. Model ids or inference profiles (`apac.…`) | `AWS_REGION`; credentials from the IAM role / `AWS_PROFILE` (no key) |
| `vertex/` | ✓ | ✓ | **Google Vertex AI** (Step 15): Gemini and partner models (`vertex/meta/…`), Claude (`vertex/claude-…@…`), Vertex embeddings | `VERTEX_PROJECT`, `VERTEX_LOCATION`; Application Default Credentials (no key) |
| `compat/` | ✓ | ✓ | Any OpenAI-compatible server: vLLM, LM Studio, OpenRouter, Groq, Mistral, DeepSeek, Together, Azure AI Foundry models, a company LLM gateway (LiteLLM, Portkey, Kong …) | `COMPAT_BASE_URL`, `COMPAT_API_KEY` |
| `voyage/` | – | ✓ | Voyage AI (Anthropic's recommended embedding partner) | `VOYAGE_API_KEY` |
| `cohere/` | – | ✓ | Cohere | `COHERE_API_KEY` |

These are examples only; check each provider's current model names.
```
QUALITY_LLM_MODEL=anthropic/claude-sonnet-4-5
FAST_LLM_MODEL=openai/gpt-4.1-mini
AGENT_MODEL_ROLE=gemini/gemini-2.5-flash        # one task on its own model
EMBED_MODEL=voyage/voyage-3.5                   # or openai/text-embedding-3-large, cohere/embed-v4.0, gemini/gemini-embedding-001
JUDGE_MODEL_ROLE=bedrock/apac.anthropic.claude-sonnet-4-5-20250929-v1:0     # Claude on AWS, in the Asia-Pacific region
EMBED_MODEL=vertex/gemini-embedding-001         # Google Cloud, with VERTEX_PROJECT and VERTEX_LOCATION=asia-south1
ALLOW_CLOUD_MODELS=true                         # see 5.3
```
**One-time install** for cloud models: `pip install -r requirements-cloud.txt`. This installs the official OpenAI and Anthropic SDKs, boto3 (Bedrock) and google-auth (Vertex), plus the storage and queue SDKs of Step 15. Voyage, Cohere and Gemini embeddings use plain HTTP and need nothing extra.

**Bedrock and Vertex AI need no API key in `.env`.** They use the identity the platform gives the app (an IAM role on AWS, a service account on Google Cloud), or your own login on a laptop (`aws sso login` / `AWS_PROFILE`, `gcloud auth application-default login`). How they work inside: doc 21 §4.1.

### 5.2 How it works (`app/llm/router.py`)
- The app talks to **one object**, the model router, which keeps the methods it always had (`chat`, `chat_stream`, `embed`). The router reads the prefix and hands the request to the right provider. Nothing else in the code knows which provider answers.
- **One common format:** every provider translates our requests (Ollama's shape) to its own API and the answer back:

| What | OpenAI-style APIs (`openai_compat.py`) | Claude (`anthropic_client.py`) |
|---|---|---|
| System instructions | a `system` message | the separate `system` parameter |
| Tool calls | give each call an id; each tool result points to its id | `tool_use` / `tool_result` blocks; neighbouring same-role messages merged (Claude needs user/assistant turns alternating) |
| JSON answers (extraction, judge, role reading) | `response_format: json_schema`; if a service refuses it, JSON mode with the schema in the instructions | a **forced tool**: Claude must call a tool whose input schema *is* our schema. Works on every Claude model |

Bedrock (`bedrock.py`) does the same with the Converse API, and tries three ways to get JSON: Converse's native structured output, then a forced tool, then the schema in the instructions. The first that works is remembered per model.
| Streaming the assistant | text pieces as they arrive; tool-call pieces put back together | the SDK's text stream, then the final message for tool calls |
| Token counts | `usage` → the same fields as Ollama | `usage` → the same fields |

- **Embeddings that know the kind of text:** Voyage (`input_type`), Cohere (`input_type`) and Gemini (`taskType`) are told whether a text is a **query** or a **document**, so no text prompts are added for them.
- **Model quirks are learned, not coded:** when a model refuses a parameter (for example `temperature` on reasoning models, or `max_tokens` where `max_completion_tokens` is wanted, or `json_schema`), the request is sent again without it once, and that is remembered for the model.
- **Errors:** every provider raises the same error type.
  - "Not this resume's fault" (service down, rate limit, missing key) → the worker pauses and tries later.
  - "This request was refused" (too long, blocked content) → it counts as a failed attempt, so one bad resume can't block the queue.
  - The SDKs also retry rate limits themselves.

### 5.3 Data protection: `ALLOW_CLOUD_MODELS`
Resumes are **personal data**. Extraction sends the full resume text to the model, and the judge and the agent send excerpts. So any model outside this PC or the company network is **refused** until `ALLOW_CLOUD_MODELS=true`:
- **What it covers:** every cloud API, plus an Ollama model whose name ends in `-cloud` (those run at ollama.com).
- **What counts as local:** `compat/` and Ollama addresses on localhost or a private network (a company server).
- **What it looks like:**
  - **At startup,** the log lists the cloud models and whether they are allowed.
  - **On the dashboard,** the health card shows each model's provider, or the reason it can't be used ("cloud models are off", "ANTHROPIC_API_KEY is not set").
  - **When a blocked model is called,** the error message says what to set.

**Before setting it to `true` for real employees,** check:
- a **data processing agreement** with the provider;
- **no training on your data**, and how long the provider keeps it;
- **data residency** (EU or India regions where the law requires it);
- the **law** (India's DPDP Act, GDPR).

Azure OpenAI, Vertex AI (`vertex/`) and Amazon Bedrock (`bedrock/`) are often chosen because they run in the company's own cloud account and region (for India: Bedrock `ap-south-1` with `apac.` profiles, Vertex `asia-south1`, Azure Central India), under the company's existing cloud agreement.

### 5.4 Which cloud models suit this project
| Task | Good fits | Why |
|---|---|---|
| Extraction (many calls, JSON) | a small fast model: `openai/gpt-4.1-mini`, `gemini/gemini-2.5-flash`, a Claude Haiku model | Cheap per resume, reliable JSON |
| Judge, role reading, assistant | a strong model: a Claude Sonnet model, GPT-4.1 / GPT-5 class, Gemini 2.5 Pro | Careful reading, good tool use |
| Embeddings | `voyage/voyage-3.5`, `openai/text-embedding-3-large`, `cohere/embed-v4.0`, `gemini/gemini-embedding-001`, `bedrock/amazon.titan-embed-text-v2:0`, `bedrock/cohere.embed-v4:0`, `vertex/gemini-embedding-001` | Strong retrieval quality, multilingual. Voyage, Cohere and Gemini/Vertex know query vs document |
| Reranker | still the local cross-encoder (doc 10) | Cohere Rerank and Voyage rerank would be the cloud options (not built yet) |

**Cost, roughly:** cloud models are paid per token. One resume is about 2,000–4,000 tokens in and 500–1,500 out. That makes extraction of 2,000 resumes a few dollars with a small model, more with a large one. Each evaluation report shows the token counts.

## 6. Tested (2026-11-06, stand-in Ollama over real HTTP)

- **Model helpers:**
  - The right prompts for nomic, qwen3-embedding, snowflake-arctic-embed and -embed2.
  - The warning and the `.env` override for an unknown model.
  - `<think>` blocks (complete, and cut off) are removed.
  - `fast` / `quality` / exact names resolve correctly.
  - Collection names are valid ChromaDB names, also for long `hf.co/...` names.
- **Thinking flag:**
  - `off` / `on` / `default` send `false` / `true` / nothing.
  - A model that rejects the flag gets one retry without it, in normal and streaming calls, and the flag is never sent to it again.
- **Switch to `qwen3-embedding:0.6b` + `qwen3.5:4b/9b` (environment variables only):**
  - The log listed every model.
  - 23 resumes were queued and re-embedded into `resume_chunks__qwen3-embedding-0-6b` (1,024-number vectors).
  - Queries arrived with the Qwen instruction, documents without a prefix.
  - Health showed all models installed, and the real-resume retrieval test ran.
- **Switch back to nomic:** 23 resumes re-embedded into `resume_chunks`, with `search_document:` prompts.
- **`.env.example`** parses as intended (empty template = automatic). Frontend checks pass (76 tests).

**Cloud providers:** tested against a stand-in for the OpenAI, Anthropic, Voyage, Cohere and Gemini APIs. The stand-in also **checks our requests** (tool-call ids, alternating Claude roles, no `$ref` in tool schemas, input types) and answers 400 on any mistake.
- **Direct provider checks (47 passed):** for openai, anthropic, gemini, compat and the "quirky" models:
  - tool calls in normal and streaming mode;
  - answers after tool results, token counts, and JSON that validates;
  - a refused `temperature`, `max_tokens` or `json_schema` retried once;
  - embeddings from five providers with the right query/document type;
  - the cloud block; an Ollama `-cloud` model treated as cloud; a localhost `compat/` treated as local;
  - missing keys reported.
- **The whole app on cloud models only** (GPT for extraction, Claude for judge and assistant, Voyage for embeddings):
  - 23 resumes re-embedded into a Voyage collection, then re-extracted through GPT;
  - a judged match run through Claude;
  - the agent evaluation gave **exactly the same results on Claude, GPT and Ollama**, so the provider layer changes nothing in the answers;
  - health "ok" with Ollama switched off;
  - with `ALLOW_CLOUD_MODELS=false`: health "degraded" with the reason, and search answers 503 with the reason.
- **Found and fixed in testing:**
  - The newest Anthropic SDK no longer has a `temperature` argument. It is now sent as raw JSON (`extra_body`), and dropped if a model refuses it.
  - An empty `.env` value followed by a comment was read as the comment. Comments now sit on their own line, and empty values mean "use the default" (`env_ignore_empty`).
- **Not tested:** the real cloud APIs (no keys here). The first real call per provider is the real test. Run `evaluate_all` with the new models.

**Review pass (same day): four more fixes**
- **Changing `EMBED_DIMENSIONS`:** this changes the vectors too, so the stored "made with" value is now the model plus the size (e.g. `openai/text-embedding-3-small@128`), and so is the collection name. Changing the size re-embeds once, and a restart with the same settings re-embeds nothing (tested).
- **Health check:** a remote or `-cloud` Ollama model is now also checked against Ollama's list of pulled models.
- **Self-contained schemas:** schemas sent to OpenAI-compatible services have their `$ref`s resolved (some services don't support them).
- **The developer similarity tool** (`/api/dev/similarity`) embeds the query as a query and the document as a document.

**Byte check:** every file in `backend/app`, `backend/scripts`, `backend/evaluation` and `frontend/src` on the PC is identical to the tested copy.

**Note:** if you change `EMBED_DOCUMENT_TEMPLATE` for a model, press **Re-embed** on the Resumes page, because the stored vectors were made with the old template.

---

## Glossary

- **Embedding model:** a model that turns text into a vector; similar meanings → nearby vectors.
- **Collection:** one named set of vectors in ChromaDB (like a table).
- **Re-embedding:** computing the vectors again with another embedding model. The resume text and extraction stay; only the vectors change.
- **Reasoning / thinking model:** a chat model that can write out intermediate reasoning before its answer.
- **Tag:** the part after `:` in a model name (`qwen3.5:9b`), usually the size or the quantisation.
