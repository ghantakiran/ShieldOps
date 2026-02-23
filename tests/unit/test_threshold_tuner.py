"""Tests for shieldops.observability.threshold_tuner — ThresholdTuningEngine."""

from __future__ import annotations

import pytest

from shieldops.observability.threshold_tuner import (
    MetricSample,
    ThresholdConfig,
    ThresholdDirection,
    ThresholdTuningEngine,
    TuningAction,
    TuningRecommendation,
    TuningStatus,
)


def _engine(**kw) -> ThresholdTuningEngine:
    return ThresholdTuningEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ThresholdDirection (3 values)

    def test_threshold_direction_upper(self):
        assert ThresholdDirection.UPPER == "upper"

    def test_threshold_direction_lower(self):
        assert ThresholdDirection.LOWER == "lower"

    def test_threshold_direction_both(self):
        assert ThresholdDirection.BOTH == "both"

    # TuningAction (4 values)

    def test_tuning_action_increase(self):
        assert TuningAction.INCREASE == "increase"

    def test_tuning_action_decrease(self):
        assert TuningAction.DECREASE == "decrease"

    def test_tuning_action_no_change(self):
        assert TuningAction.NO_CHANGE == "no_change"

    def test_tuning_action_disable(self):
        assert TuningAction.DISABLE == "disable"

    # TuningStatus (4 values)

    def test_tuning_status_proposed(self):
        assert TuningStatus.PROPOSED == "proposed"

    def test_tuning_status_approved(self):
        assert TuningStatus.APPROVED == "approved"

    def test_tuning_status_applied(self):
        assert TuningStatus.APPLIED == "applied"

    def test_tuning_status_rejected(self):
        assert TuningStatus.REJECTED == "rejected"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_threshold_config_defaults(self):
        config = ThresholdConfig(metric_name="cpu_usage")
        assert config.id
        assert config.metric_name == "cpu_usage"
        assert config.service == ""
        assert config.direction == ThresholdDirection.UPPER
        assert config.current_value == 0.0
        assert config.min_value == 0.0
        assert config.max_value == 100.0
        assert config.created_at > 0
        assert config.updated_at > 0

    def test_metric_sample_defaults(self):
        sample = MetricSample(threshold_id="th-1", value=42.0)
        assert sample.id
        assert sample.threshold_id == "th-1"
        assert sample.value == 42.0
        assert sample.triggered_alert is False
        assert sample.was_actionable is False
        assert sample.recorded_at > 0

    def test_tuning_recommendation_defaults(self):
        rec = TuningRecommendation(
            threshold_id="th-1",
            action=TuningAction.INCREASE,
        )
        assert rec.id
        assert rec.threshold_id == "th-1"
        assert rec.action == TuningAction.INCREASE
        assert rec.current_value == 0.0
        assert rec.recommended_value == 0.0
        assert rec.reason == ""
        assert rec.status == TuningStatus.PROPOSED
        assert rec.created_at > 0


# ---------------------------------------------------------------------------
# register_threshold
# ---------------------------------------------------------------------------


class TestRegisterThreshold:
    def test_basic_register(self):
        eng = _engine()
        config = eng.register_threshold("cpu_usage", 80.0)
        assert config.metric_name == "cpu_usage"
        assert config.current_value == 80.0
        assert config.direction == ThresholdDirection.UPPER
        assert eng.get_threshold(config.id) is not None

    def test_register_assigns_unique_ids(self):
        eng = _engine()
        c1 = eng.register_threshold("cpu_usage", 80.0)
        c2 = eng.register_threshold("mem_usage", 90.0)
        assert c1.id != c2.id

    def test_register_with_extra_fields(self):
        eng = _engine()
        config = eng.register_threshold(
            "latency_p99",
            500.0,
            direction=ThresholdDirection.LOWER,
            service="api-gw",
            min_value=100.0,
            max_value=2000.0,
        )
        assert config.direction == ThresholdDirection.LOWER
        assert config.service == "api-gw"
        assert config.min_value == 100.0
        assert config.max_value == 2000.0

    def test_evicts_at_max_thresholds(self):
        eng = _engine(max_thresholds=3)
        ids = []
        for i in range(4):
            config = eng.register_threshold(f"metric_{i}", float(i * 10))
            ids.append(config.id)
        assert eng.get_threshold(ids[0]) is None
        assert eng.get_threshold(ids[3]) is not None
        assert len(eng.list_thresholds()) == 3


