"""Tests for shieldops.incidents.oncall_fatigue — OnCallFatigueAnalyzer."""

from __future__ import annotations

import pytest

from shieldops.incidents.oncall_fatigue import (
    FatigueReport,
    FatigueRisk,
    OnCallFatigueAnalyzer,
    PageEvent,
    PageUrgency,
    TimeOfDay,
)


def _analyzer(**kw) -> OnCallFatigueAnalyzer:
    return OnCallFatigueAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # FatigueRisk (4 values)

    def test_fatigue_risk_low(self):
        assert FatigueRisk.LOW == "low"

    def test_fatigue_risk_moderate(self):
        assert FatigueRisk.MODERATE == "moderate"

    def test_fatigue_risk_high(self):
        assert FatigueRisk.HIGH == "high"

    def test_fatigue_risk_burnout(self):
        assert FatigueRisk.BURNOUT == "burnout"

    # PageUrgency (4 values)

    def test_page_urgency_low(self):
        assert PageUrgency.LOW == "low"

    def test_page_urgency_medium(self):
        assert PageUrgency.MEDIUM == "medium"

    def test_page_urgency_high(self):
        assert PageUrgency.HIGH == "high"

    def test_page_urgency_critical(self):
        assert PageUrgency.CRITICAL == "critical"

    # TimeOfDay (4 values)

    def test_time_of_day_business_hours(self):
        assert TimeOfDay.BUSINESS_HOURS == "business_hours"

    def test_time_of_day_after_hours(self):
        assert TimeOfDay.AFTER_HOURS == "after_hours"

    def test_time_of_day_weekend(self):
        assert TimeOfDay.WEEKEND == "weekend"

    def test_time_of_day_holiday(self):
        assert TimeOfDay.HOLIDAY == "holiday"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_page_event_defaults(self):
        event = PageEvent(engineer="alice")
        assert event.id
        assert event.engineer == "alice"
        assert event.service == ""
        assert event.urgency == PageUrgency.MEDIUM
        assert event.time_of_day == TimeOfDay.BUSINESS_HOURS
        assert event.acknowledged is False
        assert event.resolution_minutes == 0.0
        assert event.paged_at > 0

    def test_fatigue_report_defaults(self):
        report = FatigueReport(engineer="alice")
        assert report.engineer == "alice"
        assert report.total_pages == 0
        assert report.after_hours_pages == 0
        assert report.after_hours_ratio == 0.0
        assert report.avg_resolution_minutes == 0.0
        assert report.fatigue_score == 0.0
        assert report.risk == FatigueRisk.LOW


# ---------------------------------------------------------------------------
# record_page
# ---------------------------------------------------------------------------


class TestRecordPage:
    def test_basic_record(self):
        ana = _analyzer()
        event = ana.record_page("alice", service="api-gateway")
        assert event.engineer == "alice"
        assert event.service == "api-gateway"
        assert event.urgency == PageUrgency.MEDIUM
        assert len(ana.list_events()) == 1

    def test_record_assigns_unique_ids(self):
        ana = _analyzer()
        e1 = ana.record_page("alice")
        e2 = ana.record_page("bob")
        assert e1.id != e2.id

    def test_record_with_extra_fields(self):
        ana = _analyzer()
        event = ana.record_page(
            "alice",
            service="db-primary",
            urgency=PageUrgency.CRITICAL,
            time_of_day=TimeOfDay.AFTER_HOURS,
            acknowledged=True,
            resolution_minutes=45.0,
        )
        assert event.urgency == PageUrgency.CRITICAL
        assert event.time_of_day == TimeOfDay.AFTER_HOURS
        assert event.acknowledged is True
        assert event.resolution_minutes == 45.0

    def test_record_trims_at_max(self):
        ana = _analyzer(max_events=3)
        for i in range(5):
            ana.record_page(f"eng-{i}")
        assert len(ana.list_events()) == 3


# ---------------------------------------------------------------------------
# analyze_fatigue
# ---------------------------------------------------------------------------


