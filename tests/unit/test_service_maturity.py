"""Tests for shieldops.topology.service_maturity — ServiceMaturityModel.

Covers:
- MaturityLevel, MaturityDimension, AssessmentStatus enums
- MaturityAssessment, MaturityScore, MaturityModelReport defaults
- create_assessment (basic, unique IDs, extra fields, eviction)
- get_assessment (found, not found)
- list_assessments (all, filter service, filter dimension, limit)
- calculate_maturity_score (basic, no assessments)
- identify_maturity_gaps (gaps, no gaps)
- rank_services_by_maturity (multiple, single)
- track_maturity_trend (basic, empty)
- generate_improvement_plan (with gaps, no gaps)
- generate_maturity_report (populated, empty)
- clear_data (basic)
- get_stats (empty, populated)
"""

from __future__ import annotations

from shieldops.topology.service_maturity import (
    AssessmentStatus,
    MaturityAssessment,
    MaturityDimension,
    MaturityLevel,
    MaturityModelReport,
    MaturityScore,
    ServiceMaturityModel,
)


def _engine(**kw) -> ServiceMaturityModel:
    return ServiceMaturityModel(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # MaturityLevel (5 values)

    def test_level_initial(self):
        assert MaturityLevel.INITIAL == "initial"

    def test_level_developing(self):
        assert MaturityLevel.DEVELOPING == "developing"

    def test_level_defined(self):
        assert MaturityLevel.DEFINED == "defined"

    def test_level_managed(self):
        assert MaturityLevel.MANAGED == "managed"

    def test_level_optimized(self):
        assert MaturityLevel.OPTIMIZED == "optimized"

    # MaturityDimension (5 values)

    def test_dimension_observability(self):
        assert MaturityDimension.OBSERVABILITY == ("observability")

    def test_dimension_reliability(self):
        assert MaturityDimension.RELIABILITY == "reliability"

    def test_dimension_security(self):
        assert MaturityDimension.SECURITY == "security"

    def test_dimension_operations(self):
        assert MaturityDimension.OPERATIONS == "operations"

    def test_dimension_documentation(self):
        assert MaturityDimension.DOCUMENTATION == ("documentation")

    # AssessmentStatus (5 values)

    def test_status_draft(self):
        assert AssessmentStatus.DRAFT == "draft"

    def test_status_in_progress(self):
        assert AssessmentStatus.IN_PROGRESS == "in_progress"

    def test_status_completed(self):
        assert AssessmentStatus.COMPLETED == "completed"

    def test_status_reviewed(self):
        assert AssessmentStatus.REVIEWED == "reviewed"

    def test_status_archived(self):
        assert AssessmentStatus.ARCHIVED == "archived"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_maturity_assessment_defaults(self):
        a = MaturityAssessment(service_name="api-gw")
        assert a.id
        assert a.service_name == "api-gw"
        assert a.dimension == (MaturityDimension.OBSERVABILITY)
        assert a.level == MaturityLevel.INITIAL
        assert a.score == 0.0
        assert a.evidence == []
        assert a.assessor == ""
        assert a.status == AssessmentStatus.DRAFT
        assert a.assessed_at > 0
        assert a.created_at > 0

    def test_maturity_score_defaults(self):
        s = MaturityScore(service_name="api-gw")
        assert s.service_name == "api-gw"
        assert s.overall_level == MaturityLevel.INITIAL
        assert s.overall_score == 0.0
        assert s.by_dimension == {}
        assert s.gaps == []
        assert s.created_at > 0

    def test_maturity_report_defaults(self):
        r = MaturityModelReport()
        assert r.total_assessments == 0
        assert r.total_services == 0
        assert r.avg_maturity_score == 0.0
        assert r.by_level == {}
        assert r.by_dimension == {}
        assert r.low_maturity_services == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# create_assessment
# -------------------------------------------------------------------


class TestCreateAssessment:
    def test_basic(self):
        e = _engine()
        a = e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.SECURITY,
            level=MaturityLevel.DEFINED,
        )
        assert a.service_name == "api-gw"
        assert a.dimension == MaturityDimension.SECURITY
        assert a.level == MaturityLevel.DEFINED
        assert a.score == 3.0

    def test_unique_ids(self):
        e = _engine()
        a1 = e.create_assessment(service_name="a")
        a2 = e.create_assessment(service_name="b")
        assert a1.id != a2.id

    def test_extra_fields(self):
        e = _engine()
        a = e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.RELIABILITY,
            level=MaturityLevel.MANAGED,
            evidence=["SLO defined", "Circuit breakers"],
            assessor="alice",
            status=AssessmentStatus.COMPLETED,
        )
        assert a.evidence == [
            "SLO defined",
            "Circuit breakers",
        ]
        assert a.assessor == "alice"
        assert a.status == AssessmentStatus.COMPLETED
        assert a.score == 4.0

    def test_evicts_at_max(self):
        e = _engine(max_assessments=2)
        a1 = e.create_assessment(service_name="a")
        e.create_assessment(service_name="b")
        e.create_assessment(service_name="c")
        items = e.list_assessments()
        ids = {a.id for a in items}
        assert a1.id not in ids
        assert len(items) == 2