# ---------------------------------------------------------------------------
# record_sample
# ---------------------------------------------------------------------------


class TestRecordSample:
    def test_basic_record(self):
        eng = _engine()
        config = eng.register_threshold("cpu_usage", 80.0)
        sample = eng.record_sample(config.id, 75.0)
        assert sample is not None
        assert sample.threshold_id == config.id
        assert sample.value == 75.0

    def test_record_not_found(self):
        eng = _engine()
        result = eng.record_sample("nonexistent", 50.0)
        assert result is None

    def test_trims_at_max_samples(self):
        eng = _engine(max_samples=5)
        config = eng.register_threshold("cpu_usage", 80.0)
        for i in range(7):
            eng.record_sample(config.id, float(i))
        stats = eng.get_stats()
        assert stats["total_samples"] == 5


# ---------------------------------------------------------------------------
# generate_recommendations
# ---------------------------------------------------------------------------


class TestGenerateRecommendations:
    def test_no_samples_yields_no_recommendations(self):
        eng = _engine()
        eng.register_threshold("cpu_usage", 80.0)
        recs = eng.generate_recommendations()
        assert recs == []

    def test_increase_for_non_actionable_alerts(self):
        eng = _engine()
        config = eng.register_threshold("cpu_usage", 80.0, max_value=100.0)
        # 5 samples, all triggered but none actionable -> INCREASE
        for i in range(5):
            eng.record_sample(
                config.id,
                85.0 + i,
                triggered_alert=True,
                was_actionable=False,
            )
        recs = eng.generate_recommendations()
        assert len(recs) == 1
        assert recs[0].action == TuningAction.INCREASE
        # recommended = min(80.0 * 1.2, 100.0) = 96.0
        assert recs[0].recommended_value == pytest.approx(96.0, abs=0.1)

    def test_decrease_for_high_actionable(self):
        eng = _engine()
        config = eng.register_threshold("cpu_usage", 80.0, min_value=10.0)
        # 5 samples, all triggered and all actionable -> >0.8 ratio -> DECREASE
        for i in range(5):
            eng.record_sample(
                config.id,
                85.0 + i,
                triggered_alert=True,
                was_actionable=True,
            )
        recs = eng.generate_recommendations()
        assert len(recs) == 1
        assert recs[0].action == TuningAction.DECREASE
        assert recs[0].recommended_value > 0

    def test_no_change_when_no_triggered_alerts(self):
        eng = _engine()
        config = eng.register_threshold("cpu_usage", 80.0)
        # 5 samples, none triggered -> NO_CHANGE
        for i in range(5):
            eng.record_sample(config.id, 50.0 + i)
        recs = eng.generate_recommendations()
        assert len(recs) == 1
        assert recs[0].action == TuningAction.NO_CHANGE
        assert recs[0].recommended_value == 80.0


# ---------------------------------------------------------------------------
# apply_recommendation
# ---------------------------------------------------------------------------


