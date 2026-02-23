"""Tests for shieldops.billing.orphan_detector — OrphanedResourceDetector."""

from __future__ import annotations

from shieldops.billing.orphan_detector import (
    CleanupJob,
    CleanupRisk,
    OrphanAction,
    OrphanCategory,
    OrphanedResource,
    OrphanedResourceDetector,
    OrphanSummary,
)


def _engine(**kw) -> OrphanedResourceDetector:
    return OrphanedResourceDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_unattached_volume(self):
        assert OrphanCategory.UNATTACHED_VOLUME == "unattached_volume"

    def test_category_unused_ip(self):
        assert OrphanCategory.UNUSED_IP == "unused_ip"

    def test_category_idle_lb(self):
        assert OrphanCategory.IDLE_LOAD_BALANCER == "idle_load_balancer"

    def test_category_dangling_dns(self):
        assert OrphanCategory.DANGLING_DNS == "dangling_dns"

    def test_category_stale_snapshot(self):
        assert OrphanCategory.STALE_SNAPSHOT == "stale_snapshot"

    def test_action_detected(self):
        assert OrphanAction.DETECTED == "detected"

    def test_action_flagged(self):
        assert OrphanAction.FLAGGED == "flagged"

    def test_action_cleanup_scheduled(self):
        assert OrphanAction.CLEANUP_SCHEDULED == "cleanup_scheduled"

    def test_action_cleaned(self):
        assert OrphanAction.CLEANED == "cleaned"

    def test_action_exempted(self):
        assert OrphanAction.EXEMPTED == "exempted"

    def test_risk_low(self):
        assert CleanupRisk.LOW == "low"

    def test_risk_medium(self):
        assert CleanupRisk.MEDIUM == "medium"

    def test_risk_high(self):
        assert CleanupRisk.HIGH == "high"

    def test_risk_critical(self):
        assert CleanupRisk.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_orphan_defaults(self):
        o = OrphanedResource(resource_id="vol-123")
        assert o.id
        assert o.resource_id == "vol-123"
        assert o.category == OrphanCategory.UNATTACHED_VOLUME
        assert o.action == OrphanAction.DETECTED
        assert o.risk == CleanupRisk.LOW
        assert o.monthly_cost == 0.0

    def test_cleanup_job_defaults(self):
        job = CleanupJob(orphan_id="o-1")
        assert job.id
        assert job.executed_at is None
        assert job.success is False

    def test_orphan_summary_defaults(self):
        s = OrphanSummary()
        assert s.total_orphans == 0
        assert s.total_monthly_waste == 0.0


# ---------------------------------------------------------------------------
# report_orphan
# ---------------------------------------------------------------------------


class TestReportOrphan:
    def test_basic_report(self):
        eng = _engine()
        orphan = eng.report_orphan("vol-123")
        assert orphan.resource_id == "vol-123"
        assert eng.get_orphan(orphan.id) is not None

    def test_unique_ids(self):
        eng = _engine()
        o1 = eng.report_orphan("vol-1")
        o2 = eng.report_orphan("vol-2")
        assert o1.id != o2.id

    def test_with_custom_fields(self):
        eng = _engine()
        orphan = eng.report_orphan(
            "vol-123", category=OrphanCategory.UNUSED_IP, monthly_cost=50.0, provider="aws"
        )
        assert orphan.category == OrphanCategory.UNUSED_IP
        assert orphan.monthly_cost == 50.0

    def test_evicts_at_max(self):
        eng = _engine(max_resources=2)
        o1 = eng.report_orphan("vol-1")
        eng.report_orphan("vol-2")
        eng.report_orphan("vol-3")
        assert eng.get_orphan(o1.id) is None


# ---------------------------------------------------------------------------
# list_orphans
# ---------------------------------------------------------------------------


