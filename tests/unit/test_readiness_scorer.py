"""Tests for shieldops.operations.readiness_scorer — OperationalReadinessScorer."""

from __future__ import annotations

from shieldops.operations.readiness_scorer import (
    AssessmentTrigger,
    OperationalReadinessScorer,
    ReadinessAssessment,
    ReadinessDimension,
    ReadinessGap,
    ReadinessGrade,
    ReadinessReport,
)


def _engine(**kw) -> OperationalReadinessScorer:
    return OperationalReadinessScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ReadinessDimension (5)
    def test_dimension_monitoring(self):
        assert ReadinessDimension.MONITORING == "monitoring"

    def test_dimension_runbooks(self):
        assert ReadinessDimension.RUNBOOKS == "runbooks"

    def test_dimension_oncall(self):
        assert ReadinessDimension.ONCALL == "oncall"

    def test_dimension_rollback(self):
        assert ReadinessDimension.ROLLBACK == "rollback"

    def test_dimension_documentation(self):
        assert ReadinessDimension.DOCUMENTATION == "documentation"

    # ReadinessGrade (5)
    def test_grade_excellent(self):
        assert ReadinessGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert ReadinessGrade.GOOD == "good"

    def test_grade_adequate(self):
        assert ReadinessGrade.ADEQUATE == "adequate"

    def test_grade_insufficient(self):
        assert ReadinessGrade.INSUFFICIENT == "insufficient"

    def test_grade_failing(self):
        assert ReadinessGrade.FAILING == "failing"

    # AssessmentTrigger (5)
    def test_trigger_pre_deployment(self):
        assert AssessmentTrigger.PRE_DEPLOYMENT == "pre_deployment"

    def test_trigger_scheduled(self):
        assert AssessmentTrigger.SCHEDULED == "scheduled"

    def test_trigger_post_incident(self):
        assert AssessmentTrigger.POST_INCIDENT == "post_incident"

    def test_trigger_business_event(self):
        assert AssessmentTrigger.BUSINESS_EVENT == "business_event"

    def test_trigger_manual(self):
        assert AssessmentTrigger.MANUAL == "manual"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_readiness_assessment_defaults(self):
        r = ReadinessAssessment()
        assert r.id
        assert r.service_name == ""
        assert r.dimension == ReadinessDimension.MONITORING
        assert r.grade == ReadinessGrade.ADEQUATE
        assert r.score == 0.0
        assert r.trigger == AssessmentTrigger.MANUAL
        assert r.assessor == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_readiness_gap_defaults(self):
        r = ReadinessGap()
        assert r.id
        assert r.service_name == ""
        assert r.dimension == ReadinessDimension.MONITORING
        assert r.current_grade == ReadinessGrade.FAILING
        assert r.target_grade == ReadinessGrade.GOOD
        assert r.remediation == ""
        assert r.priority == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_readiness_report_defaults(self):
        r = ReadinessReport()
        assert r.total_assessments == 0
        assert r.total_gaps == 0
        assert r.avg_score == 0.0
        assert r.by_dimension == {}
        assert r.by_grade == {}
        assert r.failing_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_assessment
# -------------------------------------------------------------------


class TestRecordAssessment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_assessment("payment-svc", score=85.0, grade=ReadinessGrade.GOOD)
        assert r.service_name == "payment-svc"
        assert r.score == 85.0
        assert r.grade == ReadinessGrade.GOOD

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_assessment(
            "auth-svc",
            dimension=ReadinessDimension.RUNBOOKS,
            grade=ReadinessGrade.EXCELLENT,
            score=95.0,
            trigger=AssessmentTrigger.PRE_DEPLOYMENT,
            assessor="alice",
            details="pre-deploy check",
        )
        assert r.dimension == ReadinessDimension.RUNBOOKS
        assert r.trigger == AssessmentTrigger.PRE_DEPLOYMENT
        assert r.assessor == "alice"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_assessment(f"svc-{i}", score=80.0)
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_assessment
# -------------------------------------------------------------------


