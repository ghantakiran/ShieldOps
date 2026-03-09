"""Tests for shieldops.analytics.platform_observability_score — PlatformObservabilityScore."""

from __future__ import annotations

from shieldops.analytics.platform_observability_score import (
    GapSeverity,
    MaturityLevel,
    ObservabilityPillar,
    ObservabilityScoreRecord,
    PlatformObservabilityScore,
)


def _engine(**kw) -> PlatformObservabilityScore:
    return PlatformObservabilityScore(**kw)


class TestEnums:
    def test_pillar_metrics(self):
        assert ObservabilityPillar.METRICS == "metrics"

    def test_maturity_advanced(self):
        assert MaturityLevel.ADVANCED == "advanced"

    def test_gap_severity(self):
        assert GapSeverity.CRITICAL == "critical"


class TestModels:
    def test_record_defaults(self):
        r = ObservabilityScoreRecord()
        assert r.id
        assert r.created_at > 0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(
            service="api-gw",
            pillar=ObservabilityPillar.METRICS,
            coverage_pct=85.0,
        )
        assert rec.service == "api-gw"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(
                service=f"svc-{i}", pillar=ObservabilityPillar.LOGS, coverage_pct=float(i * 10)
            )
        assert len(eng._records) == 3


class TestServiceScore:
    def test_basic(self):
        eng = _engine()
        eng.add_record(service="api", pillar=ObservabilityPillar.METRICS, coverage_pct=90.0)
        eng.add_record(service="api", pillar=ObservabilityPillar.LOGS, coverage_pct=70.0)
        result = eng.compute_service_score("api")
        assert isinstance(result, dict)


class TestPillarBenchmark:
    def test_basic(self):
        eng = _engine()
        eng.add_record(service="api", pillar=ObservabilityPillar.METRICS, coverage_pct=90.0)
        result = eng.compute_pillar_benchmark()
        assert isinstance(result, dict)


class TestRoadmap:
    def test_basic(self):
        eng = _engine()
        eng.add_record(service="api", pillar=ObservabilityPillar.METRICS, coverage_pct=40.0)
        result = eng.generate_roadmap("api")
        assert isinstance(result, list)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(service="api", pillar=ObservabilityPillar.TRACES, coverage_pct=80.0)
        result = eng.process("api")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(service="api", pillar=ObservabilityPillar.METRICS, coverage_pct=80.0)
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(service="api", pillar=ObservabilityPillar.METRICS, coverage_pct=80.0)
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(service="api", pillar=ObservabilityPillar.METRICS, coverage_pct=80.0)
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
