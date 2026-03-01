"""Cost Attribution Engine — attribute costs to teams/services, shared cost splitting."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AttributionMethod(StrEnum):
    DIRECT = "direct"
    PROPORTIONAL = "proportional"
    EQUAL_SPLIT = "equal_split"
    USAGE_BASED = "usage_based"
    CUSTOM = "custom"


class CostCategory(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    PLATFORM = "platform"
    TOOLING = "tooling"
    SUPPORT = "support"
    OVERHEAD = "overhead"


class AttributionAccuracy(StrEnum):
    VERIFIED = "verified"
    ESTIMATED = "estimated"
    PROJECTED = "projected"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


# --- Models ---


class AttributionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    attribution_id: str = ""
    attribution_method: AttributionMethod = AttributionMethod.DIRECT
    cost_category: CostCategory = CostCategory.INFRASTRUCTURE
    attribution_accuracy: AttributionAccuracy = AttributionAccuracy.UNKNOWN
    cost_amount: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AttributionDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    attribution_id: str = ""
    attribution_method: AttributionMethod = AttributionMethod.DIRECT
    detail_amount: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostAttributionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_details: int = 0
    disputed_attributions: int = 0
    avg_cost_amount: float = 0.0
    by_method: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_accuracy: dict[str, int] = Field(default_factory=dict)
    top_attributed: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostAttributionEngine:
    """Attribute costs to teams/services, shared cost splitting."""

    def __init__(
        self,
        max_records: int = 200000,
        max_disputed_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_disputed_pct = max_disputed_pct
        self._records: list[AttributionRecord] = []
        self._details: list[AttributionDetail] = []
        logger.info(
            "cost_attribution_engine.initialized",
            max_records=max_records,
            max_disputed_pct=max_disputed_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_attribution(
        self,
        attribution_id: str,
        attribution_method: AttributionMethod = AttributionMethod.DIRECT,
        cost_category: CostCategory = CostCategory.INFRASTRUCTURE,
        attribution_accuracy: AttributionAccuracy = AttributionAccuracy.UNKNOWN,
        cost_amount: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AttributionRecord:
        record = AttributionRecord(
            attribution_id=attribution_id,
            attribution_method=attribution_method,
            cost_category=cost_category,
            attribution_accuracy=attribution_accuracy,
            cost_amount=cost_amount,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_attribution_engine.attribution_recorded",
            record_id=record.id,
            attribution_id=attribution_id,
            attribution_method=attribution_method.value,
            cost_category=cost_category.value,
        )
        return record

    def get_attribution(self, record_id: str) -> AttributionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_attributions(
        self,
        method: AttributionMethod | None = None,
        category: CostCategory | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AttributionRecord]:
        results = list(self._records)
        if method is not None:
            results = [r for r in results if r.attribution_method == method]
        if category is not None:
            results = [r for r in results if r.cost_category == category]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_detail(
        self,
        attribution_id: str,
        attribution_method: AttributionMethod = AttributionMethod.DIRECT,
        detail_amount: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AttributionDetail:
        detail = AttributionDetail(
            attribution_id=attribution_id,
            attribution_method=attribution_method,
            detail_amount=detail_amount,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._details.append(detail)
        if len(self._details) > self._max_records:
            self._details = self._details[-self._max_records :]
        logger.info(
            "cost_attribution_engine.detail_added",
            attribution_id=attribution_id,
            attribution_method=attribution_method.value,
            detail_amount=detail_amount,
        )
        return detail

    # -- domain operations --------------------------------------------------

    def analyze_attribution_distribution(self) -> dict[str, Any]:
        """Group by attribution method; return count and avg cost amount."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.attribution_method.value
            method_data.setdefault(key, []).append(r.cost_amount)
        result: dict[str, Any] = {}
        for method, amounts in method_data.items():
            result[method] = {
                "count": len(amounts),
                "avg_cost_amount": round(sum(amounts) / len(amounts), 2),
            }
        return result

    def identify_disputed_attributions(self) -> list[dict[str, Any]]:
        """Return records where accuracy is APPROXIMATE or UNKNOWN."""
        disputed_set = {AttributionAccuracy.APPROXIMATE, AttributionAccuracy.UNKNOWN}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.attribution_accuracy in disputed_set:
                results.append(
                    {
                        "record_id": r.id,
                        "attribution_id": r.attribution_id,
                        "attribution_method": r.attribution_method.value,
                        "attribution_accuracy": r.attribution_accuracy.value,
                        "cost_amount": r.cost_amount,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_cost_amount(self) -> list[dict[str, Any]]:
        """Group by service, total cost, sort descending."""
        svc_costs: dict[str, float] = {}
        for r in self._records:
            svc_costs[r.service] = svc_costs.get(r.service, 0.0) + r.cost_amount
        results: list[dict[str, Any]] = []
        for service, total_cost in svc_costs.items():
            results.append(
                {
                    "service": service,
                    "total_cost": round(total_cost, 2),
                }
            )
        results.sort(key=lambda x: x["total_cost"], reverse=True)
        return results

    def detect_attribution_trends(self) -> dict[str, Any]:
        """Split-half comparison on detail_amount; delta threshold 5.0."""
        if len(self._details) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [d.detail_amount for d in self._details]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> CostAttributionReport:
        by_method: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_accuracy: dict[str, int] = {}
        for r in self._records:
            by_method[r.attribution_method.value] = by_method.get(r.attribution_method.value, 0) + 1
            by_category[r.cost_category.value] = by_category.get(r.cost_category.value, 0) + 1
            by_accuracy[r.attribution_accuracy.value] = (
                by_accuracy.get(r.attribution_accuracy.value, 0) + 1
            )
        disputed = self.identify_disputed_attributions()
        disputed_count = len(disputed)
        avg_cost = (
            round(sum(r.cost_amount for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_cost_amount()
        top_attributed = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if disputed_count > 0:
            recs.append(f"{disputed_count} disputed attribution(s) detected — review accuracy")
        disputed_pct = round(disputed_count / len(self._records) * 100, 2) if self._records else 0.0
        if disputed_pct > self._max_disputed_pct:
            recs.append(
                f"Disputed attribution rate {disputed_pct}% exceeds "
                f"threshold ({self._max_disputed_pct}%)"
            )
        if not recs:
            recs.append("Cost attribution levels are healthy")
        return CostAttributionReport(
            total_records=len(self._records),
            total_details=len(self._details),
            disputed_attributions=disputed_count,
            avg_cost_amount=avg_cost,
            by_method=by_method,
            by_category=by_category,
            by_accuracy=by_accuracy,
            top_attributed=top_attributed,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._details.clear()
        logger.info("cost_attribution_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            key = r.attribution_method.value
            method_dist[key] = method_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_details": len(self._details),
            "max_disputed_pct": self._max_disputed_pct,
            "method_distribution": method_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
