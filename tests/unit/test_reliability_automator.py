"""Tests for shieldops.sla.reliability_automator — ReliabilityAutomationEngine."""

from __future__ import annotations

from shieldops.sla.reliability_automator import (
    AdjustmentOutcome,
    AdjustmentRecord,
    AdjustmentRule,
    AdjustmentTrigger,
    AdjustmentType,
    ReliabilityAutomationEngine,
    ReliabilityAutomatorReport,
)


def _engine(**kw) -> ReliabilityAutomationEngine:
    return ReliabilityAutomationEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # AdjustmentType (5)
    def test_type_tighten_slo(self):
        assert AdjustmentType.TIGHTEN_SLO == "tighten_slo"

    def test_type_relax_slo(self):
        assert AdjustmentType.RELAX_SLO == "relax_slo"

    def test_type_add_redundancy(self):
        assert AdjustmentType.ADD_REDUNDANCY == "add_redundancy"

    def test_type_increase_monitoring(self):
        assert AdjustmentType.INCREASE_MONITORING == "increase_monitoring"

    def test_type_trigger_runbook(self):
        assert AdjustmentType.TRIGGER_RUNBOOK == "trigger_runbook"

    # AdjustmentTrigger (5)
    def test_trigger_performance_improvement(self):
        assert AdjustmentTrigger.PERFORMANCE_IMPROVEMENT == "performance_improvement"

    def test_trigger_degradation_detected(self):
        assert AdjustmentTrigger.DEGRADATION_DETECTED == "degradation_detected"

    def test_trigger_error_budget_low(self):
        assert AdjustmentTrigger.ERROR_BUDGET_LOW == "error_budget_low"

    def test_trigger_incident_pattern(self):
        assert AdjustmentTrigger.INCIDENT_PATTERN == "incident_pattern"

    def test_trigger_manual(self):
        assert AdjustmentTrigger.MANUAL == "manual"

    # AdjustmentOutcome (5)
    def test_outcome_applied(self):
        assert AdjustmentOutcome.APPLIED == "applied"

    def test_outcome_pending_approval(self):
        assert AdjustmentOutcome.PENDING_APPROVAL == "pending_approval"

    def test_outcome_rejected(self):
        assert AdjustmentOutcome.REJECTED == "rejected"

    def test_outcome_rolled_back(self):
        assert AdjustmentOutcome.ROLLED_BACK == "rolled_back"

    def test_outcome_scheduled(self):
        assert AdjustmentOutcome.SCHEDULED == "scheduled"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_adjustment_record_defaults(self):
        r = AdjustmentRecord()
        assert r.id
        assert r.service_name == ""
        assert r.adjustment_type == AdjustmentType.TIGHTEN_SLO
        assert r.adjustment_trigger == AdjustmentTrigger.PERFORMANCE_IMPROVEMENT
        assert r.adjustment_outcome == AdjustmentOutcome.APPLIED
        assert r.impact_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_adjustment_rule_defaults(self):
        r = AdjustmentRule()
        assert r.id
        assert r.rule_name == ""
        assert r.adjustment_type == AdjustmentType.ADD_REDUNDANCY
        assert r.adjustment_trigger == AdjustmentTrigger.DEGRADATION_DETECTED
        assert r.threshold_value == 0.0
        assert r.created_at > 0

    def test_reliability_automator_report_defaults(self):
        r = ReliabilityAutomatorReport()
        assert r.total_adjustments == 0
        assert r.total_rules == 0
        assert r.applied_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_outcome == {}
        assert r.rejection_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_adjustment
# -------------------------------------------------------------------


