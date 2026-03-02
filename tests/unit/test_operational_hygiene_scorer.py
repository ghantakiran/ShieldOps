"""Tests for shieldops.operations.operational_hygiene_scorer — OperationalHygieneScorer."""

from __future__ import annotations

from shieldops.operations.operational_hygiene_scorer import (
    HygieneAssessment,
    HygieneDimension,
    HygieneGrade,
    HygieneRecord,
    OperationalHygieneReport,
    OperationalHygieneScorer,
    RemediationPriority,
)


def _engine(**kw) -> OperationalHygieneScorer:
    return OperationalHygieneScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dimension_runbook_freshness(self):
        assert HygieneDimension.RUNBOOK_FRESHNESS == "runbook_freshness"

    def test_dimension_alert_coverage(self):
        assert HygieneDimension.ALERT_COVERAGE == "alert_coverage"

    def test_dimension_documentation(self):
        assert HygieneDimension.DOCUMENTATION == "documentation"

    def test_dimension_oncall_health(self):
        assert HygieneDimension.ONCALL_HEALTH == "oncall_health"

    def test_dimension_config_drift(self):
        assert HygieneDimension.CONFIG_DRIFT == "config_drift"

    def test_grade_excellent(self):
        assert HygieneGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert HygieneGrade.GOOD == "good"

    def test_grade_acceptable(self):
        assert HygieneGrade.ACCEPTABLE == "acceptable"

    def test_grade_poor(self):
        assert HygieneGrade.POOR == "poor"

    def test_grade_critical(self):
        assert HygieneGrade.CRITICAL == "critical"

    def test_priority_immediate(self):
        assert RemediationPriority.IMMEDIATE == "immediate"

    def test_priority_this_sprint(self):
        assert RemediationPriority.THIS_SPRINT == "this_sprint"

    def test_priority_next_sprint(self):
        assert RemediationPriority.NEXT_SPRINT == "next_sprint"

    def test_priority_quarterly(self):
        assert RemediationPriority.QUARTERLY == "quarterly"

    def test_priority_backlog(self):
        assert RemediationPriority.BACKLOG == "backlog"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_hygiene_record_defaults(self):
        r = HygieneRecord()
        assert r.id
        assert r.service_name == ""
        assert r.hygiene_dimension == HygieneDimension.RUNBOOK_FRESHNESS
        assert r.hygiene_grade == HygieneGrade.EXCELLENT
        assert r.remediation_priority == RemediationPriority.IMMEDIATE
        assert r.hygiene_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_hygiene_assessment_defaults(self):
        a = HygieneAssessment()
        assert a.id
        assert a.service_name == ""
        assert a.hygiene_dimension == HygieneDimension.RUNBOOK_FRESHNESS
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_operational_hygiene_report_defaults(self):
        r = OperationalHygieneReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.poor_hygiene_count == 0
        assert r.avg_hygiene_score == 0.0
        assert r.by_dimension == {}
        assert r.by_grade == {}
        assert r.by_priority == {}
        assert r.top_poor_hygiene == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_hygiene
# ---------------------------------------------------------------------------


