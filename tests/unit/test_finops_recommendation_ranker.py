"""Tests for FinopsRecommendationRanker."""

from __future__ import annotations

from shieldops.analytics.finops_recommendation_ranker import (
    AdoptionStatus,
    FinopsRecommendationRanker,
    RecommendationType,
    RiskLevel,
)


def _engine(**kw) -> FinopsRecommendationRanker:
    return FinopsRecommendationRanker(**kw)


class TestEnums:
    def test_recommendation_type_values(self):
        for v in RecommendationType:
            assert isinstance(v.value, str)

    def test_risk_level_values(self):
        for v in RiskLevel:
            assert isinstance(v.value, str)

    def test_adoption_status_values(self):
        for v in AdoptionStatus:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(recommendation_id="r1")
        assert r.recommendation_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(recommendation_id=f"r-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            recommendation_id="r1",
            estimated_savings=1000,
            effort_hours=10,
        )
        a = eng.process(r.id)
        assert a.roi_score == 100.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_zero_effort(self):
        eng = _engine()
        r = eng.add_record(effort_hours=0)
        a = eng.process(r.id)
        assert a.roi_score == 0.0


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(estimated_savings=500)
        rpt = eng.generate_report()
        assert rpt.total_estimated_savings == 500.0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_deferred_recommendation(self):
        eng = _engine()
        eng.add_record(adoption_status=AdoptionStatus.DEFERRED)
        rpt = eng.generate_report()
        assert any("deferred" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(recommendation_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestRankByRoiAdjustedEffort:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            recommendation_id="r1",
            estimated_savings=1000,
            effort_hours=5,
        )
        eng.add_record(
            recommendation_id="r2",
            estimated_savings=500,
            effort_hours=10,
        )
        result = eng.rank_by_roi_adjusted_effort()
        assert result[0]["rank"] == 1
        assert result[0]["roi_score"] == 200.0

    def test_empty(self):
        assert _engine().rank_by_roi_adjusted_effort() == []


class TestAssessRecommendationRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            risk_level=RiskLevel.HIGH,
            estimated_savings=1000,
        )
        result = eng.assess_recommendation_risk()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().assess_recommendation_risk() == []


class TestTrackRecommendationAdoption:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            adoption_status=AdoptionStatus.IMPLEMENTED,
            estimated_savings=500,
        )
        result = eng.track_recommendation_adoption()
        assert len(result) == 1
        assert result[0]["status"] == "implemented"

    def test_empty(self):
        assert _engine().track_recommendation_adoption() == []
