"""Tests for shieldops.observability.metric_cardinality_governor — MetricCardinalityGovernor."""

from __future__ import annotations

from shieldops.observability.metric_cardinality_governor import (
    CardinalityLevel,
    CardinalityRecord,
    LabelPolicyAction,
    MetricCardinalityGovernor,
    MetricCategory,
)


def _engine(**kw) -> MetricCardinalityGovernor:
    return MetricCardinalityGovernor(**kw)


class TestEnums:
    def test_cardinality_critical(self):
        assert CardinalityLevel.CRITICAL == "critical"

    def test_label_policy_drop(self):
        assert LabelPolicyAction.DROP == "drop"

    def test_metric_category(self):
        assert MetricCategory.COUNTER == "counter"


class TestModels:
    def test_record_defaults(self):
        r = CardinalityRecord()
        assert r.id
        assert r.created_at > 0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(metric_name="http_requests_total", series_count=50000)
        assert rec.metric_name == "http_requests_total"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(metric_name=f"metric-{i}", series_count=i * 100)
        assert len(eng._records) == 3


class TestTopOffenders:
    def test_basic(self):
        eng = _engine()
        eng.add_record(metric_name="high_card_metric", series_count=100000)
        eng.add_record(metric_name="low_card_metric", series_count=10)
        result = eng.identify_top_offenders()
        assert isinstance(result, list)


class TestAggregations:
    def test_basic(self):
        eng = _engine()
        eng.add_record(metric_name="high_card_metric", series_count=100000)
        result = eng.recommend_aggregations("high_card_metric")
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", series_count=500, service="api")
        result = eng.process("cpu")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", series_count=500)
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", series_count=500)
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(metric_name="cpu", series_count=500)
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
