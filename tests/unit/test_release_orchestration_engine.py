"""Tests for shieldops.changes.release_orchestration_engine — ReleaseOrchestrationEngine."""

from __future__ import annotations

from shieldops.changes.release_orchestration_engine import (
    CanaryHealth,
    ReleaseOrchestrationEngine,
    ReleaseStage,
    RolloutStrategy,
)


def _engine(**kw) -> ReleaseOrchestrationEngine:
    return ReleaseOrchestrationEngine(**kw)


class TestEnums:
    def test_release_stage(self):
        assert ReleaseStage.CANARY == "canary"

    def test_rollout_strategy(self):
        assert RolloutStrategy.PERCENTAGE_BASED == "percentage_based"

    def test_canary_health(self):
        assert CanaryHealth.HEALTHY == "healthy"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(name="v2.0-release", stage=ReleaseStage.CANARY)
        assert rec.name == "v2.0-release"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"rel-{i}")
        assert len(eng._records) == 3


class TestCanaryHealth:
    def test_basic(self):
        eng = _engine()
        eng.record_item(
            name="rel-1",
            canary_health=CanaryHealth.HEALTHY,
            stage=ReleaseStage.CANARY,
            error_rate_delta=0.01,
        )
        result = eng.evaluate_canary_health()
        assert isinstance(result, list)


class TestRolloutProgress:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="rel-1", rollout_percentage=50.0)
        result = eng.track_rollout_progress()
        assert isinstance(result, dict)


class TestFeatureFlags:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="rel-1", feature_flags_active=5)
        result = eng.analyze_feature_flag_usage()
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="rel-1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="rel-1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="rel-1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
