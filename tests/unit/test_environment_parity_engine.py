"""Tests for shieldops.operations.environment_parity_engine — EnvironmentParityEngine."""

from __future__ import annotations

from shieldops.operations.environment_parity_engine import (
    DeviationType,
    EnvironmentParityEngine,
    EnvironmentType,
    ParityLevel,
)


def _engine(**kw) -> EnvironmentParityEngine:
    return EnvironmentParityEngine(**kw)


class TestEnums:
    def test_env_type(self):
        assert EnvironmentType.PRODUCTION == "production"

    def test_deviation(self):
        assert DeviationType.CONFIG_DRIFT == "config_drift"

    def test_parity(self):
        assert ParityLevel.IDENTICAL == "identical"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(name="api-config", source_env=EnvironmentType.PRODUCTION)
        assert rec.name == "api-config"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"cfg-{i}")
        assert len(eng._records) == 3


class TestCompareEnvironments:
    def test_basic(self):
        eng = _engine()
        eng.record_item(
            name="cfg-1", source_env=EnvironmentType.PRODUCTION, target_env=EnvironmentType.STAGING
        )
        eng.record_item(
            name="cfg-1", source_env=EnvironmentType.PRODUCTION, target_env=EnvironmentType.STAGING
        )
        result = eng.compare_environments()
        assert isinstance(result, dict)


class TestCriticalDeviations:
    def test_basic(self):
        eng = _engine()
        eng.record_item(
            name="cfg-1",
            deviation_type=DeviationType.CONFIG_DRIFT,
            parity_level=ParityLevel.CRITICAL_DEVIATION,
        )
        result = eng.identify_critical_deviations()
        assert isinstance(result, list)


class TestSyncActions:
    def test_basic(self):
        eng = _engine()
        eng.record_item(
            name="cfg-1", parity_score=10.0, parity_level=ParityLevel.CRITICAL_DEVIATION
        )
        result = eng.recommend_sync_actions()
        assert isinstance(result, list)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="cfg-1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="cfg-1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="cfg-1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
