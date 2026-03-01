"""Tests for shieldops.changes.change_risk_classifier — ChangeRiskClassifier."""

from __future__ import annotations

from shieldops.changes.change_risk_classifier import (
    ChangeRiskClassifier,
    ChangeRiskReport,
    ClassificationMethod,
    RiskAssessment,
    RiskClassificationRecord,
    RiskFactor,
    RiskLevel,
)


def _engine(**kw) -> ChangeRiskClassifier:
    return ChangeRiskClassifier(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_level_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_level_high(self):
        assert RiskLevel.HIGH == "high"

    def test_level_moderate(self):
        assert RiskLevel.MODERATE == "moderate"

    def test_level_low(self):
        assert RiskLevel.LOW == "low"

    def test_level_minimal(self):
        assert RiskLevel.MINIMAL == "minimal"

    def test_factor_blast_radius(self):
        assert RiskFactor.BLAST_RADIUS == "blast_radius"

    def test_factor_rollback_complexity(self):
        assert RiskFactor.ROLLBACK_COMPLEXITY == "rollback_complexity"

    def test_factor_dependency_count(self):
        assert RiskFactor.DEPENDENCY_COUNT == "dependency_count"

    def test_factor_change_frequency(self):
        assert RiskFactor.CHANGE_FREQUENCY == "change_frequency"

    def test_factor_team_experience(self):
        assert RiskFactor.TEAM_EXPERIENCE == "team_experience"

    def test_method_rule_based(self):
        assert ClassificationMethod.RULE_BASED == "rule_based"

    def test_method_ml_predicted(self):
        assert ClassificationMethod.ML_PREDICTED == "ml_predicted"

    def test_method_historical(self):
        assert ClassificationMethod.HISTORICAL == "historical"

    def test_method_expert_override(self):
        assert ClassificationMethod.EXPERT_OVERRIDE == "expert_override"

    def test_method_hybrid(self):
        assert ClassificationMethod.HYBRID == "hybrid"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_classification_record_defaults(self):
        r = RiskClassificationRecord()
        assert r.id
        assert r.classification_id == ""
        assert r.risk_level == RiskLevel.MODERATE
        assert r.risk_factor == RiskFactor.BLAST_RADIUS
        assert r.classification_method == ClassificationMethod.RULE_BASED
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_risk_assessment_defaults(self):
        a = RiskAssessment()
        assert a.id
        assert a.classification_id == ""
        assert a.risk_level == RiskLevel.MODERATE
        assert a.assessment_score == 0.0
        assert a.threshold == 15.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_risk_report_defaults(self):
        r = ChangeRiskReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.high_risk_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_level == {}
        assert r.by_factor == {}
        assert r.by_method == {}
        assert r.top_risky_services == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_classification
# ---------------------------------------------------------------------------


class TestRecordClassification:
    def test_basic(self):
        eng = _engine()
        r = eng.record_classification(
            classification_id="CLS-001",
            risk_level=RiskLevel.CRITICAL,
            risk_factor=RiskFactor.BLAST_RADIUS,
            classification_method=ClassificationMethod.RULE_BASED,
            risk_score=92.0,
            service="payment-svc",
            team="sre",
        )
        assert r.classification_id == "CLS-001"
        assert r.risk_level == RiskLevel.CRITICAL
        assert r.risk_factor == RiskFactor.BLAST_RADIUS
        assert r.classification_method == ClassificationMethod.RULE_BASED
        assert r.risk_score == 92.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_classification(classification_id=f"CLS-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_classification
# ---------------------------------------------------------------------------


class TestGetClassification:
    def test_found(self):
        eng = _engine()
        r = eng.record_classification(
            classification_id="CLS-001",
            risk_level=RiskLevel.HIGH,
        )
        result = eng.get_classification(r.id)
        assert result is not None
        assert result.risk_level == RiskLevel.HIGH

    def test_not_found(self):
        eng = _engine()
        assert eng.get_classification("nonexistent") is None


# ---------------------------------------------------------------------------
# list_classifications
# ---------------------------------------------------------------------------


class TestListClassifications:
    def test_list_all(self):
        eng = _engine()
        eng.record_classification(classification_id="CLS-001")
        eng.record_classification(classification_id="CLS-002")
        assert len(eng.list_classifications()) == 2

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            risk_level=RiskLevel.CRITICAL,
        )
        eng.record_classification(
            classification_id="CLS-002",
            risk_level=RiskLevel.LOW,
        )
        results = eng.list_classifications(risk_level=RiskLevel.CRITICAL)
        assert len(results) == 1

    def test_filter_by_factor(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            risk_factor=RiskFactor.BLAST_RADIUS,
        )
        eng.record_classification(
            classification_id="CLS-002",
            risk_factor=RiskFactor.TEAM_EXPERIENCE,
        )
        results = eng.list_classifications(
            risk_factor=RiskFactor.BLAST_RADIUS,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_classification(classification_id="CLS-001", team="sre")
        eng.record_classification(classification_id="CLS-002", team="platform")
        results = eng.list_classifications(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_classification(classification_id=f"CLS-{i}")
        assert len(eng.list_classifications(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            classification_id="CLS-001",
            risk_level=RiskLevel.HIGH,
            assessment_score=20.0,
            threshold=15.0,
            description="Above threshold",
        )
        assert a.classification_id == "CLS-001"
        assert a.risk_level == RiskLevel.HIGH
        assert a.assessment_score == 20.0
        assert a.breached is True

    def test_not_breached(self):
        eng = _engine()
        a = eng.add_assessment(
            classification_id="CLS-002",
            assessment_score=10.0,
            threshold=15.0,
        )
        assert a.breached is False

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(classification_id=f"CLS-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_risk_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeRiskDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            risk_level=RiskLevel.CRITICAL,
            risk_score=90.0,
        )
        eng.record_classification(
            classification_id="CLS-002",
            risk_level=RiskLevel.CRITICAL,
            risk_score=80.0,
        )
        result = eng.analyze_risk_distribution()
        assert "critical" in result
        assert result["critical"]["count"] == 2
        assert result["critical"]["avg_risk_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_risk_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_risk_changes
# ---------------------------------------------------------------------------


class TestIdentifyHighRiskChanges:
    def test_detects_critical_and_high(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            risk_level=RiskLevel.CRITICAL,
        )
        eng.record_classification(
            classification_id="CLS-002",
            risk_level=RiskLevel.HIGH,
        )
        eng.record_classification(
            classification_id="CLS-003",
            risk_level=RiskLevel.LOW,
        )
        results = eng.identify_high_risk_changes()
        assert len(results) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_changes() == []


# ---------------------------------------------------------------------------
# rank_by_risk_score
# ---------------------------------------------------------------------------


class TestRankByRiskScore:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_classification(classification_id="CLS-001", service="api", risk_score=30.0)
        eng.record_classification(classification_id="CLS-002", service="db", risk_score=90.0)
        results = eng.rank_by_risk_score()
        assert len(results) == 2
        assert results[0]["service"] == "db"
        assert results[0]["avg_risk_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# ---------------------------------------------------------------------------
# detect_risk_trends
# ---------------------------------------------------------------------------


class TestDetectRiskTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(classification_id="CLS-001", assessment_score=10.0)
        result = eng.detect_risk_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        eng.add_assessment(classification_id="CLS-001", assessment_score=5.0)
        eng.add_assessment(classification_id="CLS-002", assessment_score=5.0)
        eng.add_assessment(classification_id="CLS-003", assessment_score=30.0)
        eng.add_assessment(classification_id="CLS-004", assessment_score=30.0)
        result = eng.detect_risk_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_risk_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            risk_level=RiskLevel.CRITICAL,
            risk_factor=RiskFactor.BLAST_RADIUS,
            risk_score=92.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ChangeRiskReport)
        assert report.total_records == 1
        assert report.high_risk_count == 1
        assert len(report.top_risky_services) == 1
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
        eng.record_classification(classification_id="CLS-001")
        eng.add_assessment(classification_id="CLS-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["level_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            risk_level=RiskLevel.CRITICAL,
            team="sre",
            service="api",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "critical" in stats["level_distribution"]
