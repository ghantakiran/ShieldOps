"""Tests for shieldops.operations.operational_readiness — OperationalReadinessScorer."""

from __future__ import annotations

from shieldops.operations.operational_readiness import (
    OperationalReadinessReport,
    OperationalReadinessScorer,
    ReadinessCategory,
    ReadinessCheckpoint,
    ReadinessGrade,
    ReadinessMaturity,
    ReadinessRecord,
)


def _engine(**kw) -> OperationalReadinessScorer:
    return OperationalReadinessScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_monitoring(self):
        assert ReadinessCategory.MONITORING == "monitoring"

    def test_category_alerting(self):
        assert ReadinessCategory.ALERTING == "alerting"

    def test_category_runbooks(self):
        assert ReadinessCategory.RUNBOOKS == "runbooks"

    def test_category_incident_response(self):
        assert ReadinessCategory.INCIDENT_RESPONSE == "incident_response"

    def test_category_capacity_planning(self):
        assert ReadinessCategory.CAPACITY_PLANNING == "capacity_planning"

    def test_grade_excellent(self):
        assert ReadinessGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert ReadinessGrade.GOOD == "good"

    def test_grade_adequate(self):
        assert ReadinessGrade.ADEQUATE == "adequate"

    def test_grade_poor(self):
        assert ReadinessGrade.POOR == "poor"

    def test_grade_failing(self):
        assert ReadinessGrade.FAILING == "failing"

    def test_maturity_advanced(self):
        assert ReadinessMaturity.ADVANCED == "advanced"

    def test_maturity_mature(self):
        assert ReadinessMaturity.MATURE == "mature"

    def test_maturity_developing(self):
        assert ReadinessMaturity.DEVELOPING == "developing"

    def test_maturity_basic(self):
        assert ReadinessMaturity.BASIC == "basic"

    def test_maturity_none(self):
        assert ReadinessMaturity.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_readiness_record_defaults(self):
        r = ReadinessRecord()
        assert r.id
        assert r.assessment_id == ""
        assert r.readiness_category == ReadinessCategory.MONITORING
        assert r.readiness_grade == ReadinessGrade.ADEQUATE
        assert r.readiness_maturity == ReadinessMaturity.BASIC
        assert r.readiness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_readiness_checkpoint_defaults(self):
        c = ReadinessCheckpoint()
        assert c.id
        assert c.assessment_id == ""
        assert c.readiness_category == ReadinessCategory.MONITORING
        assert c.checkpoint_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_operational_readiness_report_defaults(self):
        r = OperationalReadinessReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_checkpoints == 0
        assert r.failing_count == 0
        assert r.avg_readiness_score == 0.0
        assert r.by_category == {}
        assert r.by_grade == {}
        assert r.by_maturity == {}
        assert r.top_failing == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_readiness
# ---------------------------------------------------------------------------


