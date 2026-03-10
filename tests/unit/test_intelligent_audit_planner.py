"""Tests for IntelligentAuditPlanner."""

from __future__ import annotations

from shieldops.audit.intelligent_audit_planner import (
    AuditPriority,
    AuditScope,
    IntelligentAuditPlanner,
    PlanningHorizon,
)


def _engine(**kw) -> IntelligentAuditPlanner:
    return IntelligentAuditPlanner(**kw)


class TestEnums:
    def test_audit_scope_values(self):
        assert AuditScope.FULL == "full"
        assert AuditScope.TARGETED == "targeted"
        assert AuditScope.CONTINUOUS == "continuous"
        assert AuditScope.SAMPLING == "sampling"

    def test_audit_priority_values(self):
        assert AuditPriority.CRITICAL == "critical"
        assert AuditPriority.HIGH == "high"
        assert AuditPriority.MEDIUM == "medium"
        assert AuditPriority.LOW == "low"

    def test_planning_horizon_values(self):
        assert PlanningHorizon.WEEKLY == "weekly"
        assert PlanningHorizon.MONTHLY == "monthly"
        assert PlanningHorizon.QUARTERLY == "quarterly"
        assert PlanningHorizon.ANNUAL == "annual"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            name="audit-001",
            audit_scope=AuditScope.FULL,
            audit_priority=AuditPriority.CRITICAL,
            score=70.0,
            service="payments",
            team="compliance",
        )
        assert r.name == "audit-001"
        assert r.audit_scope == AuditScope.FULL
        assert r.score == 70.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="test", score=40.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1

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
        eng.add_record(name="t", service="a", team="b")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(name="test")
        eng.add_analysis(name="test")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGenerateAuditPlan:
    def test_returns_sorted_by_urgency(self):
        eng = _engine()
        eng.add_record(
            name="critical",
            audit_priority=AuditPriority.CRITICAL,
            score=20.0,
        )
        eng.add_record(
            name="low",
            audit_priority=AuditPriority.LOW,
            score=90.0,
        )
        plan = eng.generate_audit_plan()
        assert plan[0]["name"] == "critical"
        assert plan[0]["urgency_score"] > plan[1]["urgency_score"]

    def test_empty(self):
        eng = _engine()
        assert eng.generate_audit_plan() == []


class TestOptimizeAuditCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            service="api",
            audit_scope=AuditScope.FULL,
            score=80.0,
        )
        result = eng.optimize_audit_coverage()
        assert result["total_services"] == 1
        cov = result["service_coverage"]
        assert len(cov) == 1
        assert cov[0]["scope_coverage_pct"] == 25.0

    def test_empty(self):
        eng = _engine()
        result = eng.optimize_audit_coverage()
        assert result["total_services"] == 0


class TestComputeAuditEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            audit_scope=AuditScope.FULL,
            score=85.0,
        )
        result = eng.compute_audit_efficiency()
        assert result["overall_efficiency"] == 85.0
        assert result["total_audits"] == 1
        assert "full" in result["by_scope"]

    def test_empty(self):
        eng = _engine()
        result = eng.compute_audit_efficiency()
        assert result["overall_efficiency"] == 0.0
