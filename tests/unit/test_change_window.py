"""Tests for shieldops.changes.change_window — ChangeWindowOptimizer."""

from __future__ import annotations

from shieldops.changes.change_window import (
    ChangeWindowOptimizer,
    ChangeWindowRecord,
    DayOfWeek,
    WindowReport,
    WindowRisk,
    WindowScore,
    WindowType,
)


def _engine(**kw) -> ChangeWindowOptimizer:
    return ChangeWindowOptimizer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # WindowType (5 values)

    def test_window_type_standard(self):
        assert WindowType.STANDARD == "standard"

    def test_window_type_expedited(self):
        assert WindowType.EXPEDITED == "expedited"

    def test_window_type_emergency(self):
        assert WindowType.EMERGENCY == "emergency"

    def test_window_type_maintenance(self):
        assert WindowType.MAINTENANCE == "maintenance"

    def test_window_type_blackout(self):
        assert WindowType.BLACKOUT == "blackout"

    # WindowRisk (5 values)

    def test_window_risk_very_low(self):
        assert WindowRisk.VERY_LOW == "very_low"

    def test_window_risk_low(self):
        assert WindowRisk.LOW == "low"

    def test_window_risk_moderate(self):
        assert WindowRisk.MODERATE == "moderate"

    def test_window_risk_high(self):
        assert WindowRisk.HIGH == "high"

    def test_window_risk_very_high(self):
        assert WindowRisk.VERY_HIGH == "very_high"

    # DayOfWeek (5 values)

    def test_day_monday(self):
        assert DayOfWeek.MONDAY == "monday"

    def test_day_tuesday(self):
        assert DayOfWeek.TUESDAY == "tuesday"

    def test_day_wednesday(self):
        assert DayOfWeek.WEDNESDAY == "wednesday"

    def test_day_thursday(self):
        assert DayOfWeek.THURSDAY == "thursday"

    def test_day_friday(self):
        assert DayOfWeek.FRIDAY == "friday"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_change_window_record_defaults(self):
        rec = ChangeWindowRecord()
        assert rec.id
        assert rec.service_name == ""
        assert rec.window_type == WindowType.STANDARD
        assert rec.day_of_week == DayOfWeek.TUESDAY
        assert rec.hour == 10
        assert rec.is_success is True
        assert rec.risk_level == WindowRisk.LOW
        assert rec.duration_minutes == 30
        assert rec.created_at > 0

    def test_window_score_defaults(self):
        score = WindowScore()
        assert score.day_of_week == DayOfWeek.TUESDAY
        assert score.hour == 10
        assert score.window_type == WindowType.STANDARD
        assert score.success_rate == 0.0
        assert score.total_changes == 0
        assert score.risk_level == WindowRisk.LOW
        assert score.score == 0.0
        assert score.created_at > 0

    def test_window_report_defaults(self):
        report = WindowReport()
        assert report.total_changes == 0
        assert report.total_windows_analyzed == 0
        assert report.best_window == {}
        assert report.worst_window == {}
        assert report.by_type == {}
        assert report.by_risk == {}
        assert report.recommendations == []
        assert report.generated_at > 0


# -------------------------------------------------------------------
# record_change
# -------------------------------------------------------------------


