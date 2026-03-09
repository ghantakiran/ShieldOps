"""Tests for shieldops.observability.cross_tenant_observability — CrossTenantObservability."""

from __future__ import annotations

from shieldops.observability.cross_tenant_observability import (
    CrossTenantObservability,
    CrossTenantReport,
    IsolationLevel,
    TenantHealthStatus,
    TenantRecord,
    TenantTier,
    TenantUsageRecord,
)


def _engine(**kw) -> CrossTenantObservability:
    return CrossTenantObservability(**kw)


class TestEnums:
    def test_tier_enterprise(self):
        assert TenantTier.ENTERPRISE == "enterprise"

    def test_tier_professional(self):
        assert TenantTier.PROFESSIONAL == "professional"

    def test_tier_starter(self):
        assert TenantTier.STARTER == "starter"

    def test_tier_free(self):
        assert TenantTier.FREE == "free"

    def test_isolation_strict(self):
        assert IsolationLevel.STRICT == "strict"

    def test_isolation_shared(self):
        assert IsolationLevel.SHARED == "shared"

    def test_isolation_hybrid(self):
        assert IsolationLevel.HYBRID == "hybrid"

    def test_health_healthy(self):
        assert TenantHealthStatus.HEALTHY == "healthy"

    def test_health_warning(self):
        assert TenantHealthStatus.WARNING == "warning"

    def test_health_critical(self):
        assert TenantHealthStatus.CRITICAL == "critical"


class TestModels:
    def test_tenant_defaults(self):
        t = TenantRecord()
        assert t.id
        assert t.tier == TenantTier.STARTER
        assert t.isolation == IsolationLevel.SHARED

    def test_usage_defaults(self):
        u = TenantUsageRecord()
        assert u.id
        assert u.cost_usd == 0.0

    def test_report_defaults(self):
        r = CrossTenantReport()
        assert r.total_tenants == 0
        assert r.recommendations == []


class TestAddTenant:
    def test_basic(self):
        eng = _engine()
        t = eng.add_tenant("t1", "Acme Corp", tier=TenantTier.ENTERPRISE)
        assert t.tenant_id == "t1"
        assert t.tier == TenantTier.ENTERPRISE

    def test_eviction(self):
        eng = _engine(max_tenants=3)
        for i in range(5):
            eng.add_tenant(f"t-{i}", f"Tenant {i}")
        assert len(eng._tenants) == 3


class TestIsolateTenantData:
    def test_not_found(self):
        eng = _engine()
        result = eng.isolate_tenant_data("nonexistent")
        assert result["status"] == "not_found"

    def test_found(self):
        eng = _engine()
        eng.add_tenant("t1", "Acme")
        result = eng.isolate_tenant_data("t1")
        assert result["tenant_id"] == "t1"
        assert result["name"] == "Acme"

    def test_includes_usage_count(self):
        eng = _engine()
        eng.add_tenant("t1", "Acme")
        eng.record_usage("t1", metrics_ingested=100)
        result = eng.isolate_tenant_data("t1")
        assert result["usage_records"] == 1


class TestAggregateCrossTenant:
    def test_empty(self):
        eng = _engine()
        result = eng.aggregate_cross_tenant()
        assert result["total_tenants"] == 0

    def test_with_tenants(self):
        eng = _engine()
        t1 = eng.add_tenant("t1", "A")
        t1.metric_count = 100
        t2 = eng.add_tenant("t2", "B")
        t2.metric_count = 200
        result = eng.aggregate_cross_tenant()
        assert result["total_metrics"] == 300
        assert result["avg_metrics_per_tenant"] == 150.0


class TestEnforceDataBoundaries:
    def test_not_found(self):
        eng = _engine()
        result = eng.enforce_data_boundaries("nonexistent")
        assert result["enforced"] is False

    def test_within_limits(self):
        eng = _engine()
        eng.add_tenant("t1", "A", tier=TenantTier.ENTERPRISE)
        result = eng.enforce_data_boundaries("t1")
        assert result["enforced"] is True

    def test_free_tier_exceeded(self):
        eng = _engine()
        t = eng.add_tenant("t1", "A", tier=TenantTier.FREE)
        t.metric_count = 20000
        result = eng.enforce_data_boundaries("t1")
        assert result["enforced"] is False
        assert len(result["violations"]) > 0

    def test_starter_tier_exceeded(self):
        eng = _engine()
        t = eng.add_tenant("t1", "A", tier=TenantTier.STARTER)
        t.metric_count = 200000
        result = eng.enforce_data_boundaries("t1")
        assert result["enforced"] is False


class TestRecordUsage:
    def test_basic(self):
        eng = _engine()
        eng.add_tenant("t1", "A")
        u = eng.record_usage("t1", metrics_ingested=500, cost_usd=10.0)
        assert u.metrics_ingested == 500

    def test_updates_tenant(self):
        eng = _engine()
        eng.add_tenant("t1", "A")
        eng.record_usage("t1", metrics_ingested=500)
        result = eng.isolate_tenant_data("t1")
        assert result["metric_count"] == 500


class TestGetTenantUsage:
    def test_empty(self):
        eng = _engine()
        assert eng.get_tenant_usage("t1") == []

    def test_with_data(self):
        eng = _engine()
        eng.add_tenant("t1", "A")
        eng.record_usage("t1", metrics_ingested=100)
        eng.record_usage("t1", metrics_ingested=200)
        usage = eng.get_tenant_usage("t1")
        assert len(usage) == 2

    def test_limit(self):
        eng = _engine()
        eng.add_tenant("t1", "A")
        for i in range(10):
            eng.record_usage("t1", metrics_ingested=i)
        assert len(eng.get_tenant_usage("t1", limit=3)) == 3


class TestCompareTenantHealth:
    def test_empty(self):
        eng = _engine()
        assert eng.compare_tenant_health() == []

    def test_sorted_by_metric_count(self):
        eng = _engine()
        t1 = eng.add_tenant("t1", "A")
        t1.metric_count = 100
        t2 = eng.add_tenant("t2", "B")
        t2.metric_count = 500
        results = eng.compare_tenant_health()
        assert results[0]["tenant_id"] == "t2"


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_tenants == 0

    def test_with_critical(self):
        eng = _engine()
        t = eng.add_tenant("t1", "A")
        t.health = TenantHealthStatus.CRITICAL
        report = eng.generate_report()
        assert any("critical" in r.lower() for r in report.recommendations)


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_tenant("t1", "A")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._tenants) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_tenants"] == 0

    def test_populated(self):
        eng = _engine()
        eng.add_tenant("t1", "A")
        stats = eng.get_stats()
        assert stats["unique_tenant_ids"] == 1
