"""Tests for shieldops.incidents.response_action_auditor — ResponseActionAuditor."""

from __future__ import annotations

from shieldops.incidents.response_action_auditor import (
    ActionAuditAnalysis,
    ActionAuditRecord,
    ActionAuditReport,
    ActionResult,
    ActionType,
    AuditSeverity,
    ResponseActionAuditor,
)


def _engine(**kw) -> ResponseActionAuditor:
    return ResponseActionAuditor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_actiontype_val1(self):
        assert ActionType.CONTAINMENT == "containment"

    def test_actiontype_val2(self):
        assert ActionType.ERADICATION == "eradication"

    def test_actiontype_val3(self):
        assert ActionType.RECOVERY == "recovery"

    def test_actiontype_val4(self):
        assert ActionType.COMMUNICATION == "communication"

    def test_actiontype_val5(self):
        assert ActionType.APPROVAL == "approval"

    def test_actionresult_val1(self):
        assert ActionResult.SUCCESS == "success"

    def test_actionresult_val2(self):
        assert ActionResult.FAILURE == "failure"

    def test_actionresult_val3(self):
        assert ActionResult.PARTIAL == "partial"

    def test_actionresult_val4(self):
        assert ActionResult.TIMEOUT == "timeout"

    def test_actionresult_val5(self):
        assert ActionResult.CANCELLED == "cancelled"

    def test_auditseverity_val1(self):
        assert AuditSeverity.CRITICAL == "critical"

    def test_auditseverity_val2(self):
        assert AuditSeverity.MAJOR == "major"

    def test_auditseverity_val3(self):
        assert AuditSeverity.MINOR == "minor"

    def test_auditseverity_val4(self):
        assert AuditSeverity.INFO == "info"

    def test_auditseverity_val5(self):
        assert AuditSeverity.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = ActionAuditRecord()
        assert r.id
        assert r.name == ""
        assert r.action_type == ActionType.CONTAINMENT
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ActionAuditAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ActionAuditReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_type == {}
        assert r.by_result == {}
        assert r.by_severity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_action(
            name="test",
            action_type=ActionType.ERADICATION,
            score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.name == "test"
        assert r.action_type == ActionType.ERADICATION
        assert r.score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_action(name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_action(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_action(name="a")
        eng.record_action(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_action(name="a", action_type=ActionType.CONTAINMENT)
        eng.record_action(name="b", action_type=ActionType.ERADICATION)
        results = eng.list_records(action_type=ActionType.CONTAINMENT)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_action(name="a", action_result=ActionResult.SUCCESS)
        eng.record_action(name="b", action_result=ActionResult.FAILURE)
        results = eng.list_records(action_result=ActionResult.SUCCESS)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_action(name="a", team="sec")
        eng.record_action(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_action(name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_action(
            name="a",
            action_type=ActionType.CONTAINMENT,
            score=90.0,
        )
        eng.record_action(
            name="b",
            action_type=ActionType.CONTAINMENT,
            score=70.0,
        )
        result = eng.analyze_type_distribution()
        assert "containment" in result
        assert result["containment"]["count"] == 2
        assert result["containment"]["avg_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(score_threshold=80.0)
        eng.record_action(name="a", score=60.0)
        eng.record_action(name="b", score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(score_threshold=80.0)
        eng.record_action(name="a", score=50.0)
        eng.record_action(name="b", score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_action(name="a", service="auth-svc", score=90.0)
        eng.record_action(name="b", service="api-gw", score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="t1", analysis_score=20.0)
        eng.add_analysis(name="t2", analysis_score=20.0)
        eng.add_analysis(name="t3", analysis_score=80.0)
        eng.add_analysis(name="t4", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(score_threshold=80.0)
        eng.record_action(
            name="test",
            action_type=ActionType.ERADICATION,
            score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ActionAuditReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy range" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_action(name="test")
        eng.add_analysis(name="test")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_action(
            name="test",
            action_type=ActionType.CONTAINMENT,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "containment" in stats["type_distribution"]