class TestRecordReadiness:
    def test_basic(self):
        eng = _engine()
        r = eng.record_readiness(
            assessment_id="ASS-001",
            readiness_category=ReadinessCategory.MONITORING,
            readiness_grade=ReadinessGrade.EXCELLENT,
            readiness_maturity=ReadinessMaturity.ADVANCED,
            readiness_score=95.0,
            service="api-gateway",
            team="sre",
        )
        assert r.assessment_id == "ASS-001"
        assert r.readiness_category == ReadinessCategory.MONITORING
        assert r.readiness_grade == ReadinessGrade.EXCELLENT
        assert r.readiness_maturity == ReadinessMaturity.ADVANCED
        assert r.readiness_score == 95.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_readiness(assessment_id=f"ASS-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_readiness
# ---------------------------------------------------------------------------


class TestGetReadiness:
    def test_found(self):
        eng = _engine()
        r = eng.record_readiness(
            assessment_id="ASS-001",
            readiness_grade=ReadinessGrade.EXCELLENT,
        )
        result = eng.get_readiness(r.id)
        assert result is not None
        assert result.readiness_grade == ReadinessGrade.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_readiness("nonexistent") is None


# ---------------------------------------------------------------------------
# list_readiness
# ---------------------------------------------------------------------------


class TestListReadiness:
    def test_list_all(self):
        eng = _engine()
        eng.record_readiness(assessment_id="ASS-001")
        eng.record_readiness(assessment_id="ASS-002")
        assert len(eng.list_readiness()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_readiness(
            assessment_id="ASS-001",
            readiness_category=ReadinessCategory.MONITORING,
        )
        eng.record_readiness(
            assessment_id="ASS-002",
            readiness_category=ReadinessCategory.ALERTING,
        )
        results = eng.list_readiness(
            category=ReadinessCategory.MONITORING,
        )
        assert len(results) == 1

    def test_filter_by_grade(self):
        eng = _engine()
        eng.record_readiness(
            assessment_id="ASS-001",
            readiness_grade=ReadinessGrade.EXCELLENT,
        )
        eng.record_readiness(
            assessment_id="ASS-002",
            readiness_grade=ReadinessGrade.FAILING,
        )
        results = eng.list_readiness(
            grade=ReadinessGrade.EXCELLENT,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_readiness(assessment_id="ASS-001", service="api-gateway")
        eng.record_readiness(assessment_id="ASS-002", service="auth-svc")
        results = eng.list_readiness(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_readiness(assessment_id="ASS-001", team="sre")
        eng.record_readiness(assessment_id="ASS-002", team="platform")
        results = eng.list_readiness(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_readiness(assessment_id=f"ASS-{i}")
        assert len(eng.list_readiness(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_checkpoint
# ---------------------------------------------------------------------------


class TestAddCheckpoint:
    def test_basic(self):
        eng = _engine()
        c = eng.add_checkpoint(
            assessment_id="ASS-001",
            readiness_category=ReadinessCategory.ALERTING,
            checkpoint_score=65.0,
            threshold=70.0,
            breached=True,
            description="Alerting coverage below threshold",
        )
        assert c.assessment_id == "ASS-001"
        assert c.readiness_category == ReadinessCategory.ALERTING
        assert c.checkpoint_score == 65.0
        assert c.threshold == 70.0
        assert c.breached is True
        assert c.description == "Alerting coverage below threshold"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_checkpoint(assessment_id=f"ASS-{i}")
        assert len(eng._checkpoints) == 2


# ---------------------------------------------------------------------------
# analyze_readiness_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeReadinessDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_readiness(
            assessment_id="ASS-001",
            readiness_category=ReadinessCategory.MONITORING,
            readiness_score=80.0,
        )
        eng.record_readiness(
            assessment_id="ASS-002",
            readiness_category=ReadinessCategory.MONITORING,
            readiness_score=60.0,
        )
        result = eng.analyze_readiness_distribution()
        assert "monitoring" in result
        assert result["monitoring"]["count"] == 2
        assert result["monitoring"]["avg_readiness_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_readiness_distribution() == {}


# ---------------------------------------------------------------------------
# identify_failing_services
# ---------------------------------------------------------------------------


class TestIdentifyFailingServices:
    def test_detects_failing(self):
        eng = _engine()
        eng.record_readiness(
            assessment_id="ASS-001",
            readiness_grade=ReadinessGrade.FAILING,
        )
        eng.record_readiness(
            assessment_id="ASS-002",
            readiness_grade=ReadinessGrade.EXCELLENT,
        )
        results = eng.identify_failing_services()
        assert len(results) == 1
        assert results[0]["assessment_id"] == "ASS-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failing_services() == []


# ---------------------------------------------------------------------------
# rank_by_readiness_score
# ---------------------------------------------------------------------------


class TestRankByReadinessScore:
    def test_ranked(self):
        eng = _engine()
        eng.record_readiness(
            assessment_id="ASS-001",
            service="api-gateway",
            readiness_score=90.0,
        )
        eng.record_readiness(
            assessment_id="ASS-002",
            service="auth-svc",
            readiness_score=40.0,
        )
        eng.record_readiness(
            assessment_id="ASS-003",
            service="api-gateway",
            readiness_score=70.0,
        )
        results = eng.rank_by_readiness_score()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"
        assert results[0]["avg_readiness_score"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_readiness_score() == []


# ---------------------------------------------------------------------------
# detect_readiness_trends
# ---------------------------------------------------------------------------


class TestDetectReadinessTrends:
    def test_stable(self):
        eng = _engine()
        for val in [50.0, 50.0, 50.0, 50.0]:
            eng.add_checkpoint(assessment_id="ASS-1", checkpoint_score=val)
        result = eng.detect_readiness_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [30.0, 30.0, 60.0, 60.0]:
            eng.add_checkpoint(assessment_id="ASS-1", checkpoint_score=val)
        result = eng.detect_readiness_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_readiness_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_readiness(
            assessment_id="ASS-001",
            readiness_category=ReadinessCategory.MONITORING,
            readiness_grade=ReadinessGrade.FAILING,
            readiness_maturity=ReadinessMaturity.NONE,
            readiness_score=20.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, OperationalReadinessReport)
        assert report.total_records == 1
        assert report.failing_count == 1
        assert len(report.top_failing) >= 1
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
        eng.record_readiness(assessment_id="ASS-001")
        eng.add_checkpoint(assessment_id="ASS-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._checkpoints) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_checkpoints"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_readiness(
            assessment_id="ASS-001",
            readiness_category=ReadinessCategory.MONITORING,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "monitoring" in stats["category_distribution"]
