"""Tests for shieldops.analytics.dynamic_risk_scorer — DynamicRiskScorer."""

from __future__ import annotations

from shieldops.analytics.dynamic_risk_scorer import (
    DynamicRiskReport,
    DynamicRiskScorer,
    RiskFactor,
    RiskScoreRecord,
    ScoreAdjustment,
    ScoreAdjustmentEvent,
    ScoringModel,
)


def _engine(**kw) -> DynamicRiskScorer:
    return DynamicRiskScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # RiskFactor (5)
    def test_factor_incident_frequency(self):
        assert RiskFactor.INCIDENT_FREQUENCY == "incident_frequency"

    def test_factor_deployment_velocity(self):
        assert RiskFactor.DEPLOYMENT_VELOCITY == "deployment_velocity"

    def test_factor_vulnerability_count(self):
        assert RiskFactor.VULNERABILITY_COUNT == "vulnerability_count"

    def test_factor_slo_burn_rate(self):
        assert RiskFactor.SLO_BURN_RATE == "slo_burn_rate"

    def test_factor_threat_level(self):
        assert RiskFactor.THREAT_LEVEL == "threat_level"

    # ScoreAdjustment (5)
    def test_adjustment_increase(self):
        assert ScoreAdjustment.INCREASE == "increase"

    def test_adjustment_decrease(self):
        assert ScoreAdjustment.DECREASE == "decrease"

    def test_adjustment_spike(self):
        assert ScoreAdjustment.SPIKE == "spike"

    def test_adjustment_decay(self):
        assert ScoreAdjustment.DECAY == "decay"

    def test_adjustment_stable(self):
        assert ScoreAdjustment.STABLE == "stable"

    # ScoringModel (5)
    def test_model_linear(self):
        assert ScoringModel.LINEAR == "linear"

    def test_model_exponential(self):
        assert ScoringModel.EXPONENTIAL == "exponential"

    def test_model_bayesian(self):
        assert ScoringModel.BAYESIAN == "bayesian"

    def test_model_ensemble(self):
        assert ScoringModel.ENSEMBLE == "ensemble"

    def test_model_custom(self):
        assert ScoringModel.CUSTOM == "custom"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_risk_score_record_defaults(self):
        r = RiskScoreRecord()
        assert r.id
        assert r.service_name == ""
        assert r.risk_factor == RiskFactor.INCIDENT_FREQUENCY
        assert r.score_adjustment == ScoreAdjustment.STABLE
        assert r.scoring_model == ScoringModel.LINEAR
        assert r.risk_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_score_adjustment_event_defaults(self):
        r = ScoreAdjustmentEvent()
        assert r.id
        assert r.event_label == ""
        assert r.risk_factor == RiskFactor.INCIDENT_FREQUENCY
        assert r.score_adjustment == ScoreAdjustment.INCREASE
        assert r.magnitude == 0.0
        assert r.created_at > 0

    def test_dynamic_risk_report_defaults(self):
        r = DynamicRiskReport()
        assert r.total_scores == 0
        assert r.total_adjustments == 0
        assert r.high_risk_rate_pct == 0.0
        assert r.by_factor == {}
        assert r.by_adjustment == {}
        assert r.spike_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_score
# -------------------------------------------------------------------


