"""Tests for shieldops.operations.soc_shift_handoff_engine — SOCShiftHandoffEngine."""

from __future__ import annotations

from shieldops.operations.soc_shift_handoff_engine import (
    HandoffAnalysis,
    HandoffPriority,
    HandoffRecord,
    HandoffReport,
    HandoffStatus,
    HandoffType,
    SOCShiftHandoffEngine,
)


def _engine(**kw) -> SOCShiftHandoffEngine:
    return SOCShiftHandoffEngine(**kw)


class TestEnums:
    def test_handofftype_val1(self):
        assert HandoffType.SHIFT_CHANGE == "shift_change"

    def test_handofftype_val2(self):
        assert HandoffType.ESCALATION == "escalation"

    def test_handofftype_val3(self):
        assert HandoffType.TEAM_TRANSFER == "team_transfer"

    def test_handofftype_val4(self):
        assert HandoffType.ON_CALL_ROTATION == "on_call_rotation"

    def test_handofftype_val5(self):
        assert HandoffType.EMERGENCY == "emergency"

    def test_handoffstatus_val1(self):
        assert HandoffStatus.PENDING == "pending"

    def test_handoffstatus_val2(self):
        assert HandoffStatus.IN_PROGRESS == "in_progress"

    def test_handoffstatus_val3(self):
        assert HandoffStatus.COMPLETED == "completed"

    def test_handoffstatus_val4(self):
        assert HandoffStatus.MISSED == "missed"

    def test_handoffstatus_val5(self):
        assert HandoffStatus.DELAYED == "delayed"

    def test_handoffpriority_val1(self):
        assert HandoffPriority.CRITICAL == "critical"

    def test_handoffpriority_val2(self):
        assert HandoffPriority.HIGH == "high"

    def test_handoffpriority_val3(self):
        assert HandoffPriority.MEDIUM == "medium"

    def test_handoffpriority_val4(self):
        assert HandoffPriority.LOW == "low"

    def test_handoffpriority_val5(self):
        assert HandoffPriority.ROUTINE == "routine"


class TestModels:
    def test_record_defaults(self):
        r = HandoffRecord()
        assert r.id
        assert r.handoff_name == ""

    def test_analysis_defaults(self):
        a = HandoffAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = HandoffReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_handoff(
            handoff_name="test",
            handoff_type=HandoffType.ESCALATION,
            completeness_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.handoff_name == "test"
        assert r.completeness_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_handoff(handoff_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_handoff(handoff_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_handoff(handoff_name="a")
        eng.record_handoff(handoff_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_handoff(handoff_name="a", handoff_type=HandoffType.SHIFT_CHANGE)
        eng.record_handoff(handoff_name="b", handoff_type=HandoffType.ESCALATION)
        assert len(eng.list_records(handoff_type=HandoffType.SHIFT_CHANGE)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_handoff(handoff_name="a", handoff_status=HandoffStatus.PENDING)
        eng.record_handoff(handoff_name="b", handoff_status=HandoffStatus.IN_PROGRESS)
        assert len(eng.list_records(handoff_status=HandoffStatus.PENDING)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_handoff(handoff_name="a", team="sec")
        eng.record_handoff(handoff_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_handoff(handoff_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            handoff_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(handoff_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_handoff(
            handoff_name="a", handoff_type=HandoffType.SHIFT_CHANGE, completeness_score=90.0
        )
        eng.record_handoff(
            handoff_name="b", handoff_type=HandoffType.SHIFT_CHANGE, completeness_score=70.0
        )
        result = eng.analyze_distribution()
        assert HandoffType.SHIFT_CHANGE.value in result
        assert result[HandoffType.SHIFT_CHANGE.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_handoff(handoff_name="a", completeness_score=60.0)
        eng.record_handoff(handoff_name="b", completeness_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_handoff(handoff_name="a", completeness_score=50.0)
        eng.record_handoff(handoff_name="b", completeness_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["completeness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_handoff(handoff_name="a", service="auth", completeness_score=90.0)
        eng.record_handoff(handoff_name="b", service="api", completeness_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(handoff_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(handoff_name="a", analysis_score=20.0)
        eng.add_analysis(handoff_name="b", analysis_score=20.0)
        eng.add_analysis(handoff_name="c", analysis_score=80.0)
        eng.add_analysis(handoff_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_handoff(handoff_name="test", completeness_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_handoff(handoff_name="test")
        eng.add_analysis(handoff_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_handoff(handoff_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
