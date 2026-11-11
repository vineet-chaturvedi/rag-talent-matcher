"""
Everything that depends on WHICH model is used, in one place, so any model can be swapped in from
backend/.env without touching the rest of the code. WHERE a model runs (Ollama, OpenAI, Anthropic, Gemini,
Azure, Voyage, Cohere, any OpenAI-compatible server) is app/llm/router.py's job: "<provider>/<model>".

Three kinds of model, each chosen in .env:
  EMBED_MODEL          turns text into vectors (search)                 e.g. nomic-embed-text, qwen3-embedding:0.6b
  FAST_LLM_MODEL       the quick chat model                             e.g. qwen2.5:3b, qwen3.5:4b
  QUALITY_LLM_MODEL    the careful chat model                           e.g. qwen2.5:7b, qwen3.5:9b
and each task picks one with *_MODEL_ROLE = fast | quality | <any Ollama model tag>
  (EXTRACTION_MODEL_ROLE, ROLE_PARSE_MODEL_ROLE, JUDGE_MODEL_ROLE, AGENT_MODEL_ROLE).

What differs between models, and how it is handled here:
  1. Embedding prompts. Most retrieval embedding models were trained with a fixed text in front of the
     query (and sometimes the document). Leaving it out costs search quality. KNOWN_EMBEDDINGS has the
     right templates for common models; for any other model set EMBED_QUERY_TEMPLATE and
     EMBED_DOCUMENT_TEMPLATE in .env (with {text} where the text goes).
  2. "Thinking". Newer chat models (qwen3, qwen3.5, deepseek-r1, ...) can reason step by step before
     answering. On a CPU that multiplies the answer time, so LLM_THINK=off (the default) asks Ollama to skip
     it. Models that don't think simply ignore it (ollama_client.py retries without the flag if a model
     rejects it). Any <think>...</think> text a model still writes is removed from the answer.
  3. Vector size. Different embedding models make vectors of different lengths (768, 1024, 4096 ...), which
     can't share one vector index. Each embedding model gets its own ChromaDB collection (collection_name),
     and after a switch the server re-embeds the resumes by itself at startup (main.py).
"""
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingProfile:
    """How texts must be written for one embedding model. {text} is replaced by the text."""
    query_template: str = "{text}"
    document_template: str = "{text}"
    note: str = ""


# Matched against the start of the model name (without the ":tag"), first match wins.
# Sources: each model's card on Hugging Face / ollama.com.
_QWEN3_TASK = "Given a job role description, retrieve resume passages of employees who match it"
KNOWN_EMBEDDINGS: list[tuple[str, EmbeddingProfile]] = [
    ("nomic-embed-text", EmbeddingProfile("search_query: {text}", "search_document: {text}", "nomic task prefixes")),
    ("qwen3-embedding", EmbeddingProfile(f"Instruct: {_QWEN3_TASK}\nQuery: {{text}}", "{text}",
                                         "instruction on the query only")),
    ("embeddinggemma", EmbeddingProfile("task: search result | query: {text}", "title: none | text: {text}",
                                        "Gemma task prompts")),
    ("mxbai-embed-large", EmbeddingProfile("Represent this sentence for searching relevant passages: {text}")),
    ("snowflake-arctic-embed2", EmbeddingProfile("query: {text}")),
    ("snowflake-arctic-embed", EmbeddingProfile("Represent this sentence for searching relevant passages: {text}")),
    ("bge-large", EmbeddingProfile("Represent this sentence for searching relevant passages: {text}")),
    ("multilingual-e5", EmbeddingProfile("query: {text}", "passage: {text}")),
    ("e5", EmbeddingProfile("query: {text}", "passage: {text}")),
    # Cloud APIs: no text prompts. OpenAI's models need none; Voyage, Cohere and Gemini get the kind of text
    # (query / document) as an API parameter instead (app/llm/embedding_apis.py).
    ("text-embedding-3", EmbeddingProfile(note="OpenAI: no prompts")),
    ("text-embedding-ada", EmbeddingProfile(note="OpenAI: no prompts")),
    ("gemini-embedding", EmbeddingProfile(note="Gemini: task type sent by the API")),
    ("text-embedding-00", EmbeddingProfile(note="Google: task type sent by the API")),
    ("text-multilingual-embedding", EmbeddingProfile(note="Google: task type sent by the API")),
    ("voyage", EmbeddingProfile(note="Voyage: input_type sent by the API")),
    ("embed-", EmbeddingProfile(note="Cohere: input_type sent by the API")),
    ("mistral-embed", EmbeddingProfile(note="Mistral: no prompts")),
    ("amazon.titan-embed", EmbeddingProfile(note="Bedrock Titan: no prompts")),
    ("cohere.embed", EmbeddingProfile(note="Bedrock Cohere: input_type sent by the API")),
    ("amazon.nova", EmbeddingProfile(note="Bedrock Nova: no prompts")),
    ("bge-m3", EmbeddingProfile(note="no prompts needed")),
    ("granite-embedding", EmbeddingProfile(note="no prompts needed")),
    ("all-minilm", EmbeddingProfile(note="no prompts needed")),
]