class TestRecordScore:
    def test_basic(self):
        eng = _engine()
        r = eng.record_score(
            "svc-a",
            risk_factor=RiskFactor.INCIDENT_FREQUENCY,
            score_adjustment=ScoreAdjustment.STABLE,
        )
        assert r.service_name == "svc-a"
        assert r.risk_factor == RiskFactor.INCIDENT_FREQUENCY

    def test_max_records_trim(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_score(f"svc-{i}")
        assert len(eng._records) == 3

    def test_get_by_id(self):
        eng = _engine()
        r = eng.record_score("svc-a")
        assert eng.get_score(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_score("nonexistent") is None

    def test_list_filter(self):
        eng = _engine()
        eng.record_score("svc-a")
        eng.record_score("svc-b")
        results = eng.list_scores(service_name="svc-a")
        assert len(results) == 1

    def test_list_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_score(f"svc-{i}")
        results = eng.list_scores(limit=3)
        assert len(results) == 3


# -------------------------------------------------------------------
# add_adjustment
# -------------------------------------------------------------------


class TestAddAdjustment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_adjustment(
            "adj-1",
            risk_factor=RiskFactor.INCIDENT_FREQUENCY,
            score_adjustment=ScoreAdjustment.INCREASE,
            magnitude=15.0,
        )
        assert a.event_label == "adj-1"
        assert a.magnitude == 15.0

    def test_trim(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_adjustment(f"adj-{i}")
        assert len(eng._adjustments) == 2


# -------------------------------------------------------------------
# analyze_risk_trajectory
# -------------------------------------------------------------------


class TestAnalyze:
    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_risk_trajectory("ghost")
        assert result["status"] == "no_data"

    def test_with_data(self):
        eng = _engine()
        eng.record_score("svc-a", risk_score=90.0)
        eng.record_score("svc-a", risk_score=10.0)
        result = eng.analyze_risk_trajectory("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_scores"] == 2
        assert result["avg_risk_score"] == 50.0

    def test_meets_threshold(self):
        eng = _engine(high_threshold=50.0)
        eng.record_score("svc-a", risk_score=80.0)
        result = eng.analyze_risk_trajectory("svc-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_high_risk_services
# -------------------------------------------------------------------


class TestIdentify:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_services() == []

    def test_with_matches(self):
        eng = _engine()
        eng.record_score("svc-a", score_adjustment=ScoreAdjustment.INCREASE)
        eng.record_score("svc-a", score_adjustment=ScoreAdjustment.SPIKE)
        eng.record_score("svc-b", score_adjustment=ScoreAdjustment.STABLE)
        results = eng.identify_high_risk_services()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"


# -------------------------------------------------------------------
# rank_by_risk_score
# -------------------------------------------------------------------


class TestRank:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []

    def test_ordering(self):
        eng = _engine()
        eng.record_score("svc-a")
        eng.record_score("svc-a")
        eng.record_score("svc-b")
        results = eng.rank_by_risk_score()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["score_count"] == 2


# -------------------------------------------------------------------
# detect_risk_spikes
# -------------------------------------------------------------------


class TestDetect:
    def test_empty(self):
        eng = _engine()
        assert eng.detect_risk_spikes() == []

    def test_detection(self):
        eng = _engine()
        for _ in range(5):
            eng.record_score("svc-a", score_adjustment=ScoreAdjustment.SPIKE)
        eng.record_score("svc-b", score_adjustment=ScoreAdjustment.STABLE)
        results = eng.detect_risk_spikes()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["spike_detected"] is True


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_scores == 0
        assert "meets targets" in report.recommendations[0]

    def test_with_data(self):
        eng = _engine()
        eng.record_score("svc-a", risk_score=90.0, score_adjustment=ScoreAdjustment.SPIKE)
        eng.record_score("svc-b", risk_score=10.0, score_adjustment=ScoreAdjustment.STABLE)
        eng.record_score("svc-b", risk_score=80.0, score_adjustment=ScoreAdjustment.INCREASE)
        eng.add_adjustment("adj-1")
        report = eng.generate_report()
        assert report.total_scores == 3
        assert report.total_adjustments == 1
        assert report.by_factor != {}
        assert report.recommendations != []

    def test_recommendations(self):
        eng = _engine()
        eng.record_score("svc-a", risk_score=90.0)
        report = eng.generate_report()
        assert len(report.recommendations) >= 1


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clear(self):
        eng = _engine()
        eng.record_score("svc-a")
        eng.add_adjustment("adj-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._adjustments) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_scores"] == 0
        assert stats["total_adjustments"] == 0
        assert stats["factor_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_score("svc-a", risk_factor=RiskFactor.INCIDENT_FREQUENCY)
        eng.record_score("svc-b", risk_factor=RiskFactor.DEPLOYMENT_VELOCITY)
        eng.add_adjustment("adj-1")
        stats = eng.get_stats()
        assert stats["total_scores"] == 2
        assert stats["total_adjustments"] == 1
        assert stats["unique_services"] == 2
