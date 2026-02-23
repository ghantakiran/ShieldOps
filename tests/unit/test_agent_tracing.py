"""Comprehensive unit tests for agent-level tracing (Phase 13 F5).

Tests cover:
- TracingConfig Pydantic model defaults and custom values
- SpanAttributes constants
- AgentSpan lifecycle (creation, attributes, events, status, duration, end)
- AgentTracer without OTEL (config.enabled=False fallback path)
- AgentTracer.start_agent_span async context manager
- AgentTracer.start_node_span sync context manager
- AgentTracer.recorded_spans property and clear()
- traced_node decorator for async functions (AgentTracer path)
- traced_node decorator for sync functions (AgentTracer path)
- traced_node decorator without tracer (fallback / no-op path)
- Error recording through spans on exception
- Confidence attribute extraction from dict results

Requires: pytest, pytest-asyncio
"""

from __future__ import annotations

import time

import pytest

from shieldops.agents.tracing import (
    AgentSpan,
    AgentTracer,
    SpanAttributes,
    TracingConfig,
    traced_node,
)

# ===========================================================================
# TracingConfig Tests
# ===========================================================================


class TestTracingConfig:
    """Tests for the TracingConfig Pydantic model."""

    def test_default_enabled_is_false(self):
        config = TracingConfig()
        assert config.enabled is False

    def test_default_otel_endpoint(self):
        config = TracingConfig()
        assert config.otel_endpoint == "http://localhost:4317"

    def test_default_service_name(self):
        config = TracingConfig()
        assert config.service_name == "shieldops-agents"

    def test_default_sample_rate(self):
        config = TracingConfig()
        assert config.sample_rate == 1.0

    def test_default_propagate_baggage(self):
        config = TracingConfig()
        assert config.propagate_baggage is True

    def test_custom_enabled(self):
        config = TracingConfig(enabled=True)
        assert config.enabled is True

    def test_custom_otel_endpoint(self):
        config = TracingConfig(otel_endpoint="http://otel:4317")
        assert config.otel_endpoint == "http://otel:4317"

    def test_custom_service_name(self):
        config = TracingConfig(service_name="my-service")
        assert config.service_name == "my-service"

    def test_custom_sample_rate(self):
        config = TracingConfig(sample_rate=0.5)
        assert config.sample_rate == 0.5

    def test_custom_propagate_baggage_false(self):
        config = TracingConfig(propagate_baggage=False)
        assert config.propagate_baggage is False


# ===========================================================================
# SpanAttributes Tests
# ===========================================================================


class TestSpanAttributes:
    """Tests for SpanAttributes constant keys."""

    def test_agent_type_key(self):
        assert SpanAttributes.AGENT_TYPE == "agent.type"

    def test_agent_id_key(self):
        assert SpanAttributes.AGENT_ID == "agent.id"

    def test_node_name_key(self):
        assert SpanAttributes.NODE_NAME == "node.name"

    def test_confidence_key(self):
        assert SpanAttributes.CONFIDENCE == "agent.confidence"

    def test_action_count_key(self):
        assert SpanAttributes.ACTION_COUNT == "agent.action_count"

    def test_correlation_id_key(self):
        assert SpanAttributes.CORRELATION_ID == "agent.correlation_id"

    def test_environment_key(self):
        assert SpanAttributes.ENVIRONMENT == "agent.environment"

    def test_duration_ms_key(self):
        assert SpanAttributes.DURATION_MS == "agent.duration_ms"

    def test_all_keys_are_strings(self):
        keys = [
            SpanAttributes.AGENT_TYPE,
            SpanAttributes.AGENT_ID,
            SpanAttributes.NODE_NAME,
            SpanAttributes.CONFIDENCE,
            SpanAttributes.ACTION_COUNT,
            SpanAttributes.CORRELATION_ID,
            SpanAttributes.ENVIRONMENT,
            SpanAttributes.DURATION_MS,
        ]
        for key in keys:
            assert isinstance(key, str), f"SpanAttributes key should be str, got {type(key)}"

    def test_all_keys_use_dot_notation(self):
        keys = [
            SpanAttributes.AGENT_TYPE,
            SpanAttributes.AGENT_ID,
            SpanAttributes.NODE_NAME,
            SpanAttributes.CONFIDENCE,
            SpanAttributes.ACTION_COUNT,
            SpanAttributes.CORRELATION_ID,
            SpanAttributes.ENVIRONMENT,
            SpanAttributes.DURATION_MS,
        ]
        for key in keys:
            assert "." in key, f"Span attribute key '{key}' should use dot notation"


