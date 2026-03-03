"""Storage Lifecycle Enforcer — enforce storage lifecycle policies to reduce costs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class StorageTier(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COOL = "cool"
    COLD = "cold"
    ARCHIVE = "archive"


class LifecycleAction(StrEnum):
    TRANSITION = "transition"
    DELETE = "delete"
    COMPRESS = "compress"
    REPLICATE = "replicate"
    TAG = "tag"


class EnforcementMode(StrEnum):
    STRICT = "strict"
    ADVISORY = "advisory"
    DRY_RUN = "dry_run"
    GRADUAL = "gradual"
    CUSTOM = "custom"


# --- Models ---


class LifecyclePolicyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    storage_tier: StorageTier = StorageTier.HOT
    lifecycle_action: LifecycleAction = LifecycleAction.TRANSITION
    enforcement_mode: EnforcementMode = EnforcementMode.ADVISORY
    data_size_gb: float = 0.0
    cost_before: float = 0.0
    cost_after: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class LifecycleAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    storage_tier: StorageTier = StorageTier.HOT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class StorageLifecycleReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    enforced_count: int = 0
    avg_cost_reduction: float = 0.0
    by_storage_tier: dict[str, int] = Field(default_factory=dict)
    by_lifecycle_action: dict[str, int] = Field(default_factory=dict)
    by_enforcement_mode: dict[str, int] = Field(default_factory=dict)
    top_transitions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class StorageLifecycleEnforcer:
    """Enforce storage lifecycle policies to transition or delete cold data."""

    def __init__(
        self,
        max_records: int = 200000,
        cost_reduction_threshold: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._cost_reduction_threshold = cost_reduction_threshold
        self._records: list[LifecyclePolicyRecord] = []
        self._analyses: list[LifecycleAnalysis] = []
        logger.info(
            "storage_lifecycle_enforcer.initialized",
            max_records=max_records,
            cost_reduction_threshold=cost_reduction_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_lifecycle_policy(
        self,
        storage_tier: StorageTier = StorageTier.HOT,
        lifecycle_action: LifecycleAction = LifecycleAction.TRANSITION,
        enforcement_mode: EnforcementMode = EnforcementMode.ADVISORY,
        data_size_gb: float = 0.0,
        cost_before: float = 0.0,
        cost_after: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> LifecyclePolicyRecord:
        record = LifecyclePolicyRecord(
            storage_tier=storage_tier,
            lifecycle_action=lifecycle_action,
            enforcement_mode=enforcement_mode,
            data_size_gb=data_size_gb,
            cost_before=cost_before,
            cost_after=cost_after,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "storage_lifecycle_enforcer.policy_recorded",
            record_id=record.id,
            storage_tier=storage_tier.value,
            lifecycle_action=lifecycle_action.value,
        )
        return record

    def get_lifecycle_policy(self, record_id: str) -> LifecyclePolicyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_lifecycle_policies(
        self,
        storage_tier: StorageTier | None = None,
        lifecycle_action: LifecycleAction | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[LifecyclePolicyRecord]:
        results = list(self._records)
        if storage_tier is not None:
            results = [r for r in results if r.storage_tier == storage_tier]
        if lifecycle_action is not None:
            results = [r for r in results if r.lifecycle_action == lifecycle_action]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        storage_tier: StorageTier = StorageTier.HOT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> LifecycleAnalysis:
        analysis = LifecycleAnalysis(
            storage_tier=storage_tier,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "storage_lifecycle_enforcer.analysis_added",
            storage_tier=storage_tier.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_tier_distribution(self) -> dict[str, Any]:
        """Group by storage_tier; return count and avg cost reduction."""
        tier_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.storage_tier.value
            reduction = r.cost_before - r.cost_after
            tier_data.setdefault(key, []).append(reduction)
        result: dict[str, Any] = {}
        for tier, reductions in tier_data.items():
            result[tier] = {
                "count": len(reductions),
                "avg_cost_reduction": round(sum(reductions) / len(reductions), 2),
            }
        return result

    def identify_high_reduction_policies(self) -> list[dict[str, Any]]:
        """Return records where cost reduction >= cost_reduction_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            reduction = r.cost_before - r.cost_after
            if reduction >= self._cost_reduction_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "storage_tier": r.storage_tier.value,
                        "lifecycle_action": r.lifecycle_action.value,
                        "cost_reduction": round(reduction, 2),
                        "data_size_gb": r.data_size_gb,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["cost_reduction"], reverse=True)

    def rank_by_cost_reduction(self) -> list[dict[str, Any]]:
        """Group by service, total cost reduction, sort descending."""
        svc_reductions: dict[str, float] = {}
        for r in self._records:
            reduction = r.cost_before - r.cost_after
            svc_reductions[r.service] = svc_reductions.get(r.service, 0.0) + reduction
        results: list[dict[str, Any]] = [
            {"service": svc, "total_cost_reduction": round(red, 2)}
            for svc, red in svc_reductions.items()
        ]
        results.sort(key=lambda x: x["total_cost_reduction"], reverse=True)
        return results

    def detect_lifecycle_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
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

    def generate_report(self) -> StorageLifecycleReport:
        by_tier: dict[str, int] = {}
        by_action: dict[str, int] = {}
        by_mode: dict[str, int] = {}
        for r in self._records:
            by_tier[r.storage_tier.value] = by_tier.get(r.storage_tier.value, 0) + 1
            by_action[r.lifecycle_action.value] = by_action.get(r.lifecycle_action.value, 0) + 1
            by_mode[r.enforcement_mode.value] = by_mode.get(r.enforcement_mode.value, 0) + 1
        enforced_count = sum(
            1 for r in self._records if r.enforcement_mode == EnforcementMode.STRICT
        )
        reductions = [r.cost_before - r.cost_after for r in self._records]
        avg_cost_reduction = round(sum(reductions) / len(reductions), 2) if reductions else 0.0
        top_list = self.identify_high_reduction_policies()
        top_transitions = [o["record_id"] for o in top_list[:5]]
        recs: list[str] = []
        if enforced_count > 0:
            recs.append(f"{enforced_count} lifecycle policies strictly enforced")
        if avg_cost_reduction > 0:
            recs.append(f"Avg cost reduction ${avg_cost_reduction:.2f} per policy")
        if not recs:
            recs.append("Storage lifecycle enforcement is healthy")
        return StorageLifecycleReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            enforced_count=enforced_count,
            avg_cost_reduction=avg_cost_reduction,
            by_storage_tier=by_tier,
            by_lifecycle_action=by_action,
            by_enforcement_mode=by_mode,
            top_transitions=top_transitions,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("storage_lifecycle_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.storage_tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "cost_reduction_threshold": self._cost_reduction_threshold,
            "storage_tier_distribution": tier_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
