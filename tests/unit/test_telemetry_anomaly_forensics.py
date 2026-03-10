"""Tests for TelemetryAnomalyForensics."""

from __future__ import annotations

from shieldops.observability.telemetry_anomaly_forensics import (
    AnomalyOrigin,
    EvidenceType,
    ForensicDepth,
    TelemetryAnomalyForensics,
)


def _engine(**kw) -> TelemetryAnomalyForensics:
    return TelemetryAnomalyForensics(**kw)


class TestEnums:
    def test_anomaly_origin(self):
        assert AnomalyOrigin.INFRASTRUCTURE == "infrastructure"
        assert AnomalyOrigin.EXTERNAL == "external"

    def test_forensic_depth(self):
        assert ForensicDepth.SURFACE == "surface"
        assert ForensicDepth.EXHAUSTIVE == "exhaustive"

    def test_evidence_type(self):
        assert EvidenceType.METRIC_SPIKE == "metric_spike"
        assert EvidenceType.CONFIG_CHANGE == "config_change"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="a-1", service="api")
        assert rec.name == "a-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"a-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="a-1", score=45.0)
        result = eng.process("a-1")
        assert result["key"] == "a-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(name="a1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.add_record(name="a1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(name="a1", service="api")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestTraceAnomalyOrigin:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="a1",
            origin=AnomalyOrigin.NETWORK,
            severity=80.0,
            confidence=0.9,
        )
        result = eng.trace_anomaly_origin()
        assert isinstance(result, dict)
        assert "network" in result

    def test_empty(self):
        eng = _engine()
        result = eng.trace_anomaly_origin()
        assert result["status"] == "no_data"


class TestCorrelateEvidenceChain:
    def test_basic(self):
        eng = _engine()
        eng.add_record(name="a1", service="api")
        eng.add_record(name="a2", service="api")
        result = eng.correlate_evidence_chain()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_single_record(self):
        eng = _engine()
        eng.add_record(name="a1", service="api")
        result = eng.correlate_evidence_chain()
        assert len(result) == 0


class TestGenerateForensicTimeline:
    def test_basic(self):
        eng = _engine()
        eng.add_record(name="a1", service="api")
        result = eng.generate_forensic_timeline(service="api")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_empty(self):
        eng = _engine()
        result = eng.generate_forensic_timeline()
        assert len(result) == 0
