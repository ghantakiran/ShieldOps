"""Tests for shieldops.changes.risk_predictor — ChangeRiskPredictor."""

from __future__ import annotations

from shieldops.changes.risk_predictor import (
    ChangeRiskPredictor,
    PredictionAccuracy,
    RiskFactor,
    RiskFactorDetail,
    RiskLevel,
    RiskPredictionRecord,
    RiskPredictorReport,
)


def _engine(**kw) -> ChangeRiskPredictor:
    return ChangeRiskPredictor(**kw)


class TestEnums:
    def test_risk_level_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_risk_level_high(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_level_medium(self):
        assert RiskLevel.MEDIUM == "medium"

    def test_risk_level_low(self):
        assert RiskLevel.LOW == "low"

    def test_risk_level_negligible(self):
        assert RiskLevel.NEGLIGIBLE == "negligible"

    def test_risk_factor_code_complexity(self):
        assert RiskFactor.CODE_COMPLEXITY == "code_complexity"

    def test_risk_factor_blast_radius(self):
        assert RiskFactor.BLAST_RADIUS == "blast_radius"

    def test_risk_factor_deployment_history(self):
        assert RiskFactor.DEPLOYMENT_HISTORY == "deployment_history"

    def test_risk_factor_test_coverage(self):
        assert RiskFactor.TEST_COVERAGE == "test_coverage"

    def test_risk_factor_team_experience(self):
        assert RiskFactor.TEAM_EXPERIENCE == "team_experience"

    def test_accuracy_exact(self):
        assert PredictionAccuracy.EXACT == "exact"

    def test_accuracy_high(self):
        assert PredictionAccuracy.HIGH == "high"

    def test_accuracy_moderate(self):
        assert PredictionAccuracy.MODERATE == "moderate"

    def test_accuracy_low(self):
        assert PredictionAccuracy.LOW == "low"

    def test_accuracy_inaccurate(self):
        assert PredictionAccuracy.INACCURATE == "inaccurate"


class TestModels:
    def test_risk_prediction_record_defaults(self):
        r = RiskPredictionRecord()
        assert r.id
        assert r.change_id == ""
        assert r.risk_level == RiskLevel.MEDIUM
        assert r.risk_factor == RiskFactor.CODE_COMPLEXITY
        assert r.accuracy == PredictionAccuracy.MODERATE
        assert r.risk_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_risk_factor_detail_defaults(self):
        d = RiskFactorDetail()
        assert d.id
        assert d.change_id == ""
        assert d.risk_factor == RiskFactor.CODE_COMPLEXITY
        assert d.factor_score == 0.0
        assert d.weight == 1.0
        assert d.notes == ""
        assert d.created_at > 0

    def test_report_defaults(self):
        r = RiskPredictorReport()
        assert r.total_predictions == 0
        assert r.total_factors == 0
        assert r.avg_risk_score == 0.0
        assert r.by_risk_level == {}
        assert r.by_risk_factor == {}
        assert r.high_risk_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordPrediction:
    def test_basic(self):
        eng = _engine()
        r = eng.record_prediction(change_id="ch-001", risk_score=65.0)
        assert r.change_id == "ch-001"
        assert r.risk_score == 65.0

    def test_with_risk_level(self):
        eng = _engine()
        r = eng.record_prediction(risk_level=RiskLevel.CRITICAL)
        assert r.risk_level == RiskLevel.CRITICAL

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_prediction(change_id=f"ch-{i}")
        assert len(eng._records) == 3


class TestGetPrediction:
    def test_found(self):
        eng = _engine()
        r = eng.record_prediction(change_id="ch-001")
        assert eng.get_prediction(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_prediction("nonexistent") is None


class TestListPredictions:
    def test_list_all(self):
        eng = _engine()
        eng.record_prediction(change_id="ch-001")
        eng.record_prediction(change_id="ch-002")
        assert len(eng.list_predictions()) == 2

    def test_filter_by_risk_level(self):
        eng = _engine()
        eng.record_prediction(risk_level=RiskLevel.CRITICAL)
        eng.record_prediction(risk_level=RiskLevel.LOW)
        results = eng.list_predictions(risk_level=RiskLevel.CRITICAL)
        assert len(results) == 1

    def test_filter_by_risk_factor(self):
        eng = _engine()
        eng.record_prediction(risk_factor=RiskFactor.BLAST_RADIUS)
        eng.record_prediction(risk_factor=RiskFactor.TEST_COVERAGE)
        results = eng.list_predictions(risk_factor=RiskFactor.BLAST_RADIUS)
        assert len(results) == 1


class TestAddFactor:
    def test_basic(self):
        eng = _engine()
        d = eng.add_factor(
            change_id="ch-001", risk_factor=RiskFactor.BLAST_RADIUS, factor_score=80.0
        )
        assert d.change_id == "ch-001"
        assert d.risk_factor == RiskFactor.BLAST_RADIUS
        assert d.factor_score == 80.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_factor(change_id=f"ch-{i}")
        assert len(eng._factors) == 2


class TestAnalyzePredictionAccuracy:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction(accuracy=PredictionAccuracy.HIGH, risk_score=60.0)
        eng.record_prediction(accuracy=PredictionAccuracy.HIGH, risk_score=80.0)
        result = eng.analyze_prediction_accuracy(PredictionAccuracy.HIGH)
        assert result["accuracy"] == "high"
        assert result["total"] == 2
        assert result["avg_risk_score"] == 70.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_prediction_accuracy(PredictionAccuracy.EXACT)
        assert result["status"] == "no_data"


class TestIdentifyHighRiskChanges:
    def test_with_high_risk(self):
        eng = _engine()
        eng.record_prediction(risk_level=RiskLevel.CRITICAL, risk_score=95.0)
        eng.record_prediction(risk_level=RiskLevel.LOW, risk_score=10.0)
        results = eng.identify_high_risk_changes()
        assert len(results) == 1
        assert results[0]["risk_level"] == "critical"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_changes() == []


class TestRankByRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction(change_id="ch-001", risk_score=20.0)
        eng.record_prediction(change_id="ch-002", risk_score=90.0)
        results = eng.rank_by_risk_score()
        assert results[0]["change_id"] == "ch-002"
        assert results[0]["risk_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


class TestDetectRiskPatterns:
    def test_escalating(self):
        eng = _engine()
        for i in range(5):
            eng.record_prediction(change_id="ch-001", risk_score=float(10 + i * 15))
        results = eng.detect_risk_patterns()
        assert len(results) == 1
        assert results[0]["change_id"] == "ch-001"
        assert results[0]["risk_pattern"] == "escalating"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_risk_patterns() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction(risk_level=RiskLevel.CRITICAL, risk_score=90.0)
        eng.record_prediction(risk_level=RiskLevel.LOW, risk_score=10.0)
        eng.add_factor(change_id="ch-001")
        report = eng.generate_report()
        assert report.total_predictions == 2
        assert report.total_factors == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_predictions == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_prediction(change_id="ch-001")
        eng.add_factor(change_id="ch-001")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._factors) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_predictions"] == 0
        assert stats["total_factors"] == 0
        assert stats["risk_factor_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_prediction(change_id="ch-001", risk_factor=RiskFactor.BLAST_RADIUS)
        eng.record_prediction(change_id="ch-002", risk_factor=RiskFactor.TEST_COVERAGE)
        eng.add_factor(change_id="ch-001")
        stats = eng.get_stats()
        assert stats["total_predictions"] == 2
        assert stats["total_factors"] == 1
        assert stats["unique_changes"] == 2