class TestGetAssessment:
    def test_found(self):
        eng = _engine()
        r = eng.record_assessment("payment-svc", score=80.0)
        assert eng.get_assessment(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_assessment("nonexistent") is None


# -------------------------------------------------------------------
# list_assessments
# -------------------------------------------------------------------


class TestListAssessments:
    def test_list_all(self):
        eng = _engine()
        eng.record_assessment("svc-a", score=80.0)
        eng.record_assessment("svc-b", score=90.0)
        assert len(eng.list_assessments()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_assessment("svc-a", score=80.0)
        eng.record_assessment("svc-b", score=90.0)
        results = eng.list_assessments(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_assessment("s1", dimension=ReadinessDimension.MONITORING, score=80.0)
        eng.record_assessment("s2", dimension=ReadinessDimension.RUNBOOKS, score=90.0)
        results = eng.list_assessments(dimension=ReadinessDimension.MONITORING)
        assert len(results) == 1
        assert results[0].service_name == "s1"


# -------------------------------------------------------------------
# record_gap
# -------------------------------------------------------------------


class TestRecordGap:
    def test_basic(self):
        eng = _engine()
        gap = eng.record_gap(
            "payment-svc",
            dimension=ReadinessDimension.ROLLBACK,
            current_grade=ReadinessGrade.FAILING,
            target_grade=ReadinessGrade.GOOD,
            remediation="Add rollback scripts",
            priority=1,
        )
        assert gap.service_name == "payment-svc"
        assert gap.dimension == ReadinessDimension.ROLLBACK
        assert gap.priority == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_gap(f"svc-{i}")
        assert len(eng._gaps) == 2


# -------------------------------------------------------------------
# analyze_service_readiness
# -------------------------------------------------------------------


class TestAnalyzeServiceReadiness:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment(
            "payment-svc",
            score=85.0,
            grade=ReadinessGrade.GOOD,
            dimension=ReadinessDimension.MONITORING,
        )
        eng.record_assessment(
            "payment-svc",
            score=75.0,
            grade=ReadinessGrade.ADEQUATE,
            dimension=ReadinessDimension.RUNBOOKS,
        )
        result = eng.analyze_service_readiness("payment-svc")
        assert result["service_name"] == "payment-svc"
        assert result["total_assessments"] == 2
        assert result["avg_score"] == 80.0
        assert result["latest_grade"] == "adequate"
        assert result["latest_dimension"] == "runbooks"

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_service_readiness("ghost-svc")
        assert result["service_name"] == "ghost-svc"
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_failing_services
# -------------------------------------------------------------------


class TestIdentifyFailingServices:
    def test_with_failing(self):
        eng = _engine(min_readiness_score=70.0)
        eng.record_assessment("good-svc", score=85.0, grade=ReadinessGrade.GOOD)
        eng.record_assessment("bad-svc", score=50.0, grade=ReadinessGrade.FAILING)
        eng.record_assessment("worse-svc", score=30.0, grade=ReadinessGrade.FAILING)
        results = eng.identify_failing_services()
        assert len(results) == 2
        # Sorted by score ascending
        assert results[0]["service_name"] == "worse-svc"
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failing_services() == []


# -------------------------------------------------------------------
# rank_by_readiness_score
# -------------------------------------------------------------------


class TestRankByReadinessScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment("s1", score=60.0)
        eng.record_assessment("s2", score=90.0)
        eng.record_assessment("s3", score=75.0)
        results = eng.rank_by_readiness_score()
        assert len(results) == 3
        assert results[0]["service_name"] == "s2"
        assert results[0]["score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_readiness_score() == []


# -------------------------------------------------------------------
# detect_dimension_weaknesses
# -------------------------------------------------------------------


class TestDetectDimensionWeaknesses:
    def test_with_weaknesses(self):
        eng = _engine()
        eng.record_assessment("s1", grade=ReadinessGrade.GOOD, score=80.0)
        eng.record_assessment(
            "s2",
            grade=ReadinessGrade.INSUFFICIENT,
            score=45.0,
            dimension=ReadinessDimension.RUNBOOKS,
        )
        eng.record_assessment(
            "s3",
            grade=ReadinessGrade.FAILING,
            score=20.0,
            dimension=ReadinessDimension.ROLLBACK,
        )
        results = eng.detect_dimension_weaknesses()
        assert len(results) == 2
        grades = {r["grade"] for r in results}
        assert grades == {"insufficient", "failing"}

    def test_empty(self):
        eng = _engine()
        assert eng.detect_dimension_weaknesses() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_readiness_score=70.0)
        eng.record_assessment("s1", score=85.0, grade=ReadinessGrade.GOOD)
        eng.record_assessment("s2", score=40.0, grade=ReadinessGrade.FAILING)
        eng.record_gap("s2", dimension=ReadinessDimension.MONITORING)
        report = eng.generate_report()
        assert report.total_assessments == 2
        assert report.total_gaps == 1
        assert report.by_dimension != {}
        assert report.by_grade != {}
        assert report.failing_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_assessments == 0
        assert report.avg_score == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_assessment("s1", score=80.0)
        eng.record_gap("s1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._gaps) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_assessments"] == 0
        assert stats["total_gaps"] == 0
        assert stats["dimension_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_assessment("s1", dimension=ReadinessDimension.MONITORING, score=80.0)
        eng.record_assessment("s2", dimension=ReadinessDimension.RUNBOOKS, score=90.0)
        eng.record_gap("s1")
        stats = eng.get_stats()
        assert stats["total_assessments"] == 2
        assert stats["total_gaps"] == 1
        assert stats["unique_services"] == 2
        assert stats["min_readiness_score"] == 70.0
