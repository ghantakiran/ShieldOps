"""Tests for ServiceReliabilityScorer."""

from __future__ import annotations

from shieldops.sla.service_reliability_scorer import (
    MetricType,
    ReliabilityTier,
    ScoringModel,
    ServiceReliabilityScorer,
)


def _engine(**kw) -> ServiceReliabilityScorer:
    return ServiceReliabilityScorer(**kw)


class TestEnums:
    def test_reliability_tier_values(self):
        for v in ReliabilityTier:
            assert isinstance(v.value, str)

    def test_metric_type_values(self):
        for v in MetricType:
            assert isinstance(v.value, str)

    def test_scoring_model_values(self):
        for v in ScoringModel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(service_id="s1")
        assert r.service_id == "s1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(service_id=f"s-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.add_record(
            service_id="s1",
            reliability_tier=ReliabilityTier.PLATINUM,
            metric_type=MetricType.LATENCY,
            scoring_model=ScoringModel.ADAPTIVE,
            score=99.5,
            threshold=99.0,
            region="us-east-1",
        )
        assert r.score == 99.5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(service_id="s1", score=99.5)
        a = eng.process(r.id)
        assert hasattr(a, "service_id")
        assert a.service_id == "s1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_degradation_detected(self):
        eng = _engine()
        r = eng.add_record(service_id="s1", score=95.0, threshold=99.0)
        a = eng.process(r.id)
        assert a.degradation_detected is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeCompositeReliabilityScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(service_id="s1", score=99.5)
        result = eng.compute_composite_reliability_score()
        assert len(result) == 1
        assert result[0]["service_id"] == "s1"

    def test_empty(self):
        assert _engine().compute_composite_reliability_score() == []


class TestDetectReliabilityDegradation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(service_id="s1", score=95.0, threshold=99.0)
        result = eng.detect_reliability_degradation()
        assert len(result) == 1
        assert result[0]["gap"] == 4.0

    def test_empty(self):
        assert _engine().detect_reliability_degradation() == []


class TestRankServicesByReliability:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(service_id="s1", score=99.5)
        eng.add_record(service_id="s2", score=95.0)
        result = eng.rank_services_by_reliability()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_services_by_reliability() == []
