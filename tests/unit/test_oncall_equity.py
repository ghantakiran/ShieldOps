"""Tests for shieldops.operations.oncall_equity — TeamOnCallEquityAnalyzer."""

from __future__ import annotations

from shieldops.operations.oncall_equity import (
    EquityAdjustment,
    EquityStatus,
    LoadCategory,
    OnCallEquityRecord,
    OnCallEquityReport,
    ShiftType,
    TeamOnCallEquityAnalyzer,
)


def _engine(**kw) -> TeamOnCallEquityAnalyzer:
    return TeamOnCallEquityAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ShiftType (5)
    def test_shift_weekday_day(self):
        assert ShiftType.WEEKDAY_DAY == "weekday_day"

    def test_shift_weekday_night(self):
        assert ShiftType.WEEKDAY_NIGHT == "weekday_night"

    def test_shift_weekend_day(self):
        assert ShiftType.WEEKEND_DAY == "weekend_day"

    def test_shift_weekend_night(self):
        assert ShiftType.WEEKEND_NIGHT == "weekend_night"

    def test_shift_holiday(self):
        assert ShiftType.HOLIDAY == "holiday"

    # LoadCategory (5)
    def test_load_pages(self):
        assert LoadCategory.PAGES == "pages"

    def test_load_incidents(self):
        assert LoadCategory.INCIDENTS == "incidents"

    def test_load_escalations(self):
        assert LoadCategory.ESCALATIONS == "escalations"

    def test_load_after_hours(self):
        assert LoadCategory.AFTER_HOURS == "after_hours"

    def test_load_toil(self):
        assert LoadCategory.TOIL == "toil"

    # EquityStatus (5)
    def test_equity_equitable(self):
        assert EquityStatus.EQUITABLE == "equitable"

    def test_equity_slightly_uneven(self):
        assert EquityStatus.SLIGHTLY_UNEVEN == "slightly_uneven"

    def test_equity_moderately_uneven(self):
        assert EquityStatus.MODERATELY_UNEVEN == "moderately_uneven"

    def test_equity_highly_uneven(self):
        assert EquityStatus.HIGHLY_UNEVEN == "highly_uneven"

    def test_equity_critical(self):
        assert EquityStatus.CRITICAL == "critical"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_oncall_equity_record_defaults(self):
        r = OnCallEquityRecord()
        assert r.id
        assert r.team_member == ""
        assert r.team == ""
        assert r.shift_type == ShiftType.WEEKDAY_DAY
        assert r.load_category == LoadCategory.PAGES
        assert r.load_count == 0
        assert r.load_hours == 0.0
        assert r.equity_score == 0.0
        assert r.period == ""
        assert r.created_at > 0

    def test_equity_adjustment_defaults(self):
        r = EquityAdjustment()
        assert r.id
        assert r.team_member == ""
        assert r.adjustment_type == ""
        assert r.reason == ""
        assert r.shift_change == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = OnCallEquityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_adjustments == 0
        assert r.avg_equity_score == 0.0
        assert r.by_shift_type == {}
        assert r.by_load_category == {}
        assert r.by_equity_status == {}
        assert r.overloaded_members == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_equity
# -------------------------------------------------------------------


class TestRecordEquity:
    def test_basic(self):
        eng = _engine()
        r = eng.record_equity("alice", "sre-team")
        assert r.team_member == "alice"
        assert r.team == "sre-team"
        assert r.shift_type == ShiftType.WEEKDAY_DAY

    def test_with_params(self):
        eng = _engine()
        r = eng.record_equity(
            "bob",
            "platform",
            shift_type=ShiftType.WEEKEND_NIGHT,
            load_category=LoadCategory.INCIDENTS,
            load_count=12,
            load_hours=8.5,
            equity_score=75.0,
            period="2026-02",
        )
        assert r.shift_type == ShiftType.WEEKEND_NIGHT
        assert r.load_count == 12
        assert r.equity_score == 75.0

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_equity("alice", "t1")
        r2 = eng.record_equity("bob", "t2")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_equity(f"user-{i}", "team")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_equity
# -------------------------------------------------------------------