class TestApplyRecommendation:
    def test_basic_apply(self):
        eng = _engine()
        config = eng.register_threshold("cpu_usage", 80.0, max_value=100.0)
        for i in range(5):
            eng.record_sample(
                config.id,
                85.0 + i,
                triggered_alert=True,
                was_actionable=False,
            )
        recs = eng.generate_recommendations()
        applied = eng.apply_recommendation(recs[0].id)
        assert applied is not None
        assert applied.status == TuningStatus.APPLIED
        # Threshold value should be updated
        updated = eng.get_threshold(config.id)
        assert updated is not None
        assert updated.current_value == applied.recommended_value

    def test_apply_not_found(self):
        eng = _engine()
        result = eng.apply_recommendation("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# reject_recommendation
# ---------------------------------------------------------------------------


class TestRejectRecommendation:
    def test_basic_reject(self):
        eng = _engine()
        config = eng.register_threshold("cpu_usage", 80.0)
        for i in range(5):
            eng.record_sample(
                config.id,
                50.0 + i,
            )
        recs = eng.generate_recommendations()
        rejected = eng.reject_recommendation(recs[0].id)
        assert rejected is not None
        assert rejected.status == TuningStatus.REJECTED

    def test_reject_not_found(self):
        eng = _engine()
        result = eng.reject_recommendation("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# get_threshold
# ---------------------------------------------------------------------------


class TestGetThreshold:
    def test_found(self):
        eng = _engine()
        config = eng.register_threshold("cpu_usage", 80.0)
        result = eng.get_threshold(config.id)
        assert result is not None
        assert result.id == config.id

    def test_not_found(self):
        eng = _engine()
        assert eng.get_threshold("nonexistent") is None


# ---------------------------------------------------------------------------
# list_thresholds
# ---------------------------------------------------------------------------


class TestListThresholds:
    def test_list_all(self):
        eng = _engine()
        eng.register_threshold("cpu_usage", 80.0)
        eng.register_threshold("mem_usage", 90.0)
        eng.register_threshold("disk_io", 70.0)
        assert len(eng.list_thresholds()) == 3

    def test_filter_by_direction(self):
        eng = _engine()
        eng.register_threshold(
            "cpu_usage",
            80.0,
            direction=ThresholdDirection.UPPER,
        )
        eng.register_threshold(
            "latency",
            500.0,
            direction=ThresholdDirection.LOWER,
        )
        eng.register_threshold(
            "mem_usage",
            90.0,
            direction=ThresholdDirection.UPPER,
        )
        results = eng.list_thresholds(direction=ThresholdDirection.UPPER)
        assert len(results) == 2
        assert all(t.direction == ThresholdDirection.UPPER for t in results)


# ---------------------------------------------------------------------------
# list_recommendations
# ---------------------------------------------------------------------------


class TestListRecommendations:
    def test_list_all(self):
        eng = _engine()
        c1 = eng.register_threshold("cpu_usage", 80.0)
        c2 = eng.register_threshold("mem_usage", 90.0)
        for config in [c1, c2]:
            for i in range(5):
                eng.record_sample(config.id, 50.0 + i)
        eng.generate_recommendations()
        recs = eng.list_recommendations()
        assert len(recs) == 2

    def test_filter_by_status(self):
        eng = _engine()
        config = eng.register_threshold("cpu_usage", 80.0)
        for i in range(5):
            eng.record_sample(config.id, 50.0 + i)
        recs = eng.generate_recommendations()
        eng.reject_recommendation(recs[0].id)
        proposed = eng.list_recommendations(status=TuningStatus.PROPOSED)
        rejected = eng.list_recommendations(status=TuningStatus.REJECTED)
        assert len(proposed) == 0
        assert len(rejected) == 1


# ---------------------------------------------------------------------------
# delete_threshold
# ---------------------------------------------------------------------------


class TestDeleteThreshold:
    def test_delete_success(self):
        eng = _engine()
        config = eng.register_threshold("cpu_usage", 80.0)
        assert eng.delete_threshold(config.id) is True
        assert eng.get_threshold(config.id) is None

    def test_delete_not_found(self):
        eng = _engine()
        assert eng.delete_threshold("nonexistent") is False


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_thresholds"] == 0
        assert stats["total_samples"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["direction_distribution"] == {}
        assert stats["recommendation_status_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        c1 = eng.register_threshold(
            "cpu_usage",
            80.0,
            direction=ThresholdDirection.UPPER,
        )
        eng.register_threshold(
            "latency",
            500.0,
            direction=ThresholdDirection.LOWER,
        )
        for i in range(5):
            eng.record_sample(c1.id, 50.0 + i)
        eng.generate_recommendations()

        stats = eng.get_stats()
        assert stats["total_thresholds"] == 2
        assert stats["total_samples"] == 5
        assert stats["total_recommendations"] == 1
        assert stats["direction_distribution"][ThresholdDirection.UPPER] == 1
        assert stats["direction_distribution"][ThresholdDirection.LOWER] == 1
        assert stats["recommendation_status_distribution"][TuningStatus.PROPOSED] == 1
