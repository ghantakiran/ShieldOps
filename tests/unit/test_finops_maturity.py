"""Tests for shieldops.billing.finops_maturity — FinOpsMaturityScorer."""

from __future__ import annotations

from shieldops.billing.finops_maturity import (
    AssessmentArea,
    DimensionScore,
    FinOpsMaturityScorer,
    MaturityAssessment,
    MaturityDimension,
    MaturityLevel,
    MaturityReport,
)


def _engine(**kw) -> FinOpsMaturityScorer:
    return FinOpsMaturityScorer(**kw)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestMaturityDimension:
    """Test every MaturityDimension member."""

    def test_visibility(self):
        assert MaturityDimension.VISIBILITY == "visibility"

    def test_allocation(self):
        assert MaturityDimension.ALLOCATION == "allocation"

    def test_optimization(self):
        assert MaturityDimension.OPTIMIZATION == "optimization"

    def test_governance(self):
        assert MaturityDimension.GOVERNANCE == "governance"

    def test_culture(self):
        assert MaturityDimension.CULTURE == "culture"


class TestMaturityLevel:
    """Test every MaturityLevel member."""

    def test_crawl(self):
        assert MaturityLevel.CRAWL == "crawl"

    def test_walk(self):
        assert MaturityLevel.WALK == "walk"

    def test_run(self):
        assert MaturityLevel.RUN == "run"

    def test_sprint(self):
        assert MaturityLevel.SPRINT == "sprint"

    def test_lead(self):
        assert MaturityLevel.LEAD == "lead"


