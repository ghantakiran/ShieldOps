"""Tests for MultiTenantObservabilityEngine."""

from __future__ import annotations

from shieldops.observability.multi_tenant_observability_engine import (
    IsolationLevel,
    MultiTenantObservabilityEngine,
    QuotaStatus,
    TenantTier,
)


def _engine(**kw) -> MultiTenantObservabilityEngine:
    return MultiTenantObservabilityEngine(**kw)


class TestEnums:
    def test_tenant_tier(self):
        assert TenantTier.FREE == "free"
        assert TenantTier.ENTERPRISE == "enterprise"

    def test_isolation_level(self):
        assert IsolationLevel.SHARED == "shared"
        assert IsolationLevel.DEDICATED == "dedicated"

    def test_quota_status(self):
        assert QuotaStatus.WITHIN_LIMIT == "within_limit"
        assert QuotaStatus.SUSPENDED == "suspended"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="t-1", service="api")
        assert rec.name == "t-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"t-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="t-1", score=70.0)
        result = eng.process("t-1")
        assert result["key"] == "t-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(name="t1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.add_record(name="t1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(name="t1", service="api")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestEnforceTenantQuotas:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="t1",
            tier=TenantTier.FREE,
            data_volume_gb=15.0,
        )
        result = eng.enforce_tenant_quotas()
        assert "total_tenants" in result
        assert result["violations"] >= 1

    def test_empty(self):
        eng = _engine()
        result = eng.enforce_tenant_quotas()
        assert result["status"] == "no_data"


class TestDetectNoisyNeighbors:
    def test_basic(self):
        eng = _engine()
        eng.add_record(name="noisy", usage_pct=90.0)
        eng.add_record(name="quiet", usage_pct=10.0)
        result = eng.detect_noisy_neighbors()
        assert isinstance(result, list)


class TestComputeTenantUtilization:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="t1",
            tier=TenantTier.PREMIUM,
            usage_pct=60.0,
            data_volume_gb=50.0,
        )
        result = eng.compute_tenant_utilization()
        assert isinstance(result, dict)
        assert "premium" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_tenant_utilization()
        assert result["status"] == "no_data"
