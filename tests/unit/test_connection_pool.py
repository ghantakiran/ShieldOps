"""Tests for shieldops.analytics.connection_pool — ConnectionPoolMonitor."""

from __future__ import annotations

from shieldops.analytics.connection_pool import (
    ConnectionPoolMonitor,
    ConnectionPoolReport,
    DatabaseType,
    PoolAction,
    PoolMetricRecord,
    PoolRecommendation,
    PoolStatus,
)


def _engine(**kw) -> ConnectionPoolMonitor:
    return ConnectionPoolMonitor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PoolStatus (5)
    def test_status_healthy(self):
        assert PoolStatus.HEALTHY == "healthy"

    def test_status_elevated(self):
        assert PoolStatus.ELEVATED == "elevated"

    def test_status_saturated(self):
        assert PoolStatus.SATURATED == "saturated"

    def test_status_exhausted(self):
        assert PoolStatus.EXHAUSTED == "exhausted"

    def test_status_leaking(self):
        assert PoolStatus.LEAKING == "leaking"

    # DatabaseType (5)
    def test_db_postgresql(self):
        assert DatabaseType.POSTGRESQL == "postgresql"

    def test_db_mysql(self):
        assert DatabaseType.MYSQL == "mysql"

    def test_db_mongodb(self):
        assert DatabaseType.MONGODB == "mongodb"

    def test_db_redis(self):
        assert DatabaseType.REDIS == "redis"

    def test_db_elasticsearch(self):
        assert DatabaseType.ELASTICSEARCH == "elasticsearch"

    # PoolAction (5)
    def test_action_scale_up(self):
        assert PoolAction.SCALE_UP == "scale_up"

    def test_action_scale_down(self):
        assert PoolAction.SCALE_DOWN == "scale_down"

    def test_action_recycle(self):
        assert PoolAction.RECYCLE == "recycle"

    def test_action_investigate_leak(self):
        assert PoolAction.INVESTIGATE_LEAK == "investigate_leak"

    def test_action_no_action(self):
        assert PoolAction.NO_ACTION == "no_action"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_pool_metric_record_defaults(self):
        r = PoolMetricRecord()
        assert r.id
        assert r.pool_name == ""
        assert r.db_type == DatabaseType.POSTGRESQL
        assert r.status == PoolStatus.HEALTHY
        assert r.total_connections == 0
        assert r.active_connections == 0
        assert r.idle_connections == 0
        assert r.wait_time_ms == 0.0
        assert r.utilization_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_pool_recommendation_defaults(self):
        r = PoolRecommendation()
        assert r.id
        assert r.pool_name == ""
        assert r.action == PoolAction.NO_ACTION
        assert r.reason == ""
        assert r.priority == 0
        assert r.created_at > 0

    def test_connection_pool_report_defaults(self):
        r = ConnectionPoolReport()
        assert r.total_pools == 0
        assert r.total_recommendations == 0
        assert r.avg_utilization_pct == 0.0
        assert r.by_status == {}
        assert r.by_db_type == {}
        assert r.saturated_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_metrics
# -------------------------------------------------------------------


class TestRecordMetrics:
    def test_basic(self):
        eng = _engine()
        r = eng.record_metrics("pg-main", utilization_pct=60.0, active_connections=30)
        assert r.pool_name == "pg-main"
        assert r.utilization_pct == 60.0
        assert r.active_connections == 30

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_metrics(
            "redis-cache",
            db_type=DatabaseType.REDIS,
            status=PoolStatus.ELEVATED,
            total_connections=100,
            active_connections=70,
            idle_connections=30,
            wait_time_ms=15.5,
            utilization_pct=70.0,
            details="elevated load",
        )
        assert r.db_type == DatabaseType.REDIS
        assert r.status == PoolStatus.ELEVATED
        assert r.details == "elevated load"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_metrics(f"pool-{i}", utilization_pct=50.0)
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_metrics
# -------------------------------------------------------------------