class TestListOrphans:
    def test_list_all(self):
        eng = _engine()
        eng.report_orphan("vol-1")
        eng.report_orphan("vol-2")
        assert len(eng.list_orphans()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.report_orphan("vol-1", category=OrphanCategory.UNATTACHED_VOLUME)
        eng.report_orphan("ip-1", category=OrphanCategory.UNUSED_IP)
        results = eng.list_orphans(category=OrphanCategory.UNUSED_IP)
        assert len(results) == 1

    def test_filter_by_provider(self):
        eng = _engine()
        eng.report_orphan("vol-1", provider="aws")
        eng.report_orphan("vol-2", provider="gcp")
        results = eng.list_orphans(provider="aws")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# flag / exempt / cleanup
# ---------------------------------------------------------------------------


class TestFlagForCleanup:
    def test_flag(self):
        eng = _engine()
        orphan = eng.report_orphan("vol-1")
        flagged = eng.flag_for_cleanup(orphan.id)
        assert flagged is not None
        assert flagged.action == OrphanAction.FLAGGED

    def test_flag_not_found(self):
        eng = _engine()
        assert eng.flag_for_cleanup("nonexistent") is None


class TestExemptResource:
    def test_exempt(self):
        eng = _engine()
        orphan = eng.report_orphan("vol-1")
        exempted = eng.exempt_resource(orphan.id)
        assert exempted is not None
        assert exempted.action == OrphanAction.EXEMPTED

    def test_exempt_not_found(self):
        eng = _engine()
        assert eng.exempt_resource("nonexistent") is None


class TestScheduleCleanup:
    def test_schedule(self):
        eng = _engine()
        orphan = eng.report_orphan("vol-1")
        job = eng.schedule_cleanup(orphan.id)
        assert job is not None
        assert job.orphan_id == orphan.id

    def test_schedule_not_found(self):
        eng = _engine()
        assert eng.schedule_cleanup("nonexistent") is None


class TestExecuteCleanup:
    def test_execute_success(self):
        eng = _engine()
        orphan = eng.report_orphan("vol-1")
        job = eng.schedule_cleanup(orphan.id)
        result = eng.execute_cleanup(job.id, success=True)
        assert result is not None
        assert result.success is True
        assert eng.get_orphan(orphan.id).action == OrphanAction.CLEANED

    def test_execute_failure(self):
        eng = _engine()
        orphan = eng.report_orphan("vol-1")
        job = eng.schedule_cleanup(orphan.id)
        result = eng.execute_cleanup(job.id, success=False, notes="permission denied")
        assert result.success is False
        assert result.notes == "permission denied"

    def test_execute_not_found(self):
        eng = _engine()
        assert eng.execute_cleanup("nonexistent") is None


# ---------------------------------------------------------------------------
# monthly_waste / summary / stats
# ---------------------------------------------------------------------------


class TestMonthlyWaste:
    def test_waste_calculation(self):
        eng = _engine()
        eng.report_orphan("vol-1", monthly_cost=100.0)
        eng.report_orphan("vol-2", monthly_cost=50.0)
        waste = eng.get_monthly_waste()
        assert waste["total_monthly_waste"] == 150.0
        assert waste["active_orphan_count"] == 2

    def test_exempted_excluded(self):
        eng = _engine()
        o1 = eng.report_orphan("vol-1", monthly_cost=100.0)
        eng.report_orphan("vol-2", monthly_cost=50.0)
        eng.exempt_resource(o1.id)
        waste = eng.get_monthly_waste()
        assert waste["total_monthly_waste"] == 50.0


class TestGetSummary:
    def test_summary(self):
        eng = _engine()
        eng.report_orphan("vol-1", category=OrphanCategory.UNATTACHED_VOLUME)
        eng.report_orphan("ip-1", category=OrphanCategory.UNUSED_IP)
        summary = eng.get_summary()
        assert summary.total_orphans == 2


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_orphans"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.report_orphan("vol-1", monthly_cost=100.0)
        stats = eng.get_stats()
        assert stats["total_orphans"] == 1
        assert stats["total_monthly_waste"] == 100.0