class TestAssessmentArea:
    """Test every AssessmentArea member."""

    def test_tagging(self):
        assert AssessmentArea.TAGGING == "tagging"

    def test_forecasting(self):
        assert AssessmentArea.FORECASTING == "forecasting"

    def test_rightsizing(self):
        assert AssessmentArea.RIGHTSIZING == "rightsizing"

    def test_commitment_usage(self):
        assert AssessmentArea.COMMITMENT_USAGE == "commitment_usage"

    def test_anomaly_detection(self):
        assert AssessmentArea.ANOMALY_DETECTION == "anomaly_detection"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test model defaults."""

    def test_maturity_assessment_defaults(self):
        m = MaturityAssessment()
        assert m.id
        assert m.organization == ""
        assert m.assessor == ""
        assert m.overall_score == 0.0
        assert m.overall_level == MaturityLevel.CRAWL
        assert m.dimension_scores == []
        assert m.notes == ""
        assert m.created_at > 0

    def test_dimension_score_defaults(self):
        m = DimensionScore()
        assert m.id
        assert m.assessment_id == ""
        assert m.dimension == MaturityDimension.VISIBILITY
        assert m.area == AssessmentArea.TAGGING
        assert m.score == 0.0
        assert m.level == MaturityLevel.CRAWL
        assert m.findings == []

    def test_maturity_report_defaults(self):
        m = MaturityReport()
        assert m.total_assessments == 0
        assert m.avg_overall_score == 0.0
        assert m.avg_level == ""
        assert m.by_dimension == {}
        assert m.by_level == {}
        assert m.improvement_areas == []
        assert m.benchmarks == {}
        assert m.recommendations == []


# ---------------------------------------------------------------------------
# create_assessment
# ---------------------------------------------------------------------------


class TestCreateAssessment:
    """Test FinOpsMaturityScorer.create_assessment."""

    def test_basic(self):
        eng = _engine()
        a = eng.create_assessment(
            organization="acme-corp",
            assessor="alice",
            notes="Q1 review",
        )
        assert a.organization == "acme-corp"
        assert a.assessor == "alice"
        assert a.notes == "Q1 review"
        assert eng.get_assessment(a.id) is a

    def test_eviction_on_overflow(self):
        eng = _engine(max_assessments=2)
        a1 = eng.create_assessment(organization="org1")
        eng.create_assessment(organization="org2")
        eng.create_assessment(organization="org3")
        assert eng.get_assessment(a1.id) is None
        assert len(eng.list_assessments()) == 2


# ---------------------------------------------------------------------------
# get_assessment
# ---------------------------------------------------------------------------


class TestGetAssessment:
    """Test FinOpsMaturityScorer.get_assessment."""

    def test_found(self):
        eng = _engine()
        a = eng.create_assessment(organization="test")
        assert eng.get_assessment(a.id) is a

    def test_not_found(self):
        eng = _engine()
        assert eng.get_assessment("nonexistent") is None


# ---------------------------------------------------------------------------
# list_assessments
# ---------------------------------------------------------------------------


class TestListAssessments:
    """Test FinOpsMaturityScorer.list_assessments."""

    def test_all(self):
        eng = _engine()
        eng.create_assessment(organization="a")
        eng.create_assessment(organization="b")
        assert len(eng.list_assessments()) == 2

    def test_filter_by_organization(self):
        eng = _engine()
        eng.create_assessment(organization="acme")
        eng.create_assessment(organization="globex")
        eng.create_assessment(organization="acme")
        result = eng.list_assessments(organization="acme")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# score_dimension
# ---------------------------------------------------------------------------


class TestScoreDimension:
    """Test FinOpsMaturityScorer.score_dimension."""

    def test_high_score_lead_level(self):
        eng = _engine()
        a = eng.create_assessment(organization="acme")
        ds = eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=90.0,
            findings=["Excellent tagging coverage"],
        )
        assert ds is not None
        assert ds.score == 90.0
        assert ds.level == MaturityLevel.LEAD
        assert ds.findings == ["Excellent tagging coverage"]
        assert a.overall_score == 90.0
        assert a.overall_level == MaturityLevel.LEAD

    def test_low_score_crawl_level(self):
        eng = _engine()
        a = eng.create_assessment(organization="startup")
        ds = eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.GOVERNANCE,
            area=AssessmentArea.FORECASTING,
            score=10.0,
        )
        assert ds is not None
        assert ds.score == 10.0
        assert ds.level == MaturityLevel.CRAWL

    def test_not_found_returns_none(self):
        eng = _engine()
        result = eng.score_dimension(
            assessment_id="missing",
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=50.0,
        )
        assert result is None

    def test_updates_overall_score_as_average(self):
        eng = _engine()
        a = eng.create_assessment(organization="acme")
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=80.0,
        )
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.OPTIMIZATION,
            area=AssessmentArea.RIGHTSIZING,
            score=40.0,
        )
        assert a.overall_score == 60.0
        assert a.overall_level == MaturityLevel.SPRINT


# ---------------------------------------------------------------------------
# calculate_overall_maturity
# ---------------------------------------------------------------------------


class TestCalculateOverallMaturity:
    """Test FinOpsMaturityScorer.calculate_overall_maturity."""

    def test_basic_with_dimensions(self):
        eng = _engine()
        a = eng.create_assessment(organization="acme")
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=70.0,
        )
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.ALLOCATION,
            area=AssessmentArea.FORECASTING,
            score=50.0,
        )
        result = eng.calculate_overall_maturity(a.id)
        assert result["overall_score"] == 60.0
        assert result["overall_level"] == "sprint"
        assert len(result["dimension_breakdown"]) == 2

    def test_not_found(self):
        eng = _engine()
        result = eng.calculate_overall_maturity("missing")
        assert result["overall_score"] == 0.0
        assert result["overall_level"] == "crawl"
        assert result["dimension_breakdown"] == []


# ---------------------------------------------------------------------------
# score_dimension (additional boundary tests)
# ---------------------------------------------------------------------------


class TestScoreDimensionBoundary:
    """Test _score_to_level boundary values via score_dimension."""

    def test_walk_level(self):
        eng = _engine()
        a = eng.create_assessment(organization="boundary")
        ds = eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.ALLOCATION,
            area=AssessmentArea.FORECASTING,
            score=35.0,
        )
        assert ds is not None
        assert ds.level == MaturityLevel.WALK

    def test_run_level(self):
        eng = _engine()
        a = eng.create_assessment(organization="boundary")
        ds = eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.OPTIMIZATION,
            area=AssessmentArea.RIGHTSIZING,
            score=55.0,
        )
        assert ds is not None
        assert ds.level == MaturityLevel.RUN

    def test_sprint_level(self):
        eng = _engine()
        a = eng.create_assessment(organization="boundary")
        ds = eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.CULTURE,
            area=AssessmentArea.ANOMALY_DETECTION,
            score=65.0,
        )
        assert ds is not None
        assert ds.level == MaturityLevel.SPRINT


# ---------------------------------------------------------------------------
# identify_improvement_areas
# ---------------------------------------------------------------------------


class TestIdentifyImprovementAreas:
    """Test FinOpsMaturityScorer.identify_improvement_areas."""

    def test_below_target(self):
        eng = _engine(target_level=3)  # target_score = 60
        a = eng.create_assessment(organization="acme")
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=30.0,
        )
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.OPTIMIZATION,
            area=AssessmentArea.RIGHTSIZING,
            score=80.0,
        )
        improvements = eng.identify_improvement_areas(a.id)
        assert len(improvements) == 1
        assert improvements[0]["dimension"] == "visibility"
        assert improvements[0]["current_score"] == 30.0
        assert improvements[0]["target_score"] == 60.0
        assert improvements[0]["gap"] == 30.0

    def test_above_target_no_improvements(self):
        eng = _engine(target_level=2)  # target_score = 40
        a = eng.create_assessment(organization="acme")
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=50.0,
        )
        improvements = eng.identify_improvement_areas(a.id)
        assert improvements == []


# ---------------------------------------------------------------------------
# track_maturity_trend
# ---------------------------------------------------------------------------


class TestTrackMaturityTrend:
    """Test FinOpsMaturityScorer.track_maturity_trend."""

    def test_multiple_assessments_for_same_org(self):
        eng = _engine()
        a1 = eng.create_assessment(organization="acme")
        eng.score_dimension(
            assessment_id=a1.id,
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=30.0,
        )
        a2 = eng.create_assessment(organization="acme")
        eng.score_dimension(
            assessment_id=a2.id,
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=60.0,
        )
        eng.create_assessment(organization="other")
        trend = eng.track_maturity_trend("acme")
        assert len(trend) == 2
        assert trend[0]["overall_score"] == 30.0
        assert trend[1]["overall_score"] == 60.0
        assert trend[0]["assessed_at"] <= trend[1]["assessed_at"]


# ---------------------------------------------------------------------------
# compare_with_benchmarks
# ---------------------------------------------------------------------------


class TestCompareWithBenchmarks:
    """Test FinOpsMaturityScorer.compare_with_benchmarks."""

    def test_basic_comparison(self):
        eng = _engine()
        a = eng.create_assessment(organization="acme")
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=80.0,
        )
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.GOVERNANCE,
            area=AssessmentArea.COMMITMENT_USAGE,
            score=30.0,
        )
        result = eng.compare_with_benchmarks(a.id)
        assert result["assessment_id"] == a.id
        comparisons = result["comparisons"]
        assert len(comparisons) == 2
        visibility = next(c for c in comparisons if c["dimension"] == "visibility")
        assert visibility["score"] == 80.0
        assert visibility["benchmark"] == 65.0
        assert visibility["delta"] == 15.0
        governance = next(c for c in comparisons if c["dimension"] == "governance")
        assert governance["score"] == 30.0
        assert governance["benchmark"] == 45.0
        assert governance["delta"] == -15.0


# ---------------------------------------------------------------------------
# generate_maturity_report
# ---------------------------------------------------------------------------


class TestGenerateMaturityReport:
    """Test FinOpsMaturityScorer.generate_maturity_report."""

    def test_basic(self):
        eng = _engine()
        a = eng.create_assessment(organization="acme")
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=70.0,
        )
        report = eng.generate_maturity_report()
        assert isinstance(report, MaturityReport)
        assert report.total_assessments == 1
        assert report.avg_overall_score == 70.0
        assert report.avg_level == "sprint"
        assert "visibility" in report.by_dimension
        assert report.benchmarks["visibility"] == 65.0
        assert len(report.recommendations) >= 0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    """Test FinOpsMaturityScorer.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        a = eng.create_assessment(organization="acme")
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=50.0,
        )
        eng.clear_data()
        assert eng.list_assessments() == []
        stats = eng.get_stats()
        assert stats["total_assessments"] == 0
        assert stats["total_dimension_scores"] == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    """Test FinOpsMaturityScorer.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_assessments"] == 0
        assert stats["total_dimension_scores"] == 0
        assert stats["organization_distribution"] == {}
        assert stats["level_distribution"] == {}
        assert stats["dimension_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        a = eng.create_assessment(organization="acme")
        eng.score_dimension(
            assessment_id=a.id,
            dimension=MaturityDimension.VISIBILITY,
            area=AssessmentArea.TAGGING,
            score=70.0,
        )
        eng.create_assessment(organization="acme")
        stats = eng.get_stats()
        assert stats["total_assessments"] == 2
        assert stats["total_dimension_scores"] == 1
        assert stats["organization_distribution"]["acme"] == 2
        assert stats["dimension_distribution"]["visibility"] == 1
