"""Tests for shieldops.sla.penalty_calculator — SLAPenaltyCalculator."""

from __future__ import annotations

from shieldops.sla.penalty_calculator import (
    ContractType,
    PenaltyRecord,
    PenaltyReport,
    PenaltyStatus,
    PenaltyThreshold,
    PenaltyTier,
    SLAPenaltyCalculator,
)


def _engine(**kw) -> SLAPenaltyCalculator:
    return SLAPenaltyCalculator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # PenaltyTier (5)
    def test_tier_no_penalty(self):
        assert PenaltyTier.NO_PENALTY == "no_penalty"

    def test_tier_1_minor(self):
        assert PenaltyTier.TIER_1_MINOR == "tier_1_minor"

    def test_tier_2_moderate(self):
        assert PenaltyTier.TIER_2_MODERATE == "tier_2_moderate"

    def test_tier_3_severe(self):
        assert PenaltyTier.TIER_3_SEVERE == "tier_3_severe"

    def test_tier_4_critical(self):
        assert PenaltyTier.TIER_4_CRITICAL == "tier_4_critical"

    # ContractType (5)
    def test_contract_standard(self):
        assert ContractType.STANDARD == "standard"

    def test_contract_premium(self):
        assert ContractType.PREMIUM == "premium"

    def test_contract_enterprise(self):
        assert ContractType.ENTERPRISE == "enterprise"

    def test_contract_custom(self):
        assert ContractType.CUSTOM == "custom"

    def test_contract_internal(self):
        assert ContractType.INTERNAL == "internal"

    # PenaltyStatus (5)
    def test_status_estimated(self):
        assert PenaltyStatus.ESTIMATED == "estimated"

    def test_status_confirmed(self):
        assert PenaltyStatus.CONFIRMED == "confirmed"

    def test_status_disputed(self):
        assert PenaltyStatus.DISPUTED == "disputed"

    def test_status_credited(self):
        assert PenaltyStatus.CREDITED == "credited"

    def test_status_waived(self):
        assert PenaltyStatus.WAIVED == "waived"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_penalty_record_defaults(self):
        r = PenaltyRecord()
        assert r.id
        assert r.customer_id == ""
        assert r.service_name == ""
        assert r.contract_type == ContractType.STANDARD
        assert r.tier == PenaltyTier.NO_PENALTY
        assert r.status == PenaltyStatus.ESTIMATED
        assert r.sla_target_pct == 99.9
        assert r.actual_pct == 99.9
        assert r.penalty_amount == 0.0
        assert r.created_at > 0

    def test_penalty_threshold_defaults(self):
        t = PenaltyThreshold()
        assert t.id
        assert t.contract_type == ContractType.STANDARD
        assert t.tier_1_breach_pct == 0.1
        assert t.tier_2_breach_pct == 0.5
        assert t.tier_3_breach_pct == 1.0
        assert t.tier_4_breach_pct == 5.0
        assert t.tier_1_credit_pct == 5.0
        assert t.tier_2_credit_pct == 10.0
        assert t.created_at > 0

    def test_penalty_report_defaults(self):
        r = PenaltyReport()
        assert r.total_penalties == 0
        assert r.total_exposure == 0.0
        assert r.total_credited == 0.0
        assert r.by_tier == {}
        assert r.by_status == {}
        assert r.by_contract == {}
        assert r.high_risk_customers == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_penalty
# ---------------------------------------------------------------------------


class TestRecordPenalty:
    def test_no_breach_yields_no_penalty(self):
        eng = _engine()
        rec = eng.record_penalty(
            customer_id="cust-1",
            service_name="api-gateway",
            contract_type=ContractType.STANDARD,
            sla_target_pct=99.9,
            actual_pct=99.95,
            breach_duration_minutes=0.0,
            monthly_revenue=10000.0,
        )
        assert rec.tier == PenaltyTier.NO_PENALTY
        assert rec.penalty_amount == 0.0

    def test_minor_breach(self):
        # breach = 99.9 - 99.7 = 0.2 → >= 0.1 (tier_1) and < 0.5 (tier_2) → TIER_1_MINOR
        eng = _engine()
        rec = eng.record_penalty(
            customer_id="cust-2",
            service_name="api-gateway",
            contract_type=ContractType.STANDARD,
            sla_target_pct=99.9,
            actual_pct=99.7,
            breach_duration_minutes=30.0,
            monthly_revenue=10000.0,
        )
        assert rec.tier == PenaltyTier.TIER_1_MINOR
        # credit_pct = 5.0% → 10000 * 5 / 100 = 500.0
        assert rec.penalty_amount == 500.0

    def test_severe_breach(self):
        # breach = 99.9 - 97.5 = 2.4 → >= 1.0 (tier_3) and < 5.0 (tier_4) → TIER_3_SEVERE
        eng = _engine()
        rec = eng.record_penalty(
            customer_id="cust-3",
            service_name="db-primary",
            contract_type=ContractType.STANDARD,
            sla_target_pct=99.9,
            actual_pct=97.5,
            breach_duration_minutes=180.0,
            monthly_revenue=20000.0,
        )
        assert rec.tier == PenaltyTier.TIER_3_SEVERE
        # credit_pct = 25% → 20000 * 25 / 100 = 5000.0
        assert rec.penalty_amount == 5000.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_penalty(
                customer_id=f"cust-{i}",
                service_name="svc",
                contract_type=ContractType.STANDARD,
                sla_target_pct=99.9,
                actual_pct=99.9,
                breach_duration_minutes=0.0,
                monthly_revenue=1000.0,
            )
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_penalty
# ---------------------------------------------------------------------------