# ===========================================================================
# AgentSpan Tests
# ===========================================================================


class TestAgentSpan:
    """Tests for the lightweight AgentSpan wrapper."""

    def test_span_creation_with_name(self):
        span = AgentSpan(name="test.span")
        assert span.name == "test.span"

    def test_span_default_attributes_empty(self):
        span = AgentSpan(name="test.span")
        assert span.attributes == {}

    def test_span_creation_with_attributes(self):
        attrs = {"agent.type": "investigation", "agent.id": "inv-123"}
        span = AgentSpan(name="test.span", attributes=attrs)
        assert span.attributes == attrs

    def test_span_default_status_is_ok(self):
        span = AgentSpan(name="test.span")
        assert span.status == "ok"

    def test_span_default_events_empty(self):
        span = AgentSpan(name="test.span")
        assert span.events == []

    def test_span_default_end_time_none(self):
        span = AgentSpan(name="test.span")
        assert span.end_time is None

    def test_span_start_time_is_set(self):
        before = time.monotonic()
        span = AgentSpan(name="test.span")
        after = time.monotonic()
        assert before <= span.start_time <= after

    def test_span_otel_span_is_none(self):
        span = AgentSpan(name="test.span")
        assert span._otel_span is None

    def test_set_attribute(self):
        span = AgentSpan(name="test.span")
        span.set_attribute("key", "value")
        assert span.attributes["key"] == "value"

    def test_set_attribute_overwrites(self):
        span = AgentSpan(name="test.span", attributes={"key": "old"})
        span.set_attribute("key", "new")
        assert span.attributes["key"] == "new"

    def test_set_attribute_numeric_value(self):
        span = AgentSpan(name="test.span")
        span.set_attribute("count", 42)
        assert span.attributes["count"] == 42

    def test_add_event(self):
        span = AgentSpan(name="test.span")
        span.add_event("checkpoint", {"step": 1})
        assert len(span.events) == 1
        assert span.events[0]["name"] == "checkpoint"
        assert span.events[0]["attributes"] == {"step": 1}

    def test_add_event_without_attributes(self):
        span = AgentSpan(name="test.span")
        span.add_event("simple_event")
        assert span.events[0]["attributes"] == {}

    def test_add_multiple_events(self):
        span = AgentSpan(name="test.span")
        span.add_event("event_a")
        span.add_event("event_b")
        span.add_event("event_c")
        assert len(span.events) == 3
        assert [e["name"] for e in span.events] == ["event_a", "event_b", "event_c"]

    def test_set_status(self):
        span = AgentSpan(name="test.span")
        span.set_status("error")
        assert span.status == "error"

    def test_set_status_custom_value(self):
        span = AgentSpan(name="test.span")
        span.set_status("warning")
        assert span.status == "warning"

    def test_end_sets_end_time(self):
        span = AgentSpan(name="test.span")
        span.end()
        assert span.end_time is not None
        assert span.end_time >= span.start_time

    def test_duration_ms_before_end(self):
        span = AgentSpan(name="test.span")
        # Before calling end(), duration_ms should compute using current time
        duration = span.duration_ms
        assert duration >= 0

    def test_duration_ms_after_end(self):
        span = AgentSpan(name="test.span")
        time.sleep(0.01)  # 10ms
        span.end()
        duration = span.duration_ms
        assert duration >= 5  # At least 5ms given sleep
        # After end, repeated calls should return same value
        duration2 = span.duration_ms
        assert duration == duration2

    def test_duration_ms_returns_float(self):
        span = AgentSpan(name="test.span")
        span.end()
        assert isinstance(span.duration_ms, float)

    def test_attributes_none_becomes_empty_dict(self):
        span = AgentSpan(name="test.span", attributes=None)
        assert span.attributes == {}


# ===========================================================================
# AgentTracer Tests (no OTEL / fallback path)
# ===========================================================================