class TestGetMetrics:
    def test_found(self):
        eng = _engine()
        r = eng.record_metrics("pg-main", utilization_pct=50.0)
        assert eng.get_metrics(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_metrics("nonexistent") is None


# -------------------------------------------------------------------
# list_metrics
# -------------------------------------------------------------------


class TestListMetrics:
    def test_list_all(self):
        eng = _engine()
        eng.record_metrics("pool-a", utilization_pct=50.0)
        eng.record_metrics("pool-b", utilization_pct=60.0)
        assert len(eng.list_metrics()) == 2

    def test_filter_by_pool_name(self):
        eng = _engine()
        eng.record_metrics("pool-a", utilization_pct=50.0)
        eng.record_metrics("pool-b", utilization_pct=60.0)
        results = eng.list_metrics(pool_name="pool-a")
        assert len(results) == 1
        assert results[0].pool_name == "pool-a"

    def test_filter_by_db_type(self):
        eng = _engine()
        eng.record_metrics("p1", db_type=DatabaseType.MYSQL, utilization_pct=50.0)
        eng.record_metrics("p2", db_type=DatabaseType.REDIS, utilization_pct=60.0)
        results = eng.list_metrics(db_type=DatabaseType.MYSQL)
        assert len(results) == 1
        assert results[0].pool_name == "p1"


# -------------------------------------------------------------------
# add_recommendation
# -------------------------------------------------------------------


class TestAddRecommendation:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_recommendation(
            "pg-main",
            action=PoolAction.SCALE_UP,
            reason="High utilization",
            priority=1,
        )
        assert rec.pool_name == "pg-main"
        assert rec.action == PoolAction.SCALE_UP
        assert rec.priority == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_recommendation(f"pool-{i}")
        assert len(eng._recommendations) == 2


# -------------------------------------------------------------------
# analyze_pool_health
# -------------------------------------------------------------------


class TestAnalyzePoolHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_metrics(
            "pg-main",
            utilization_pct=75.0,
            status=PoolStatus.ELEVATED,
            db_type=DatabaseType.POSTGRESQL,
            active_connections=30,
            idle_connections=10,
        )
        result = eng.analyze_pool_health("pg-main")
        assert result["pool_name"] == "pg-main"
        assert result["utilization_pct"] == 75.0
        assert result["status"] == "elevated"
        assert result["db_type"] == "postgresql"
        assert result["active_connections"] == 30
        assert result["idle_connections"] == 10

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_pool_health("ghost-pool")
        assert result["pool_name"] == "ghost-pool"
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_saturated_pools
# -------------------------------------------------------------------


class TestIdentifySaturatedPools:
    def test_with_saturated(self):
        eng = _engine(saturation_threshold_pct=85.0)
        eng.record_metrics("good-pool", utilization_pct=50.0)
        eng.record_metrics("bad-pool", utilization_pct=90.0)
        eng.record_metrics("worse-pool", utilization_pct=95.0)
        results = eng.identify_saturated_pools()
        assert len(results) == 2
        # Sorted by utilization desc
        assert results[0]["pool_name"] == "worse-pool"
        assert results[0]["utilization_pct"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_saturated_pools() == []


# -------------------------------------------------------------------
# detect_potential_leaks
# -------------------------------------------------------------------


class TestDetectPotentialLeaks:
    def test_with_leaks(self):
        eng = _engine()
        eng.record_metrics("leaky-pool", status=PoolStatus.LEAKING, utilization_pct=80.0)
        eng.record_metrics("healthy-pool", status=PoolStatus.HEALTHY, utilization_pct=40.0)
        results = eng.detect_potential_leaks()
        assert len(results) == 1
        assert results[0]["pool_name"] == "leaky-pool"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_potential_leaks() == []


# -------------------------------------------------------------------
# rank_by_wait_time
# -------------------------------------------------------------------


class TestRankByWaitTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_metrics("p1", wait_time_ms=10.0)
        eng.record_metrics("p2", wait_time_ms=50.0)
        eng.record_metrics("p3", wait_time_ms=30.0)
        results = eng.rank_by_wait_time()
        assert len(results) == 3
        assert results[0]["pool_name"] == "p2"
        assert results[0]["wait_time_ms"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_wait_time() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(saturation_threshold_pct=85.0)
        eng.record_metrics("p1", utilization_pct=90.0, status=PoolStatus.SATURATED)
        eng.record_metrics("p2", utilization_pct=40.0, status=PoolStatus.HEALTHY)
        eng.add_recommendation("p1", action=PoolAction.SCALE_UP)
        report = eng.generate_report()
        assert report.total_pools == 2
        assert report.total_recommendations == 1
        assert report.by_status != {}
        assert report.by_db_type != {}
        assert report.saturated_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_pools == 0
        assert report.avg_utilization_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_metrics("p1", utilization_pct=50.0)
        eng.add_recommendation("p1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._recommendations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_pools"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_metrics("p1", utilization_pct=50.0, status=PoolStatus.HEALTHY)
        eng.record_metrics("p2", utilization_pct=90.0, status=PoolStatus.SATURATED)
        eng.add_recommendation("p2")
        stats = eng.get_stats()
        assert stats["total_pools"] == 2
        assert stats["total_recommendations"] == 1
        assert stats["unique_pools"] == 2
        assert stats["saturation_threshold_pct"] == 85.0