class TestAnalyzeFatigue:
    def test_low_risk(self):
        ana = _analyzer()
        # 2 business-hours pages: score = 2*2 + 0*3 + 0*5 = 4 -> LOW
        ana.record_page("alice")
        ana.record_page("alice")
        report = ana.analyze_fatigue("alice")
        assert report.total_pages == 2
        assert report.fatigue_score == pytest.approx(4.0)
        assert report.risk == FatigueRisk.LOW

    def test_moderate_risk(self):
        ana = _analyzer()
        # 5 biz pages + 2 after-hours: score = 7*2 + 2*3 + 0*5 = 20 -> LOW
        # Need more: 8 biz + 3 after-hours: score = 11*2 + 3*3 + 0*5 = 31 -> MODERATE
        for _ in range(8):
            ana.record_page("alice")
        for _ in range(3):
            ana.record_page("alice", time_of_day=TimeOfDay.AFTER_HOURS)
        report = ana.analyze_fatigue("alice")
        assert report.risk == FatigueRisk.MODERATE
        assert 25.0 <= report.fatigue_score < 50.0

    def test_high_risk(self):
        ana = _analyzer()
        # 15 biz + 5 after-hours: score = 20*2 + 5*3 + 0*5 = 55 -> HIGH
        for _ in range(15):
            ana.record_page("alice")
        for _ in range(5):
            ana.record_page("alice", time_of_day=TimeOfDay.WEEKEND)
        report = ana.analyze_fatigue("alice")
        assert report.risk == FatigueRisk.HIGH
        assert 50.0 <= report.fatigue_score < 75.0

    def test_burnout_risk(self):
        ana = _analyzer()
        # 20 biz + 10 after-hours + 3 critical -> BURNOUT
        for _ in range(20):
            ana.record_page("alice")
        for _ in range(10):
            ana.record_page("alice", time_of_day=TimeOfDay.HOLIDAY)
        for _ in range(3):
            ana.record_page("alice", urgency=PageUrgency.CRITICAL)
        report = ana.analyze_fatigue("alice")
        assert report.risk == FatigueRisk.BURNOUT
        assert report.fatigue_score >= 75.0

    def test_no_events_returns_low(self):
        ana = _analyzer()
        report = ana.analyze_fatigue("alice")
        assert report.total_pages == 0
        assert report.fatigue_score == 0.0
        assert report.risk == FatigueRisk.LOW
        assert report.after_hours_ratio == 0.0
        assert report.avg_resolution_minutes == 0.0


# ---------------------------------------------------------------------------
# get_team_report
# ---------------------------------------------------------------------------


class TestGetTeamReport:
    def test_basic_team_report(self):
        ana = _analyzer()
        ana.record_page("alice")
        ana.record_page("bob")
        ana.record_page("alice")
        reports = ana.get_team_report()
        assert len(reports) == 2
        engineers = {r.engineer for r in reports}
        assert engineers == {"alice", "bob"}

    def test_specific_engineers(self):
        ana = _analyzer()
        ana.record_page("alice")
        ana.record_page("bob")
        ana.record_page("charlie")
        reports = ana.get_team_report(engineers=["alice", "charlie"])
        assert len(reports) == 2
        engineers = {r.engineer for r in reports}
        assert engineers == {"alice", "charlie"}


# ---------------------------------------------------------------------------
# get_burnout_risks
# ---------------------------------------------------------------------------


class TestGetBurnoutRisks:
    def test_basic_burnout_risks(self):
        ana = _analyzer()
        # Push alice into HIGH/BURNOUT range
        for _ in range(15):
            ana.record_page("alice")
        for _ in range(5):
            ana.record_page("alice", time_of_day=TimeOfDay.AFTER_HOURS)
        # Bob stays LOW
        ana.record_page("bob")
        risks = ana.get_burnout_risks()
        assert len(risks) == 1
        assert risks[0].engineer == "alice"

    def test_no_burnout_risks(self):
        ana = _analyzer()
        ana.record_page("alice")
        ana.record_page("bob")
        risks = ana.get_burnout_risks()
        assert risks == []


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_list_all(self):
        ana = _analyzer()
        ana.record_page("alice")
        ana.record_page("bob")
        ana.record_page("alice")
        events = ana.list_events()
        assert len(events) == 3

    def test_filter_by_engineer(self):
        ana = _analyzer()
        ana.record_page("alice")
        ana.record_page("bob")
        ana.record_page("alice")
        events = ana.list_events(engineer="alice")
        assert len(events) == 2
        assert all(e.engineer == "alice" for e in events)

    def test_filter_by_urgency(self):
        ana = _analyzer()
        ana.record_page("alice", urgency=PageUrgency.LOW)
        ana.record_page("bob", urgency=PageUrgency.CRITICAL)
        ana.record_page("alice", urgency=PageUrgency.CRITICAL)
        events = ana.list_events(urgency=PageUrgency.CRITICAL)
        assert len(events) == 2
        assert all(e.urgency == PageUrgency.CRITICAL for e in events)


