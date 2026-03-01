"""Tests for shieldops.operations.runbook_quality_scorer — RunbookQualityScorer."""

from __future__ import annotations

from shieldops.operations.runbook_quality_scorer import (
    QualityAssessment,
    QualityDimension,
    QualityGrade,
    QualityRecord,
    RunbookQualityReport,
    RunbookQualityScorer,
    RunbookType,
)


def _engine(**kw) -> RunbookQualityScorer:
    return RunbookQualityScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dimension_completeness(self):
        assert QualityDimension.COMPLETENESS == "completeness"

    def test_dimension_accuracy(self):
        assert QualityDimension.ACCURACY == "accuracy"

    def test_dimension_clarity(self):
        assert QualityDimension.CLARITY == "clarity"

    def test_dimension_currency(self):
        assert QualityDimension.CURRENCY == "currency"

    def test_dimension_testability(self):
        assert QualityDimension.TESTABILITY == "testability"

    def test_grade_excellent(self):
        assert QualityGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert QualityGrade.GOOD == "good"

    def test_grade_adequate(self):
        assert QualityGrade.ADEQUATE == "adequate"

    def test_grade_poor(self):
        assert QualityGrade.POOR == "poor"

    def test_grade_failing(self):
        assert QualityGrade.FAILING == "failing"

    def test_type_automated(self):
        assert RunbookType.AUTOMATED == "automated"

    def test_type_semi_automated(self):
        assert RunbookType.SEMI_AUTOMATED == "semi_automated"

    def test_type_manual(self):
        assert RunbookType.MANUAL == "manual"

    def test_type_reference(self):
        assert RunbookType.REFERENCE == "reference"

    def test_type_troubleshooting(self):
        assert RunbookType.TROUBLESHOOTING == "troubleshooting"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_quality_record_defaults(self):
        r = QualityRecord()
        assert r.id
        assert r.runbook_id == ""
        assert r.quality_dimension == QualityDimension.COMPLETENESS
        assert r.quality_grade == QualityGrade.ADEQUATE
        assert r.runbook_type == RunbookType.AUTOMATED
        assert r.quality_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_quality_assessment_defaults(self):
        a = QualityAssessment()
        assert a.id
        assert a.runbook_id == ""
        assert a.quality_dimension == QualityDimension.COMPLETENESS
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_runbook_quality_report_defaults(self):
        r = RunbookQualityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.low_quality_count == 0
        assert r.avg_quality_score == 0.0
        assert r.by_dimension == {}
        assert r.by_grade == {}
        assert r.by_type == {}
        assert r.top_low_quality == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_quality
# ---------------------------------------------------------------------------


