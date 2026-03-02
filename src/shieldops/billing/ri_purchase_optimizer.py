"""RI Purchase Optimizer — optimize reserved instance and savings plan purchases."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReservationType(StrEnum):
    STANDARD = "standard"
    CONVERTIBLE = "convertible"
    SAVINGS_PLAN = "savings_plan"
    SPOT = "spot"
    ON_DEMAND = "on_demand"


class CommitmentTerm(StrEnum):
    ONE_YEAR = "one_year"
    THREE_YEAR = "three_year"
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    NONE = "none"


class PaymentOption(StrEnum):
    ALL_UPFRONT = "all_upfront"
    PARTIAL_UPFRONT = "partial_upfront"
    NO_UPFRONT = "no_upfront"
    MONTHLY = "monthly"
    CUSTOM = "custom"


# --- Models ---


class RIPurchaseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reservation_type: ReservationType = ReservationType.STANDARD
    commitment_term: CommitmentTerm = CommitmentTerm.ONE_YEAR
    payment_option: PaymentOption = PaymentOption.NO_UPFRONT
    on_demand_cost: float = 0.0
    reserved_cost: float = 0.0
    savings_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PurchaseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reservation_type: ReservationType = ReservationType.STANDARD
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RIPurchaseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_savings_count: int = 0
    avg_savings_pct: float = 0.0
    by_reservation_type: dict[str, int] = Field(default_factory=dict)
    by_commitment_term: dict[str, int] = Field(default_factory=dict)
    by_payment_option: dict[str, int] = Field(default_factory=dict)
    top_opportunities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RIPurchaseOptimizer:
    """Optimize reserved instance and savings plan purchases for cloud cost reduction."""

    def __init__(
        self,
        max_records: int = 200000,
        savings_threshold: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._savings_threshold = savings_threshold
        self._records: list[RIPurchaseRecord] = []
        self._analyses: list[PurchaseAnalysis] = []
        logger.info(
            "ri_purchase_optimizer.initialized",
            max_records=max_records,
            savings_threshold=savings_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_purchase(
        self,
        reservation_type: ReservationType = ReservationType.STANDARD,
        commitment_term: CommitmentTerm = CommitmentTerm.ONE_YEAR,
        payment_option: PaymentOption = PaymentOption.NO_UPFRONT,
        on_demand_cost: float = 0.0,
        reserved_cost: float = 0.0,
        savings_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RIPurchaseRecord:
        record = RIPurchaseRecord(
            reservation_type=reservation_type,
            commitment_term=commitment_term,
            payment_option=payment_option,
            on_demand_cost=on_demand_cost,
            reserved_cost=reserved_cost,
            savings_pct=savings_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "ri_purchase_optimizer.purchase_recorded",
            record_id=record.id,
            reservation_type=reservation_type.value,
            savings_pct=savings_pct,
        )
        return record

    def get_purchase(self, record_id: str) -> RIPurchaseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_purchases(
        self,
        reservation_type: ReservationType | None = None,
        commitment_term: CommitmentTerm | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RIPurchaseRecord]:
        results = list(self._records)
        if reservation_type is not None:
            results = [r for r in results if r.reservation_type == reservation_type]
        if commitment_term is not None:
            results = [r for r in results if r.commitment_term == commitment_term]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        reservation_type: ReservationType = ReservationType.STANDARD,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PurchaseAnalysis:
        analysis = PurchaseAnalysis(
            reservation_type=reservation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "ri_purchase_optimizer.analysis_added",
            reservation_type=reservation_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by reservation_type; return count and avg savings_pct."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.reservation_type.value
            type_data.setdefault(key, []).append(r.savings_pct)
        result: dict[str, Any] = {}
        for rtype, savings in type_data.items():
            result[rtype] = {
                "count": len(savings),
                "avg_savings_pct": round(sum(savings) / len(savings), 2),
            }
        return result

    def identify_high_savings_opportunities(self) -> list[dict[str, Any]]:
        """Return records where savings_pct >= savings_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.savings_pct >= self._savings_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "reservation_type": r.reservation_type.value,
                        "savings_pct": r.savings_pct,
                        "on_demand_cost": r.on_demand_cost,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["savings_pct"], reverse=True)

    def rank_by_savings(self) -> list[dict[str, Any]]:
        """Group by service, avg savings_pct, sort descending."""
        svc_savings: dict[str, list[float]] = {}
        for r in self._records:
            svc_savings.setdefault(r.service, []).append(r.savings_pct)
        results: list[dict[str, Any]] = [
            {
                "service": svc,
                "avg_savings_pct": round(sum(s) / len(s), 2),
            }
            for svc, s in svc_savings.items()
        ]
        results.sort(key=lambda x: x["avg_savings_pct"], reverse=True)
        return results

    def detect_savings_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> RIPurchaseReport:
        by_type: dict[str, int] = {}
        by_term: dict[str, int] = {}
        by_payment: dict[str, int] = {}
        for r in self._records:
            by_type[r.reservation_type.value] = by_type.get(r.reservation_type.value, 0) + 1
            by_term[r.commitment_term.value] = by_term.get(r.commitment_term.value, 0) + 1
            by_payment[r.payment_option.value] = by_payment.get(r.payment_option.value, 0) + 1
        high_savings_count = sum(
            1 for r in self._records if r.savings_pct >= self._savings_threshold
        )
        savings = [r.savings_pct for r in self._records]
        avg_savings_pct = round(sum(savings) / len(savings), 2) if savings else 0.0
        opps = self.identify_high_savings_opportunities()
        top_opportunities = [o["record_id"] for o in opps[:5]]
        recs: list[str] = []
        if high_savings_count > 0:
            recs.append(f"{high_savings_count} high-savings RI opportunity(ies) identified")
        if avg_savings_pct < self._savings_threshold and self._records:
            recs.append(f"Avg savings {avg_savings_pct}% below target ({self._savings_threshold}%)")
        if not recs:
            recs.append("RI purchase optimization is healthy")
        return RIPurchaseReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_savings_count=high_savings_count,
            avg_savings_pct=avg_savings_pct,
            by_reservation_type=by_type,
            by_commitment_term=by_term,
            by_payment_option=by_payment,
            top_opportunities=top_opportunities,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("ri_purchase_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.reservation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "savings_threshold": self._savings_threshold,
            "reservation_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
