"""Tests for shieldops.operations.capacity_right_timing."""

from __future__ import annotations

from shieldops.operations.capacity_right_timing import (
    CapacityRightTimingAdvisor,
    ScaleDirection,
    TimingConfidence,
    TimingRecommendation,
    TimingReport,
    TrafficForecastWindow,
    TrafficPattern,
)


def _engine(**kw) -> CapacityRightTimingAdvisor:
    return CapacityRightTimingAdvisor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ScaleDirection (5 values)

    def test_direction_scale_up(self):
        assert ScaleDirection.SCALE_UP == "scale_up"

    def test_direction_scale_down(self):
        assert ScaleDirection.SCALE_DOWN == "scale_down"

    def test_direction_scale_out(self):
        assert ScaleDirection.SCALE_OUT == "scale_out"

    def test_direction_scale_in(self):
        assert ScaleDirection.SCALE_IN == "scale_in"

    def test_direction_no_change(self):
        assert ScaleDirection.NO_CHANGE == "no_change"

    # TimingConfidence (5 values)

    def test_confidence_very_low(self):
        assert TimingConfidence.VERY_LOW == "very_low"

    def test_confidence_low(self):
        assert TimingConfidence.LOW == "low"

    def test_confidence_moderate(self):
        assert TimingConfidence.MODERATE == "moderate"

    def test_confidence_high(self):
        assert TimingConfidence.HIGH == "high"

    def test_confidence_very_high(self):
        assert TimingConfidence.VERY_HIGH == "very_high"

    # TrafficPattern (5 values)

    def test_pattern_diurnal(self):
        assert TrafficPattern.DIURNAL == "diurnal"

    def test_pattern_weekly_cycle(self):
        assert TrafficPattern.WEEKLY_CYCLE == "weekly_cycle"

    def test_pattern_seasonal(self):
        assert TrafficPattern.SEASONAL == "seasonal"

    def test_pattern_event_driven(self):
        assert TrafficPattern.EVENT_DRIVEN == "event_driven"

    def test_pattern_unpredictable(self):
        assert TrafficPattern.UNPREDICTABLE == "unpredictable"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_timing_recommendation_defaults(self):
        tr = TimingRecommendation()
        assert tr.id
        assert tr.service_name == ""
        assert tr.direction == ScaleDirection.NO_CHANGE
        assert tr.recommended_at_hour == 0
        assert tr.confidence == TimingConfidence.VERY_LOW
        assert tr.traffic_pattern == TrafficPattern.DIURNAL
        assert tr.cost_saving_pct == 0.0
        assert tr.reason == ""
        assert tr.status == "pending"
        assert tr.created_at > 0

    def test_traffic_forecast_window_defaults(self):
        tw = TrafficForecastWindow()
        assert tw.id
        assert tw.service_name == ""
        assert tw.start_hour == 0
        assert tw.end_hour == 23
        assert tw.expected_load_pct == 0.0
        assert tw.pattern == TrafficPattern.DIURNAL
        assert tw.day_of_week == 0
        assert tw.created_at > 0

    def test_timing_report_defaults(self):
        tr = TimingReport()
        assert tr.total_recommendations == 0
        assert tr.total_windows == 0
        assert tr.by_direction == {}
        assert tr.by_pattern == {}
        assert tr.by_confidence == {}
        assert tr.avg_cost_saving_pct == 0.0
        assert tr.recommendations == []
        assert tr.generated_at > 0


# -------------------------------------------------------------------
# create_recommendation
# -------------------------------------------------------------------


class TestCreateRecommendation:
    def test_basic_create(self):
        eng = _engine()
        rec = eng.create_recommendation("svc-a")
        assert rec.service_name == "svc-a"
        assert len(eng.list_recommendations()) == 1

    def test_create_assigns_unique_ids(self):
        eng = _engine()
        r1 = eng.create_recommendation("svc-a")
        r2 = eng.create_recommendation("svc-b")
        assert r1.id != r2.id

    def test_create_with_values(self):
        eng = _engine()
        rec = eng.create_recommendation(
            "svc-a",
            direction=ScaleDirection.SCALE_UP,
            recommended_at_hour=14,
            confidence=TimingConfidence.HIGH,
            traffic_pattern=TrafficPattern.WEEKLY_CYCLE,
            cost_saving_pct=12.5,
            reason="peak traffic expected",
        )
        assert rec.direction == ScaleDirection.SCALE_UP
        assert rec.recommended_at_hour == 14
        assert rec.confidence == TimingConfidence.HIGH
        assert rec.traffic_pattern == TrafficPattern.WEEKLY_CYCLE
        assert rec.cost_saving_pct == 12.5
        assert rec.reason == "peak traffic expected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            rec = eng.create_recommendation(f"svc-{i}")
            ids.append(rec.id)
        recs = eng.list_recommendations(limit=100)
        assert len(recs) == 3
        found = {r.id for r in recs}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_recommendation
# -------------------------------------------------------------------


class TestGetRecommendation:
    def test_get_existing(self):
        eng = _engine()
        rec = eng.create_recommendation("svc-a")
        found = eng.get_recommendation(rec.id)
        assert found is not None
        assert found.id == rec.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_recommendation("nonexistent") is None


# -------------------------------------------------------------------
# list_recommendations
# -------------------------------------------------------------------


