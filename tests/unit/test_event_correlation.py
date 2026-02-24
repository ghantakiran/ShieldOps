"""Tests for shieldops.analytics.event_correlation — EventCorrelationEngine."""

from __future__ import annotations

import time

from shieldops.analytics.event_correlation import (
    CausalChain,
    CausalityConfidence,
    CorrelationEvent,
    CorrelationReport,
    CorrelationStrategy,
    EventCorrelationEngine,
    EventSource,
)


def _engine(**kw) -> EventCorrelationEngine:
    return EventCorrelationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_source_metrics(self):
        assert EventSource.METRICS == "metrics"

    def test_source_logs(self):
        assert EventSource.LOGS == "logs"

    def test_source_traces(self):
        assert EventSource.TRACES == "traces"

    def test_source_kubernetes(self):
        assert EventSource.KUBERNETES == "kubernetes"

    def test_source_deployment(self):
        assert EventSource.DEPLOYMENT == "deployment"

    def test_source_dns(self):
        assert EventSource.DNS == "dns"

    def test_source_network(self):
        assert EventSource.NETWORK == "network"

    def test_source_manual(self):
        assert EventSource.MANUAL == "manual"

    def test_confidence_definite(self):
        assert CausalityConfidence.DEFINITE == "definite"

    def test_confidence_probable(self):
        assert CausalityConfidence.PROBABLE == "probable"

    def test_confidence_possible(self):
        assert CausalityConfidence.POSSIBLE == "possible"

    def test_confidence_unlikely(self):
        assert CausalityConfidence.UNLIKELY == "unlikely"

    def test_confidence_unknown(self):
        assert CausalityConfidence.UNKNOWN == "unknown"

    def test_strategy_temporal(self):
        assert CorrelationStrategy.TEMPORAL == "temporal"

    def test_strategy_causal(self):
        assert CorrelationStrategy.CAUSAL == "causal"

    def test_strategy_topological(self):
        assert CorrelationStrategy.TOPOLOGICAL == "topological"

    def test_strategy_hybrid(self):
        assert CorrelationStrategy.HYBRID == "hybrid"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_event_defaults(self):
        e = CorrelationEvent()
        assert e.id
        assert e.source == EventSource.METRICS
        assert e.severity == "info"

    def test_chain_defaults(self):
        c = CausalChain()
        assert c.confidence == CausalityConfidence.UNKNOWN
        assert c.chain == []

    def test_report_defaults(self):
        r = CorrelationReport()
        assert r.events_analyzed == 0
        assert r.causal_chains == []


# ---------------------------------------------------------------------------
# submit_event
# ---------------------------------------------------------------------------


class TestSubmitEvent:
    def test_basic_submit(self):
        eng = _engine()
        event = eng.submit_event(service="svc-a", event_type="cpu_spike")
        assert event.service == "svc-a"
        assert event.event_type == "cpu_spike"

    def test_unique_ids(self):
        eng = _engine()
        e1 = eng.submit_event(service="svc-a")
        e2 = eng.submit_event(service="svc-b")
        assert e1.id != e2.id

    def test_eviction_at_max(self):
        eng = _engine(max_events=3)
        for i in range(5):
            eng.submit_event(service=f"svc-{i}")
        assert len(eng._events) == 3

    def test_with_tags(self):
        eng = _engine()
        event = eng.submit_event(service="svc-a", tags={"env": "prod"})
        assert event.tags == {"env": "prod"}


# ---------------------------------------------------------------------------
# get_event / list_events
# ---------------------------------------------------------------------------


class TestGetEvent:
    def test_found(self):
        eng = _engine()
        event = eng.submit_event(service="svc-a")
        assert eng.get_event(event.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_event("nonexistent") is None


class TestListEvents:
    def test_list_all(self):
        eng = _engine()
        eng.submit_event(service="svc-a")
        eng.submit_event(service="svc-b")
        assert len(eng.list_events()) == 2

    def test_filter_by_source(self):
        eng = _engine()
        eng.submit_event(source=EventSource.METRICS)
        eng.submit_event(source=EventSource.LOGS)
        results = eng.list_events(source=EventSource.METRICS)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.submit_event(service="svc-a")
        eng.submit_event(service="svc-b")
        results = eng.list_events(service="svc-a")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# correlate_window
# ---------------------------------------------------------------------------


class TestCorrelateWindow:
    def test_empty_window(self):
        eng = _engine()
        report = eng.correlate_window(window_start=0, window_end=1)
        assert report.events_analyzed == 0

    def test_window_with_events(self):
        eng = _engine(window_minutes=60)
        now = time.time()
        eng.submit_event(service="svc-a", occurred_at=now - 10)
        eng.submit_event(service="svc-b", occurred_at=now - 5)
        report = eng.correlate_window(window_start=now - 60, window_end=now)
        assert report.events_analyzed == 2

    def test_causal_chain_built(self):
        eng = _engine(window_minutes=60)
        now = time.time()
        # Close events should form a chain
        eng.submit_event(service="svc-a", occurred_at=now - 10)
        eng.submit_event(service="svc-b", occurred_at=now - 9)
        eng.submit_event(service="svc-c", occurred_at=now - 8)
        report = eng.correlate_window(window_start=now - 60, window_end=now)
        assert len(report.causal_chains) >= 1


# ---------------------------------------------------------------------------
# build_causal_chain / rank_root_causes
# ---------------------------------------------------------------------------


class TestBuildCausalChain:
    def test_basic_chain(self):
        eng = _engine()
        e1 = eng.submit_event(service="svc-a")
        e2 = eng.submit_event(service="svc-b")
        chain = eng.build_causal_chain([e1.id, e2.id])
        assert len(chain.chain) == 2
        assert chain.strategy == CorrelationStrategy.CAUSAL


class TestRankRootCauses:
    def test_ranking(self):
        eng = _engine(window_minutes=60)
        now = time.time()
        eng.submit_event(service="svc-a", occurred_at=now - 10)
        eng.submit_event(service="svc-b", occurred_at=now - 9)
        eng.correlate_window(window_start=now - 60, window_end=now)
        causes = eng.rank_root_causes()
        assert isinstance(causes, list)


# ---------------------------------------------------------------------------
# timeline / list_reports / clear / stats
# ---------------------------------------------------------------------------


class TestTimeline:
    def test_timeline(self):
        eng = _engine(window_minutes=60)
        eng.submit_event(service="svc-a")
        timeline = eng.get_timeline()
        assert len(timeline) >= 1

    def test_timeline_filter(self):
        eng = _engine(window_minutes=60)
        eng.submit_event(service="svc-a")
        eng.submit_event(service="svc-b")
        timeline = eng.get_timeline(service="svc-a")
        assert all(t["service"] == "svc-a" for t in timeline)


class TestListReports:
    def test_list(self):
        eng = _engine()
        eng.correlate_window()
        assert len(eng.list_reports()) >= 1


class TestClearEvents:
    def test_clear(self):
        eng = _engine()
        eng.submit_event(service="svc-a")
        count = eng.clear_events()
        assert count == 1
        assert len(eng._events) == 0


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_events"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.submit_event(source=EventSource.METRICS, service="svc-a")
        eng.submit_event(source=EventSource.LOGS, service="svc-b")
        stats = eng.get_stats()
        assert stats["total_events"] == 2
        assert stats["unique_services"] == 2
