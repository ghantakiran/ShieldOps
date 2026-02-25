"""SLA Penalty Calculator — compute financial penalty exposure from SLA breaches."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PenaltyTier(StrEnum):
    NO_PENALTY = "no_penalty"
    TIER_1_MINOR = "tier_1_minor"
    TIER_2_MODERATE = "tier_2_moderate"
    TIER_3_SEVERE = "tier_3_severe"
    TIER_4_CRITICAL = "tier_4_critical"


class ContractType(StrEnum):
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"
    INTERNAL = "internal"


class PenaltyStatus(StrEnum):
    ESTIMATED = "estimated"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    CREDITED = "credited"
    WAIVED = "waived"


# --- Models ---


class PenaltyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str = ""
    service_name: str = ""
    contract_type: ContractType = ContractType.STANDARD
    tier: PenaltyTier = PenaltyTier.NO_PENALTY
    status: PenaltyStatus = PenaltyStatus.ESTIMATED
    sla_target_pct: float = 99.9
    actual_pct: float = 99.9
    breach_duration_minutes: float = 0.0
    monthly_revenue: float = 0.0
    penalty_amount: float = 0.0
    credit_amount: float = 0.0
    created_at: float = Field(default_factory=time.time)


class PenaltyThreshold(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_type: ContractType = ContractType.STANDARD
    tier_1_breach_pct: float = 0.1
    tier_2_breach_pct: float = 0.5
    tier_3_breach_pct: float = 1.0
    tier_4_breach_pct: float = 5.0
    tier_1_credit_pct: float = 5.0
    tier_2_credit_pct: float = 10.0
    tier_3_credit_pct: float = 25.0
    tier_4_credit_pct: float = 50.0
    created_at: float = Field(default_factory=time.time)


class PenaltyReport(BaseModel):
    total_penalties: int = 0
    total_exposure: float = 0.0
    total_credited: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_contract: dict[str, int] = Field(default_factory=dict)
    high_risk_customers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---

_DEFAULT_THRESHOLDS = PenaltyThreshold()


class SLAPenaltyCalculator:
    """Compute financial penalty exposure from SLA breaches."""

    def __init__(
        self,
        max_records: int = 200000,
        default_credit_multiplier: float = 1.0,
    ) -> None:
        self._max_records = max_records
        self._default_credit_multiplier = default_credit_multiplier
        self._records: list[PenaltyRecord] = []
        self._thresholds: dict[str, PenaltyThreshold] = {}
        logger.info(
            "penalty_calculator.initialized",
            max_records=max_records,
            default_credit_multiplier=default_credit_multiplier,
        )

    # -- internal helpers ------------------------------------------------

    def _get_threshold(self, contract_type: ContractType) -> PenaltyThreshold:
        return self._thresholds.get(contract_type.value, _DEFAULT_THRESHOLDS)

    def _determine_tier(
        self,
        breach_pct: float,
        threshold: PenaltyThreshold,
    ) -> PenaltyTier:
        if breach_pct <= 0:
            return PenaltyTier.NO_PENALTY
        if breach_pct < threshold.tier_1_breach_pct:
            return PenaltyTier.NO_PENALTY
        if breach_pct < threshold.tier_2_breach_pct:
            return PenaltyTier.TIER_1_MINOR
        if breach_pct < threshold.tier_3_breach_pct:
            return PenaltyTier.TIER_2_MODERATE
        if breach_pct < threshold.tier_4_breach_pct:
            return PenaltyTier.TIER_3_SEVERE
        return PenaltyTier.TIER_4_CRITICAL

    def _credit_pct_for_tier(
        self,
        tier: PenaltyTier,
        threshold: PenaltyThreshold,
    ) -> float:
        mapping = {
            PenaltyTier.NO_PENALTY: 0.0,
            PenaltyTier.TIER_1_MINOR: threshold.tier_1_credit_pct,
            PenaltyTier.TIER_2_MODERATE: threshold.tier_2_credit_pct,
            PenaltyTier.TIER_3_SEVERE: threshold.tier_3_credit_pct,
            PenaltyTier.TIER_4_CRITICAL: threshold.tier_4_credit_pct,
        }
        return mapping.get(tier, 0.0)

    # -- record / get / list ---------------------------------------------

    def record_penalty(
        self,
        customer_id: str,
        service_name: str,
        contract_type: ContractType,
        sla_target_pct: float,
        actual_pct: float,
        breach_duration_minutes: float,
        monthly_revenue: float,
    ) -> PenaltyRecord:
        breach_pct = sla_target_pct - actual_pct
        threshold = self._get_threshold(contract_type)
        tier = self._determine_tier(breach_pct, threshold)
        credit_pct = self._credit_pct_for_tier(tier, threshold)
        penalty_amount = round(monthly_revenue * credit_pct / 100, 2)
        credit_amount = round(penalty_amount * self._default_credit_multiplier, 2)
        record = PenaltyRecord(
            customer_id=customer_id,
            service_name=service_name,
            contract_type=contract_type,
            tier=tier,
            sla_target_pct=sla_target_pct,
            actual_pct=actual_pct,
            breach_duration_minutes=breach_duration_minutes,
            monthly_revenue=monthly_revenue,
            penalty_amount=penalty_amount,
            credit_amount=credit_amount,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "penalty_calculator.penalty_recorded",
            record_id=record.id,
            customer_id=customer_id,
            tier=tier.value,
        )
        return record

    def get_penalty(self, record_id: str) -> PenaltyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_penalties(
        self,
        customer_id: str | None = None,
        tier: PenaltyTier | None = None,
        limit: int = 50,
    ) -> list[PenaltyRecord]:
        results = list(self._records)
        if customer_id is not None:
            results = [r for r in results if r.customer_id == customer_id]
        if tier is not None:
            results = [r for r in results if r.tier == tier]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def calculate_penalty(
        self,
        sla_target_pct: float,
        actual_pct: float,
        monthly_revenue: float,
        contract_type: ContractType = ContractType.STANDARD,
    ) -> dict[str, Any]:
        """Standalone penalty calculation without recording."""
        breach_pct = sla_target_pct - actual_pct
        threshold = self._get_threshold(contract_type)
        tier = self._determine_tier(breach_pct, threshold)
        credit_pct = self._credit_pct_for_tier(tier, threshold)
        penalty_amount = round(monthly_revenue * credit_pct / 100, 2)
        credit_amount = round(penalty_amount * self._default_credit_multiplier, 2)
        return {
            "breach_pct": round(breach_pct, 4),
            "tier": tier.value,
            "credit_pct": credit_pct,
            "penalty_amount": penalty_amount,
            "credit_amount": credit_amount,
            "contract_type": contract_type.value,
        }

    def set_threshold(
        self,
        contract_type: ContractType,
        tier_1_breach_pct: float = 0.1,
        tier_2_breach_pct: float = 0.5,
        tier_3_breach_pct: float = 1.0,
        tier_4_breach_pct: float = 5.0,
        tier_1_credit_pct: float = 5.0,
        tier_2_credit_pct: float = 10.0,
        tier_3_credit_pct: float = 25.0,
        tier_4_credit_pct: float = 50.0,
    ) -> PenaltyThreshold:
        threshold = PenaltyThreshold(
            contract_type=contract_type,
            tier_1_breach_pct=tier_1_breach_pct,
            tier_2_breach_pct=tier_2_breach_pct,
            tier_3_breach_pct=tier_3_breach_pct,
            tier_4_breach_pct=tier_4_breach_pct,
            tier_1_credit_pct=tier_1_credit_pct,
            tier_2_credit_pct=tier_2_credit_pct,
            tier_3_credit_pct=tier_3_credit_pct,
            tier_4_credit_pct=tier_4_credit_pct,
        )
        self._thresholds[contract_type.value] = threshold
        logger.info(
            "penalty_calculator.threshold_set",
            contract_type=contract_type.value,
            threshold_id=threshold.id,
        )
        return threshold

    def estimate_total_exposure(self) -> dict[str, Any]:
        """Sum of all estimated penalties."""
        estimated = [r for r in self._records if r.status == PenaltyStatus.ESTIMATED]
        total_exposure = round(sum(r.penalty_amount for r in estimated), 2)
        total_credit = round(sum(r.credit_amount for r in estimated), 2)
        by_contract: dict[str, float] = {}
        for r in estimated:
            key = r.contract_type.value
            by_contract[key] = round(by_contract.get(key, 0.0) + r.penalty_amount, 2)
        return {
            "estimated_count": len(estimated),
            "total_exposure": total_exposure,
            "total_credit": total_credit,
            "by_contract": by_contract,
        }

    def identify_high_risk_customers(self) -> list[dict[str, Any]]:
        """Customers with highest penalty exposure."""
        exposure: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            exposure[r.customer_id] = round(
                exposure.get(r.customer_id, 0.0) + r.penalty_amount,
                2,
            )
            counts[r.customer_id] = counts.get(r.customer_id, 0) + 1
        results: list[dict[str, Any]] = [
            {"customer_id": cid, "total_exposure": exp, "penalty_count": counts[cid]}
            for cid, exp in exposure.items()
        ]
        results.sort(key=lambda x: x["total_exposure"], reverse=True)
        return results

    def update_status(
        self,
        record_id: str,
        status: PenaltyStatus,
    ) -> dict[str, Any]:
        record = self.get_penalty(record_id)
        if record is None:
            return {"found": False, "record_id": record_id}
        previous = record.status.value
        record.status = status
        logger.info(
            "penalty_calculator.status_updated",
            record_id=record_id,
            previous=previous,
            new_status=status.value,
        )
        return {
            "found": True,
            "record_id": record_id,
            "previous_status": previous,
            "new_status": status.value,
        }

    # -- report / stats --------------------------------------------------

    def generate_penalty_report(self) -> PenaltyReport:
        by_tier: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_contract: dict[str, int] = {}
        total_exposure = 0.0
        total_credited = 0.0
        for r in self._records:
            by_tier[r.tier.value] = by_tier.get(r.tier.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_contract[r.contract_type.value] = by_contract.get(r.contract_type.value, 0) + 1
            total_exposure += r.penalty_amount
            if r.status == PenaltyStatus.CREDITED:
                total_credited += r.credit_amount
        high_risk = self.identify_high_risk_customers()
        high_risk_ids = [c["customer_id"] for c in high_risk[:5]]
        recs: list[str] = []
        critical = by_tier.get(PenaltyTier.TIER_4_CRITICAL.value, 0)
        if critical > 0:
            recs.append(f"{critical} critical-tier penalty(ies) require review")
        disputed = by_status.get(PenaltyStatus.DISPUTED.value, 0)
        if disputed > 0:
            recs.append(f"{disputed} penalty(ies) are in dispute")
        if total_exposure > 0:
            recs.append(f"Total financial exposure: ${round(total_exposure, 2):,.2f}")
        if not recs:
            recs.append("No SLA penalty exposure detected")
        return PenaltyReport(
            total_penalties=len(self._records),
            total_exposure=round(total_exposure, 2),
            total_credited=round(total_credited, 2),
            by_tier=by_tier,
            by_status=by_status,
            by_contract=by_contract,
            high_risk_customers=high_risk_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._thresholds.clear()
        logger.info("penalty_calculator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_thresholds": len(self._thresholds),
            "default_credit_multiplier": self._default_credit_multiplier,
            "tier_distribution": tier_dist,
            "unique_customers": len({r.customer_id for r in self._records}),
        }
