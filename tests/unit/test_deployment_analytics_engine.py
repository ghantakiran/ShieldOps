"""Tests for shieldops.analytics.deployment_analytics_engine — DeploymentAnalyticsEngine."""

from __future__ import annotations

from shieldops.analytics.deployment_analytics_engine import (
    DeploymentAnalyticsEngine,
    DeploymentClass,
    DORAMetric,
    PerformanceLevel,
)


def _engine(**kw) -> DeploymentAnalyticsEngine:
    return DeploymentAnalyticsEngine(**kw)


class TestEnums:
    def test_dora_metric(self):
        assert DORAMetric.DEPLOYMENT_FREQUENCY == "deployment_frequency"

    def test_performance_level(self):
        assert PerformanceLevel.ELITE == "elite"

    def test_deployment_class(self):
        assert DeploymentClass.STANDARD == "standard"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(name="api-deploy", dora_metric=DORAMetric.DEPLOYMENT_FREQUENCY)
        assert rec.name == "api-deploy"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"d-{i}")
        assert len(eng._records) == 3


class TestDORAClassification:
    def test_basic(self):
        eng = _engine()
        eng.record_item(
            name="d1", dora_metric=DORAMetric.DEPLOYMENT_FREQUENCY, deploys_per_day=10.0
        )
        result = eng.classify_dora_performance()
        assert isinstance(result, (dict, list))


class TestLeadTimeBottlenecks:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="d1", lead_time_hours=48.0, pipeline_duration_minutes=30.0)
        result = eng.analyze_lead_time_bottlenecks()
        assert isinstance(result, dict)


class TestChangeFailureRate:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="d1", change_failure_rate_pct=5.0)
        result = eng.track_change_failure_rate()
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="d1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="d1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="d1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