# ---------------------------------------------------------------------------
# get_load_distribution
# ---------------------------------------------------------------------------


class TestGetLoadDistribution:
    def test_basic_distribution(self):
        ana = _analyzer()
        ana.record_page("alice")
        ana.record_page("alice")
        ana.record_page("bob")
        dist = ana.get_load_distribution()
        assert len(dist) == 2
        # Sorted descending by page_count, alice should be first
        assert dist[0]["engineer"] == "alice"
        assert dist[0]["page_count"] == 2
        assert dist[0]["percentage"] == pytest.approx(66.67, abs=0.01)
        assert dist[1]["engineer"] == "bob"
        assert dist[1]["page_count"] == 1

    def test_empty_distribution(self):
        ana = _analyzer()
        dist = ana.get_load_distribution()
        assert dist == []


# ---------------------------------------------------------------------------
# get_after_hours_ratio
# ---------------------------------------------------------------------------


class TestGetAfterHoursRatio:
    def test_basic_ratio(self):
        ana = _analyzer()
        ana.record_page("alice", time_of_day=TimeOfDay.BUSINESS_HOURS)
        ana.record_page("alice", time_of_day=TimeOfDay.AFTER_HOURS)
        ana.record_page("bob", time_of_day=TimeOfDay.WEEKEND)
        ana.record_page("bob", time_of_day=TimeOfDay.BUSINESS_HOURS)
        result = ana.get_after_hours_ratio()
        assert result["total_pages"] == 4
        assert result["after_hours_pages"] == 2
        assert result["ratio"] == pytest.approx(0.5, abs=1e-4)

    def test_empty_ratio(self):
        ana = _analyzer()
        result = ana.get_after_hours_ratio()
        assert result["total_pages"] == 0
        assert result["after_hours_pages"] == 0
        assert result["ratio"] == 0.0


# ---------------------------------------------------------------------------
# clear_events
# ---------------------------------------------------------------------------


class TestClearEvents:
    def test_basic_clear(self):
        ana = _analyzer()
        ana.record_page("alice")
        ana.record_page("bob")
        count = ana.clear_events()
        assert count == 2
        assert len(ana.list_events()) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        ana = _analyzer()
        stats = ana.get_stats()
        assert stats["total_events"] == 0
        assert stats["unique_engineers"] == 0
        assert stats["urgency_distribution"] == {}
        assert stats["time_of_day_distribution"] == {}

    def test_stats_populated(self):
        ana = _analyzer()
        ana.record_page("alice", urgency=PageUrgency.HIGH, time_of_day=TimeOfDay.BUSINESS_HOURS)
        ana.record_page("bob", urgency=PageUrgency.CRITICAL, time_of_day=TimeOfDay.AFTER_HOURS)
        ana.record_page("alice", urgency=PageUrgency.HIGH, time_of_day=TimeOfDay.WEEKEND)

        stats = ana.get_stats()
        assert stats["total_events"] == 3
        assert stats["unique_engineers"] == 2
        assert stats["urgency_distribution"][PageUrgency.HIGH] == 2
        assert stats["urgency_distribution"][PageUrgency.CRITICAL] == 1
        assert stats["time_of_day_distribution"][TimeOfDay.BUSINESS_HOURS] == 1
        assert stats["time_of_day_distribution"][TimeOfDay.AFTER_HOURS] == 1
        assert stats["time_of_day_distribution"][TimeOfDay.WEEKEND] == 1
