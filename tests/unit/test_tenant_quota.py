"""Tests for shieldops.operations.tenant_quota — TenantResourceQuotaManager."""

from __future__ import annotations

from shieldops.operations.tenant_quota import (
    EnforcementAction,
    QuotaPolicy,
    QuotaRecord,
    QuotaStatus,
    ResourceType,
    TenantQuotaReport,
    TenantResourceQuotaManager,
)


def _engine(**kw) -> TenantResourceQuotaManager:
    return TenantResourceQuotaManager(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ResourceType (5)
    def test_resource_cpu(self):
        assert ResourceType.CPU == "cpu"

    def test_resource_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_resource_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_resource_network(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_api_calls(self):
        assert ResourceType.API_CALLS == "api_calls"

    # QuotaStatus (5)
    def test_status_within_limit(self):
        assert QuotaStatus.WITHIN_LIMIT == "within_limit"

    def test_status_warning(self):
        assert QuotaStatus.WARNING == "warning"

    def test_status_near_limit(self):
        assert QuotaStatus.NEAR_LIMIT == "near_limit"

    def test_status_exceeded(self):
        assert QuotaStatus.EXCEEDED == "exceeded"

    def test_status_suspended(self):
        assert QuotaStatus.SUSPENDED == "suspended"

    # EnforcementAction (5)
    def test_action_throttle(self):
        assert EnforcementAction.THROTTLE == "throttle"

    def test_action_notify(self):
        assert EnforcementAction.NOTIFY == "notify"

    def test_action_block(self):
        assert EnforcementAction.BLOCK == "block"

    def test_action_scale_up(self):
        assert EnforcementAction.SCALE_UP == "scale_up"

    def test_action_no_action(self):
        assert EnforcementAction.NO_ACTION == "no_action"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_quota_record_defaults(self):
        r = QuotaRecord()
        assert r.id
        assert r.tenant_name == ""
        assert r.resource_type == ResourceType.CPU
        assert r.status == QuotaStatus.WITHIN_LIMIT
        assert r.utilization_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_quota_policy_defaults(self):
        r = QuotaPolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.resource_type == ResourceType.CPU
        assert r.action == EnforcementAction.NO_ACTION
        assert r.limit_value == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = TenantQuotaReport()
        assert r.total_records == 0
        assert r.total_policies == 0
        assert r.avg_utilization_pct == 0.0
        assert r.by_resource == {}
        assert r.by_status == {}
        assert r.exceeded_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_quota
# -------------------------------------------------------------------


class TestRecordQuota:
    def test_basic(self):
        eng = _engine()
        r = eng.record_quota(
            "tenant-a",
            resource_type=ResourceType.MEMORY,
            status=QuotaStatus.WARNING,
        )
        assert r.tenant_name == "tenant-a"
        assert r.resource_type == ResourceType.MEMORY

    def test_with_utilization(self):
        eng = _engine()
        r = eng.record_quota("tenant-b", utilization_pct=85.0)
        assert r.utilization_pct == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_quota(f"tenant-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_quota
# -------------------------------------------------------------------


class TestGetQuota:
    def test_found(self):
        eng = _engine()
        r = eng.record_quota("tenant-a")
        assert eng.get_quota(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_quota("nonexistent") is None


# -------------------------------------------------------------------
# list_quotas
# -------------------------------------------------------------------


class TestListQuotas:
    def test_list_all(self):
        eng = _engine()
        eng.record_quota("tenant-a")
        eng.record_quota("tenant-b")
        assert len(eng.list_quotas()) == 2

    def test_filter_by_tenant(self):
        eng = _engine()
        eng.record_quota("tenant-a")
        eng.record_quota("tenant-b")
        results = eng.list_quotas(tenant_name="tenant-a")
        assert len(results) == 1

    def test_filter_by_resource_type(self):
        eng = _engine()
        eng.record_quota("tenant-a", resource_type=ResourceType.STORAGE)
        eng.record_quota("tenant-b", resource_type=ResourceType.CPU)
        results = eng.list_quotas(resource_type=ResourceType.STORAGE)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "policy-1",
            resource_type=ResourceType.MEMORY,
            action=EnforcementAction.THROTTLE,
            limit_value=90.0,
        )
        assert p.policy_name == "policy-1"
        assert p.limit_value == 90.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_tenant_utilization
# -------------------------------------------------------------------


class TestAnalyzeTenantUtilization:
    def test_with_data(self):
        eng = _engine()
        eng.record_quota("tenant-a", utilization_pct=80.0, status=QuotaStatus.EXCEEDED)
        eng.record_quota("tenant-a", utilization_pct=60.0, status=QuotaStatus.WITHIN_LIMIT)
        result = eng.analyze_tenant_utilization("tenant-a")
        assert result["tenant_name"] == "tenant-a"
        assert result["total_records"] == 2
        assert result["avg_utilization_pct"] == 70.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_tenant_utilization("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(max_utilization_pct=90.0)
        eng.record_quota("tenant-a", utilization_pct=85.0)
        result = eng.analyze_tenant_utilization("tenant-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_exceeded_quotas
# -------------------------------------------------------------------


class TestIdentifyExceededQuotas:
    def test_with_exceeded(self):
        eng = _engine()
        eng.record_quota("tenant-a", status=QuotaStatus.EXCEEDED)
        eng.record_quota("tenant-a", status=QuotaStatus.NEAR_LIMIT)
        eng.record_quota("tenant-b", status=QuotaStatus.WITHIN_LIMIT)
        results = eng.identify_exceeded_quotas()
        assert len(results) == 1
        assert results[0]["tenant_name"] == "tenant-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_exceeded_quotas() == []


# -------------------------------------------------------------------
# rank_by_utilization
# -------------------------------------------------------------------


class TestRankByUtilization:
    def test_with_data(self):
        eng = _engine()
        eng.record_quota("tenant-a", utilization_pct=95.0)
        eng.record_quota("tenant-a", utilization_pct=85.0)
        eng.record_quota("tenant-b", utilization_pct=40.0)
        results = eng.rank_by_utilization()
        assert results[0]["tenant_name"] == "tenant-a"
        assert results[0]["avg_utilization_pct"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization() == []


# -------------------------------------------------------------------
# detect_quota_trends
# -------------------------------------------------------------------


class TestDetectQuotaTrends:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_quota("tenant-a")
        eng.record_quota("tenant-b")
        results = eng.detect_quota_trends()
        assert len(results) == 1
        assert results[0]["tenant_name"] == "tenant-a"
        assert results[0]["recurring"] is True

    def test_no_recurring(self):
        eng = _engine()
        eng.record_quota("tenant-a")
        assert eng.detect_quota_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_quota("tenant-a", status=QuotaStatus.EXCEEDED, utilization_pct=95.0)
        eng.record_quota("tenant-b", status=QuotaStatus.WITHIN_LIMIT, utilization_pct=30.0)
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_policies == 1
        assert report.by_resource != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.recommendations[0] == "Tenant quota management meets targets"

    def test_exceeds_threshold(self):
        eng = _engine(max_utilization_pct=50.0)
        eng.record_quota("tenant-a", utilization_pct=95.0)
        report = eng.generate_report()
        assert "exceeds" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_quota("tenant-a")
        eng.add_policy("policy-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_policies"] == 0
        assert stats["resource_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_quota("tenant-a", resource_type=ResourceType.CPU)
        eng.record_quota("tenant-b", resource_type=ResourceType.MEMORY)
        eng.add_policy("p1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_tenants"] == 2