# -------------------------------------------------------------------
# get_assessment
# -------------------------------------------------------------------


class TestGetAssessment:
    def test_found(self):
        e = _engine()
        a = e.create_assessment(service_name="api-gw")
        assert e.get_assessment(a.id) is not None
        assert e.get_assessment(a.id).service_name == ("api-gw")

    def test_not_found(self):
        e = _engine()
        assert e.get_assessment("nonexistent") is None


# -------------------------------------------------------------------
# list_assessments
# -------------------------------------------------------------------


class TestListAssessments:
    def test_list_all(self):
        e = _engine()
        e.create_assessment(service_name="a")
        e.create_assessment(service_name="b")
        e.create_assessment(service_name="c")
        assert len(e.list_assessments()) == 3

    def test_filter_by_service(self):
        e = _engine()
        e.create_assessment(service_name="api-gw")
        e.create_assessment(service_name="auth-svc")
        filtered = e.list_assessments(service_name="api-gw")
        assert len(filtered) == 1
        assert filtered[0].service_name == "api-gw"

    def test_filter_by_dimension(self):
        e = _engine()
        e.create_assessment(
            service_name="a",
            dimension=MaturityDimension.SECURITY,
        )
        e.create_assessment(
            service_name="b",
            dimension=MaturityDimension.RELIABILITY,
        )
        filtered = e.list_assessments(dimension=MaturityDimension.SECURITY)
        assert len(filtered) == 1

    def test_limit(self):
        e = _engine()
        for i in range(10):
            e.create_assessment(service_name=f"svc-{i}")
        assert len(e.list_assessments(limit=3)) == 3


# -------------------------------------------------------------------
# calculate_maturity_score
# -------------------------------------------------------------------


class TestCalculateMaturityScore:
    def test_basic(self):
        e = _engine()
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.SECURITY,
            level=MaturityLevel.DEFINED,
        )
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.RELIABILITY,
            level=MaturityLevel.MANAGED,
        )
        score = e.calculate_maturity_score("api-gw")
        assert score.service_name == "api-gw"
        assert score.overall_score == 3.5
        assert score.overall_level == MaturityLevel.MANAGED
        assert "security" in score.by_dimension
        assert "reliability" in score.by_dimension

    def test_no_assessments(self):
        e = _engine()
        score = e.calculate_maturity_score("unknown")
        assert score.overall_score == 0.0
        assert score.overall_level == MaturityLevel.INITIAL


# -------------------------------------------------------------------
# identify_maturity_gaps
# -------------------------------------------------------------------


class TestIdentifyMaturityGaps:
    def test_gaps(self):
        e = _engine(target_maturity_level=3)
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.SECURITY,
            level=MaturityLevel.INITIAL,
        )
        gaps = e.identify_maturity_gaps("api-gw")
        assert len(gaps) >= 1
        sec_gap = [g for g in gaps if g["dimension"] == "security"]
        assert len(sec_gap) == 1
        assert sec_gap[0]["gap"] == 2.0

    def test_no_gaps(self):
        e = _engine(target_maturity_level=1)
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.SECURITY,
            level=MaturityLevel.INITIAL,
        )
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.RELIABILITY,
            level=MaturityLevel.DEFINED,
        )
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.OBSERVABILITY,
            level=MaturityLevel.MANAGED,
        )
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.OPERATIONS,
            level=MaturityLevel.DEVELOPING,
        )
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.DOCUMENTATION,
            level=MaturityLevel.DEFINED,
        )
        gaps = e.identify_maturity_gaps("api-gw")
        assert len(gaps) == 0


