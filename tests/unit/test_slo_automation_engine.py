"""Tests for shieldops.sla.slo_automation_engine — SLOAutomationEngine."""

from __future__ import annotations

from shieldops.sla.slo_automation_engine import (
    BudgetPolicy,
    ErrorBudgetPolicyRecord,
    SLOAutomationEngine,
    SLORecord,
    SLOReport,
    SLOStatus,
    SLOType,
)


def _engine(**kw) -> SLOAutomationEngine:
    return SLOAutomationEngine(**kw)


class TestEnums:
    def test_slo_type_availability(self):
        assert SLOType.AVAILABILITY == "availability"

    def test_slo_type_latency(self):
        assert SLOType.LATENCY == "latency"

    def test_slo_type_error_rate(self):
        assert SLOType.ERROR_RATE == "error_rate"

    def test_slo_type_throughput(self):
        assert SLOType.THROUGHPUT == "throughput"

    def test_slo_type_saturation(self):
        assert SLOType.SATURATION == "saturation"

    def test_status_active(self):
        assert SLOStatus.ACTIVE == "active"

    def test_status_proposed(self):
        assert SLOStatus.PROPOSED == "proposed"

    def test_status_breached(self):
        assert SLOStatus.BREACHED == "breached"

    def test_status_deprecated(self):
        assert SLOStatus.DEPRECATED == "deprecated"

    def test_budget_strict(self):
        assert BudgetPolicy.STRICT == "strict"

    def test_budget_relaxed(self):
        assert BudgetPolicy.RELAXED == "relaxed"

    def test_budget_adaptive(self):
        assert BudgetPolicy.ADAPTIVE == "adaptive"

    def test_budget_freeze(self):
        assert BudgetPolicy.FREEZE == "freeze"


class TestModels:
    def test_slo_record_defaults(self):
        r = SLORecord()
        assert r.id
        assert r.slo_type == SLOType.AVAILABILITY
        assert r.target_pct == 99.9
        assert r.status == SLOStatus.DRAFT

    def test_policy_defaults(self):
        p = ErrorBudgetPolicyRecord()
        assert p.id
        assert p.policy == BudgetPolicy.STRICT

    def test_report_defaults(self):
        r = SLOReport()
        assert r.total_slos == 0
        assert r.recommendations == []


class TestAddSLO:
    def test_basic(self):
        eng = _engine()
        s = eng.add_slo("api-avail", "api-svc", target_pct=99.95)
        assert s.name == "api-avail"
        assert s.target_pct == 99.95

    def test_eviction(self):
        eng = _engine(max_slos=3)
        for i in range(5):
            eng.add_slo(f"s-{i}", "svc")
        assert len(eng._slos) == 3


class TestProposeSLO:
    def test_new_service(self):
        eng = _engine()
        s = eng.propose_slo("api-svc")
        assert s.status == SLOStatus.PROPOSED
        assert s.target_pct == 99.5

    def test_existing_service(self):
        eng = _engine()
        s1 = eng.add_slo("existing", "api-svc")
        s1.current_pct = 99.8
        s2 = eng.propose_slo("api-svc")
        assert s2.target_pct > 0


class TestValidateSLO:
    def test_not_found(self):
        eng = _engine()
        result = eng.validate_slo("nonexistent")
        assert result["valid"] is False

    def test_valid(self):
        eng = _engine()
        eng.add_slo("api-avail", "api-svc", target_pct=99.9)
        result = eng.validate_slo("api-avail")
        assert result["valid"] is True

    def test_too_loose(self):
        eng = _engine()
        eng.add_slo("loose", "svc", target_pct=80.0)
        result = eng.validate_slo("loose")
        assert "too loose" in result["errors"][0]

    def test_too_strict(self):
        eng = _engine()
        eng.add_slo("strict", "svc", target_pct=99.9999)
        result = eng.validate_slo("strict")
        assert "unachievable" in result["errors"][0]

    def test_bad_window(self):
        eng = _engine()
        eng.add_slo("bad", "svc", window_days=0)
        # window_days=0 triggers error
        result = eng.validate_slo("bad")
        assert not result["valid"]


class TestAutoAdjustTargets:
    def test_budget_low(self):
        eng = _engine()
        s = eng.add_slo("api", "svc", target_pct=99.9)
        s.status = SLOStatus.ACTIVE
        s.error_budget_remaining_pct = 5.0
        adjustments = eng.auto_adjust_targets("svc")
        assert len(adjustments) == 1
        assert adjustments[0]["reason"] == "error budget nearly exhausted"

    def test_excess_budget(self):
        eng = _engine()
        s = eng.add_slo("api", "svc", target_pct=99.0)
        s.status = SLOStatus.ACTIVE
        s.error_budget_remaining_pct = 95.0
        adjustments = eng.auto_adjust_targets("svc")
        assert adjustments[0]["new_target"] > 99.0

    def test_skip_deprecated(self):
        eng = _engine()
        s = eng.add_slo("api", "svc")
        s.status = SLOStatus.DEPRECATED
        adjustments = eng.auto_adjust_targets("svc")
        assert len(adjustments) == 0

    def test_no_adjustments_needed(self):
        eng = _engine()
        s = eng.add_slo("api", "svc")
        s.status = SLOStatus.ACTIVE
        s.error_budget_remaining_pct = 50.0
        adjustments = eng.auto_adjust_targets("svc")
        assert len(adjustments) == 0


class TestGenerateErrorBudgetPolicy:
    def test_strict(self):
        eng = _engine()
        p = eng.generate_error_budget_policy("api-slo", BudgetPolicy.STRICT)
        assert p.policy == BudgetPolicy.STRICT
        assert "freeze" in p.action

    def test_relaxed(self):
        eng = _engine()
        p = eng.generate_error_budget_policy("api-slo", BudgetPolicy.RELAXED)
        assert "alert" in p.action

    def test_adaptive(self):
        eng = _engine()
        p = eng.generate_error_budget_policy("api-slo", BudgetPolicy.ADAPTIVE)
        assert "velocity" in p.action


class TestGetSLORecommendations:
    def test_missing_types(self):
        eng = _engine()
        eng.add_slo("api-avail", "api-svc", slo_type=SLOType.AVAILABILITY)
        recs = eng.get_slo_recommendations("api-svc")
        missing = [r for r in recs if r["type"] == "missing_slo"]
        assert len(missing) > 0

    def test_budget_low_warning(self):
        eng = _engine()
        s = eng.add_slo("api-avail", "api-svc")
        s.error_budget_remaining_pct = 10.0
        recs = eng.get_slo_recommendations("api-svc")
        budget_recs = [r for r in recs if r["type"] == "budget_low"]
        assert len(budget_recs) == 1

    def test_healthy(self):
        eng = _engine()
        for t in SLOType:
            eng.add_slo(f"slo-{t.value}", "svc", slo_type=t)
        recs = eng.get_slo_recommendations("svc")
        assert recs[0]["type"] == "healthy"


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_slos == 0

    def test_with_breached(self):
        eng = _engine()
        s = eng.add_slo("api", "svc")
        s.status = SLOStatus.BREACHED
        report = eng.generate_report()
        assert report.breached_count == 1
        assert any("breached" in r.lower() for r in report.recommendations)


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_slo("api", "svc")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._slos) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_slos"] == 0

    def test_populated(self):
        eng = _engine()
        eng.add_slo("api", "svc-a")
        eng.add_slo("db", "svc-b")
        stats = eng.get_stats()
        assert stats["unique_services"] == 2
