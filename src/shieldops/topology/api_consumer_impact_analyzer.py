"""API Consumer Impact Analyzer.

Map consumer dependencies, simulate change impact,
and prioritize consumer notification."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactLevel(StrEnum):
    BREAKING = "breaking"
    DEGRADING = "degrading"
    COSMETIC = "cosmetic"
    NONE = "none"


class ConsumerTier(StrEnum):
    PREMIUM = "premium"
    STANDARD = "standard"
    FREE = "free"
    INTERNAL = "internal"


class ChangeType(StrEnum):
    BREAKING = "breaking"
    DEPRECATION = "deprecation"
    ENHANCEMENT = "enhancement"
    PATCH = "patch"


# --- Models ---


class ConsumerImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str = ""
    consumer_id: str = ""
    impact_level: ImpactLevel = ImpactLevel.NONE
    consumer_tier: ConsumerTier = ConsumerTier.STANDARD
    change_type: ChangeType = ChangeType.PATCH
    affected_endpoints: int = 0
    request_volume: float = 0.0
    notified: bool = False
    created_at: float = Field(default_factory=time.time)


class ConsumerImpactAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str = ""
    consumer_id: str = ""
    is_breaking: bool = False
    impact_score: float = 0.0
    notification_priority: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConsumerImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_affected_endpoints: float = 0.0
    by_impact_level: dict[str, int] = Field(default_factory=dict)
    by_consumer_tier: dict[str, int] = Field(default_factory=dict)
    by_change_type: dict[str, int] = Field(default_factory=dict)
    breaking_consumers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ApiConsumerImpactAnalyzer:
    """Map consumer dependencies, simulate change
    impact, prioritize notifications."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ConsumerImpactRecord] = []
        self._analyses: dict[str, ConsumerImpactAnalysis] = {}
        logger.info(
            "api_consumer_impact_analyzer.init",
            max_records=max_records,
        )

    def record_item(
        self,
        api_name: str = "",
        consumer_id: str = "",
        impact_level: ImpactLevel = ImpactLevel.NONE,
        consumer_tier: ConsumerTier = (ConsumerTier.STANDARD),
        change_type: ChangeType = ChangeType.PATCH,
        affected_endpoints: int = 0,
        request_volume: float = 0.0,
        notified: bool = False,
    ) -> ConsumerImpactRecord:
        record = ConsumerImpactRecord(
            api_name=api_name,
            consumer_id=consumer_id,
            impact_level=impact_level,
            consumer_tier=consumer_tier,
            change_type=change_type,
            affected_endpoints=affected_endpoints,
            request_volume=request_volume,
            notified=notified,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "consumer_impact.record_added",
            record_id=record.id,
            consumer_id=consumer_id,
        )
        return record

    def process(self, key: str) -> ConsumerImpactAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_breaking = rec.impact_level == ImpactLevel.BREAKING
        tier_weight = {
            ConsumerTier.PREMIUM: 4,
            ConsumerTier.STANDARD: 3,
            ConsumerTier.FREE: 2,
            ConsumerTier.INTERNAL: 1,
        }
        priority = tier_weight.get(rec.consumer_tier, 1)
        score = round(
            rec.affected_endpoints * priority * (2.0 if is_breaking else 1.0),
            2,
        )
        analysis = ConsumerImpactAnalysis(
            api_name=rec.api_name,
            consumer_id=rec.consumer_id,
            is_breaking=is_breaking,
            impact_score=score,
            notification_priority=priority,
            description=(f"Consumer {rec.consumer_id} impact {rec.impact_level.value}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ConsumerImpactReport:
        by_il: dict[str, int] = {}
        by_ct: dict[str, int] = {}
        by_ch: dict[str, int] = {}
        eps: list[int] = []
        for r in self._records:
            k = r.impact_level.value
            by_il[k] = by_il.get(k, 0) + 1
            k2 = r.consumer_tier.value
            by_ct[k2] = by_ct.get(k2, 0) + 1
            k3 = r.change_type.value
            by_ch[k3] = by_ch.get(k3, 0) + 1
            eps.append(r.affected_endpoints)
        avg = round(sum(eps) / len(eps), 2) if eps else 0.0
        breaking = list(
            {r.consumer_id for r in self._records if r.impact_level == ImpactLevel.BREAKING}
        )[:10]
        recs: list[str] = []
        if breaking:
            recs.append(f"{len(breaking)} consumers with breaking changes")
        if not recs:
            recs.append("No breaking impacts")
        return ConsumerImpactReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_affected_endpoints=avg,
            by_impact_level=by_il,
            by_consumer_tier=by_ct,
            by_change_type=by_ch,
            breaking_consumers=breaking,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.impact_level.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "impact_level_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("api_consumer_impact_analyzer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def map_consumer_dependencies(
        self,
    ) -> list[dict[str, Any]]:
        """Map consumer dependencies per API."""
        api_consumers: dict[str, set[str]] = {}
        for r in self._records:
            api_consumers.setdefault(r.api_name, set()).add(r.consumer_id)
        results: list[dict[str, Any]] = []
        for api, consumers in api_consumers.items():
            results.append(
                {
                    "api_name": api,
                    "consumer_count": len(consumers),
                    "consumers": sorted(consumers)[:10],
                }
            )
        results.sort(
            key=lambda x: x["consumer_count"],
            reverse=True,
        )
        return results

    def simulate_change_impact(
        self,
    ) -> list[dict[str, Any]]:
        """Simulate impact of changes on consumers."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            k = f"{r.api_name}:{r.consumer_id}"
            if (
                r.impact_level
                in (
                    ImpactLevel.BREAKING,
                    ImpactLevel.DEGRADING,
                )
                and k not in seen
            ):
                seen.add(k)
                results.append(
                    {
                        "api_name": r.api_name,
                        "consumer_id": (r.consumer_id),
                        "impact": (r.impact_level.value),
                        "change_type": (r.change_type.value),
                        "affected_endpoints": (r.affected_endpoints),
                    }
                )
        results.sort(
            key=lambda x: x["affected_endpoints"],
            reverse=True,
        )
        return results

    def prioritize_consumer_notification(
        self,
    ) -> list[dict[str, Any]]:
        """Prioritize consumers for notification."""
        tier_weight = {
            "premium": 4,
            "standard": 3,
            "free": 2,
            "internal": 1,
        }
        consumer_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.consumer_id not in consumer_data:
                consumer_data[r.consumer_id] = {
                    "consumer_id": r.consumer_id,
                    "tier": r.consumer_tier.value,
                    "volume": r.request_volume,
                    "priority": tier_weight.get(r.consumer_tier.value, 1),
                    "notified": r.notified,
                }
        results = list(consumer_data.values())
        results.sort(
            key=lambda x: x["priority"],
            reverse=True,
        )
        return results