class TestListRecommendations:
    def test_list_all(self):
        eng = _engine()
        eng.create_recommendation("svc-a")
        eng.create_recommendation("svc-b")
        eng.create_recommendation("svc-c")
        assert len(eng.list_recommendations()) == 3

    def test_filter_by_service(self):
        eng = _engine()
        eng.create_recommendation("svc-a")
        eng.create_recommendation("svc-b")
        eng.create_recommendation("svc-a")
        results = eng.list_recommendations(service_name="svc-a")
        assert len(results) == 2
        assert all(r.service_name == "svc-a" for r in results)

    def test_filter_by_direction(self):
        eng = _engine()
        eng.create_recommendation("svc-a", direction=ScaleDirection.SCALE_UP)
        eng.create_recommendation("svc-b", direction=ScaleDirection.SCALE_DOWN)
        results = eng.list_recommendations(direction=ScaleDirection.SCALE_UP)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.create_recommendation(f"svc-{i}")
        results = eng.list_recommendations(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# register_traffic_window
# -------------------------------------------------------------------


class TestRegisterTrafficWindow:
    def test_basic_register(self):
        eng = _engine()
        window = eng.register_traffic_window(
            "svc-a",
            start_hour=8,
            end_hour=18,
            expected_load_pct=75.0,
        )
        assert window.service_name == "svc-a"
        assert window.start_hour == 8
        assert window.end_hour == 18
        assert window.expected_load_pct == 75.0
        assert len(eng.list_traffic_windows()) == 1


# -------------------------------------------------------------------
# list_traffic_windows
# -------------------------------------------------------------------


class TestListTrafficWindows:
    def test_list_all(self):
        eng = _engine()
        eng.register_traffic_window("svc-a")
        eng.register_traffic_window("svc-b")
        assert len(eng.list_traffic_windows()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.register_traffic_window("svc-a")
        eng.register_traffic_window("svc-b")
        eng.register_traffic_window("svc-a")
        results = eng.list_traffic_windows(service_name="svc-a")
        assert len(results) == 2
        assert all(w.service_name == "svc-a" for w in results)


# -------------------------------------------------------------------
# find_optimal_scale_time
# -------------------------------------------------------------------


class TestFindOptimalScaleTime:
    def test_with_windows(self):
        eng = _engine()
        eng.register_traffic_window(
            "svc-a",
            start_hour=2,
            end_hour=6,
            expected_load_pct=20.0,
        )
        eng.register_traffic_window(
            "svc-a",
            start_hour=8,
            end_hour=18,
            expected_load_pct=80.0,
        )
        rec = eng.find_optimal_scale_time("svc-a", ScaleDirection.SCALE_UP)
        assert rec.service_name == "svc-a"
        assert rec.direction == ScaleDirection.SCALE_UP
        assert rec.confidence == TimingConfidence.MODERATE

    def test_without_windows(self):
        eng = _engine()
        rec = eng.find_optimal_scale_time("svc-a")
        assert rec.confidence == TimingConfidence.VERY_LOW
        assert rec.reason == "No traffic windows registered"


# -------------------------------------------------------------------
# evaluate_timing
# -------------------------------------------------------------------


class TestEvaluateTiming:
    def test_valid_recommendation(self):
        eng = _engine()
        eng.register_traffic_window("svc-a", expected_load_pct=50.0)
        rec = eng.create_recommendation("svc-a")
        result = eng.evaluate_timing(rec.id)
        assert result["valid"] is True
        assert result["recommendation_id"] == rec.id

    def test_not_found(self):
        eng = _engine()
        result = eng.evaluate_timing("nonexistent")
        assert result["valid"] is False
        assert result["reason"] == "Recommendation not found"


# -------------------------------------------------------------------
# cancel_recommendation
# -------------------------------------------------------------------


class TestCancelRecommendation:
    def test_cancel_success(self):
        eng = _engine()
        rec = eng.create_recommendation("svc-a")
        assert eng.cancel_recommendation(rec.id) is True
        assert rec.status == "cancelled"

    def test_cancel_not_found(self):
        eng = _engine()
        assert eng.cancel_recommendation("nonexistent") is False


# -------------------------------------------------------------------
# generate_timing_report
# -------------------------------------------------------------------


class TestGenerateTimingReport:
    def test_basic_report(self):
        eng = _engine()
        eng.create_recommendation(
            "svc-a",
            direction=ScaleDirection.SCALE_UP,
            cost_saving_pct=10.0,
        )
        eng.create_recommendation(
            "svc-b",
            direction=ScaleDirection.SCALE_DOWN,
            cost_saving_pct=5.0,
        )
        eng.register_traffic_window("svc-a")
        report = eng.generate_timing_report()
        assert report.total_recommendations == 2
        assert report.total_windows == 1
        assert isinstance(report.by_direction, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_timing_report()
        assert report.total_recommendations == 0
        assert report.total_windows == 0
        assert report.avg_cost_saving_pct == 0.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.create_recommendation("svc-a")
        eng.create_recommendation("svc-b")
        eng.register_traffic_window("svc-a")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_recommendations()) == 0
        assert len(eng.list_traffic_windows()) == 0

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
        assert stats["total_recommendations"] == 0
        assert stats["total_windows"] == 0
        assert stats["lookahead_hours"] == 24
        assert stats["direction_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.create_recommendation(
            "svc-a",
            direction=ScaleDirection.SCALE_UP,
        )
        eng.create_recommendation(
            "svc-b",
            direction=ScaleDirection.SCALE_DOWN,
        )
        eng.register_traffic_window("svc-a")
        stats = eng.get_stats()
        assert stats["total_recommendations"] == 2
        assert stats["total_windows"] == 1
        assert len(stats["direction_distribution"]) == 2
