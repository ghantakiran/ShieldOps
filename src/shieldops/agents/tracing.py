"""Shared OpenTelemetry tracing utilities for LangGraph agent nodes.

Provides the ``traced_node`` decorator that wraps any LangGraph node function
with an OTEL span, recording timing, attributes, and exceptions.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

from opentelemetry import trace

from shieldops.observability.tracing import get_tracer


def traced_node(name: str, agent_type: str = "") -> Callable[..., Any]:
    """Decorator that wraps a LangGraph node function with an OTEL span.

    Args:
        name: Span name, e.g. ``"investigation.gather_context"``.
        agent_type: Agent type attribute, e.g. ``"investigation"``.

    Returns:
        A decorator that adds tracing to both sync and async node functions.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        import asyncio

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer("shieldops.agents")
                with tracer.start_as_current_span(name) as span:
                    span.set_attribute("agent.node.name", name)
                    if agent_type:
                        span.set_attribute("agent.type", agent_type)
                    start = time.monotonic()
                    try:
                        result = await func(*args, **kwargs)
                        duration_ms = (time.monotonic() - start) * 1000
                        span.set_attribute("agent.node.duration_ms", duration_ms)
                        return result
                    except Exception as exc:
                        duration_ms = (time.monotonic() - start) * 1000
                        span.set_attribute("agent.node.duration_ms", duration_ms)
                        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
                        span.record_exception(exc)
                        raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer("shieldops.agents")
                with tracer.start_as_current_span(name) as span:
                    span.set_attribute("agent.node.name", name)
                    if agent_type:
                        span.set_attribute("agent.type", agent_type)
                    start = time.monotonic()
                    try:
                        result = func(*args, **kwargs)
                        duration_ms = (time.monotonic() - start) * 1000
                        span.set_attribute("agent.node.duration_ms", duration_ms)
                        return result
                    except Exception as exc:
                        duration_ms = (time.monotonic() - start) * 1000
                        span.set_attribute("agent.node.duration_ms", duration_ms)
                        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
                        span.record_exception(exc)
                        raise

            return sync_wrapper

    return decorator