_warned: set[str] = set()


def base_name(model: str) -> str:
    """'qwen3-embedding:0.6b' -> 'qwen3-embedding'; 'hf.co/org/x:Q4' -> 'x'."""
    return model.split("/")[-1].split(":")[0].lower()


def embedding_profile(model: str, query_template: str | None = None,
                      document_template: str | None = None) -> EmbeddingProfile:
    """The templates for this model; .env overrides (EMBED_QUERY_TEMPLATE / EMBED_DOCUMENT_TEMPLATE) win."""
    name = base_name(model)
    known = next((p for prefix, p in KNOWN_EMBEDDINGS if name.startswith(prefix)), None)
    if known is None and query_template is None and model not in _warned:
        _warned.add(model)
        logger.warning("Embedding model %s is not in app/llm/models.py: texts are embedded without prompts. "
                       "If its model card asks for a query prefix, set EMBED_QUERY_TEMPLATE in .env.", model)
    profile = known or EmbeddingProfile()
    return EmbeddingProfile(
        query_template=query_template if query_template is not None else profile.query_template,
        document_template=document_template if document_template is not None else profile.document_template,
        note=profile.note,
    )


def apply(template: str, text: str) -> str:
    return template.replace("{text}", text) if "{text}" in template else template + text


# ---------------------------------------------------------------------------- chat models
_THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def strip_thinking(text: str) -> str:
    """Remove a model's written-out reasoning (<think>...</think>), keeping only the answer."""
    if not text or "<think>" not in text.lower():
        return text
    cleaned = _THINK_BLOCK.sub("", text)
    # An unclosed <think> (answer cut off while still thinking): nothing usable after it.
    return re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL | re.IGNORECASE).strip()


def resolve_model(choice: str, fast: str, quality: str) -> str:
    """A task's model: 'fast' / 'quality' pick the two shared models; anything else is an exact Ollama tag."""
    value = (choice or "").strip()
    if value.lower() == "fast":
        return fast
    if value.lower() == "quality":
        return quality
    if not value:
        raise ValueError("A *_MODEL_ROLE setting is empty: use fast, quality or an Ollama model name.")
    return value


def collection_name(base: str, embed_model: str) -> str:
    """
    The ChromaDB collection for this embedding model. nomic-embed-text keeps the original name, so existing
    data stays valid; every other model gets its own collection (vectors of different models never mix).
    Chroma names: 3-63 characters, letters, digits, . _ -, starting and ending with a letter or digit.
    """
    if base_name(embed_model) == "nomic-embed-text":
        return base
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", embed_model.lower()).strip("-")
    return f"{base}__{slug}"[:63].rstrip("-_.")


def inline_refs(schema: dict) -> dict:
    """
    Replace "$ref": "#/$defs/X" with the definition itself (Pydantic puts nested models in $defs). Some
    providers' tool schemas don't resolve $ref, and a self-contained schema works everywhere.
    """
    defs = schema.get("$defs", {}) or schema.get("definitions", {})

    def walk(node, depth=0):
        if depth > 20:                       # a recursive model: stop expanding
            return {}
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.split("/")[-1] in defs:
                merged = {**defs[ref.split("/")[-1]], **{k: v for k, v in node.items() if k != "$ref"}}
                return walk(merged, depth + 1)
            return {k: walk(v, depth) for k, v in node.items() if k not in ("$defs", "definitions")}
        if isinstance(node, list):
            return [walk(v, depth) for v in node]
        return node

    return walk(schema)


def same_model(a: str | None, b: str | None) -> bool:
    """'nomic-embed-text' and 'nomic-embed-text:latest' are the same model."""
    norm = lambda m: (m or "") if ":" in (m or "") else f"{m}:latest"   # noqa: E731
    return norm(a) == norm(b)
