"""Tests for shieldops.analytics.db_performance — DatabasePerformanceAnalyzer."""

from __future__ import annotations

from shieldops.analytics.db_performance import (
    ConnectionPoolSnapshot,
    DatabaseHealthReport,
    DatabasePerformanceAnalyzer,
    PerformanceLevel,
    PoolStatus,
    QueryCategory,
    QueryProfile,
)


def _engine(**kw) -> DatabasePerformanceAnalyzer:
    return DatabasePerformanceAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # QueryCategory (6)
    def test_category_select(self):
        assert QueryCategory.SELECT == "select"

    def test_category_insert(self):
        assert QueryCategory.INSERT == "insert"

    def test_category_update(self):
        assert QueryCategory.UPDATE == "update"

    def test_category_delete(self):
        assert QueryCategory.DELETE == "delete"

    def test_category_ddl(self):
        assert QueryCategory.DDL == "ddl"

    def test_category_procedure(self):
        assert QueryCategory.PROCEDURE == "procedure"

    # PerformanceLevel (4)
    def test_perf_optimal(self):
        assert PerformanceLevel.OPTIMAL == "optimal"

    def test_perf_acceptable(self):
        assert PerformanceLevel.ACCEPTABLE == "acceptable"

    def test_perf_degraded(self):
        assert PerformanceLevel.DEGRADED == "degraded"

    def test_perf_critical(self):
        assert PerformanceLevel.CRITICAL == "critical"

    # PoolStatus (4)
    def test_pool_healthy(self):
        assert PoolStatus.HEALTHY == "healthy"

    def test_pool_saturated(self):
        assert PoolStatus.SATURATED == "saturated"

    def test_pool_exhausted(self):
        assert PoolStatus.EXHAUSTED == "exhausted"

    def test_pool_idle(self):
        assert PoolStatus.IDLE == "idle"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_query_profile_defaults(self):
        q = QueryProfile()
        assert q.id
        assert q.category == QueryCategory.SELECT
        assert q.duration_ms == 0.0
        assert q.is_slow is False

    def test_connection_pool_snapshot_defaults(self):
        s = ConnectionPoolSnapshot()
        assert s.id
        assert s.status == PoolStatus.HEALTHY
        assert s.max_connections == 100

    def test_database_health_report_defaults(self):
        r = DatabaseHealthReport()
        assert r.performance_level == PerformanceLevel.OPTIMAL
        assert r.pool_status == PoolStatus.HEALTHY
        assert r.recommendations == []


# ---------------------------------------------------------------------------
# record_query
# ---------------------------------------------------------------------------


class TestRecordQuery:
    def test_basic_record(self):
        eng = _engine()
        q = eng.record_query(
            query_text="SELECT 1",
            category=QueryCategory.SELECT,
            database="prod",
            duration_ms=10.0,
        )
        assert q.query_text == "SELECT 1"
        assert q.database == "prod"
        assert q.is_slow is False

    def test_unique_ids(self):
        eng = _engine()
        q1 = eng.record_query("SELECT 1", QueryCategory.SELECT, "db", 1.0)
        q2 = eng.record_query("SELECT 2", QueryCategory.SELECT, "db", 2.0)
        assert q1.id != q2.id

    def test_eviction_at_max(self):
        eng = _engine(max_queries=3)
        for i in range(5):
            eng.record_query(f"SELECT {i}", QueryCategory.SELECT, "db", 1.0)
        assert len(eng._queries) == 3

    def test_slow_detection(self):
        eng = _engine(slow_threshold_ms=100.0)
        q = eng.record_query("SELECT *", QueryCategory.SELECT, "db", 200.0)
        assert q.is_slow is True


# ---------------------------------------------------------------------------
# get_query
# ---------------------------------------------------------------------------


