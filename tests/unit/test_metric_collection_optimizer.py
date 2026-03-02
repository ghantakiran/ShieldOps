"""Tests for shieldops.observability.metric_collection_optimizer — MetricCollectionOptimizer."""

from __future__ import annotations

from shieldops.observability.metric_collection_optimizer import (
    CollectionAnalysis,
    CollectionRecord,
    CollectionStatus,
    MetricCollectionOptimizer,
    MetricCollectionReport,
    MetricTier,
    OptimizationStrategy,
)


def _engine(**kw) -> MetricCollectionOptimizer:
    return MetricCollectionOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_optimal(self):
        assert CollectionStatus.OPTIMAL == "optimal"

    def test_status_redundant(self):
        assert CollectionStatus.REDUNDANT == "redundant"

    def test_status_stale(self):
        assert CollectionStatus.STALE == "stale"

    def test_status_expensive(self):
        assert CollectionStatus.EXPENSIVE == "expensive"

    def test_status_missing(self):
        assert CollectionStatus.MISSING == "missing"

    def test_strategy_reduce_frequency(self):
        assert OptimizationStrategy.REDUCE_FREQUENCY == "reduce_frequency"

    def test_strategy_aggregate(self):
        assert OptimizationStrategy.AGGREGATE == "aggregate"

    def test_strategy_drop_metric(self):
        assert OptimizationStrategy.DROP_METRIC == "drop_metric"

    def test_strategy_tier_storage(self):
        assert OptimizationStrategy.TIER_STORAGE == "tier_storage"

    def test_strategy_add_collection(self):
        assert OptimizationStrategy.ADD_COLLECTION == "add_collection"

    def test_tier_real_time(self):
        assert MetricTier.REAL_TIME == "real_time"

    def test_tier_near_real_time(self):
        assert MetricTier.NEAR_REAL_TIME == "near_real_time"

    def test_tier_hourly(self):
        assert MetricTier.HOURLY == "hourly"

    def test_tier_daily(self):
        assert MetricTier.DAILY == "daily"

    def test_tier_archival(self):
        assert MetricTier.ARCHIVAL == "archival"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_collection_record_defaults(self):
        r = CollectionRecord()
        assert r.id
        assert r.metric_name == ""
        assert r.collection_status == CollectionStatus.OPTIMAL
        assert r.optimization_strategy == OptimizationStrategy.REDUCE_FREQUENCY
        assert r.metric_tier == MetricTier.REAL_TIME
        assert r.efficiency_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_collection_analysis_defaults(self):
        a = CollectionAnalysis()
        assert a.id
        assert a.metric_name == ""
        assert a.collection_status == CollectionStatus.OPTIMAL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_metric_collection_report_defaults(self):
        r = MetricCollectionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_efficiency_count == 0
        assert r.avg_efficiency_score == 0.0
        assert r.by_status == {}
        assert r.by_strategy == {}
        assert r.by_tier == {}
        assert r.top_inefficient == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_collection
# ---------------------------------------------------------------------------


