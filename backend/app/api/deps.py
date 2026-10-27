"""Shared FastAPI dependencies, injected into endpoints with Depends(...)."""
from fastapi import Request

from app.llm.ollama_client import OllamaClient


def get_ollama(request: Request) -> OllamaClient:
    # The client was created once at startup (see lifespan in main.py) and stored on app.state.
    return request.app.state.ollama