class TestRecordQuality:
    def test_basic(self):
        eng = _engine()
        r = eng.record_quality(
            runbook_id="RB-001",
            quality_dimension=QualityDimension.COMPLETENESS,
            quality_grade=QualityGrade.GOOD,
            runbook_type=RunbookType.AUTOMATED,
            quality_score=85.0,
            service="api-gw",
            team="sre",
        )
        assert r.runbook_id == "RB-001"
        assert r.quality_dimension == QualityDimension.COMPLETENESS
        assert r.quality_grade == QualityGrade.GOOD
        assert r.runbook_type == RunbookType.AUTOMATED
        assert r.quality_score == 85.0
        assert r.service == "api-gw"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_quality(runbook_id=f"RB-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_quality
# ---------------------------------------------------------------------------


class TestGetQuality:
    def test_found(self):
        eng = _engine()
        r = eng.record_quality(
            runbook_id="RB-001",
            quality_grade=QualityGrade.POOR,
        )
        result = eng.get_quality(r.id)
        assert result is not None
        assert result.quality_grade == QualityGrade.POOR

    def test_not_found(self):
        eng = _engine()
        assert eng.get_quality("nonexistent") is None


# ---------------------------------------------------------------------------
# list_qualities
# ---------------------------------------------------------------------------


class TestListQualities:
    def test_list_all(self):
        eng = _engine()
        eng.record_quality(runbook_id="RB-001")
        eng.record_quality(runbook_id="RB-002")
        assert len(eng.list_qualities()) == 2

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_quality(
            runbook_id="RB-001",
            quality_dimension=QualityDimension.COMPLETENESS,
        )
        eng.record_quality(
            runbook_id="RB-002",
            quality_dimension=QualityDimension.CLARITY,
        )
        results = eng.list_qualities(
            dimension=QualityDimension.COMPLETENESS,
        )
        assert len(results) == 1

    def test_filter_by_grade(self):
        eng = _engine()
        eng.record_quality(
            runbook_id="RB-001",
            quality_grade=QualityGrade.EXCELLENT,
        )
        eng.record_quality(
            runbook_id="RB-002",
            quality_grade=QualityGrade.POOR,
        )
        results = eng.list_qualities(
            grade=QualityGrade.EXCELLENT,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_quality(runbook_id="RB-001", service="api-gw")
        eng.record_quality(runbook_id="RB-002", service="auth")
        results = eng.list_qualities(service="api-gw")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_quality(runbook_id=f"RB-{i}")
        assert len(eng.list_qualities(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            runbook_id="RB-001",
            quality_dimension=QualityDimension.ACCURACY,
            assessment_score=72.0,
            threshold=70.0,
            breached=True,
            description="accuracy slightly above minimum",
        )
        assert a.runbook_id == "RB-001"
        assert a.quality_dimension == QualityDimension.ACCURACY
        assert a.assessment_score == 72.0
        assert a.threshold == 70.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(runbook_id=f"RB-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_quality_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeQualityDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_quality(
            runbook_id="RB-001",
            quality_dimension=QualityDimension.COMPLETENESS,
            quality_score=90.0,
        )
        eng.record_quality(
            runbook_id="RB-002",
            quality_dimension=QualityDimension.COMPLETENESS,
            quality_score=70.0,
        )
        result = eng.analyze_quality_distribution()
        assert "completeness" in result
        assert result["completeness"]["count"] == 2
        assert result["completeness"]["avg_quality_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_quality_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_quality
# ---------------------------------------------------------------------------


class TestIdentifyLowQuality:
    def test_detects_poor_and_failing(self):
        eng = _engine()
        eng.record_quality(
            runbook_id="RB-001",
            quality_grade=QualityGrade.POOR,
        )
        eng.record_quality(
            runbook_id="RB-002",
            quality_grade=QualityGrade.FAILING,
        )
        eng.record_quality(
            runbook_id="RB-003",
            quality_grade=QualityGrade.GOOD,
        )
        results = eng.identify_low_quality()
        assert len(results) == 2
        assert results[0]["runbook_id"] == "RB-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_quality() == []


# ---------------------------------------------------------------------------
# rank_by_quality
# ---------------------------------------------------------------------------


class TestRankByQuality:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_quality(runbook_id="RB-001", service="api-gw", quality_score=90.0)
        eng.record_quality(runbook_id="RB-002", service="auth", quality_score=40.0)
        results = eng.rank_by_quality()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_quality_score"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_quality() == []


# ---------------------------------------------------------------------------
# detect_quality_trends
# ---------------------------------------------------------------------------


class TestDetectQualityTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(runbook_id="RB-001", assessment_score=50.0)
        result = eng.detect_quality_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(runbook_id="RB-001", assessment_score=20.0)
        eng.add_assessment(runbook_id="RB-002", assessment_score=20.0)
        eng.add_assessment(runbook_id="RB-003", assessment_score=80.0)
        eng.add_assessment(runbook_id="RB-004", assessment_score=80.0)
        result = eng.detect_quality_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_quality_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_quality(
            runbook_id="RB-001",
            quality_dimension=QualityDimension.COMPLETENESS,
            quality_grade=QualityGrade.POOR,
            runbook_type=RunbookType.AUTOMATED,
            quality_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RunbookQualityReport)
        assert report.total_records == 1
        assert report.low_quality_count == 1
        assert len(report.top_low_quality) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_quality(runbook_id="RB-001")
        eng.add_assessment(runbook_id="RB-001")
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
        assert stats["dimension_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_quality(
            runbook_id="RB-001",
            quality_dimension=QualityDimension.COMPLETENESS,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "completeness" in stats["dimension_distribution"]
