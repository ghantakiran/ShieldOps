"""Capacity Right-Sizer — resource utilization analysis, instance recommendations, savings."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResourceType(StrEnum):
    COMPUTE = "compute"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    GPU = "gpu"
    DATABASE = "database"


class SizingAction(StrEnum):
    DOWNSIZE = "downsize"
    UPSIZE = "upsize"
    MAINTAIN = "maintain"
    TERMINATE = "terminate"
    RESERVE = "reserve"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class UtilizationSample(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str
    resource_type: ResourceType
    utilization_pct: float = 0.0
    instance_type: str = ""
    cost_per_hour: float = 0.0
    region: str = ""
    created_at: float = Field(default_factory=time.time)


class SizingRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str
    resource_type: ResourceType
    current_instance: str = ""
    recommended_instance: str = ""
    action: SizingAction
    confidence: ConfidenceLevel
    estimated_monthly_savings: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class RightSizingSummary(BaseModel):
    total_resources_analyzed: int = 0
    downsize_count: int = 0
    upsize_count: int = 0
    terminate_count: int = 0
    maintain_count: int = 0
    total_estimated_monthly_savings: float = 0.0
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityRightSizer:
    """Resource utilization analysis, instance type recommendations, and savings estimation."""

    def __init__(
        self,
        max_samples: int = 500000,
        underutil_threshold: float = 0.3,
    ) -> None:
        self._max_samples = max_samples
        self._underutil_threshold = underutil_threshold
        self._samples: list[UtilizationSample] = []
        self._recommendations: list[SizingRecommendation] = []
        logger.info(
            "right_sizer.initialized",
            max_samples=max_samples,
            underutil_threshold=underutil_threshold,
        )

    def record_utilization(
        self,
        resource_id: str,
        resource_type: ResourceType,
        utilization_pct: float,
        instance_type: str = "",
        cost_per_hour: float = 0.0,
        region: str = "",
    ) -> UtilizationSample:
        sample = UtilizationSample(
            resource_id=resource_id,
            resource_type=resource_type,
            utilization_pct=utilization_pct,
            instance_type=instance_type,
            cost_per_hour=cost_per_hour,
            region=region,
        )
        self._samples.append(sample)
        if len(self._samples) > self._max_samples:
            self._samples = self._samples[-self._max_samples :]
        logger.info(
            "right_sizer.utilization_recorded",
            sample_id=sample.id,
            resource_id=resource_id,
            utilization_pct=utilization_pct,
        )
        return sample

    def get_sample(self, sample_id: str) -> UtilizationSample | None:
        for s in self._samples:
            if s.id == sample_id:
                return s
        return None

    def list_samples(
        self,
        resource_id: str | None = None,
        resource_type: ResourceType | None = None,
        limit: int = 100,
    ) -> list[UtilizationSample]:
        results = self._samples
        if resource_id is not None:
            results = [s for s in results if s.resource_id == resource_id]
        if resource_type is not None:
            results = [s for s in results if s.resource_type == resource_type]
        return results[-limit:]

    def generate_recommendations(self) -> list[SizingRecommendation]:
        resource_samples: dict[str, list[UtilizationSample]] = {}
        for s in self._samples:
            resource_samples.setdefault(s.resource_id, []).append(s)

        new_recs: list[SizingRecommendation] = []
        for resource_id, samples in resource_samples.items():
            avg_util = sum(s.utilization_pct for s in samples) / len(samples)
            sample_count = len(samples)

            # Determine action
            if avg_util < 0.05:
                action = SizingAction.TERMINATE
                reason = f"Near-zero utilization ({avg_util:.1%}), candidate for termination"
            elif avg_util < self._underutil_threshold:
                action = SizingAction.DOWNSIZE
                reason = (
                    f"Underutilized ({avg_util:.1%}), "
                    f"below {self._underutil_threshold:.0%} threshold"
                )
            elif avg_util > 0.85:
                action = SizingAction.UPSIZE
                reason = f"High utilization ({avg_util:.1%}), risk of saturation"
            else:
                action = SizingAction.MAINTAIN
                reason = f"Utilization within normal range ({avg_util:.1%})"

            # Determine confidence
            if sample_count >= 30:
                confidence = ConfidenceLevel.HIGH
            elif sample_count >= 10:
                confidence = ConfidenceLevel.MEDIUM
            elif sample_count >= 3:
                confidence = ConfidenceLevel.LOW
            else:
                confidence = ConfidenceLevel.INSUFFICIENT_DATA

            # Estimate savings
            estimated_monthly_savings = 0.0
            if action == SizingAction.DOWNSIZE:
                avg_cost = sum(s.cost_per_hour for s in samples) / len(samples)
                estimated_monthly_savings = round(avg_cost * 730 * (1 - avg_util), 2)

            latest = samples[-1]
            rec = SizingRecommendation(
                resource_id=resource_id,
                resource_type=latest.resource_type,
                current_instance=latest.instance_type,
                action=action,
                confidence=confidence,
                estimated_monthly_savings=estimated_monthly_savings,
                reason=reason,
            )
            new_recs.append(rec)
            self._recommendations.append(rec)

        logger.info(
            "right_sizer.recommendations_generated",
            count=len(new_recs),
        )
        return new_recs

    def get_recommendation(self, rec_id: str) -> SizingRecommendation | None:
        for r in self._recommendations:
            if r.id == rec_id:
                return r
        return None

    def list_recommendations(
        self,
        action: SizingAction | None = None,
        limit: int = 100,
    ) -> list[SizingRecommendation]:
        results = self._recommendations
        if action is not None:
            results = [r for r in results if r.action == action]
        return results[-limit:]

    def estimate_savings(self) -> dict[str, Any]:
        total = 0.0
        by_action: dict[str, float] = {}
        by_resource_type: dict[str, float] = {}
        for r in self._recommendations:
            total += r.estimated_monthly_savings
            by_action[r.action] = by_action.get(r.action, 0.0) + r.estimated_monthly_savings
            by_resource_type[r.resource_type] = (
                by_resource_type.get(r.resource_type, 0.0) + r.estimated_monthly_savings
            )
        return {
            "total_monthly_savings": round(total, 2),
            "by_action": {k: round(v, 2) for k, v in by_action.items()},
            "by_resource_type": {k: round(v, 2) for k, v in by_resource_type.items()},
        }

    def analyze_utilization_trends(self, resource_id: str) -> dict[str, Any]:
        samples = [s for s in self._samples if s.resource_id == resource_id]
        if not samples:
            return {
                "resource_id": resource_id,
                "sample_count": 0,
                "samples": [],
                "avg_utilization": 0.0,
                "min_utilization": 0.0,
                "max_utilization": 0.0,
            }
        sorted_samples = sorted(samples, key=lambda s: s.created_at)
        utils = [s.utilization_pct for s in sorted_samples]
        return {
            "resource_id": resource_id,
            "sample_count": len(sorted_samples),
            "samples": [s.model_dump() for s in sorted_samples],
            "avg_utilization": round(sum(utils) / len(utils), 4),
            "min_utilization": round(min(utils), 4),
            "max_utilization": round(max(utils), 4),
        }

    def generate_summary(self) -> RightSizingSummary:
        resource_ids = {s.resource_id for s in self._samples}
        downsize = [r for r in self._recommendations if r.action == SizingAction.DOWNSIZE]
        upsize = [r for r in self._recommendations if r.action == SizingAction.UPSIZE]
        terminate = [r for r in self._recommendations if r.action == SizingAction.TERMINATE]
        maintain = [r for r in self._recommendations if r.action == SizingAction.MAINTAIN]
        total_savings = sum(r.estimated_monthly_savings for r in self._recommendations)
        return RightSizingSummary(
            total_resources_analyzed=len(resource_ids),
            downsize_count=len(downsize),
            upsize_count=len(upsize),
            terminate_count=len(terminate),
            maintain_count=len(maintain),
            total_estimated_monthly_savings=round(total_savings, 2),
            recommendations=[r.model_dump() for r in self._recommendations],
        )

    def clear_data(self) -> None:
        self._samples.clear()
        self._recommendations.clear()
        logger.info("right_sizer.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        resource_ids = {s.resource_id for s in self._samples}
        action_counts: dict[str, int] = {}
        for r in self._recommendations:
            action_counts[r.action] = action_counts.get(r.action, 0) + 1
        return {
            "total_samples": len(self._samples),
            "total_recommendations": len(self._recommendations),
            "unique_resources": len(resource_ids),
            "action_distribution": action_counts,
            "max_samples": self._max_samples,
            "underutil_threshold": self._underutil_threshold,
        }