class TestGetPenalty:
    def test_found(self):
        eng = _engine()
        rec = eng.record_penalty(
            customer_id="cust-1",
            service_name="api",
            contract_type=ContractType.STANDARD,
            sla_target_pct=99.9,
            actual_pct=99.9,
            breach_duration_minutes=0.0,
            monthly_revenue=5000.0,
        )
        result = eng.get_penalty(rec.id)
        assert result is not None
        assert result.customer_id == "cust-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_penalty("nonexistent") is None


# ---------------------------------------------------------------------------
# list_penalties
# ---------------------------------------------------------------------------


class TestListPenalties:
    def test_list_all(self):
        eng = _engine()
        eng.record_penalty("c1", "svc-a", ContractType.STANDARD, 99.9, 99.5, 10.0, 5000.0)
        eng.record_penalty("c2", "svc-b", ContractType.PREMIUM, 99.9, 99.5, 10.0, 5000.0)
        assert len(eng.list_penalties()) == 2

    def test_filter_by_customer(self):
        eng = _engine()
        eng.record_penalty("c1", "svc-a", ContractType.STANDARD, 99.9, 99.5, 10.0, 5000.0)
        eng.record_penalty("c2", "svc-b", ContractType.PREMIUM, 99.9, 99.5, 10.0, 5000.0)
        results = eng.list_penalties(customer_id="c1")
        assert len(results) == 1
        assert results[0].customer_id == "c1"

    def test_filter_by_tier(self):
        eng = _engine()
        # breach=0.4 → TIER_1_MINOR
        eng.record_penalty("c1", "svc", ContractType.STANDARD, 99.9, 99.5, 10.0, 5000.0)
        # breach=0 → NO_PENALTY
        eng.record_penalty("c2", "svc", ContractType.STANDARD, 99.9, 99.95, 0.0, 5000.0)
        results = eng.list_penalties(tier=PenaltyTier.NO_PENALTY)
        assert len(results) == 1
        assert results[0].customer_id == "c2"


# ---------------------------------------------------------------------------
# calculate_penalty
# ---------------------------------------------------------------------------


class TestCalculatePenalty:
    def test_no_breach(self):
        eng = _engine()
        result = eng.calculate_penalty(
            sla_target_pct=99.9,
            actual_pct=99.95,
            monthly_revenue=10000.0,
        )
        assert result["tier"] == PenaltyTier.NO_PENALTY.value
        assert result["penalty_amount"] == 0.0

    def test_tier_1(self):
        eng = _engine()
        # breach = 99.9 - 99.7 = 0.2 → TIER_1_MINOR, credit_pct=5%
        result = eng.calculate_penalty(
            sla_target_pct=99.9,
            actual_pct=99.7,
            monthly_revenue=10000.0,
        )
        assert result["tier"] == PenaltyTier.TIER_1_MINOR.value
        assert result["credit_pct"] == 5.0
        assert result["penalty_amount"] == 500.0

    def test_tier_4(self):
        eng = _engine()
        # breach = 99.9 - 90.0 = 9.9 → >= 5.0 → TIER_4_CRITICAL, credit_pct=50%
        result = eng.calculate_penalty(
            sla_target_pct=99.9,
            actual_pct=90.0,
            monthly_revenue=10000.0,
        )
        assert result["tier"] == PenaltyTier.TIER_4_CRITICAL.value
        assert result["credit_pct"] == 50.0
        assert result["penalty_amount"] == 5000.0


# ---------------------------------------------------------------------------
# set_threshold
# ---------------------------------------------------------------------------


class TestSetThreshold:
    def test_set_custom_threshold(self):
        eng = _engine()
        t = eng.set_threshold(
            contract_type=ContractType.ENTERPRISE,
            tier_1_breach_pct=0.05,
            tier_2_breach_pct=0.2,
            tier_3_breach_pct=0.5,
            tier_4_breach_pct=2.0,
            tier_1_credit_pct=10.0,
            tier_2_credit_pct=20.0,
            tier_3_credit_pct=40.0,
            tier_4_credit_pct=75.0,
        )
        assert t.contract_type == ContractType.ENTERPRISE
        assert t.tier_1_breach_pct == 0.05
        assert t.tier_4_credit_pct == 75.0

    def test_custom_threshold_applies_to_calculation(self):
        eng = _engine()
        eng.set_threshold(
            contract_type=ContractType.ENTERPRISE,
            tier_1_breach_pct=0.05,
            tier_2_breach_pct=0.2,
            tier_1_credit_pct=15.0,
            tier_2_credit_pct=30.0,
        )
        # breach = 99.9 - 99.8 = 0.1 → with custom thresholds: >= 0.05, < 0.2 → TIER_1
        result = eng.calculate_penalty(
            sla_target_pct=99.9,
            actual_pct=99.8,
            monthly_revenue=10000.0,
            contract_type=ContractType.ENTERPRISE,
        )
        assert result["tier"] == PenaltyTier.TIER_1_MINOR.value
        assert result["credit_pct"] == 15.0
        assert result["penalty_amount"] == 1500.0


