"""Tests for shieldops.billing.savings_tracker — CloudSavingsTracker."""

from __future__ import annotations

from shieldops.billing.savings_tracker import (
    CloudSavingsTracker,
    SavingsGoal,
    SavingsRecord,
    SavingsReport,
    SavingsSource,
    SavingsStatus,
    TrackingPeriod,
)


def _engine(**kw) -> CloudSavingsTracker:
    return CloudSavingsTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # SavingsSource (5)
    def test_source_right_sizing(self):
        assert SavingsSource.RIGHT_SIZING == "right_sizing"

    def test_source_reserved_instances(self):
        assert SavingsSource.RESERVED_INSTANCES == "reserved_instances"

    def test_source_spot_usage(self):
        assert SavingsSource.SPOT_USAGE == "spot_usage"

    def test_source_waste_elimination(self):
        assert SavingsSource.WASTE_ELIMINATION == "waste_elimination"

    def test_source_rate_negotiation(self):
        assert SavingsSource.RATE_NEGOTIATION == "rate_negotiation"

    # SavingsStatus (5)
    def test_status_projected(self):
        assert SavingsStatus.PROJECTED == "projected"

    def test_status_in_progress(self):
        assert SavingsStatus.IN_PROGRESS == "in_progress"

    def test_status_realized(self):
        assert SavingsStatus.REALIZED == "realized"

    def test_status_partially_realized(self):
        assert SavingsStatus.PARTIALLY_REALIZED == "partially_realized"

    def test_status_missed(self):
        assert SavingsStatus.MISSED == "missed"

    # TrackingPeriod (5)
    def test_period_weekly(self):
        assert TrackingPeriod.WEEKLY == "weekly"

    def test_period_monthly(self):
        assert TrackingPeriod.MONTHLY == "monthly"

    def test_period_quarterly(self):
        assert TrackingPeriod.QUARTERLY == "quarterly"

    def test_period_annual(self):
        assert TrackingPeriod.ANNUAL == "annual"

    def test_period_custom(self):
        assert TrackingPeriod.CUSTOM == "custom"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_savings_record_defaults(self):
        r = SavingsRecord()
        assert r.id
        assert r.source == SavingsSource.RIGHT_SIZING
        assert r.service_name == ""
        assert r.team == ""
        assert r.projected_savings == 0.0
        assert r.realized_savings == 0.0
        assert r.status == SavingsStatus.PROJECTED
        assert r.period == TrackingPeriod.MONTHLY
        assert r.start_date == ""
        assert r.end_date == ""
        assert r.created_at > 0

    def test_savings_goal_defaults(self):
        g = SavingsGoal()
        assert g.id
        assert g.team == ""
        assert g.target_amount == 0.0
        assert g.current_amount == 0.0
        assert g.period == TrackingPeriod.MONTHLY
        assert g.progress_pct == 0.0
        assert g.on_track is False
        assert g.created_at > 0

    def test_savings_report_defaults(self):
        r = SavingsReport()
        assert r.total_projected == 0.0
        assert r.total_realized == 0.0
        assert r.realization_rate_pct == 0.0
        assert r.by_source == {}
        assert r.by_status == {}
        assert r.by_team == {}
        assert r.top_savers == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_savings
# ---------------------------------------------------------------------------


class TestRecordSavings:
    def test_basic_projected(self):
        eng = _engine()
        rec = eng.record_savings(
            source=SavingsSource.RIGHT_SIZING,
            service_name="ec2",
            team="platform",
            projected_savings=1000.0,
        )
        assert rec.source == SavingsSource.RIGHT_SIZING
        assert rec.service_name == "ec2"
        assert rec.team == "platform"
        assert rec.projected_savings == 1000.0
        assert rec.status == SavingsStatus.PROJECTED

    def test_auto_status_realized(self):
        eng = _engine()
        rec = eng.record_savings(
            source=SavingsSource.SPOT_USAGE,
            service_name="lambda",
            team="data",
            projected_savings=500.0,
            realized_savings=500.0,
        )
        assert rec.status == SavingsStatus.REALIZED

    def test_auto_status_in_progress(self):
        eng = _engine()
        rec = eng.record_savings(
            source=SavingsSource.WASTE_ELIMINATION,
            service_name="rds",
            team="infra",
            projected_savings=500.0,
            realized_savings=100.0,
        )
        assert rec.status == SavingsStatus.IN_PROGRESS

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_savings(
                source=SavingsSource.RIGHT_SIZING,
                service_name=f"svc-{i}",
                team="team",
                projected_savings=100.0,
            )
        assert len(eng._items) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        rec = eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
        )
        result = eng.get_record(rec.id)
        assert result is not None
        assert result.service_name == "ec2"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
        )
        eng.record_savings(
            SavingsSource.SPOT_USAGE,
            "lambda",
            "data",
            500.0,
        )
        assert len(eng.list_records()) == 2

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
        )
        eng.record_savings(
            SavingsSource.SPOT_USAGE,
            "lambda",
            "data",
            500.0,
        )
        results = eng.list_records(
            source=SavingsSource.SPOT_USAGE,
        )
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
            realized_savings=1000.0,
        )
        eng.record_savings(
            SavingsSource.SPOT_USAGE,
            "lambda",
            "data",
            500.0,
        )
        results = eng.list_records(
            status=SavingsStatus.REALIZED,
        )
        assert len(results) == 1


