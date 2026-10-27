"""Shared FastAPI dependencies, injected into endpoints with Depends(...)."""
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.llm.ollama_client import OllamaClient


def get_ollama(request: Request) -> OllamaClient:
    # The client was created once at startup (see lifespan in main.py) and stored on app.state.
    return request.app.state.ollama


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    One database session per request.
    `async with` guarantees the session is closed when the request ends, even if it crashed,
    so connections are never leaked.
    """
    async with SessionLocal() as session:
        yield session