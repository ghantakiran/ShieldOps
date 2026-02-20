"""LangSmith integration for agent workflow tracing.

Provides a thin wrapper around the LangSmith client for tracing
LangGraph agent runs. Only active when SHIELDOPS_LANGSMITH_ENABLED=true.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

logger = structlog.get_logger()

_client: Any = None
_enabled: bool = False


def init_langsmith(
    api_key: str,
    project: str = "shieldops",
    enabled: bool = True,
) -> None:
    """Initialize LangSmith client for agent tracing."""
    global _client, _enabled  # noqa: PLW0603
    _enabled = enabled
    if not enabled or not api_key:
        logger.info("langsmith_disabled")
        return
    try:
        from langsmith import Client

        _client = Client(api_key=api_key)
        # Set env vars for LangGraph auto-tracing
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = project
        logger.info("langsmith_initialized", project=project)
    except ImportError:
        logger.warning("langsmith_package_not_installed")
    except Exception as e:
        logger.warning("langsmith_init_failed", error=str(e))


def get_client() -> Any:
    """Return the LangSmith client (or None)."""
    return _client


def is_enabled() -> bool:
    """Whether LangSmith tracing is active."""
    return _enabled and _client is not None
