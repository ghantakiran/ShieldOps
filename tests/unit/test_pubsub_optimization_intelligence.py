"""Tests for PubsubOptimizationIntelligence."""

from __future__ import annotations

from shieldops.observability.pubsub_optimization_intelligence import (
    DistributionHealth,
    OptimizationAction,
    PartitionStrategy,
    PubsubOptimizationIntelligence,
)


def _engine(**kw) -> PubsubOptimizationIntelligence:
    return PubsubOptimizationIntelligence(**kw)


class TestEnums:
    def test_partition_strategy_values(self):
        for v in PartitionStrategy:
            assert isinstance(v.value, str)

    def test_distribution_health_values(self):
        for v in DistributionHealth:
            assert isinstance(v.value, str)

    def test_optimization_action_values(self):
        for v in OptimizationAction:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(topic_name="t1")
        assert r.topic_name == "t1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(topic_name=f"t-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().add_record()
        assert r.partition_strategy == (PartitionStrategy.KEY_BASED)


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(topic_name="t1", skew_ratio=0.3)
        a = eng.process(r.id)
        assert hasattr(a, "topic_name")
        assert a.topic_name == "t1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(topic_name="t1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_skewed_topics(self):
        eng = _engine()
        eng.add_record(
            topic_name="t1",
            distribution_health=(DistributionHealth.SKEWED),
        )
        rpt = eng.generate_report()
        assert len(rpt.skewed_topics) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(topic_name="t1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(topic_name="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestOptimizePartitionDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(topic_name="t1", skew_ratio=0.5)
        result = eng.optimize_partition_distribution()
        assert len(result) == 1
        assert result[0]["action"] == "rebalance"

    def test_empty(self):
        r = _engine().optimize_partition_distribution()
        assert r == []


class TestDetectHotPartitions:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(topic_name="t1", skew_ratio=0.8)
        result = eng.detect_hot_partitions()
        assert len(result) == 1

    def test_no_hot(self):
        eng = _engine()
        eng.add_record(topic_name="t1", skew_ratio=0.1)
        assert eng.detect_hot_partitions() == []


class TestRankTopicsByRebalancingNeed:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            topic_name="t1",
            skew_ratio=0.8,
            partition_count=12,
        )
        eng.add_record(
            topic_name="t2",
            skew_ratio=0.1,
            partition_count=4,
        )
        result = eng.rank_topics_by_rebalancing_need()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_topics_by_rebalancing_need()
        assert r == []