class TestGetQuery:
    def test_found(self):
        eng = _engine()
        q = eng.record_query("SELECT 1", QueryCategory.SELECT, "db", 1.0)
        assert eng.get_query(q.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_query("nonexistent") is None


# ---------------------------------------------------------------------------
# list_queries
# ---------------------------------------------------------------------------


class TestListQueries:
    def test_list_all(self):
        eng = _engine()
        eng.record_query("SELECT 1", QueryCategory.SELECT, "db1", 1.0)
        eng.record_query("INSERT INTO t", QueryCategory.INSERT, "db2", 2.0)
        assert len(eng.list_queries()) == 2

    def test_filter_by_database(self):
        eng = _engine()
        eng.record_query("SELECT 1", QueryCategory.SELECT, "db1", 1.0)
        eng.record_query("SELECT 2", QueryCategory.SELECT, "db2", 2.0)
        results = eng.list_queries(database="db1")
        assert len(results) == 1
        assert results[0].database == "db1"

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_query("SELECT 1", QueryCategory.SELECT, "db", 1.0)
        eng.record_query("INSERT INTO t", QueryCategory.INSERT, "db", 2.0)
        results = eng.list_queries(category=QueryCategory.INSERT)
        assert len(results) == 1
        assert results[0].category == QueryCategory.INSERT


# ---------------------------------------------------------------------------
# detect_slow_queries
# ---------------------------------------------------------------------------


class TestDetectSlowQueries:
    def test_no_slow(self):
        eng = _engine(slow_threshold_ms=500.0)
        eng.record_query("SELECT 1", QueryCategory.SELECT, "db", 10.0)
        assert len(eng.detect_slow_queries()) == 0

    def test_with_slow_queries(self):
        eng = _engine(slow_threshold_ms=100.0)
        eng.record_query("SELECT 1", QueryCategory.SELECT, "db", 10.0)
        eng.record_query("SELECT *", QueryCategory.SELECT, "db", 200.0)
        slow = eng.detect_slow_queries()
        assert len(slow) == 1
        assert slow[0].is_slow is True


# ---------------------------------------------------------------------------
# record_pool_snapshot
# ---------------------------------------------------------------------------


class TestRecordPoolSnapshot:
    def test_healthy(self):
        eng = _engine()
        s = eng.record_pool_snapshot(
            "db",
            active_connections=10,
            idle_connections=5,
            max_connections=100,
        )
        assert s.status == PoolStatus.HEALTHY

    def test_saturated(self):
        eng = _engine()
        s = eng.record_pool_snapshot(
            "db",
            active_connections=85,
            idle_connections=5,
            max_connections=100,
        )
        assert s.status == PoolStatus.SATURATED

    def test_exhausted(self):
        eng = _engine()
        s = eng.record_pool_snapshot(
            "db",
            active_connections=100,
            idle_connections=0,
            max_connections=100,
        )
        assert s.status == PoolStatus.EXHAUSTED

    def test_idle(self):
        eng = _engine()
        s = eng.record_pool_snapshot(
            "db",
            active_connections=0,
            idle_connections=10,
            max_connections=100,
        )
        assert s.status == PoolStatus.IDLE


# ---------------------------------------------------------------------------
# list_pool_snapshots
# ---------------------------------------------------------------------------


class TestListPoolSnapshots:
    def test_list_all(self):
        eng = _engine()
        eng.record_pool_snapshot("db1", 5, 5, 100)
        eng.record_pool_snapshot("db2", 10, 5, 100)
        assert len(eng.list_pool_snapshots()) == 2

    def test_filter_by_database(self):
        eng = _engine()
        eng.record_pool_snapshot("db1", 5, 5, 100)
        eng.record_pool_snapshot("db2", 10, 5, 100)
        results = eng.list_pool_snapshots(database="db1")
        assert len(results) == 1
        assert results[0].database == "db1"


# ---------------------------------------------------------------------------
# analyze_query_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeQueryPatterns:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_query_patterns()
        assert result["total_queries"] == 0
        assert result["category_breakdown"] == {}

    def test_with_data(self):
        eng = _engine()
        eng.record_query("SELECT 1", QueryCategory.SELECT, "db", 10.0)
        eng.record_query("INSERT INTO t", QueryCategory.INSERT, "db", 20.0)
        result = eng.analyze_query_patterns()
        assert result["total_queries"] == 2
        assert "select" in result["category_breakdown"]
        assert "insert" in result["category_breakdown"]


# ---------------------------------------------------------------------------
# generate_health_report
# ---------------------------------------------------------------------------


class TestGenerateHealthReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_query("SELECT 1", QueryCategory.SELECT, "prod", 10.0)
        report = eng.generate_health_report("prod")
        assert report.database == "prod"
        assert report.total_queries == 1
        assert report.performance_level == PerformanceLevel.OPTIMAL

    def test_slow_queries_affect_performance_level(self):
        eng = _engine(slow_threshold_ms=100.0)
        # >30% slow -> CRITICAL
        eng.record_query("SELECT 1", QueryCategory.SELECT, "prod", 200.0)
        eng.record_query("SELECT 2", QueryCategory.SELECT, "prod", 200.0)
        eng.record_query("SELECT 3", QueryCategory.SELECT, "prod", 10.0)
        report = eng.generate_health_report("prod")
        assert report.performance_level in (PerformanceLevel.DEGRADED, PerformanceLevel.CRITICAL)
        assert report.slow_query_count >= 2


# ---------------------------------------------------------------------------
# get_index_recommendations
# ---------------------------------------------------------------------------


class TestGetIndexRecommendations:
    def test_no_slow_queries(self):
        eng = _engine(slow_threshold_ms=500.0)
        eng.record_query("SELECT 1", QueryCategory.SELECT, "db", 10.0)
        assert len(eng.get_index_recommendations()) == 0

    def test_with_slow_selects(self):
        eng = _engine(slow_threshold_ms=100.0)
        eng.record_query("SELECT * FROM users", QueryCategory.SELECT, "db", 200.0)
        recs = eng.get_index_recommendations()
        assert len(recs) == 1
        assert recs[0]["recommendation"].startswith("Consider adding an index")


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        eng.record_query("SELECT 1", QueryCategory.SELECT, "db", 1.0)
        eng.record_pool_snapshot("db", 5, 5, 100)
        eng.clear_data()
        assert len(eng._queries) == 0
        assert len(eng._pool_snapshots) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_queries"] == 0
        assert stats["total_snapshots"] == 0

    def test_populated(self):
        eng = _engine(slow_threshold_ms=100.0)
        eng.record_query("SELECT 1", QueryCategory.SELECT, "db", 200.0)
        eng.record_pool_snapshot("db", 5, 5, 100)
        stats = eng.get_stats()
        assert stats["total_queries"] == 1
        assert stats["total_snapshots"] == 1
        assert stats["slow_query_count"] == 1
        assert "db" in stats["databases"]
