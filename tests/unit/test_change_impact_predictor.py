"""Tests for shieldops.changes.change_impact_predictor — ChangeImpactPredictor."""

from __future__ import annotations

from shieldops.changes.change_impact_predictor import (
    BlastRadius,
    ChangeImpactPredictor,
    ChangeImpactReport,
    ImpactCategory,
    ImpactPredictionRecord,
    PredictionAccuracy,
    PredictionConfidence,
)


def _engine(**kw) -> ChangeImpactPredictor:
    return ChangeImpactPredictor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_cat_performance(self):
        assert ImpactCategory.PERFORMANCE == "performance"

    def test_cat_availability(self):
        assert ImpactCategory.AVAILABILITY == "availability"

    def test_cat_security(self):
        assert ImpactCategory.SECURITY == "security"

    def test_cat_data_integrity(self):
        assert ImpactCategory.DATA_INTEGRITY == "data_integrity"

    def test_cat_user_experience(self):
        assert ImpactCategory.USER_EXPERIENCE == "user_experience"

    def test_conf_very_high(self):
        assert PredictionConfidence.VERY_HIGH == "very_high"

    def test_conf_high(self):
        assert PredictionConfidence.HIGH == "high"

    def test_conf_moderate(self):
        assert PredictionConfidence.MODERATE == "moderate"

    def test_conf_low(self):
        assert PredictionConfidence.LOW == "low"

    def test_conf_uncertain(self):
        assert PredictionConfidence.UNCERTAIN == "uncertain"

    def test_radius_isolated(self):
        assert BlastRadius.ISOLATED == "isolated"

    def test_radius_service(self):
        assert BlastRadius.SERVICE == "service"

    def test_radius_cluster(self):
        assert BlastRadius.CLUSTER == "cluster"

    def test_radius_region(self):
        assert BlastRadius.REGION == "region"

    def test_radius_global(self):
        assert BlastRadius.GLOBAL == "global"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_prediction_record_defaults(self):
        r = ImpactPredictionRecord()
        assert r.id
        assert r.prediction_id == ""
        assert r.impact_category == ImpactCategory.PERFORMANCE
        assert r.prediction_confidence == PredictionConfidence.UNCERTAIN
        assert r.blast_radius == BlastRadius.ISOLATED
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_prediction_accuracy_defaults(self):
        a = PredictionAccuracy()
        assert a.id
        assert a.prediction_id == ""
        assert a.impact_category == ImpactCategory.PERFORMANCE
        assert a.accuracy_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_change_impact_report_defaults(self):
        r = ChangeImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_accuracy_checks == 0
        assert r.high_impact_count == 0
        assert r.avg_impact_score == 0.0
        assert r.by_category == {}
        assert r.by_confidence == {}
        assert r.by_radius == {}
        assert r.top_high_impact == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_prediction
# ---------------------------------------------------------------------------


