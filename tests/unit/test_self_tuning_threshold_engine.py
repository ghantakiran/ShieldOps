"""Tests for shieldops.observability.self_tuning_threshold_engine — SelfTuningThresholdEngine."""

from __future__ import annotations

from shieldops.observability.self_tuning_threshold_engine import (
    SeasonalityType,
    SelfTuningThresholdEngine,
    ThresholdRecord,
    ThresholdReport,
    ThresholdStatus,
    TuningAction,
    TuningEvent,
)


def _engine(**kw) -> SelfTuningThresholdEngine:
    return SelfTuningThresholdEngine(**kw)


class TestEnums:
    def test_seasonality_hourly(self):
        assert SeasonalityType.HOURLY == "hourly"

    def test_seasonality_daily(self):
        assert SeasonalityType.DAILY == "daily"

    def test_seasonality_weekly(self):
        assert SeasonalityType.WEEKLY == "weekly"

    def test_seasonality_none(self):
        assert SeasonalityType.NONE == "none"

    def test_tuning_action_raise(self):
        assert TuningAction.RAISE == "raise"

    def test_tuning_action_lower(self):
        assert TuningAction.LOWER == "lower"

    def test_tuning_action_hold(self):
        assert TuningAction.HOLD == "hold"

    def test_threshold_status_active(self):
        assert ThresholdStatus.ACTIVE == "active"

    def test_threshold_status_locked(self):
        assert ThresholdStatus.LOCKED == "locked"

    def test_threshold_status_disabled(self):
        assert ThresholdStatus.DISABLED == "disabled"


class TestModels:
    def test_threshold_record_defaults(self):
        r = ThresholdRecord()
        assert r.id
        assert r.metric_name == ""
        assert r.baseline == 0.0
        assert r.status == ThresholdStatus.ACTIVE

    def test_tuning_event_defaults(self):
        e = TuningEvent()
        assert e.id
        assert e.action == TuningAction.HOLD

    def test_report_defaults(self):
        r = ThresholdReport()
        assert r.total_thresholds == 0
        assert r.recommendations == []


class TestAddThreshold:
    def test_basic(self):
        eng = _engine()
        t = eng.add_threshold("cpu", baseline=50.0, upper_bound=90.0)
        assert t.metric_name == "cpu"
        assert t.baseline == 50.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_threshold(f"m-{i}")
        assert len(eng._thresholds) == 3


class TestTuneThresholds:
    def test_hold_within_sensitivity(self):
        eng = _engine(sensitivity=5.0)
        eng.add_threshold("cpu", baseline=50.0)
        events = eng.tune_thresholds()
        assert len(events) == 1
        assert events[0].action == TuningAction.HOLD

    def test_raise_above_sensitivity(self):
        eng = _engine(sensitivity=2.0)
        t = eng.add_threshold("cpu", baseline=50.0)
        t.current_value = 60.0
        events = eng.tune_thresholds()
        assert events[0].action == TuningAction.RAISE

    def test_lower_below_sensitivity(self):
        eng = _engine(sensitivity=2.0)
        t = eng.add_threshold("cpu", baseline=50.0)
        t.current_value = 40.0
        events = eng.tune_thresholds()
        assert events[0].action == TuningAction.LOWER

    def test_skip_disabled(self):
        eng = _engine()
        eng.add_threshold("cpu", status=ThresholdStatus.DISABLED)
        events = eng.tune_thresholds()
        assert len(events) == 0

    def test_skip_locked(self):
        eng = _engine()
        eng.add_threshold("cpu", status=ThresholdStatus.LOCKED)
        events = eng.tune_thresholds()
        assert len(events) == 0

    def test_filter_by_metric(self):
        eng = _engine(sensitivity=2.0)
        t = eng.add_threshold("cpu", baseline=50.0)
        t.current_value = 60.0
        eng.add_threshold("mem", baseline=50.0)
        events = eng.tune_thresholds(metric_name="cpu")
        assert len(events) == 1


class TestAnalyzeSeasonality:
    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_seasonality("cpu")
        assert result["seasonality"] == "none"
        assert result["sample_count"] == 0

    def test_with_data(self):
        eng = _engine()
        eng.add_threshold("cpu", baseline=50.0)
        result = eng.analyze_seasonality("cpu")
        assert result["sample_count"] == 1

    def test_high_variance_daily(self):
        eng = _engine()
        for v in [10, 100, 10, 100]:
            t = eng.add_threshold("cpu", baseline=float(v))
            t.current_value = float(v)
        result = eng.analyze_seasonality("cpu")
        assert result["seasonality"] in ("hourly", "daily")


class TestCalculateDynamicBaseline:
    def test_no_data(self):
        eng = _engine()
        result = eng.calculate_dynamic_baseline("cpu")
        assert result["samples"] == 0

    def test_with_data(self):
        eng = _engine()
        eng.add_threshold("cpu", baseline=50.0)
        result = eng.calculate_dynamic_baseline("cpu")
        assert result["samples"] == 1
        assert result["baseline"] == 50.0


class TestApplyThresholds:
    def test_no_threshold(self):
        eng = _engine()
        result = eng.apply_thresholds("cpu", 50.0)
        assert result["status"] == "no_threshold"

    def test_within_bounds(self):
        eng = _engine()
        eng.add_threshold("cpu", upper_bound=90.0, lower_bound=10.0)
        result = eng.apply_thresholds("cpu", 50.0)
        assert result["breached"] is False

    def test_breach_upper(self):
        eng = _engine()
        eng.add_threshold("cpu", upper_bound=90.0, lower_bound=10.0)
        result = eng.apply_thresholds("cpu", 95.0)
        assert result["breached"] is True

    def test_breach_lower(self):
        eng = _engine()
        eng.add_threshold("cpu", upper_bound=90.0, lower_bound=10.0)
        result = eng.apply_thresholds("cpu", 5.0)
        assert result["breached"] is True


class TestGetTuningHistory:
    def test_empty(self):
        eng = _engine()
        assert eng.get_tuning_history() == []

    def test_with_events(self):
        eng = _engine(sensitivity=2.0)
        t = eng.add_threshold("cpu", baseline=50.0)
        t.current_value = 60.0
        eng.tune_thresholds()
        assert len(eng.get_tuning_history()) == 1

    def test_filter_by_metric(self):
        eng = _engine(sensitivity=2.0)
        t1 = eng.add_threshold("cpu", baseline=50.0)
        t1.current_value = 60.0
        t2 = eng.add_threshold("mem", baseline=50.0)
        t2.current_value = 60.0
        eng.tune_thresholds()
        assert len(eng.get_tuning_history(metric_name="cpu")) == 1

    def test_limit(self):
        eng = _engine(sensitivity=2.0)
        for i in range(10):
            t = eng.add_threshold(f"m-{i}", baseline=50.0)
            t.current_value = 60.0
        eng.tune_thresholds()
        assert len(eng.get_tuning_history(limit=3)) == 3


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_thresholds == 0

    def test_with_locked(self):
        eng = _engine()
        eng.add_threshold("cpu", status=ThresholdStatus.LOCKED)
        report = eng.generate_report()
        assert any("locked" in r.lower() for r in report.recommendations)


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_threshold("cpu")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._thresholds) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_thresholds"] == 0

    def test_populated(self):
        eng = _engine()
        eng.add_threshold("cpu")
        stats = eng.get_stats()
        assert stats["unique_metrics"] == 1