class TestGetEquity:
    def test_found(self):
        eng = _engine()
        r = eng.record_equity("alice", "team")
        assert eng.get_equity(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_equity("nonexistent") is None


# -------------------------------------------------------------------
# list_equities
# -------------------------------------------------------------------


class TestListEquities:
    def test_list_all(self):
        eng = _engine()
        eng.record_equity("alice", "t1")
        eng.record_equity("bob", "t2")
        assert len(eng.list_equities()) == 2

    def test_filter_by_shift_type(self):
        eng = _engine()
        eng.record_equity(
            "alice",
            "t1",
            shift_type=ShiftType.HOLIDAY,
        )
        eng.record_equity(
            "bob",
            "t1",
            shift_type=ShiftType.WEEKDAY_DAY,
        )
        results = eng.list_equities(shift_type=ShiftType.HOLIDAY)
        assert len(results) == 1
        assert results[0].shift_type == ShiftType.HOLIDAY

    def test_filter_by_load_category(self):
        eng = _engine()
        eng.record_equity(
            "alice",
            "t1",
            load_category=LoadCategory.ESCALATIONS,
        )
        eng.record_equity(
            "bob",
            "t1",
            load_category=LoadCategory.PAGES,
        )
        results = eng.list_equities(load_category=LoadCategory.ESCALATIONS)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_equity("alice", "sre")
        eng.record_equity("bob", "platform")
        results = eng.list_equities(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_equity(f"user-{i}", "team")
        assert len(eng.list_equities(limit=5)) == 5


# -------------------------------------------------------------------
# add_adjustment
# -------------------------------------------------------------------


class TestAddAdjustment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_adjustment(
            "alice",
            "swap",
            "overloaded",
            "weekend to weekday",
        )
        assert a.team_member == "alice"
        assert a.adjustment_type == "swap"
        assert a.reason == "overloaded"
        assert a.shift_change == "weekend to weekday"

    def test_unique_ids(self):
        eng = _engine()
        a1 = eng.add_adjustment("alice", "swap", "reason", "change")
        a2 = eng.add_adjustment("bob", "skip", "reason2", "change2")
        assert a1.id != a2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_adjustment(f"user-{i}", "type", "reason", "change")
        assert len(eng._adjustments) == 2


# -------------------------------------------------------------------
# analyze_equity_by_team
# -------------------------------------------------------------------


class TestAnalyzeEquityByTeam:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_equity_by_team()
        assert result["total_teams"] == 0
        assert result["breakdown"] == []

    def test_with_data(self):
        eng = _engine()
        eng.record_equity("alice", "sre", equity_score=80.0)
        eng.record_equity("bob", "sre", equity_score=60.0)
        eng.record_equity("carol", "platform", equity_score=90.0)
        result = eng.analyze_equity_by_team()
        assert result["total_teams"] == 2


# -------------------------------------------------------------------
# identify_overloaded_members
# -------------------------------------------------------------------


class TestIdentifyOverloadedMembers:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_overloaded_members() == []

    def test_with_overloaded(self):
        eng = _engine(max_inequity_pct=10.0)
        eng.record_equity("alice", "t1", equity_score=50.0)
        eng.record_equity("bob", "t1", equity_score=50.0)
        eng.record_equity("carol", "t1", equity_score=90.0)
        results = eng.identify_overloaded_members()
        assert len(results) >= 1

    def test_no_overloaded(self):
        eng = _engine(max_inequity_pct=50.0)
        eng.record_equity("alice", "t1", equity_score=50.0)
        eng.record_equity("bob", "t1", equity_score=55.0)
        results = eng.identify_overloaded_members()
        assert len(results) == 0


# -------------------------------------------------------------------
# rank_by_equity_score
# -------------------------------------------------------------------


class TestRankByEquityScore:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_equity_score() == []

    def test_ascending_order(self):
        eng = _engine()
        eng.record_equity("alice", "t1", equity_score=90.0)
        eng.record_equity("bob", "t1", equity_score=30.0)
        results = eng.rank_by_equity_score()
        assert results[0]["team_member"] == "bob"
        assert results[0]["avg_equity_score"] <= results[-1]["avg_equity_score"]


# -------------------------------------------------------------------
# detect_equity_trends
# -------------------------------------------------------------------


class TestDetectEquityTrends:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_equity("alice", "t1")
        result = eng.detect_equity_trends()
        assert result["trend"] == "insufficient_data"

    def test_stable_trend(self):
        eng = _engine()
        for _ in range(8):
            eng.record_equity("alice", "t1", equity_score=50.0)
        result = eng.detect_equity_trends()
        assert result["trend"] in (
            "stable",
            "improving",
            "worsening",
        )

    def test_improving_trend(self):
        eng = _engine()
        for _ in range(8):
            eng.record_equity("alice", "t1", equity_score=20.0)
        for _ in range(8):
            eng.record_equity("alice", "t1", equity_score=80.0)
        result = eng.detect_equity_trends()
        assert result["trend"] == "improving"
        assert result["total_records"] == 16


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert isinstance(report, OnCallEquityReport)
        assert report.total_records == 0
        assert report.recommendations

    def test_with_data(self):
        eng = _engine(max_inequity_pct=10.0)
        eng.record_equity(
            "alice",
            "sre",
            shift_type=ShiftType.WEEKEND_NIGHT,
            equity_score=90.0,
        )
        eng.record_equity(
            "bob",
            "sre",
            shift_type=ShiftType.WEEKDAY_DAY,
            equity_score=50.0,
        )
        eng.add_adjustment("alice", "swap", "overloaded", "shift")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_adjustments == 1
        assert report.by_shift_type
        assert report.by_load_category


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_records_and_adjustments(self):
        eng = _engine()
        eng.record_equity("alice", "t1")
        eng.add_adjustment("alice", "swap", "reason", "change")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._adjustments) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_adjustments"] == 0
        assert stats["shift_type_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_inequity_pct=30.0)
        eng.record_equity(
            "alice",
            "sre",
            shift_type=ShiftType.WEEKDAY_DAY,
        )
        eng.record_equity(
            "bob",
            "platform",
            shift_type=ShiftType.WEEKEND_NIGHT,
        )
        eng.add_adjustment("alice", "swap", "reason", "change")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_adjustments"] == 1
        assert stats["max_inequity_pct"] == 30.0
        assert stats["unique_members"] == 2