class TestAgentTracerInit:
    """Tests for AgentTracer initialization."""

    def test_default_config_when_none(self):
        tracer = AgentTracer()
        assert tracer.config.enabled is False
        assert tracer.config.service_name == "shieldops-agents"

    def test_custom_config(self):
        config = TracingConfig(enabled=False, service_name="custom")
        tracer = AgentTracer(config=config)
        assert tracer.config.service_name == "custom"

    def test_tracer_is_none_when_disabled(self):
        tracer = AgentTracer(config=TracingConfig(enabled=False))
        assert tracer._tracer is None

    def test_recorded_spans_initially_empty(self):
        tracer = AgentTracer()
        assert tracer.recorded_spans == []

    def test_clear_empties_spans(self):
        tracer = AgentTracer()
        # Manually append to test clear
        tracer._spans.append(AgentSpan(name="dummy"))
        assert len(tracer.recorded_spans) == 1
        tracer.clear()
        assert tracer.recorded_spans == []

    def test_recorded_spans_returns_copy(self):
        tracer = AgentTracer()
        tracer._spans.append(AgentSpan(name="dummy"))
        spans = tracer.recorded_spans
        spans.clear()
        # Internal list should be unaffected
        assert len(tracer.recorded_spans) == 1


class TestAgentTracerStartAgentSpan:
    """Tests for AgentTracer.start_agent_span async context manager."""

    @pytest.mark.asyncio
    async def test_start_agent_span_yields_span(self):
        tracer = AgentTracer()
        async with tracer.start_agent_span("investigation", agent_id="inv-1") as span:
            assert isinstance(span, AgentSpan)

    @pytest.mark.asyncio
    async def test_start_agent_span_name_format(self):
        tracer = AgentTracer()
        async with tracer.start_agent_span("remediation") as span:
            assert span.name == "agent.remediation"

    @pytest.mark.asyncio
    async def test_start_agent_span_sets_agent_type_attribute(self):
        tracer = AgentTracer()
        async with tracer.start_agent_span("security") as span:
            assert span.attributes[SpanAttributes.AGENT_TYPE] == "security"

    @pytest.mark.asyncio
    async def test_start_agent_span_sets_agent_id_attribute(self):
        tracer = AgentTracer()
        async with tracer.start_agent_span("investigation", agent_id="inv-abc") as span:
            assert span.attributes[SpanAttributes.AGENT_ID] == "inv-abc"

    @pytest.mark.asyncio
    async def test_start_agent_span_sets_correlation_id(self):
        tracer = AgentTracer()
        async with tracer.start_agent_span("investigation", correlation_id="corr-xyz") as span:
            assert span.attributes[SpanAttributes.CORRELATION_ID] == "corr-xyz"

    @pytest.mark.asyncio
    async def test_start_agent_span_extra_attributes(self):
        tracer = AgentTracer()
        async with tracer.start_agent_span(
            "investigation",
            custom_key="custom_value",
        ) as span:
            assert span.attributes["custom_key"] == "custom_value"

    @pytest.mark.asyncio
    async def test_start_agent_span_records_after_exit(self):
        tracer = AgentTracer()
        async with tracer.start_agent_span("investigation"):
            pass
        assert len(tracer.recorded_spans) == 1
        assert tracer.recorded_spans[0].name == "agent.investigation"

    @pytest.mark.asyncio
    async def test_start_agent_span_ends_span(self):
        tracer = AgentTracer()
        async with tracer.start_agent_span("investigation") as span:
            pass
        assert span.end_time is not None

    @pytest.mark.asyncio
    async def test_start_agent_span_status_ok_on_success(self):
        tracer = AgentTracer()
        async with tracer.start_agent_span("investigation") as span:
            pass
        assert span.status == "ok"

    @pytest.mark.asyncio
    async def test_start_agent_span_status_error_on_exception(self):
        tracer = AgentTracer()
        with pytest.raises(ValueError, match="boom"):
            async with tracer.start_agent_span("investigation") as span:
                raise ValueError("boom")
        assert span.status == "error"

    @pytest.mark.asyncio
    async def test_start_agent_span_records_span_on_exception(self):
        tracer = AgentTracer()
        with pytest.raises(RuntimeError):
            async with tracer.start_agent_span("investigation"):
                raise RuntimeError("fail")
        assert len(tracer.recorded_spans) == 1

    @pytest.mark.asyncio
    async def test_start_agent_span_re_raises_exception(self):
        tracer = AgentTracer()
        with pytest.raises(TypeError, match="bad type"):
            async with tracer.start_agent_span("investigation"):
                raise TypeError("bad type")

    @pytest.mark.asyncio
    async def test_multiple_agent_spans_recorded(self):
        tracer = AgentTracer()
        async with tracer.start_agent_span("investigation"):
            pass
        async with tracer.start_agent_span("remediation"):
            pass
        assert len(tracer.recorded_spans) == 2
        names = [s.name for s in tracer.recorded_spans]
        assert names == ["agent.investigation", "agent.remediation"]


