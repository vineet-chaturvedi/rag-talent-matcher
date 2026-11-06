"""
Reranking with a cross-encoder (optional; off unless RERANK_MODEL is set).

Why: our three retrieval signals (skills, BM25 keywords, vectors) each look at the role and the resume
SEPARATELY: the vector search compares two embeddings made independently. A cross-encoder reads the role
description and one chunk TOGETHER and scores how well that chunk answers it, which is much more precise.
It is too slow to run over every chunk, so it only re-scores the chunks of the shortlist that the cheap
signals produced. Anthropic measured retrieval failures falling from 2.9% to 1.9% by adding a reranker on top
of contextual embeddings + BM25 (https://www.anthropic.com/research/contextual-retrieval).

Model: runs locally on the CPU with ONNX (fastembed, no PyTorch). Default suggestion
"Xenova/ms-marco-MiniLM-L-6-v2" (~80 MB, English): about 2-5 s for a shortlist of 30 people.
"BAAI/bge-reranker-v2-m3-int8" (~570 MB) is stronger and multilingual, but slower.
The model is downloaded from Hugging Face on first use into data/models/.

Failure is never fatal: if fastembed isn't installed or the model can't load, a warning is logged once and
matching continues without this signal.
"""
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model = None
_failed_for: str | None = None


def _load(model_name: str, cache_dir: str):
    global _model, _failed_for
    with _lock:
        if _model is not None and getattr(_model, "_rag_name", None) == model_name:
            return _model
        if _failed_for == model_name:
            return None
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
        except ImportError:
            logger.warning("RERANK_MODEL is set but fastembed is not installed (pip install fastembed); "
                           "matching continues without reranking.")
            _failed_for = model_name
            return None
        try:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            model = TextCrossEncoder(model_name=model_name, cache_dir=cache_dir)
        except Exception as exc:  # download failure, unknown model name, broken file ...
            logger.warning("Could not load the reranker %s (%s); matching continues without reranking.",
                           model_name, exc)
            _failed_for = model_name
            return None
        model._rag_name = model_name
        _model = model
        logger.info("Reranker loaded: %s", model_name)
        return _model


def rerank_scores(query: str, documents: list[str], model_name: str, cache_dir: str,
                  batch_size: int = 32) -> list[float] | None:
    """
    One relevance score per document (higher = more relevant to the query), or None when reranking is off or
    unavailable. Synchronous and CPU-bound: call it with asyncio.to_thread.
    """
    if not model_name or not documents:
        return None
    model = _load(model_name, cache_dir)
    if model is None:
        return None
    try:
        return [float(s) for s in model.rerank(query, documents, batch_size=batch_size)]
    except Exception as exc:
        logger.warning("Reranking failed (%s); matching continues without it.", exc)
        return None


def reset_for_tests() -> None:
    """Forget the loaded model and earlier failures (used by tests and after a settings change)."""
    global _model, _failed_for
    with _lock:
        _model, _failed_for = None, None