# ---------------------------------------------------------------------------
# estimate_total_exposure
# ---------------------------------------------------------------------------


class TestEstimateTotalExposure:
    def test_with_penalties(self):
        eng = _engine()
        # breach=0.4 → TIER_1_MINOR, credit_pct=5% → penalty=500
        eng.record_penalty("c1", "svc", ContractType.STANDARD, 99.9, 99.5, 10.0, 10000.0)
        # breach=0.4 → TIER_1_MINOR, credit_pct=5% → penalty=250
        eng.record_penalty("c2", "svc", ContractType.STANDARD, 99.9, 99.5, 10.0, 5000.0)
        result = eng.estimate_total_exposure()
        assert result["estimated_count"] == 2
        assert result["total_exposure"] == 750.0
        assert "standard" in result["by_contract"]

    def test_empty(self):
        eng = _engine()
        result = eng.estimate_total_exposure()
        assert result["estimated_count"] == 0
        assert result["total_exposure"] == 0.0


# ---------------------------------------------------------------------------
# identify_high_risk_customers
# ---------------------------------------------------------------------------


class TestIdentifyHighRiskCustomers:
    def test_has_high_risk(self):
        eng = _engine()
        eng.record_penalty("c1", "svc", ContractType.STANDARD, 99.9, 99.5, 10.0, 50000.0)
        eng.record_penalty("c1", "svc", ContractType.STANDARD, 99.9, 99.5, 10.0, 30000.0)
        eng.record_penalty("c2", "svc", ContractType.STANDARD, 99.9, 99.5, 10.0, 1000.0)
        results = eng.identify_high_risk_customers()
        assert len(results) >= 2
        # c1 has highest total exposure, should be first
        assert results[0]["customer_id"] == "c1"
        assert results[0]["penalty_count"] == 2

    def test_none(self):
        eng = _engine()
        results = eng.identify_high_risk_customers()
        assert results == []


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------


class TestUpdateStatus:
    def test_valid_update(self):
        eng = _engine()
        rec = eng.record_penalty("c1", "svc", ContractType.STANDARD, 99.9, 99.5, 10.0, 5000.0)
        result = eng.update_status(rec.id, PenaltyStatus.CONFIRMED)
        assert result["found"] is True
        assert result["previous_status"] == PenaltyStatus.ESTIMATED.value
        assert result["new_status"] == PenaltyStatus.CONFIRMED.value

    def test_not_found(self):
        eng = _engine()
        result = eng.update_status("nonexistent", PenaltyStatus.CONFIRMED)
        assert result["found"] is False


# ---------------------------------------------------------------------------
# generate_penalty_report
# ---------------------------------------------------------------------------


class TestGeneratePenaltyReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_penalty("c1", "svc", ContractType.STANDARD, 99.9, 99.5, 10.0, 10000.0)
        eng.record_penalty("c2", "svc", ContractType.PREMIUM, 99.9, 90.0, 60.0, 20000.0)
        report = eng.generate_penalty_report()
        assert isinstance(report, PenaltyReport)
        assert report.total_penalties == 2
        assert report.total_exposure > 0
        assert len(report.by_tier) > 0
        assert len(report.by_status) > 0
        assert len(report.by_contract) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_penalty_report()
        assert report.total_penalties == 0
        assert report.total_exposure == 0.0
        assert "No SLA penalty exposure detected" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_penalty("c1", "svc", ContractType.STANDARD, 99.9, 99.5, 10.0, 5000.0)
        eng.set_threshold(ContractType.ENTERPRISE)
        assert len(eng._records) == 1
        assert len(eng._thresholds) == 1
        result = eng.clear_data()
        assert result["status"] == "cleared"
        assert len(eng._records) == 0
        assert len(eng._thresholds) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_thresholds"] == 0
        assert stats["tier_distribution"] == {}
        assert stats["unique_customers"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_penalty("c1", "svc", ContractType.STANDARD, 99.9, 99.5, 10.0, 5000.0)
        eng.record_penalty("c2", "svc", ContractType.PREMIUM, 99.9, 99.5, 10.0, 5000.0)
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["unique_customers"] == 2
        assert stats["default_credit_multiplier"] == 1.0
        assert len(stats["tier_distribution"]) > 0
