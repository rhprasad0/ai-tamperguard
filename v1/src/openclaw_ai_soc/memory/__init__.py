"""Graphiti-only incident memory backend for Openclaw v1."""

from typing import Any

from openclaw_ai_soc.config import OpenclawSettings
from openclaw_ai_soc.memory.graphiti import GraphitiMemoryClient


def create_memory_client(
    settings: OpenclawSettings, *, transport: Any = None
) -> GraphitiMemoryClient:
    """Resolve the v1 incident memory backend.

    Graphiti is the only allowed backend. This factory intentionally rejects all
    other values even if a caller bypasses settings validation in tests or graph
    construction.
    """

    backend = settings.ai_soc_memory_backend
    if backend == "graphiti":
        return GraphitiMemoryClient(settings=settings, transport=transport)
    if backend == "honcho":
        raise ValueError("Honcho is not a v1 incident memory backend; use graphiti")
    raise ValueError("AI_SOC_MEMORY_BACKEND must be graphiti in v1")


__all__ = ["create_memory_client"]