# -------------------------------------------------------------------
# rank_services_by_maturity
# -------------------------------------------------------------------


class TestRankServicesByMaturity:
    def test_multiple(self):
        e = _engine()
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.SECURITY,
            level=MaturityLevel.OPTIMIZED,
        )
        e.create_assessment(
            service_name="auth-svc",
            dimension=MaturityDimension.SECURITY,
            level=MaturityLevel.INITIAL,
        )
        rankings = e.rank_services_by_maturity()
        assert len(rankings) == 2
        assert rankings[0]["service_name"] == "api-gw"
        assert rankings[0]["overall_score"] > (rankings[1]["overall_score"])

    def test_single(self):
        e = _engine()
        e.create_assessment(
            service_name="api-gw",
            level=MaturityLevel.DEFINED,
        )
        rankings = e.rank_services_by_maturity()
        assert len(rankings) == 1


# -------------------------------------------------------------------
# track_maturity_trend
# -------------------------------------------------------------------


class TestTrackMaturityTrend:
    def test_basic(self):
        e = _engine()
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.SECURITY,
            level=MaturityLevel.INITIAL,
        )
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.SECURITY,
            level=MaturityLevel.DEFINED,
        )
        trend = e.track_maturity_trend("api-gw")
        assert len(trend) == 2
        assert trend[0]["level"] == "initial"
        assert trend[1]["level"] == "defined"

    def test_empty(self):
        e = _engine()
        trend = e.track_maturity_trend("unknown")
        assert trend == []


# -------------------------------------------------------------------
# generate_improvement_plan
# -------------------------------------------------------------------


class TestGenerateImprovementPlan:
    def test_with_gaps(self):
        e = _engine(target_maturity_level=4)
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.SECURITY,
            level=MaturityLevel.INITIAL,
        )
        plan = e.generate_improvement_plan("api-gw")
        assert plan["service_name"] == "api-gw"
        assert plan["target_score"] == 4.0
        assert plan["total_gaps"] > 0
        assert len(plan["actions"]) > 0
        sec = [a for a in plan["actions"] if a["dimension"] == "security"]
        assert sec[0]["priority"] == "high"

    def test_no_gaps(self):
        e = _engine(target_maturity_level=1)
        for dim in MaturityDimension:
            e.create_assessment(
                service_name="api-gw",
                dimension=dim,
                level=MaturityLevel.OPTIMIZED,
            )
        plan = e.generate_improvement_plan("api-gw")
        assert plan["total_gaps"] == 0
        assert plan["actions"] == []


# -------------------------------------------------------------------
# generate_maturity_report
# -------------------------------------------------------------------


class TestGenerateMaturityReport:
    def test_populated(self):
        e = _engine()
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.SECURITY,
            level=MaturityLevel.DEFINED,
        )
        e.create_assessment(
            service_name="auth-svc",
            dimension=MaturityDimension.RELIABILITY,
            level=MaturityLevel.INITIAL,
        )
        report = e.generate_maturity_report()
        assert report.total_assessments == 2
        assert report.total_services == 2
        assert "defined" in report.by_level
        assert "security" in report.by_dimension
        assert len(report.recommendations) > 0

    def test_empty(self):
        e = _engine()
        report = e.generate_maturity_report()
        assert report.total_assessments == 0
        assert report.total_services == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_basic(self):
        e = _engine()
        e.create_assessment(service_name="a")
        e.create_assessment(service_name="b")
        count = e.clear_data()
        assert count == 2
        assert e.list_assessments() == []


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_assessments"] == 0
        assert stats["total_services"] == 0
        assert stats["max_assessments"] == 100000
        assert stats["target_maturity_level"] == 3
        assert stats["dimension_distribution"] == {}

    def test_populated(self):
        e = _engine()
        e.create_assessment(
            service_name="api-gw",
            dimension=MaturityDimension.SECURITY,
        )
        e.create_assessment(
            service_name="auth-svc",
            dimension=MaturityDimension.RELIABILITY,
        )
        stats = e.get_stats()
        assert stats["total_assessments"] == 2
        assert stats["total_services"] == 2
        assert "security" in stats["dimension_distribution"]
        assert "reliability" in stats["dimension_distribution"]
