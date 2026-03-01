"""Tests for shieldops.sla.slo_error_budget_tracker — SLOErrorBudgetTracker."""

from __future__ import annotations

from shieldops.sla.slo_error_budget_tracker import (
    BudgetAllocation,
    BudgetRecord,
    BudgetScope,
    BudgetStatus,
    BurnRate,
    SLOErrorBudgetReport,
    SLOErrorBudgetTracker,
)


def _engine(**kw) -> SLOErrorBudgetTracker:
    return SLOErrorBudgetTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_healthy(self):
        assert BudgetStatus.HEALTHY == "healthy"

    def test_status_warning(self):
        assert BudgetStatus.WARNING == "warning"

    def test_status_critical(self):
        assert BudgetStatus.CRITICAL == "critical"

    def test_status_exhausted(self):
        assert BudgetStatus.EXHAUSTED == "exhausted"

    def test_status_unknown(self):
        assert BudgetStatus.UNKNOWN == "unknown"

    def test_scope_service(self):
        assert BudgetScope.SERVICE == "service"

    def test_scope_endpoint(self):
        assert BudgetScope.ENDPOINT == "endpoint"

    def test_scope_region(self):
        assert BudgetScope.REGION == "region"

    def test_scope_team(self):
        assert BudgetScope.TEAM == "team"

    def test_scope_platform(self):
        assert BudgetScope.PLATFORM == "platform"

    def test_burn_rate_slow(self):
        assert BurnRate.SLOW == "slow"

    def test_burn_rate_normal(self):
        assert BurnRate.NORMAL == "normal"

    def test_burn_rate_fast(self):
        assert BurnRate.FAST == "fast"

    def test_burn_rate_critical(self):
        assert BurnRate.CRITICAL == "critical"

    def test_burn_rate_exceeded(self):
        assert BurnRate.EXCEEDED == "exceeded"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_budget_record_defaults(self):
        r = BudgetRecord()
        assert r.id
        assert r.slo_id == ""
        assert r.budget_status == BudgetStatus.UNKNOWN
        assert r.budget_scope == BudgetScope.SERVICE
        assert r.burn_rate == BurnRate.NORMAL
        assert r.remaining_budget_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_budget_allocation_defaults(self):
        a = BudgetAllocation()
        assert a.id
        assert a.slo_id == ""
        assert a.budget_status == BudgetStatus.UNKNOWN
        assert a.allocation_pct == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_slo_error_budget_report_defaults(self):
        r = SLOErrorBudgetReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_allocations == 0
        assert r.exhausted_count == 0
        assert r.avg_remaining_budget_pct == 0.0
        assert r.by_status == {}
        assert r.by_scope == {}
        assert r.by_burn_rate == {}
        assert r.top_exhausted == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_budget
# ---------------------------------------------------------------------------


