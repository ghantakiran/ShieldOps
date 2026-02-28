"""Platform Cost Optimizer — holistic cost optimization across platform."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CostDomain(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    OBSERVABILITY = "observability"
    LICENSING = "licensing"


class OptimizationAction(StrEnum):
    RIGHTSIZE = "rightsize"
    CONSOLIDATE = "consolidate"
    ELIMINATE = "eliminate"
    NEGOTIATE = "negotiate"
    MIGRATE = "migrate"


class OptimizationStatus(StrEnum):
    IDENTIFIED = "identified"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"
    DEFERRED = "deferred"


# --- Models ---


class OptimizationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str = ""
    cost_domain: CostDomain = CostDomain.COMPUTE
    action: OptimizationAction = OptimizationAction.RIGHTSIZE
    status: OptimizationStatus = OptimizationStatus.IDENTIFIED
    savings_amount: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class OptimizationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    cost_domain: CostDomain = CostDomain.COMPUTE
    action: OptimizationAction = OptimizationAction.RIGHTSIZE
    min_savings_threshold: float = 100.0
    auto_implement: bool = False
    created_at: float = Field(default_factory=time.time)


class PlatformCostReport(BaseModel):
    total_optimizations: int = 0
    total_rules: int = 0
    implementation_rate_pct: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    total_savings: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PlatformCostOptimizer:
    """Holistic cost optimization across platform."""

    def __init__(
        self,
        max_records: int = 200000,
        min_savings_threshold: float = 100.0,
    ) -> None:
        self._max_records = max_records
        self._min_savings_threshold = min_savings_threshold
        self._records: list[OptimizationRecord] = []
        self._rules: list[OptimizationRule] = []
        logger.info(
            "platform_cost.initialized",
            max_records=max_records,
            min_savings=min_savings_threshold,
        )

    # -- record / get / list -----------------------------------------

    def record_optimization(
        self,
        domain_name: str,
        cost_domain: CostDomain = CostDomain.COMPUTE,
        action: OptimizationAction = (OptimizationAction.RIGHTSIZE),
        status: OptimizationStatus = (OptimizationStatus.IDENTIFIED),
        savings_amount: float = 0.0,
        details: str = "",
    ) -> OptimizationRecord:
        record = OptimizationRecord(
            domain_name=domain_name,
            cost_domain=cost_domain,
            action=action,
            status=status,
            savings_amount=savings_amount,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "platform_cost.optimization_recorded",
            record_id=record.id,
            domain_name=domain_name,
            cost_domain=cost_domain.value,
            status=status.value,
        )
        return record

    def get_optimization(self, record_id: str) -> OptimizationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_optimizations(
        self,
        domain_name: str | None = None,
        cost_domain: CostDomain | None = None,
        limit: int = 50,
    ) -> list[OptimizationRecord]:
        results = list(self._records)
        if domain_name is not None:
            results = [r for r in results if r.domain_name == domain_name]
        if cost_domain is not None:
            results = [r for r in results if r.cost_domain == cost_domain]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        cost_domain: CostDomain = CostDomain.COMPUTE,
        action: OptimizationAction = (OptimizationAction.RIGHTSIZE),
        min_savings_threshold: float = 100.0,
        auto_implement: bool = False,
    ) -> OptimizationRule:
        rule = OptimizationRule(
            rule_name=rule_name,
            cost_domain=cost_domain,
            action=action,
            min_savings_threshold=min_savings_threshold,
            auto_implement=auto_implement,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "platform_cost.rule_added",
            rule_name=rule_name,
            cost_domain=cost_domain.value,
            action=action.value,
        )
        return rule

    # -- domain operations -------------------------------------------

    def analyze_cost_efficiency(self, domain_name: str) -> dict[str, Any]:
        """Analyze cost efficiency for a domain."""
        records = [r for r in self._records if r.domain_name == domain_name]
        if not records:
            return {
                "domain_name": domain_name,
                "status": "no_data",
            }
        implemented = sum(1 for r in records if r.status == OptimizationStatus.IMPLEMENTED)
        impl_rate = round(implemented / len(records) * 100, 2)
        avg_savings = round(
            sum(r.savings_amount for r in records) / len(records),
            2,
        )
        return {
            "domain_name": domain_name,
            "optimization_count": len(records),
            "implemented_count": implemented,
            "implementation_rate": impl_rate,
            "avg_savings": avg_savings,
            "meets_threshold": (avg_savings >= self._min_savings_threshold),
        }

    def identify_rejected_optimizations(
        self,
    ) -> list[dict[str, Any]]:
        """Find domains with repeated rejections."""
        reject_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (
                OptimizationStatus.REJECTED,
                OptimizationStatus.DEFERRED,
            ):
                reject_counts[r.domain_name] = reject_counts.get(r.domain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for dom, count in reject_counts.items():
            if count > 1:
                results.append(
                    {
                        "domain_name": dom,
                        "rejected_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["rejected_count"],
            reverse=True,
        )
        return results

    def rank_by_savings(
        self,
    ) -> list[dict[str, Any]]:
        """Rank domains by avg savings descending."""
        totals: dict[str, list[float]] = {}
        for r in self._records:
            totals.setdefault(r.domain_name, []).append(r.savings_amount)
        results: list[dict[str, Any]] = []
        for dom, savings in totals.items():
            avg = round(sum(savings) / len(savings), 2)
            results.append(
                {
                    "domain_name": dom,
                    "avg_savings": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_savings"],
            reverse=True,
        )
        return results

    def detect_cost_anomalies(
        self,
    ) -> list[dict[str, Any]]:
        """Detect domains with >3 non-IMPLEMENTED."""
        dom_non_impl: dict[str, int] = {}
        for r in self._records:
            if r.status != (OptimizationStatus.IMPLEMENTED):
                dom_non_impl[r.domain_name] = dom_non_impl.get(r.domain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for dom, count in dom_non_impl.items():
            if count > 3:
                results.append(
                    {
                        "domain_name": dom,
                        "non_implemented_count": count,
                        "anomaly_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_implemented_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> PlatformCostReport:
        by_domain: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_domain[r.cost_domain.value] = by_domain.get(r.cost_domain.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        impl_count = sum(1 for r in self._records if r.status == OptimizationStatus.IMPLEMENTED)
        impl_rate = (
            round(
                impl_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        total_savings = round(
            sum(r.savings_amount for r in self._records),
            2,
        )
        rejected = len(self.identify_rejected_optimizations())
        recs: list[str] = []
        if impl_rate < 50.0:
            recs.append(f"Implementation rate {impl_rate}% is below 50.0% threshold")
        if rejected > 0:
            recs.append(f"{rejected} domain(s) with rejected optimizations")
        anomalies = len(self.detect_cost_anomalies())
        if anomalies > 0:
            recs.append(f"{anomalies} domain(s) with cost anomalies")
        if not recs:
            recs.append("Cost optimization efficiency is healthy")
        return PlatformCostReport(
            total_optimizations=len(self._records),
            total_rules=len(self._rules),
            implementation_rate_pct=impl_rate,
            by_domain=by_domain,
            by_status=by_status,
            total_savings=total_savings,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("platform_cost.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.cost_domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_optimizations": len(self._records),
            "total_rules": len(self._rules),
            "min_savings_threshold": (self._min_savings_threshold),
            "domain_distribution": domain_dist,
            "unique_domains": len({r.domain_name for r in self._records}),
        }