class TestAgentTracerStartNodeSpan:
    """Tests for AgentTracer.start_node_span sync context manager."""

    def test_start_node_span_yields_span(self):
        tracer = AgentTracer()
        with tracer.start_node_span("gather_context") as span:
            assert isinstance(span, AgentSpan)

    def test_start_node_span_name_format(self):
        tracer = AgentTracer()
        with tracer.start_node_span("evaluate") as span:
            assert span.name == "node.evaluate"

    def test_start_node_span_sets_node_name_attribute(self):
        tracer = AgentTracer()
        with tracer.start_node_span("gather_context") as span:
            assert span.attributes[SpanAttributes.NODE_NAME] == "gather_context"

    def test_start_node_span_sets_agent_type(self):
        tracer = AgentTracer()
        with tracer.start_node_span("gather", agent_type="investigation") as span:
            assert span.attributes[SpanAttributes.AGENT_TYPE] == "investigation"

    def test_start_node_span_extra_attrs(self):
        tracer = AgentTracer()
        with tracer.start_node_span("gather", extra="val") as span:
            assert span.attributes["extra"] == "val"

    def test_start_node_span_records_after_exit(self):
        tracer = AgentTracer()
        with tracer.start_node_span("step"):
            pass
        assert len(tracer.recorded_spans) == 1

    def test_start_node_span_ends_span(self):
        tracer = AgentTracer()
        with tracer.start_node_span("step") as span:
            pass
        assert span.end_time is not None

    def test_start_node_span_status_ok_on_success(self):
        tracer = AgentTracer()
        with tracer.start_node_span("step") as span:
            pass
        assert span.status == "ok"

    def test_start_node_span_status_error_on_exception(self):
        tracer = AgentTracer()
        with pytest.raises(ValueError), tracer.start_node_span("step") as span:
            raise ValueError("fail")
        assert span.status == "error"

    def test_start_node_span_re_raises_exception(self):
        tracer = AgentTracer()
        with pytest.raises(RuntimeError, match="sync fail"), tracer.start_node_span("step"):
            raise RuntimeError("sync fail")

    def test_start_node_span_records_span_on_exception(self):
        tracer = AgentTracer()
        with pytest.raises(RuntimeError), tracer.start_node_span("step"):
            raise RuntimeError("fail")
        assert len(tracer.recorded_spans) == 1


# ===========================================================================
# traced_node Decorator Tests (AgentTracer path)
# ===========================================================================


class TestTracedNodeAsyncWithTracer:
    """Tests for traced_node decorator wrapping async functions via AgentTracer."""

    @pytest.mark.asyncio
    async def test_async_decorated_function_returns_result(self):
        tracer = AgentTracer()

        @traced_node("my_node", agent_type="test", tracer=tracer)
        async def my_node(state):
            return {"result": "ok"}

        result = await my_node({"input": "data"})
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_async_decorated_creates_span(self):
        tracer = AgentTracer()

        @traced_node("my_node", agent_type="test", tracer=tracer)
        async def my_node(state):
            return {}

        await my_node({})
        assert len(tracer.recorded_spans) == 1
        assert tracer.recorded_spans[0].name == "node.my_node"

    @pytest.mark.asyncio
    async def test_async_decorated_extracts_confidence(self):
        tracer = AgentTracer()

        @traced_node("my_node", tracer=tracer)
        async def my_node(state):
            return {"confidence": 0.95}

        await my_node({})
        span = tracer.recorded_spans[0]
        assert span.attributes[SpanAttributes.CONFIDENCE] == 0.95

    @pytest.mark.asyncio
    async def test_async_decorated_no_confidence_when_missing(self):
        tracer = AgentTracer()

        @traced_node("my_node", tracer=tracer)
        async def my_node(state):
            return {"other": "data"}

        await my_node({})
        span = tracer.recorded_spans[0]
        assert SpanAttributes.CONFIDENCE not in span.attributes

    @pytest.mark.asyncio
    async def test_async_decorated_no_confidence_for_non_dict(self):
        tracer = AgentTracer()

        @traced_node("my_node", tracer=tracer)
        async def my_node(state):
            return "string_result"

        await my_node({})
        span = tracer.recorded_spans[0]
        assert SpanAttributes.CONFIDENCE not in span.attributes

    @pytest.mark.asyncio
    async def test_async_decorated_propagates_exception(self):
        tracer = AgentTracer()

        @traced_node("failing_node", tracer=tracer)
        async def failing_node(state):
            raise ValueError("async boom")

        with pytest.raises(ValueError, match="async boom"):
            await failing_node({})

    @pytest.mark.asyncio
    async def test_async_decorated_records_span_on_exception(self):
        tracer = AgentTracer()

        @traced_node("failing_node", tracer=tracer)
        async def failing_node(state):
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await failing_node({})

        assert len(tracer.recorded_spans) == 1

    @pytest.mark.asyncio
    async def test_async_decorated_preserves_func_name(self):
        tracer = AgentTracer()

        @traced_node("my_node", tracer=tracer)
        async def original_name(state):
            return {}

        assert original_name.__name__ == "original_name"

    @pytest.mark.asyncio
    async def test_async_decorated_confidence_none_not_set(self):
        tracer = AgentTracer()

        @traced_node("my_node", tracer=tracer)
        async def my_node(state):
            return {"confidence": None}

        await my_node({})
        span = tracer.recorded_spans[0]
        assert SpanAttributes.CONFIDENCE not in span.attributes