# ---------------------------------------------------------------------------
# create_goal
# ---------------------------------------------------------------------------


class TestCreateGoal:
    def test_basic_goal(self):
        eng = _engine()
        goal = eng.create_goal(
            team="platform",
            target_amount=10000.0,
            period=TrackingPeriod.QUARTERLY,
        )
        assert goal.team == "platform"
        assert goal.target_amount == 10000.0
        assert goal.period == TrackingPeriod.QUARTERLY
        assert goal.current_amount == 0.0
        assert goal.progress_pct == 0.0

    def test_goal_with_existing_savings(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            5000.0,
            realized_savings=3000.0,
        )
        goal = eng.create_goal(
            team="platform",
            target_amount=5000.0,
            period=TrackingPeriod.MONTHLY,
        )
        assert goal.current_amount == 3000.0
        assert goal.progress_pct == 60.0
        assert goal.on_track is True

    def test_goal_not_on_track(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "infra",
            5000.0,
            realized_savings=500.0,
        )
        goal = eng.create_goal(
            team="infra",
            target_amount=10000.0,
            period=TrackingPeriod.MONTHLY,
        )
        assert goal.progress_pct == 5.0
        assert goal.on_track is False


# ---------------------------------------------------------------------------
# update_realized
# ---------------------------------------------------------------------------


class TestUpdateRealized:
    def test_partial_update(self):
        eng = _engine()
        rec = eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
        )
        result = eng.update_realized(rec.id, 500.0)
        assert result is not None
        assert result.realized_savings == 500.0
        assert result.status == SavingsStatus.PARTIALLY_REALIZED

    def test_full_update(self):
        eng = _engine()
        rec = eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
        )
        result = eng.update_realized(rec.id, 1000.0)
        assert result is not None
        assert result.status == SavingsStatus.REALIZED

    def test_not_found(self):
        eng = _engine()
        assert eng.update_realized("bad", 100.0) is None


# ---------------------------------------------------------------------------
# calculate_realization_rate
# ---------------------------------------------------------------------------


class TestCalculateRealizationRate:
    def test_no_records(self):
        eng = _engine()
        assert eng.calculate_realization_rate() == 0.0

    def test_partial_realization(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
            realized_savings=500.0,
        )
        assert eng.calculate_realization_rate() == 50.0


# ---------------------------------------------------------------------------
# rank_teams_by_savings
# ---------------------------------------------------------------------------


class TestRankTeamsBySavings:
    def test_multiple_teams(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
            realized_savings=800.0,
        )
        eng.record_savings(
            SavingsSource.SPOT_USAGE,
            "lambda",
            "data",
            2000.0,
            realized_savings=1500.0,
        )
        ranked = eng.rank_teams_by_savings()
        assert len(ranked) == 2
        assert ranked[0]["team"] == "data"
        assert ranked[0]["total_realized"] == 1500.0
        assert ranked[1]["team"] == "platform"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_teams_by_savings() == []


# ---------------------------------------------------------------------------
# identify_missed_opportunities
# ---------------------------------------------------------------------------


class TestIdentifyMissedOpportunities:
    def test_finds_low_realization(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
            realized_savings=200.0,
        )
        eng.record_savings(
            SavingsSource.SPOT_USAGE,
            "lambda",
            "data",
            500.0,
            realized_savings=400.0,
        )
        missed = eng.identify_missed_opportunities()
        assert len(missed) == 1
        assert missed[0].service_name == "ec2"

    def test_none_missed(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
            realized_savings=1000.0,
        )
        assert len(eng.identify_missed_opportunities()) == 0


# ---------------------------------------------------------------------------
# generate_savings_report
# ---------------------------------------------------------------------------


class TestGenerateSavingsReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
            realized_savings=800.0,
        )
        eng.record_savings(
            SavingsSource.SPOT_USAGE,
            "lambda",
            "data",
            500.0,
            realized_savings=100.0,
        )
        report = eng.generate_savings_report()
        assert report.total_projected == 1500.0
        assert report.total_realized == 900.0
        assert report.realization_rate_pct == 60.0
        assert len(report.by_source) > 0
        assert len(report.by_status) > 0
        assert len(report.by_team) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_savings_report()
        assert report.total_projected == 0.0
        assert report.total_realized == 0.0
        assert report.realization_rate_pct == 0.0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
        )
        eng.create_goal(
            "platform",
            5000.0,
            TrackingPeriod.MONTHLY,
        )
        assert len(eng._items) == 1
        assert len(eng._goals) == 1
        eng.clear_data()
        assert len(eng._items) == 0
        assert len(eng._goals) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_goals"] == 0
        assert stats["source_distribution"] == {}
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_savings(
            SavingsSource.RIGHT_SIZING,
            "ec2",
            "platform",
            1000.0,
        )
        eng.create_goal(
            "platform",
            5000.0,
            TrackingPeriod.MONTHLY,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["total_goals"] == 1
        assert stats["max_records"] == 200000
        assert stats["realization_target_pct"] == 80.0