class TestRecordCollection:
    def test_basic(self):
        eng = _engine()
        r = eng.record_collection(
            metric_name="cpu_utilization",
            collection_status=CollectionStatus.REDUNDANT,
            optimization_strategy=OptimizationStrategy.AGGREGATE,
            metric_tier=MetricTier.HOURLY,
            efficiency_score=45.0,
            service="api-gateway",
            team="sre",
        )
        assert r.metric_name == "cpu_utilization"
        assert r.collection_status == CollectionStatus.REDUNDANT
        assert r.optimization_strategy == OptimizationStrategy.AGGREGATE
        assert r.metric_tier == MetricTier.HOURLY
        assert r.efficiency_score == 45.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_collection(metric_name=f"metric-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_collection
# ---------------------------------------------------------------------------


class TestGetCollection:
    def test_found(self):
        eng = _engine()
        r = eng.record_collection(
            metric_name="cpu_utilization",
            collection_status=CollectionStatus.STALE,
        )
        result = eng.get_collection(r.id)
        assert result is not None
        assert result.collection_status == CollectionStatus.STALE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_collection("nonexistent") is None


# ---------------------------------------------------------------------------
# list_collections
# ---------------------------------------------------------------------------


class TestListCollections:
    def test_list_all(self):
        eng = _engine()
        eng.record_collection(metric_name="metric-1")
        eng.record_collection(metric_name="metric-2")
        assert len(eng.list_collections()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_collection(
            metric_name="metric-1",
            collection_status=CollectionStatus.REDUNDANT,
        )
        eng.record_collection(
            metric_name="metric-2",
            collection_status=CollectionStatus.OPTIMAL,
        )
        results = eng.list_collections(
            collection_status=CollectionStatus.REDUNDANT,
        )
        assert len(results) == 1

    def test_filter_by_strategy(self):
        eng = _engine()
        eng.record_collection(
            metric_name="metric-1",
            optimization_strategy=OptimizationStrategy.AGGREGATE,
        )
        eng.record_collection(
            metric_name="metric-2",
            optimization_strategy=OptimizationStrategy.DROP_METRIC,
        )
        results = eng.list_collections(
            optimization_strategy=OptimizationStrategy.AGGREGATE,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_collection(metric_name="metric-1", team="sre")
        eng.record_collection(metric_name="metric-2", team="platform")
        results = eng.list_collections(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_collection(metric_name=f"metric-{i}")
        assert len(eng.list_collections(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            metric_name="cpu_utilization",
            collection_status=CollectionStatus.EXPENSIVE,
            analysis_score=35.0,
            threshold=75.0,
            breached=True,
            description="Expensive metric collection detected",
        )
        assert a.metric_name == "cpu_utilization"
        assert a.collection_status == CollectionStatus.EXPENSIVE
        assert a.analysis_score == 35.0
        assert a.threshold == 75.0
        assert a.breached is True
        assert a.description == "Expensive metric collection detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(metric_name=f"metric-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_collection_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCollectionDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_collection(
            metric_name="metric-1",
            collection_status=CollectionStatus.REDUNDANT,
            efficiency_score=40.0,
        )
        eng.record_collection(
            metric_name="metric-2",
            collection_status=CollectionStatus.REDUNDANT,
            efficiency_score=50.0,
        )
        result = eng.analyze_collection_distribution()
        assert "redundant" in result
        assert result["redundant"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_collection_distribution() == {}


# ---------------------------------------------------------------------------
# identify_inefficient_collections
# ---------------------------------------------------------------------------


class TestIdentifyInefficientCollections:
    def test_detects_inefficient(self):
        eng = _engine(collection_efficiency_threshold=75.0)
        eng.record_collection(
            metric_name="metric-1",
            efficiency_score=50.0,
        )
        eng.record_collection(
            metric_name="metric-2",
            efficiency_score=90.0,
        )
        results = eng.identify_inefficient_collections()
        assert len(results) == 1
        assert results[0]["metric_name"] == "metric-1"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_inefficient_collections() == []


# ---------------------------------------------------------------------------
# rank_by_efficiency
# ---------------------------------------------------------------------------


class TestRankByEfficiency:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_collection(
            metric_name="metric-1",
            service="api-gateway",
            efficiency_score=90.0,
        )
        eng.record_collection(
            metric_name="metric-2",
            service="payments",
            efficiency_score=30.0,
        )
        results = eng.rank_by_efficiency()
        assert len(results) == 2
        assert results[0]["service"] == "payments"
        assert results[0]["avg_efficiency_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_efficiency() == []


# ---------------------------------------------------------------------------
# detect_collection_trends
# ---------------------------------------------------------------------------


class TestDetectCollectionTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(
                metric_name="metric-1",
                analysis_score=50.0,
            )
        result = eng.detect_collection_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(metric_name="metric-1", analysis_score=30.0)
        eng.add_analysis(metric_name="metric-2", analysis_score=30.0)
        eng.add_analysis(metric_name="metric-3", analysis_score=80.0)
        eng.add_analysis(metric_name="metric-4", analysis_score=80.0)
        result = eng.detect_collection_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_collection_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(collection_efficiency_threshold=75.0)
        eng.record_collection(
            metric_name="cpu_utilization",
            collection_status=CollectionStatus.REDUNDANT,
            optimization_strategy=OptimizationStrategy.AGGREGATE,
            metric_tier=MetricTier.HOURLY,
            efficiency_score=45.0,
        )
        report = eng.generate_report()
        assert isinstance(report, MetricCollectionReport)
        assert report.total_records == 1
        assert report.low_efficiency_count == 1
        assert len(report.top_inefficient) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_collection(metric_name="metric-1")
        eng.add_analysis(metric_name="metric-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_collection(
            metric_name="cpu_utilization",
            collection_status=CollectionStatus.REDUNDANT,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "redundant" in stats["status_distribution"]