class TestTracedNodeSyncWithTracer:
    """Tests for traced_node decorator wrapping sync functions via AgentTracer."""

    def test_sync_decorated_function_returns_result(self):
        tracer = AgentTracer()

        @traced_node("sync_node", agent_type="test", tracer=tracer)
        def sync_node(state):
            return {"status": "done"}

        result = sync_node({})
        assert result == {"status": "done"}

    def test_sync_decorated_creates_span(self):
        tracer = AgentTracer()

        @traced_node("sync_node", tracer=tracer)
        def sync_node(state):
            return {}

        sync_node({})
        assert len(tracer.recorded_spans) == 1
        assert tracer.recorded_spans[0].name == "node.sync_node"

    def test_sync_decorated_extracts_confidence(self):
        tracer = AgentTracer()

        @traced_node("sync_node", tracer=tracer)
        def sync_node(state):
            return {"confidence": 0.88}

        sync_node({})
        span = tracer.recorded_spans[0]
        assert span.attributes[SpanAttributes.CONFIDENCE] == 0.88

    def test_sync_decorated_no_confidence_when_missing(self):
        tracer = AgentTracer()

        @traced_node("sync_node", tracer=tracer)
        def sync_node(state):
            return {"other": "data"}

        sync_node({})
        span = tracer.recorded_spans[0]
        assert SpanAttributes.CONFIDENCE not in span.attributes

    def test_sync_decorated_propagates_exception(self):
        tracer = AgentTracer()

        @traced_node("sync_fail", tracer=tracer)
        def sync_fail(state):
            raise RuntimeError("sync boom")

        with pytest.raises(RuntimeError, match="sync boom"):
            sync_fail({})

    def test_sync_decorated_records_span_on_exception(self):
        tracer = AgentTracer()

        @traced_node("sync_fail", tracer=tracer)
        def sync_fail(state):
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            sync_fail({})

        assert len(tracer.recorded_spans) == 1

    def test_sync_decorated_preserves_func_name(self):
        tracer = AgentTracer()

        @traced_node("sync_node", tracer=tracer)
        def original_sync(state):
            return {}

        assert original_sync.__name__ == "original_sync"

    def test_sync_decorated_confidence_none_not_set(self):
        tracer = AgentTracer()

        @traced_node("sync_node", tracer=tracer)
        def sync_node(state):
            return {"confidence": None}

        sync_node({})
        span = tracer.recorded_spans[0]
        assert SpanAttributes.CONFIDENCE not in span.attributes


class TestTracedNodeWithoutTracer:
    """Tests for traced_node without an AgentTracer (fallback / no-op path)."""

    @pytest.mark.asyncio
    async def test_async_no_tracer_returns_result(self):
        @traced_node("node_no_tracer")
        async def my_node(state):
            return {"key": "value"}

        result = await my_node({})
        assert result == {"key": "value"}

    def test_sync_no_tracer_returns_result(self):
        @traced_node("sync_no_tracer")
        def my_node(state):
            return {"key": "value"}

        result = my_node({})
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_async_no_tracer_propagates_exception(self):
        @traced_node("fail_node")
        async def fail_node(state):
            raise ValueError("no tracer boom")

        with pytest.raises(ValueError, match="no tracer boom"):
            await fail_node({})

    def test_sync_no_tracer_propagates_exception(self):
        @traced_node("fail_node")
        def fail_node(state):
            raise ValueError("no tracer sync boom")

        with pytest.raises(ValueError, match="no tracer sync boom"):
            fail_node({})