class TestRecordBudget:
    def test_basic(self):
        eng = _engine()
        r = eng.record_budget(
            slo_id="SLO-001",
            budget_status=BudgetStatus.HEALTHY,
            budget_scope=BudgetScope.SERVICE,
            burn_rate=BurnRate.NORMAL,
            remaining_budget_pct=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.slo_id == "SLO-001"
        assert r.budget_status == BudgetStatus.HEALTHY
        assert r.budget_scope == BudgetScope.SERVICE
        assert r.burn_rate == BurnRate.NORMAL
        assert r.remaining_budget_pct == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_budget(slo_id=f"SLO-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_budget
# ---------------------------------------------------------------------------


class TestGetBudget:
    def test_found(self):
        eng = _engine()
        r = eng.record_budget(
            slo_id="SLO-001",
            budget_status=BudgetStatus.HEALTHY,
        )
        result = eng.get_budget(r.id)
        assert result is not None
        assert result.budget_status == BudgetStatus.HEALTHY

    def test_not_found(self):
        eng = _engine()
        assert eng.get_budget("nonexistent") is None


# ---------------------------------------------------------------------------
# list_budgets
# ---------------------------------------------------------------------------


class TestListBudgets:
    def test_list_all(self):
        eng = _engine()
        eng.record_budget(slo_id="SLO-001")
        eng.record_budget(slo_id="SLO-002")
        assert len(eng.list_budgets()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_budget(
            slo_id="SLO-001",
            budget_status=BudgetStatus.HEALTHY,
        )
        eng.record_budget(
            slo_id="SLO-002",
            budget_status=BudgetStatus.EXHAUSTED,
        )
        results = eng.list_budgets(
            status=BudgetStatus.HEALTHY,
        )
        assert len(results) == 1

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_budget(
            slo_id="SLO-001",
            budget_scope=BudgetScope.SERVICE,
        )
        eng.record_budget(
            slo_id="SLO-002",
            budget_scope=BudgetScope.REGION,
        )
        results = eng.list_budgets(
            scope=BudgetScope.SERVICE,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_budget(slo_id="SLO-001", service="api-gateway")
        eng.record_budget(slo_id="SLO-002", service="auth-svc")
        results = eng.list_budgets(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_budget(slo_id="SLO-001", team="sre")
        eng.record_budget(slo_id="SLO-002", team="platform")
        results = eng.list_budgets(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_budget(slo_id=f"SLO-{i}")
        assert len(eng.list_budgets(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_allocation
# ---------------------------------------------------------------------------


class TestAddAllocation:
    def test_basic(self):
        eng = _engine()
        a = eng.add_allocation(
            slo_id="SLO-001",
            budget_status=BudgetStatus.WARNING,
            allocation_pct=75.0,
            threshold=80.0,
            breached=True,
            description="Budget nearing exhaustion",
        )
        assert a.slo_id == "SLO-001"
        assert a.budget_status == BudgetStatus.WARNING
        assert a.allocation_pct == 75.0
        assert a.threshold == 80.0
        assert a.breached is True
        assert a.description == "Budget nearing exhaustion"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_allocation(slo_id=f"SLO-{i}")
        assert len(eng._allocations) == 2


# ---------------------------------------------------------------------------
# analyze_budget_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeBudgetDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_budget(
            slo_id="SLO-001",
            budget_status=BudgetStatus.HEALTHY,
            remaining_budget_pct=80.0,
        )
        eng.record_budget(
            slo_id="SLO-002",
            budget_status=BudgetStatus.HEALTHY,
            remaining_budget_pct=60.0,
        )
        result = eng.analyze_budget_distribution()
        assert "healthy" in result
        assert result["healthy"]["count"] == 2
        assert result["healthy"]["avg_remaining_budget_pct"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_budget_distribution() == {}


# ---------------------------------------------------------------------------
# identify_exhausted_budgets
# ---------------------------------------------------------------------------


class TestIdentifyExhaustedBudgets:
    def test_detects_exhausted(self):
        eng = _engine()
        eng.record_budget(
            slo_id="SLO-001",
            budget_status=BudgetStatus.EXHAUSTED,
        )
        eng.record_budget(
            slo_id="SLO-002",
            budget_status=BudgetStatus.HEALTHY,
        )
        results = eng.identify_exhausted_budgets()
        assert len(results) == 1
        assert results[0]["slo_id"] == "SLO-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_exhausted_budgets() == []


# ---------------------------------------------------------------------------
# rank_by_remaining_budget
# ---------------------------------------------------------------------------


class TestRankByRemainingBudget:
    def test_ranked(self):
        eng = _engine()
        eng.record_budget(
            slo_id="SLO-001",
            service="api-gateway",
            remaining_budget_pct=80.0,
        )
        eng.record_budget(
            slo_id="SLO-002",
            service="auth-svc",
            remaining_budget_pct=20.0,
        )
        eng.record_budget(
            slo_id="SLO-003",
            service="api-gateway",
            remaining_budget_pct=60.0,
        )
        results = eng.rank_by_remaining_budget()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"
        assert results[0]["avg_remaining_budget_pct"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_remaining_budget() == []


# ---------------------------------------------------------------------------
# detect_budget_trends
# ---------------------------------------------------------------------------


class TestDetectBudgetTrends:
    def test_stable(self):
        eng = _engine()
        for val in [50.0, 50.0, 50.0, 50.0]:
            eng.add_allocation(slo_id="SLO-1", allocation_pct=val)
        result = eng.detect_budget_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [20.0, 20.0, 40.0, 40.0]:
            eng.add_allocation(slo_id="SLO-1", allocation_pct=val)
        result = eng.detect_budget_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_budget_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_budget(
            slo_id="SLO-001",
            budget_status=BudgetStatus.EXHAUSTED,
            budget_scope=BudgetScope.SERVICE,
            burn_rate=BurnRate.CRITICAL,
            remaining_budget_pct=0.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, SLOErrorBudgetReport)
        assert report.total_records == 1
        assert report.exhausted_count == 1
        assert len(report.top_exhausted) >= 1
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
        eng.record_budget(slo_id="SLO-001")
        eng.add_allocation(slo_id="SLO-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._allocations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_allocations"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_budget(
            slo_id="SLO-001",
            budget_status=BudgetStatus.HEALTHY,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "healthy" in stats["status_distribution"]
