"""Distributed tracing for agent execution via OpenTelemetry.

Provides span creation, attribute injection, and baggage propagation
for LangGraph agent nodes. Extends original ``traced_node`` decorator
with a full ``AgentTracer`` class for agent-level spans.
"""

from __future__ import annotations

import functools
import time
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TracingConfig(BaseModel):
    """Configuration for agent tracing."""

    enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"
    service_name: str = "shieldops-agents"
    sample_rate: float = 1.0
    propagate_baggage: bool = True


# ---------------------------------------------------------------------------
# Span attribute constants
# ---------------------------------------------------------------------------


class SpanAttributes:
    """Standard span attribute keys for agent traces."""

    AGENT_TYPE = "agent.type"
    AGENT_ID = "agent.id"
    NODE_NAME = "node.name"
    CONFIDENCE = "agent.confidence"
    ACTION_COUNT = "agent.action_count"
    CORRELATION_ID = "agent.correlation_id"
    ENVIRONMENT = "agent.environment"
    DURATION_MS = "agent.duration_ms"


# ---------------------------------------------------------------------------
# Lightweight span (works without OTEL installed)
# ---------------------------------------------------------------------------


class AgentSpan:
    """Lightweight span wrapper for agent tracing."""

    def __init__(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.name = name
        self.attributes: dict[str, Any] = attributes or {}
        self.start_time: float = time.monotonic()
        self.end_time: float | None = None
        self.status: str = "ok"
        self.events: list[dict[str, Any]] = []
        self._otel_span: Any = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append({"name": name, "attributes": attributes or {}})

    def set_status(self, status: str) -> None:
        self.status = status

    def end(self) -> None:
        self.end_time = time.monotonic()

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.monotonic()
        return (end - self.start_time) * 1000


# ---------------------------------------------------------------------------
# AgentTracer
# ---------------------------------------------------------------------------


class AgentTracer:
    """Wraps agent execution with OpenTelemetry spans.

    Falls back to lightweight internal spans when OTEL is not available.
    """

    def __init__(self, config: TracingConfig | None = None) -> None:
        self.config = config or TracingConfig()
        self._tracer: Any = None
        self._spans: list[AgentSpan] = []

        if self.config.enabled:
            try:
                from opentelemetry import trace as _trace

                self._tracer = _trace.get_tracer(self.config.service_name)
            except ImportError:
                logger.debug("otel_not_available_using_internal_tracer")

    @asynccontextmanager
    async def start_agent_span(
        self,
        agent_type: str,
        agent_id: str = "",
        correlation_id: str = "",
        **extra_attrs: Any,
    ) -> AsyncIterator[AgentSpan]:
        """Start a span for an agent execution."""
        span = AgentSpan(
            name=f"agent.{agent_type}",
            attributes={
                SpanAttributes.AGENT_TYPE: agent_type,
                SpanAttributes.AGENT_ID: agent_id,
                SpanAttributes.CORRELATION_ID: correlation_id,
                **extra_attrs,
            },
        )

        if self._tracer is not None:
            try:
                from opentelemetry import trace as _trace

                with self._tracer.start_as_current_span(
                    span.name,
                    attributes=span.attributes,
                ) as otel_span:
                    span._otel_span = otel_span
                    try:
                        yield span
                    except Exception as exc:
                        span.set_status("error")
                        otel_span.set_status(_trace.StatusCode.ERROR, str(exc))
                        raise
                    finally:
                        span.end()
                        self._spans.append(span)
                return
            except Exception:  # noqa: S110
                pass  # OTEL context creation failed; fall through to no-OTEL path

        # Fallback: no OTEL
        try:
            yield span
        except Exception:
            span.set_status("error")
            raise
        finally:
            span.end()
            self._spans.append(span)

    @contextmanager
    def start_node_span(
        self,
        node_name: str,
        agent_type: str = "",
        **extra_attrs: Any,
    ) -> Iterator[AgentSpan]:
        """Start a synchronous span for a LangGraph node."""
        span = AgentSpan(
            name=f"node.{node_name}",
            attributes={
                SpanAttributes.NODE_NAME: node_name,
                SpanAttributes.AGENT_TYPE: agent_type,
                **extra_attrs,
            },
        )

        try:
            yield span
        except Exception:
            span.set_status("error")
            raise
        finally:
            span.end()
            self._spans.append(span)

    @property
    def recorded_spans(self) -> list[AgentSpan]:
        return list(self._spans)

    def clear(self) -> None:
        self._spans.clear()


# ---------------------------------------------------------------------------
# Helper to get OTEL tracer (backward-compatible)
# ---------------------------------------------------------------------------


def _get_tracer(name: str = "shieldops.agents") -> Any:
    """Get an OTEL tracer, falling back to no-op if unavailable."""
    try:
        from shieldops.observability.tracing import get_tracer

        return get_tracer(name)
    except Exception:
        try:
            from opentelemetry import trace as _trace

            return _trace.get_tracer(name)
        except ImportError:
            return None


# ---------------------------------------------------------------------------
# traced_node decorator (original API preserved)
# ---------------------------------------------------------------------------


def traced_node(
    name: str,
    agent_type: str = "",
    tracer: AgentTracer | None = None,
) -> Callable[..., Any]:
    """Decorator for LangGraph nodes that wraps execution in a trace span.

    Supports both the original OTEL-based approach and the new AgentTracer.
    """

    def decorator(func: F) -> F:
        import asyncio

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # New AgentTracer path
                if tracer is not None:
                    with tracer.start_node_span(name, agent_type=agent_type) as span:
                        result = await func(*args, **kwargs)
                        if isinstance(result, dict):
                            confidence = result.get("confidence")
                            if confidence is not None:
                                span.set_attribute(SpanAttributes.CONFIDENCE, confidence)
                        return result

                # Original OTEL path
                otel_tracer = _get_tracer()
                if otel_tracer is None:
                    return await func(*args, **kwargs)

                with otel_tracer.start_as_current_span(name) as span:
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
                        try:
                            from opentelemetry import trace as _trace

                            span.set_status(_trace.Status(_trace.StatusCode.ERROR, str(exc)))
                        except ImportError:
                            pass
                        raise

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                if tracer is not None:
                    with tracer.start_node_span(name, agent_type=agent_type) as span:
                        result = func(*args, **kwargs)
                        if isinstance(result, dict):
                            confidence = result.get("confidence")
                            if confidence is not None:
                                span.set_attribute(SpanAttributes.CONFIDENCE, confidence)
                        return result

                otel_tracer = _get_tracer()
                if otel_tracer is None:
                    return func(*args, **kwargs)

                with otel_tracer.start_as_current_span(name) as span:
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
                        try:
                            from opentelemetry import trace as _trace

                            span.set_status(_trace.Status(_trace.StatusCode.ERROR, str(exc)))
                        except ImportError:
                            pass
                        raise

            return sync_wrapper  # type: ignore[return-value]

    return decorator
