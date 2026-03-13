"""Tests for ApiHealthCompositeScorer."""

from __future__ import annotations

from shieldops.topology.api_health_composite_scorer import (
    ApiHealthCompositeScorer,
    BenchmarkScope,
    HealthGrade,
    SignalType,
)


def _engine(**kw) -> ApiHealthCompositeScorer:
    return ApiHealthCompositeScorer(**kw)


class TestEnums:
    def test_health_grade_values(self):
        for v in HealthGrade:
            assert isinstance(v.value, str)

    def test_signal_type_values(self):
        for v in SignalType:
            assert isinstance(v.value, str)

    def test_benchmark_scope_values(self):
        for v in BenchmarkScope:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(endpoint="/api/v1")
        assert r.endpoint == "/api/v1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(endpoint=f"/ep-{i}")
        assert len(eng._records) == 5

    def test_all_fields(self):
        eng = _engine()
        r = eng.record_item(
            endpoint="/health",
            service="svc-a",
            health_grade=HealthGrade.POOR,
            signal_type=SignalType.ERROR_RATE,
            benchmark_scope=BenchmarkScope.TEAM,
            score=45.0,
        )
        assert r.health_grade == HealthGrade.POOR
        assert r.score == 45.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(endpoint="/api", score=80.0)
        a = eng.process(r.id)
        assert hasattr(a, "endpoint")
        assert a.composite_score == 80.0

    def test_degraded(self):
        eng = _engine()
        r = eng.record_item(
            endpoint="/api",
            health_grade=HealthGrade.POOR,
        )
        a = eng.process(r.id)
        assert a.degraded is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(endpoint="/api")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_degraded_endpoints(self):
        eng = _engine()
        eng.record_item(
            endpoint="/bad",
            health_grade=HealthGrade.POOR,
        )
        rpt = eng.generate_report()
        assert len(rpt.degraded_endpoints) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(endpoint="/api")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(endpoint="/api")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeCompositeHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(endpoint="/api", score=90.0)
        result = eng.compute_composite_health()
        assert len(result) == 1
        assert result[0]["composite_score"] == 90.0

    def test_empty(self):
        assert _engine().compute_composite_health() == []


class TestIdentifyDegradedEndpoints:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            endpoint="/bad",
            health_grade=HealthGrade.POOR,
            score=20.0,
        )
        result = eng.identify_degraded_endpoints()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().identify_degraded_endpoints() == []


class TestBenchmarkApiHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            endpoint="/api",
            benchmark_scope=BenchmarkScope.TEAM,
            score=85.0,
        )
        result = eng.benchmark_api_health()
        assert len(result) == 1
        assert result[0]["scope"] == "team"

    def test_empty(self):
        assert _engine().benchmark_api_health() == []
