"""LLM call instrumentation utilities for ShieldOps agents.

Provides a ``@track_llm_call`` decorator that wraps async functions
making LLM calls and automatically records latency, token counts, and
model information on the shared ``AgentMetricsCollector``.

Usage::

    from shieldops.utils.llm_metrics import track_llm_call

    @track_llm_call(agent_type="investigation")
    async def analyze_incident(prompt: str) -> dict:
        return await llm_structured(system, prompt, Schema)

The decorator is opt-in; it does **not** modify the existing
``shieldops.utils.llm`` module.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

from shieldops.observability.agent_metrics import get_agent_metrics

logger = structlog.get_logger()

F = TypeVar("F", bound=Callable[..., Any])

# Rough estimate: ~4 characters per token (English text average).
# Used only when actual token counts are unavailable.
_CHARS_PER_TOKEN_ESTIMATE = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count from character length.

    This is a coarse heuristic (~4 chars/token for English).  Prefer
    actual token counts from the LLM response when available.
    """
    return max(1, len(text) // _CHARS_PER_TOKEN_ESTIMATE)


def track_llm_call(
    agent_type: str,
    model: str | None = None,
) -> Callable[[F], F]:
    """Decorator that instruments an async LLM call with metrics.

    Args:
        agent_type: The agent kind (investigation, remediation, etc.).
        model: LLM model name.  If ``None``, defaults to ``"unknown"``.

    The decorated function can return:
    - A dict with optional ``usage`` key containing ``input_tokens``
      and ``output_tokens``.
    - A Pydantic ``BaseModel`` (tokens estimated from content length).
    - Any other value (tokens estimated from ``str()`` length).

    On exception the decorator still records the LLM call (with zero
    tokens) so latency data is captured, then re-raises.
    """
    resolved_model = model or "unknown"

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            metrics = get_agent_metrics()
            start = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
            except Exception:
                # Record the failed call so latency is still tracked
                elapsed = time.perf_counter() - start
                try:
                    metrics.record_llm_call(
                        agent_type=agent_type,
                        model=resolved_model,
                        latency_seconds=elapsed,
                        input_tokens=0,
                        output_tokens=0,
                    )
                except Exception:
                    logger.warning(
                        "llm_metrics_recording_failed_on_exception",
                        agent_type=agent_type,
                    )
                raise

            elapsed = time.perf_counter() - start

            # Extract token counts
            input_tokens, output_tokens = _extract_tokens(
                result,
                args,
                kwargs,
            )

            try:
                metrics.record_llm_call(
                    agent_type=agent_type,
                    model=resolved_model,
                    latency_seconds=elapsed,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            except Exception:
                logger.warning(
                    "llm_metrics_recording_failed",
                    agent_type=agent_type,
                    exc_info=True,
                )

            return result

        return wrapper  # type: ignore[return-value]

    return decorator


def _extract_tokens(
    result: Any,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[int, int]:
    """Best-effort extraction of token counts from an LLM result.

    Checks for ``usage`` metadata in the result dict, then falls back
    to character-length estimation.
    """
    input_tokens = 0
    output_tokens = 0

    # If result is a dict with a "usage" key (langchain-style)
    if isinstance(result, dict):
        usage = result.get("usage", {})
        if isinstance(usage, dict):
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

        # Fallback: estimate from content if usage not present
        if output_tokens == 0:
            content = result.get("content", "")
            if content:
                output_tokens = estimate_tokens(str(content))

    # Pydantic model or other object -- estimate from string repr
    elif result is not None:
        output_tokens = estimate_tokens(str(result))

    # Estimate input tokens from positional args (prompts are
    # typically the first two string arguments: system + user)
    if input_tokens == 0:
        prompt_text = ""
        for arg in args:
            if isinstance(arg, str):
                prompt_text += arg
        for key in ("system_prompt", "user_prompt", "prompt"):
            val = kwargs.get(key)
            if isinstance(val, str):
                prompt_text += val
        if prompt_text:
            input_tokens = estimate_tokens(prompt_text)

    return input_tokens, output_tokens
