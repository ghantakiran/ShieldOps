"""Tests for shieldops.operations.team_capacity_planner — TeamCapacityPlanner."""

from __future__ import annotations

from shieldops.operations.team_capacity_planner import (
    BurnoutRisk,
    CapacityAssessment,
    CapacityRecord,
    CapacityStatus,
    LoadCategory,
    TeamCapacityPlanner,
    TeamCapacityReport,
)


def _engine(**kw) -> TeamCapacityPlanner:
    return TeamCapacityPlanner(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_available(self):
        assert CapacityStatus.AVAILABLE == "available"

    def test_status_loaded(self):
        assert CapacityStatus.LOADED == "loaded"

    def test_status_overloaded(self):
        assert CapacityStatus.OVERLOADED == "overloaded"

    def test_status_critical(self):
        assert CapacityStatus.CRITICAL == "critical"

    def test_status_unknown(self):
        assert CapacityStatus.UNKNOWN == "unknown"

    def test_category_incident_response(self):
        assert LoadCategory.INCIDENT_RESPONSE == "incident_response"

    def test_category_toil(self):
        assert LoadCategory.TOIL == "toil"

    def test_category_project_work(self):
        assert LoadCategory.PROJECT_WORK == "project_work"

    def test_category_on_call(self):
        assert LoadCategory.ON_CALL == "on_call"

    def test_category_training(self):
        assert LoadCategory.TRAINING == "training"

    def test_risk_minimal(self):
        assert BurnoutRisk.MINIMAL == "minimal"

    def test_risk_low(self):
        assert BurnoutRisk.LOW == "low"

    def test_risk_moderate(self):
        assert BurnoutRisk.MODERATE == "moderate"

    def test_risk_high(self):
        assert BurnoutRisk.HIGH == "high"

    def test_risk_critical(self):
        assert BurnoutRisk.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_capacity_record_defaults(self):
        r = CapacityRecord()
        assert r.id
        assert r.team_name == ""
        assert r.capacity_status == CapacityStatus.AVAILABLE
        assert r.load_category == LoadCategory.INCIDENT_RESPONSE
        assert r.burnout_risk == BurnoutRisk.MINIMAL
        assert r.utilization_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_capacity_assessment_defaults(self):
        a = CapacityAssessment()
        assert a.id
        assert a.team_name == ""
        assert a.capacity_status == CapacityStatus.AVAILABLE
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_team_capacity_report_defaults(self):
        r = TeamCapacityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.overloaded_count == 0
        assert r.avg_utilization_score == 0.0
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.by_risk == {}
        assert r.top_overloaded == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_capacity
# ---------------------------------------------------------------------------


class TestRecordCapacity:
    def test_basic(self):
        eng = _engine()
        r = eng.record_capacity(
            team_name="sre-team",
            capacity_status=CapacityStatus.OVERLOADED,
            load_category=LoadCategory.INCIDENT_RESPONSE,
            burnout_risk=BurnoutRisk.HIGH,
            utilization_score=92.0,
            service="api-gw",
            team="sre",
        )
        assert r.team_name == "sre-team"
        assert r.capacity_status == CapacityStatus.OVERLOADED
        assert r.load_category == LoadCategory.INCIDENT_RESPONSE
        assert r.burnout_risk == BurnoutRisk.HIGH
        assert r.utilization_score == 92.0
        assert r.service == "api-gw"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_capacity(team_name=f"team-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_capacity
# ---------------------------------------------------------------------------


class TestGetCapacity:
    def test_found(self):
        eng = _engine()
        r = eng.record_capacity(
            team_name="sre-team",
            burnout_risk=BurnoutRisk.CRITICAL,
        )
        result = eng.get_capacity(r.id)
        assert result is not None
        assert result.burnout_risk == BurnoutRisk.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_capacity("nonexistent") is None


# ---------------------------------------------------------------------------
# list_capacity_records
# ---------------------------------------------------------------------------


class TestListCapacityRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_capacity(team_name="team-1")
        eng.record_capacity(team_name="team-2")
        assert len(eng.list_capacity_records()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_capacity(
            team_name="team-1",
            capacity_status=CapacityStatus.AVAILABLE,
        )
        eng.record_capacity(
            team_name="team-2",
            capacity_status=CapacityStatus.OVERLOADED,
        )
        results = eng.list_capacity_records(capacity_status=CapacityStatus.AVAILABLE)
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_capacity(
            team_name="team-1",
            load_category=LoadCategory.INCIDENT_RESPONSE,
        )
        eng.record_capacity(
            team_name="team-2",
            load_category=LoadCategory.TOIL,
        )
        results = eng.list_capacity_records(load_category=LoadCategory.INCIDENT_RESPONSE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_capacity(team_name="team-1", team="sre")
        eng.record_capacity(team_name="team-2", team="platform")
        results = eng.list_capacity_records(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_capacity(team_name=f"team-{i}")
        assert len(eng.list_capacity_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            team_name="sre-team",
            capacity_status=CapacityStatus.OVERLOADED,
            assessment_score=88.5,
            threshold=80.0,
            breached=True,
            description="utilization threshold exceeded",
        )
        assert a.team_name == "sre-team"
        assert a.capacity_status == CapacityStatus.OVERLOADED
        assert a.assessment_score == 88.5
        assert a.threshold == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(team_name=f"team-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_capacity_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCapacityDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_capacity(
            team_name="team-1",
            capacity_status=CapacityStatus.AVAILABLE,
            utilization_score=40.0,
        )
        eng.record_capacity(
            team_name="team-2",
            capacity_status=CapacityStatus.AVAILABLE,
            utilization_score=60.0,
        )
        result = eng.analyze_capacity_distribution()
        assert "available" in result
        assert result["available"]["count"] == 2
        assert result["available"]["avg_utilization_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_capacity_distribution() == {}


# ---------------------------------------------------------------------------
# identify_overloaded_teams
# ---------------------------------------------------------------------------


class TestIdentifyOverloadedTeams:
    def test_detects_above_threshold(self):
        eng = _engine(capacity_utilization_threshold=80.0)
        eng.record_capacity(team_name="team-1", utilization_score=90.0)
        eng.record_capacity(team_name="team-2", utilization_score=50.0)
        results = eng.identify_overloaded_teams()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-1"

    def test_sorted_descending(self):
        eng = _engine(capacity_utilization_threshold=30.0)
        eng.record_capacity(team_name="team-1", utilization_score=50.0)
        eng.record_capacity(team_name="team-2", utilization_score=90.0)
        results = eng.identify_overloaded_teams()
        assert len(results) == 2
        assert results[0]["utilization_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overloaded_teams() == []


# ---------------------------------------------------------------------------
# rank_by_utilization
# ---------------------------------------------------------------------------


class TestRankByUtilization:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_capacity(team_name="team-1", service="api-gw", utilization_score=40.0)
        eng.record_capacity(team_name="team-2", service="auth", utilization_score=90.0)
        results = eng.rank_by_utilization()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_utilization_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization() == []


# ---------------------------------------------------------------------------
# detect_capacity_trends
# ---------------------------------------------------------------------------


class TestDetectCapacityTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(team_name="team-1", assessment_score=50.0)
        result = eng.detect_capacity_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(team_name="team-1", assessment_score=20.0)
        eng.add_assessment(team_name="team-2", assessment_score=20.0)
        eng.add_assessment(team_name="team-3", assessment_score=80.0)
        eng.add_assessment(team_name="team-4", assessment_score=80.0)
        result = eng.detect_capacity_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_capacity_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(capacity_utilization_threshold=80.0)
        eng.record_capacity(
            team_name="sre-team",
            capacity_status=CapacityStatus.OVERLOADED,
            load_category=LoadCategory.INCIDENT_RESPONSE,
            burnout_risk=BurnoutRisk.HIGH,
            utilization_score=92.0,
        )
        report = eng.generate_report()
        assert isinstance(report, TeamCapacityReport)
        assert report.total_records == 1
        assert report.overloaded_count == 1
        assert len(report.top_overloaded) == 1
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
        eng.record_capacity(team_name="team-1")
        eng.add_assessment(team_name="team-1")
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
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_capacity(
            team_name="sre-team",
            capacity_status=CapacityStatus.AVAILABLE,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "available" in stats["status_distribution"]