class TestRecordAdjustment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_adjustment("api-gateway", adjustment_type=AdjustmentType.TIGHTEN_SLO)
        assert r.service_name == "api-gateway"
        assert r.adjustment_type == AdjustmentType.TIGHTEN_SLO

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_adjustment(
            "payment-service",
            adjustment_type=AdjustmentType.ADD_REDUNDANCY,
            adjustment_trigger=AdjustmentTrigger.DEGRADATION_DETECTED,
            adjustment_outcome=AdjustmentOutcome.REJECTED,
            impact_score=75.0,
            details="Redundancy rejected by policy",
        )
        assert r.adjustment_outcome == AdjustmentOutcome.REJECTED
        assert r.adjustment_trigger == AdjustmentTrigger.DEGRADATION_DETECTED
        assert r.impact_score == 75.0
        assert r.details == "Redundancy rejected by policy"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_adjustment(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_adjustment
# -------------------------------------------------------------------


class TestGetAdjustment:
    def test_found(self):
        eng = _engine()
        r = eng.record_adjustment("api-gateway")
        assert eng.get_adjustment(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_adjustment("nonexistent") is None


# -------------------------------------------------------------------
# list_adjustments
# -------------------------------------------------------------------


class TestListAdjustments:
    def test_list_all(self):
        eng = _engine()
        eng.record_adjustment("svc-a")
        eng.record_adjustment("svc-b")
        assert len(eng.list_adjustments()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_adjustment("svc-a")
        eng.record_adjustment("svc-b")
        results = eng.list_adjustments(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_adjustment_type(self):
        eng = _engine()
        eng.record_adjustment("svc-a", adjustment_type=AdjustmentType.TIGHTEN_SLO)
        eng.record_adjustment("svc-b", adjustment_type=AdjustmentType.RELAX_SLO)
        results = eng.list_adjustments(adjustment_type=AdjustmentType.RELAX_SLO)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        rl = eng.add_rule(
            "auto-redundancy",
            adjustment_type=AdjustmentType.ADD_REDUNDANCY,
            adjustment_trigger=AdjustmentTrigger.ERROR_BUDGET_LOW,
            threshold_value=10.0,
        )
        assert rl.rule_name == "auto-redundancy"
        assert rl.adjustment_type == AdjustmentType.ADD_REDUNDANCY
        assert rl.threshold_value == 10.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_adjustment_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeAdjustmentEffectiveness:
    def test_with_data(self):
        eng = _engine(min_impact_score=50.0)
        eng.record_adjustment(
            "svc-a", adjustment_outcome=AdjustmentOutcome.APPLIED, impact_score=80.0
        )
        eng.record_adjustment(
            "svc-a", adjustment_outcome=AdjustmentOutcome.APPLIED, impact_score=60.0
        )
        eng.record_adjustment(
            "svc-a", adjustment_outcome=AdjustmentOutcome.REJECTED, impact_score=20.0
        )
        result = eng.analyze_adjustment_effectiveness("svc-a")
        assert result["applied_rate"] == 66.67
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_adjustment_effectiveness("unknown-svc")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_impact_score=50.0)
        eng.record_adjustment("svc-a", impact_score=80.0)
        eng.record_adjustment("svc-a", impact_score=60.0)
        result = eng.analyze_adjustment_effectiveness("svc-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_rejected_adjustments
# -------------------------------------------------------------------


class TestIdentifyRejectedAdjustments:
    def test_with_rejected(self):
        eng = _engine()
        eng.record_adjustment("svc-a", adjustment_outcome=AdjustmentOutcome.REJECTED)
        eng.record_adjustment("svc-a", adjustment_outcome=AdjustmentOutcome.ROLLED_BACK)
        eng.record_adjustment("svc-b", adjustment_outcome=AdjustmentOutcome.APPLIED)
        results = eng.identify_rejected_adjustments()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["rejected_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_rejected_adjustments() == []

    def test_single_rejected_not_returned(self):
        eng = _engine()
        eng.record_adjustment("svc-a", adjustment_outcome=AdjustmentOutcome.REJECTED)
        assert eng.identify_rejected_adjustments() == []


# -------------------------------------------------------------------
# rank_by_impact_score
# -------------------------------------------------------------------


class TestRankByImpactScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_adjustment("svc-a", impact_score=20.0)
        eng.record_adjustment("svc-b", impact_score=90.0)
        results = eng.rank_by_impact_score()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_impact_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_score() == []


# -------------------------------------------------------------------
# detect_adjustment_conflicts
# -------------------------------------------------------------------


class TestDetectAdjustmentConflicts:
    def test_with_conflicts(self):
        eng = _engine()
        for _ in range(5):
            eng.record_adjustment("svc-a")
        eng.record_adjustment("svc-b")
        results = eng.detect_adjustment_conflicts()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_adjustment_conflicts() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_adjustment("svc-a")
        assert eng.detect_adjustment_conflicts() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_adjustment("svc-a", adjustment_outcome=AdjustmentOutcome.REJECTED)
        eng.record_adjustment("svc-b", adjustment_outcome=AdjustmentOutcome.APPLIED)
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_adjustments == 2
        assert report.total_rules == 1
        assert report.rejection_count == 1
        assert report.by_type != {}
        assert report.by_outcome != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_adjustments == 0
        assert report.applied_rate_pct == 0.0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_adjustment("svc-a")
        eng.add_rule("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_adjustments"] == 0
        assert stats["total_rules"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_impact_score=50.0)
        eng.record_adjustment("svc-a", adjustment_type=AdjustmentType.TIGHTEN_SLO)
        eng.record_adjustment("svc-b", adjustment_type=AdjustmentType.RELAX_SLO)
        eng.add_rule("rule-1")
        stats = eng.get_stats()
        assert stats["total_adjustments"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_services"] == 2
        assert stats["min_impact_score"] == 50.0
