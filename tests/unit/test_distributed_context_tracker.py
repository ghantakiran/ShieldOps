"""Tests for shieldops.observability.distributed_context_tracker — DistributedContextTracker."""

from __future__ import annotations

from shieldops.observability.distributed_context_tracker import (
    ComplianceLevel,
    ContextHealth,
    ContextRecord,
    DistributedContextTracker,
    PropagationFormat,
)


def _engine(**kw) -> DistributedContextTracker:
    return DistributedContextTracker(**kw)


class TestEnums:
    def test_format_w3c(self):
        assert PropagationFormat.W3C_TRACEPARENT == "w3c_traceparent"

    def test_health_valid(self):
        assert ContextHealth.VALID == "valid"

    def test_compliance(self):
        assert ComplianceLevel.COMPLIANT == "compliant"


class TestModels:
    def test_record_defaults(self):
        r = ContextRecord()
        assert r.id
        assert r.created_at > 0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(
            trace_id="t-1", span_id="s-1", source_service="api", target_service="db"
        )
        assert rec.trace_id == "t-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(
                trace_id=f"t-{i}",
                span_id=f"s-{i}",
                source_service=f"svc-{i}",
                target_service=f"tgt-{i}",
            )
        assert len(eng._records) == 3


class TestContextLeaks:
    def test_basic(self):
        eng = _engine()
        eng.add_record(trace_id="t-1", span_id="s-1", source_service="api", target_service="db")
        result = eng.detect_context_leaks()
        assert isinstance(result, list)


class TestBaggageValidation:
    def test_basic(self):
        eng = _engine()
        eng.add_record(trace_id="t-1", span_id="s-1", source_service="api", target_service="db")
        result = eng.validate_baggage()
        assert isinstance(result, dict)


class TestW3CCompliance:
    def test_basic(self):
        eng = _engine()
        eng.add_record(trace_id="t-1", span_id="s-1", source_service="api", target_service="db")
        result = eng.check_w3c_compliance()
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(trace_id="t-1", span_id="s-1", source_service="api", target_service="db")
        result = eng.process("api")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(trace_id="t-1", span_id="s-1", source_service="api", target_service="db")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(trace_id="t-1", span_id="s-1", source_service="api", target_service="db")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(trace_id="t-1", span_id="s-1", source_service="api", target_service="db")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