class TestRecordPrediction:
    def test_basic(self):
        eng = _engine()
        r = eng.record_prediction(
            prediction_id="PRD-001",
            impact_category=ImpactCategory.AVAILABILITY,
            prediction_confidence=PredictionConfidence.HIGH,
            blast_radius=BlastRadius.REGION,
            impact_score=85.0,
            service="api-gw",
            team="sre",
        )
        assert r.prediction_id == "PRD-001"
        assert r.impact_category == ImpactCategory.AVAILABILITY
        assert r.prediction_confidence == PredictionConfidence.HIGH
        assert r.blast_radius == BlastRadius.REGION
        assert r.impact_score == 85.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_prediction(prediction_id=f"PRD-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_prediction
# ---------------------------------------------------------------------------


class TestGetPrediction:
    def test_found(self):
        eng = _engine()
        r = eng.record_prediction(
            prediction_id="PRD-001",
            blast_radius=BlastRadius.GLOBAL,
        )
        result = eng.get_prediction(r.id)
        assert result is not None
        assert result.blast_radius == BlastRadius.GLOBAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_prediction("nonexistent") is None


# ---------------------------------------------------------------------------
# list_predictions
# ---------------------------------------------------------------------------


class TestListPredictions:
    def test_list_all(self):
        eng = _engine()
        eng.record_prediction(prediction_id="PRD-001")
        eng.record_prediction(prediction_id="PRD-002")
        assert len(eng.list_predictions()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_prediction(
            prediction_id="PRD-001",
            impact_category=ImpactCategory.PERFORMANCE,
        )
        eng.record_prediction(
            prediction_id="PRD-002",
            impact_category=ImpactCategory.SECURITY,
        )
        results = eng.list_predictions(
            category=ImpactCategory.PERFORMANCE,
        )
        assert len(results) == 1

    def test_filter_by_confidence(self):
        eng = _engine()
        eng.record_prediction(
            prediction_id="PRD-001",
            prediction_confidence=PredictionConfidence.HIGH,
        )
        eng.record_prediction(
            prediction_id="PRD-002",
            prediction_confidence=PredictionConfidence.LOW,
        )
        results = eng.list_predictions(
            confidence=PredictionConfidence.HIGH,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_prediction(prediction_id="PRD-001", team="sre")
        eng.record_prediction(prediction_id="PRD-002", team="platform")
        results = eng.list_predictions(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_prediction(prediction_id=f"PRD-{i}")
        assert len(eng.list_predictions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_accuracy
# ---------------------------------------------------------------------------


class TestAddAccuracy:
    def test_basic(self):
        eng = _engine()
        a = eng.add_accuracy(
            prediction_id="PRD-001",
            impact_category=ImpactCategory.AVAILABILITY,
            accuracy_score=92.0,
            threshold=80.0,
            breached=False,
            description="Accurate prediction",
        )
        assert a.prediction_id == "PRD-001"
        assert a.impact_category == ImpactCategory.AVAILABILITY
        assert a.accuracy_score == 92.0
        assert a.breached is False

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_accuracy(prediction_id=f"PRD-{i}")
        assert len(eng._accuracy_checks) == 2


# ---------------------------------------------------------------------------
# analyze_impact_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeImpactDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction(
            prediction_id="PRD-001",
            impact_category=ImpactCategory.PERFORMANCE,
            impact_score=80.0,
        )
        eng.record_prediction(
            prediction_id="PRD-002",
            impact_category=ImpactCategory.PERFORMANCE,
            impact_score=60.0,
        )
        result = eng.analyze_impact_distribution()
        assert "performance" in result
        assert result["performance"]["count"] == 2
        assert result["performance"]["avg_impact_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_impact_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_impact
# ---------------------------------------------------------------------------


class TestIdentifyHighImpact:
    def test_detects_region(self):
        eng = _engine()
        eng.record_prediction(
            prediction_id="PRD-001",
            blast_radius=BlastRadius.REGION,
        )
        eng.record_prediction(
            prediction_id="PRD-002",
            blast_radius=BlastRadius.ISOLATED,
        )
        results = eng.identify_high_impact()
        assert len(results) == 1
        assert results[0]["prediction_id"] == "PRD-001"

    def test_detects_global(self):
        eng = _engine()
        eng.record_prediction(
            prediction_id="PRD-001",
            blast_radius=BlastRadius.GLOBAL,
        )
        results = eng.identify_high_impact()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact() == []


# ---------------------------------------------------------------------------
# rank_by_impact_score
# ---------------------------------------------------------------------------


class TestRankByImpactScore:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_prediction(
            prediction_id="PRD-001",
            service="api-gw",
            impact_score=40.0,
        )
        eng.record_prediction(
            prediction_id="PRD-002",
            service="auth",
            impact_score=90.0,
        )
        results = eng.rank_by_impact_score()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_impact_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_score() == []


# ---------------------------------------------------------------------------
# detect_prediction_trends
# ---------------------------------------------------------------------------


class TestDetectPredictionTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_accuracy(prediction_id="PRD-001", accuracy_score=50.0)
        result = eng.detect_prediction_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_accuracy(prediction_id="PRD-001", accuracy_score=30.0)
        eng.add_accuracy(prediction_id="PRD-002", accuracy_score=30.0)
        eng.add_accuracy(prediction_id="PRD-003", accuracy_score=50.0)
        eng.add_accuracy(prediction_id="PRD-004", accuracy_score=50.0)
        result = eng.detect_prediction_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_prediction_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_prediction(
            prediction_id="PRD-001",
            impact_category=ImpactCategory.AVAILABILITY,
            blast_radius=BlastRadius.REGION,
            impact_score=85.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ChangeImpactReport)
        assert report.total_records == 1
        assert report.high_impact_count == 1
        assert len(report.top_high_impact) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_prediction(prediction_id="PRD-001")
        eng.add_accuracy(prediction_id="PRD-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._accuracy_checks) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_accuracy_checks"] == 0
        assert stats["impact_category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_prediction(
            prediction_id="PRD-001",
            impact_category=ImpactCategory.PERFORMANCE,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "performance" in stats["impact_category_distribution"]
