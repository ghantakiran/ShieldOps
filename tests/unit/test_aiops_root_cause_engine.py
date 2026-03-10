"""Tests for AIOpsRootCauseEngine."""

from __future__ import annotations

from shieldops.analytics.aiops_root_cause_engine import (
    AIOpsRootCauseEngine,
    ConfidenceLevel,
    CorrelationMethod,
    RootCauseType,
)


def _engine(**kw) -> AIOpsRootCauseEngine:
    return AIOpsRootCauseEngine(**kw)


class TestEnums:
    def test_root_cause_type(self):
        assert RootCauseType.INFRASTRUCTURE == "infrastructure"

    def test_correlation_method(self):
        assert CorrelationMethod.TEMPORAL == "temporal"

    def test_confidence_level(self):
        assert ConfidenceLevel.HIGH == "high"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(incident_id="inc-1", service="api")
        assert rec.incident_id == "inc-1"
        assert rec.service == "api"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(
                incident_id=f"inc-{i}",
                service="svc",
            )
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(incident_id="inc-1", service="api")
        result = eng.process("inc-1")
        assert isinstance(result, dict)
        assert result["incident_id"] == "inc-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestIdentifyProbableCauses:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            incident_id="inc-1",
            service="api",
            confidence_score=0.9,
        )
        result = eng.identify_probable_causes("inc-1")
        assert isinstance(result, list)


class TestBuildCausalGraph:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            incident_id="inc-1",
            service="api",
            signal_type="cpu",
        )
        result = eng.build_causal_graph("api")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(incident_id="inc-1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(incident_id="inc-1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(incident_id="inc-1", service="api")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0