class TestRecordChange:
    def test_basic_record(self):
        eng = _engine()
        rec = eng.record_change(
            service_name="api",
            day_of_week=DayOfWeek.MONDAY,
            hour=14,
        )
        assert rec.service_name == "api"
        assert rec.day_of_week == DayOfWeek.MONDAY
        assert rec.hour == 14
        assert len(eng.list_records()) == 1

    def test_record_assigns_unique_ids(self):
        eng = _engine()
        r1 = eng.record_change(service_name="a")
        r2 = eng.record_change(service_name="b")
        assert r1.id != r2.id

    def test_record_failure(self):
        eng = _engine()
        rec = eng.record_change(
            service_name="api",
            is_success=False,
        )
        assert rec.is_success is False

    def test_eviction_at_max_records(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            rec = eng.record_change(
                service_name=f"svc-{i}",
            )
            ids.append(rec.id)
        records = eng.list_records(limit=100)
        assert len(records) == 3
        found = {r.id for r in records}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_record
# -------------------------------------------------------------------


class TestGetRecord:
    def test_get_existing(self):
        eng = _engine()
        rec = eng.record_change(service_name="api")
        found = eng.get_record(rec.id)
        assert found is not None
        assert found.id == rec.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# -------------------------------------------------------------------
# list_records
# -------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_change(service_name="a")
        eng.record_change(service_name="b")
        eng.record_change(service_name="c")
        assert len(eng.list_records()) == 3

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_change(service_name="api")
        eng.record_change(service_name="web")
        eng.record_change(service_name="api")
        results = eng.list_records(service_name="api")
        assert len(results) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_change(
            window_type=WindowType.STANDARD,
        )
        eng.record_change(
            window_type=WindowType.EMERGENCY,
        )
        eng.record_change(
            window_type=WindowType.STANDARD,
        )
        results = eng.list_records(
            window_type=WindowType.STANDARD,
        )
        assert len(results) == 2

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_change(service_name=f"svc-{i}")
        results = eng.list_records(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# calculate_window_score
# -------------------------------------------------------------------


class TestCalculateWindowScore:
    def test_basic_score(self):
        eng = _engine()
        for _ in range(8):
            eng.record_change(
                day_of_week=DayOfWeek.TUESDAY,
                hour=10,
                is_success=True,
            )
        for _ in range(2):
            eng.record_change(
                day_of_week=DayOfWeek.TUESDAY,
                hour=10,
                is_success=False,
            )
        score = eng.calculate_window_score(
            DayOfWeek.TUESDAY,
            10,
        )
        assert score.success_rate == 80.0
        assert score.total_changes == 10
        assert score.risk_level == WindowRisk.HIGH

    def test_no_data(self):
        eng = _engine()
        score = eng.calculate_window_score(
            DayOfWeek.FRIDAY,
            22,
        )
        assert score.total_changes == 0
        assert score.success_rate == 0.0

    def test_perfect_rate(self):
        eng = _engine()
        for _ in range(5):
            eng.record_change(
                day_of_week=DayOfWeek.WEDNESDAY,
                hour=9,
                is_success=True,
            )
        score = eng.calculate_window_score(
            DayOfWeek.WEDNESDAY,
            9,
        )
        assert score.success_rate == 100.0
        assert score.risk_level == WindowRisk.VERY_LOW


# -------------------------------------------------------------------
# find_optimal_windows
# -------------------------------------------------------------------


class TestFindOptimalWindows:
    def test_basic_optimal(self):
        eng = _engine()
        # Good window
        for _ in range(10):
            eng.record_change(
                day_of_week=DayOfWeek.TUESDAY,
                hour=10,
                is_success=True,
            )
        # Bad window
        for _ in range(10):
            eng.record_change(
                day_of_week=DayOfWeek.FRIDAY,
                hour=17,
                is_success=False,
            )
        optimal = eng.find_optimal_windows()
        assert len(optimal) == 2
        assert optimal[0].day_of_week == DayOfWeek.TUESDAY
        assert optimal[0].success_rate == 100.0

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_change(
            service_name="api",
            day_of_week=DayOfWeek.MONDAY,
            hour=10,
        )
        eng.record_change(
            service_name="web",
            day_of_week=DayOfWeek.TUESDAY,
            hour=14,
        )
        optimal = eng.find_optimal_windows(
            service_name="api",
        )
        assert len(optimal) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.find_optimal_windows() == []


# -------------------------------------------------------------------
# detect_risky_windows
# -------------------------------------------------------------------


class TestDetectRiskyWindows:
    def test_finds_risky(self):
        eng = _engine(min_success_rate=90.0)
        for _ in range(10):
            eng.record_change(
                day_of_week=DayOfWeek.FRIDAY,
                hour=17,
                is_success=False,
            )
        risky = eng.detect_risky_windows()
        assert len(risky) == 1
        assert risky[0].success_rate == 0.0

    def test_no_risky(self):
        eng = _engine()
        for _ in range(10):
            eng.record_change(
                day_of_week=DayOfWeek.TUESDAY,
                hour=10,
                is_success=True,
            )
        risky = eng.detect_risky_windows()
        assert len(risky) == 0


# -------------------------------------------------------------------
# analyze_by_day_of_week
# -------------------------------------------------------------------


class TestAnalyzeByDayOfWeek:
    def test_basic_analysis(self):
        eng = _engine()
        eng.record_change(
            day_of_week=DayOfWeek.MONDAY,
            is_success=True,
        )
        eng.record_change(
            day_of_week=DayOfWeek.MONDAY,
            is_success=False,
        )
        eng.record_change(
            day_of_week=DayOfWeek.FRIDAY,
            is_success=True,
        )
        result = eng.analyze_by_day_of_week()
        assert DayOfWeek.MONDAY in result
        assert result[DayOfWeek.MONDAY]["total_changes"] == 2
        assert result[DayOfWeek.MONDAY]["success_rate"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_by_day_of_week() == {}


# -------------------------------------------------------------------
# compare_window_types
# -------------------------------------------------------------------


class TestCompareWindowTypes:
    def test_basic_comparison(self):
        eng = _engine()
        eng.record_change(
            window_type=WindowType.STANDARD,
            is_success=True,
        )
        eng.record_change(
            window_type=WindowType.EMERGENCY,
            is_success=False,
        )
        result = eng.compare_window_types()
        assert WindowType.STANDARD in result
        assert result[WindowType.STANDARD]["success_rate"] == 100.0
        assert result[WindowType.EMERGENCY]["success_rate"] == 0.0

    def test_empty(self):
        eng = _engine()
        assert eng.compare_window_types() == {}


# -------------------------------------------------------------------
# generate_window_report
# -------------------------------------------------------------------


class TestGenerateWindowReport:
    def test_basic_report(self):
        eng = _engine()
        for _ in range(5):
            eng.record_change(
                day_of_week=DayOfWeek.TUESDAY,
                hour=10,
                is_success=True,
            )
        for _ in range(5):
            eng.record_change(
                day_of_week=DayOfWeek.FRIDAY,
                hour=17,
                is_success=False,
            )
        report = eng.generate_window_report()
        assert report.total_changes == 10
        assert report.total_windows_analyzed == 2
        assert report.best_window != {}
        assert report.worst_window != {}
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_window_report()
        assert report.total_changes == 0
        assert report.total_windows_analyzed == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_change(service_name="api")
        eng.record_change(service_name="web")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_records()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["min_success_rate"] == 90.0
        assert stats["type_distribution"] == {}
        assert stats["day_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_change(
            window_type=WindowType.STANDARD,
            day_of_week=DayOfWeek.MONDAY,
        )
        eng.record_change(
            window_type=WindowType.EMERGENCY,
            day_of_week=DayOfWeek.FRIDAY,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert "standard" in stats["type_distribution"]
        assert "emergency" in stats["type_distribution"]
        assert "monday" in stats["day_distribution"]
        assert "friday" in stats["day_distribution"]
