"""Unit tests for agent-level OTEL tracing (traced_node decorator)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

from shieldops.agents.tracing import traced_node


class _InMemoryExporter(SpanExporter):
    """Collect finished spans in a list for test assertions."""

    def __init__(self) -> None:
        self._spans: list[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 0) -> bool:
        return True

    def get_finished_spans(self) -> list[ReadableSpan]:
        return list(self._spans)

    def clear(self) -> None:
        self._spans.clear()


def _force_set_tracer_provider(provider: TracerProvider) -> None:
    """Force-set the global tracer provider, bypassing the do_once guard.

    Only for use in tests — resets the internal _TRACER_PROVIDER global.
    """
    import opentelemetry.trace as _mod

    _mod._TRACER_PROVIDER = provider  # type: ignore[attr-defined]
    _mod._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]
    trace.set_tracer_provider(provider)


@pytest.fixture()
def tracing_setup():
    """Set up a TracerProvider with an in-memory exporter."""
    exporter = _InMemoryExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    _force_set_tracer_provider(provider)
    yield exporter
    provider.shutdown()


class TestTracedNodeAsync:
    @pytest.mark.asyncio
    async def test_creates_span_with_correct_name(self, tracing_setup):
        exporter = tracing_setup

        @traced_node("test.my_node", agent_type="test")
        async def my_node(state):
            return {"result": "ok"}

        await my_node({"input": "data"})

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test.my_node"

    @pytest.mark.asyncio
    async def test_sets_agent_attributes(self, tracing_setup):
        exporter = tracing_setup

        @traced_node("investigation.gather_context", agent_type="investigation")
        async def gather(state):
            return {}

        await gather({})

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes)
        assert attrs["agent.node.name"] == "investigation.gather_context"
        assert attrs["agent.type"] == "investigation"

    @pytest.mark.asyncio
    async def test_records_duration_ms(self, tracing_setup):
        exporter = tracing_setup

        @traced_node("test.timed_node")
        async def timed_node(state):
            return {}

        await timed_node({})

        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert "agent.node.duration_ms" in attrs
        assert attrs["agent.node.duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_records_exceptions(self, tracing_setup):
        exporter = tracing_setup

        @traced_node("test.failing_node")
        async def failing_node(state):
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await failing_node({})

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.ERROR
        events = spans[0].events
        assert any(e.name == "exception" for e in events)

    @pytest.mark.asyncio
    async def test_preserves_return_value(self, tracing_setup):
        @traced_node("test.returning_node")
        async def returning_node(state):
            return {"key": "value", "count": 42}

        result = await returning_node({})
        assert result == {"key": "value", "count": 42}


class TestTracedNodeSync:
    def test_sync_node_creates_span(self, tracing_setup):
        exporter = tracing_setup

        @traced_node("test.sync_node", agent_type="sync_test")
        def sync_node(state):
            return {"ok": True}

        result = sync_node({})
        assert result == {"ok": True}

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test.sync_node"

    def test_sync_node_records_exception(self, tracing_setup):
        exporter = tracing_setup

        @traced_node("test.sync_fail")
        def sync_fail(state):
            raise RuntimeError("sync error")

        with pytest.raises(RuntimeError, match="sync error"):
            sync_fail({})

        spans = exporter.get_finished_spans()
        assert spans[0].status.status_code == trace.StatusCode.ERROR


class TestInvestigationRunnerSpan:
    @pytest.mark.asyncio
    async def test_investigation_runner_creates_root_span(self, tracing_setup):
        """Verify InvestigationRunner.investigate() creates a root span."""
        exporter = tracing_setup

        from shieldops.observability.tracing import get_tracer

        tracer = get_tracer("shieldops.agents")
        with tracer.start_as_current_span("investigation.run") as span:
            span.set_attribute("investigation.id", "inv-test123")
            span.set_attribute("investigation.alert_id", "alert-abc")
            span.set_attribute("investigation.alert_name", "HighCPU")
            span.set_attribute("investigation.severity", "critical")

        spans = exporter.get_finished_spans()
        root = [s for s in spans if s.name == "investigation.run"]
        assert len(root) == 1
        attrs = dict(root[0].attributes)
        assert attrs["investigation.id"] == "inv-test123"
        assert attrs["investigation.alert_name"] == "HighCPU"


class TestRemediationRunnerSpan:
    @pytest.mark.asyncio
    async def test_remediation_runner_creates_root_span(self, tracing_setup):
        """Verify RemediationRunner.remediate() creates a root span."""
        exporter = tracing_setup

        from shieldops.observability.tracing import get_tracer

        tracer = get_tracer("shieldops.agents")
        with tracer.start_as_current_span("remediation.run") as span:
            span.set_attribute("remediation.id", "rem-test456")
            span.set_attribute("remediation.action_type", "restart_ec2")
            span.set_attribute("remediation.target_resource", "i-abc123")
            span.set_attribute("remediation.risk_level", "medium")

        spans = exporter.get_finished_spans()
        root = [s for s in spans if s.name == "remediation.run"]
        assert len(root) == 1
        attrs = dict(root[0].attributes)
        assert attrs["remediation.action_type"] == "restart_ec2"
        assert attrs["remediation.target_resource"] == "i-abc123"