class TestRecordHygiene:
    def test_basic(self):
        eng = _engine()
        r = eng.record_hygiene(
            service_name="payment-svc",
            hygiene_dimension=HygieneDimension.ALERT_COVERAGE,
            hygiene_grade=HygieneGrade.GOOD,
            remediation_priority=RemediationPriority.THIS_SPRINT,
            hygiene_score=75.0,
            service="api-gw",
            team="sre",
        )
        assert r.service_name == "payment-svc"
        assert r.hygiene_dimension == HygieneDimension.ALERT_COVERAGE
        assert r.hygiene_grade == HygieneGrade.GOOD
        assert r.remediation_priority == RemediationPriority.THIS_SPRINT
        assert r.hygiene_score == 75.0
        assert r.service == "api-gw"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_hygiene(service_name=f"SVC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_hygiene
# ---------------------------------------------------------------------------


class TestGetHygiene:
    def test_found(self):
        eng = _engine()
        r = eng.record_hygiene(
            service_name="payment-svc",
            hygiene_grade=HygieneGrade.POOR,
        )
        result = eng.get_hygiene(r.id)
        assert result is not None
        assert result.hygiene_grade == HygieneGrade.POOR

    def test_not_found(self):
        eng = _engine()
        assert eng.get_hygiene("nonexistent") is None


# ---------------------------------------------------------------------------
# list_hygiene_records
# ---------------------------------------------------------------------------


class TestListHygieneRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_hygiene(service_name="SVC-001")
        eng.record_hygiene(service_name="SVC-002")
        assert len(eng.list_hygiene_records()) == 2

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_hygiene(
            service_name="SVC-001",
            hygiene_dimension=HygieneDimension.RUNBOOK_FRESHNESS,
        )
        eng.record_hygiene(
            service_name="SVC-002",
            hygiene_dimension=HygieneDimension.ALERT_COVERAGE,
        )
        results = eng.list_hygiene_records(
            hygiene_dimension=HygieneDimension.RUNBOOK_FRESHNESS,
        )
        assert len(results) == 1

    def test_filter_by_grade(self):
        eng = _engine()
        eng.record_hygiene(
            service_name="SVC-001",
            hygiene_grade=HygieneGrade.EXCELLENT,
        )
        eng.record_hygiene(
            service_name="SVC-002",
            hygiene_grade=HygieneGrade.POOR,
        )
        results = eng.list_hygiene_records(hygiene_grade=HygieneGrade.EXCELLENT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_hygiene(service_name="SVC-001", team="sre")
        eng.record_hygiene(service_name="SVC-002", team="platform")
        results = eng.list_hygiene_records(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_hygiene(service_name=f"SVC-{i}")
        assert len(eng.list_hygiene_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            service_name="payment-svc",
            hygiene_dimension=HygieneDimension.DOCUMENTATION,
            assessment_score=45.0,
            threshold=60.0,
            breached=True,
            description="documentation stale",
        )
        assert a.service_name == "payment-svc"
        assert a.hygiene_dimension == HygieneDimension.DOCUMENTATION
        assert a.assessment_score == 45.0
        assert a.threshold == 60.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(service_name=f"SVC-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_hygiene_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeHygieneDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_hygiene(
            service_name="SVC-001",
            hygiene_dimension=HygieneDimension.RUNBOOK_FRESHNESS,
            hygiene_score=80.0,
        )
        eng.record_hygiene(
            service_name="SVC-002",
            hygiene_dimension=HygieneDimension.RUNBOOK_FRESHNESS,
            hygiene_score=60.0,
        )
        result = eng.analyze_hygiene_distribution()
        assert "runbook_freshness" in result
        assert result["runbook_freshness"]["count"] == 2
        assert result["runbook_freshness"]["avg_hygiene_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_hygiene_distribution() == {}


# ---------------------------------------------------------------------------
# identify_poor_hygiene
# ---------------------------------------------------------------------------


class TestIdentifyPoorHygiene:
    def test_detects_below_threshold(self):
        eng = _engine(min_hygiene_score=60.0)
        eng.record_hygiene(service_name="SVC-001", hygiene_score=40.0)
        eng.record_hygiene(service_name="SVC-002", hygiene_score=80.0)
        results = eng.identify_poor_hygiene()
        assert len(results) == 1
        assert results[0]["service_name"] == "SVC-001"

    def test_sorted_ascending(self):
        eng = _engine(min_hygiene_score=60.0)
        eng.record_hygiene(service_name="SVC-001", hygiene_score=50.0)
        eng.record_hygiene(service_name="SVC-002", hygiene_score=30.0)
        results = eng.identify_poor_hygiene()
        assert len(results) == 2
        assert results[0]["hygiene_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_hygiene() == []


# ---------------------------------------------------------------------------
# rank_by_hygiene
# ---------------------------------------------------------------------------


class TestRankByHygiene:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_hygiene(service_name="SVC-001", service="api-gw", hygiene_score=90.0)
        eng.record_hygiene(service_name="SVC-002", service="auth", hygiene_score=40.0)
        results = eng.rank_by_hygiene()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_hygiene_score"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_hygiene() == []


# ---------------------------------------------------------------------------
# detect_hygiene_trends
# ---------------------------------------------------------------------------


class TestDetectHygieneTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(service_name="SVC-001", assessment_score=50.0)
        result = eng.detect_hygiene_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(service_name="SVC-001", assessment_score=20.0)
        eng.add_assessment(service_name="SVC-002", assessment_score=20.0)
        eng.add_assessment(service_name="SVC-003", assessment_score=80.0)
        eng.add_assessment(service_name="SVC-004", assessment_score=80.0)
        result = eng.detect_hygiene_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_hygiene_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_hygiene_score=60.0)
        eng.record_hygiene(
            service_name="payment-svc",
            hygiene_dimension=HygieneDimension.ALERT_COVERAGE,
            hygiene_grade=HygieneGrade.POOR,
            remediation_priority=RemediationPriority.IMMEDIATE,
            hygiene_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, OperationalHygieneReport)
        assert report.total_records == 1
        assert report.poor_hygiene_count == 1
        assert len(report.top_poor_hygiene) == 1
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
        eng.record_hygiene(service_name="SVC-001")
        eng.add_assessment(service_name="SVC-001")
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
        eng.record_hygiene(
            service_name="SVC-001",
            hygiene_dimension=HygieneDimension.RUNBOOK_FRESHNESS,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "runbook_freshness" in stats["dimension_distribution"]
