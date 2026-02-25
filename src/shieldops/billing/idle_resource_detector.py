"""Idle Resource Detector — detect resources with zero/near-zero utilization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IdleClassification(StrEnum):
    ACTIVE = "active"
    LOW_UTILIZATION = "low_utilization"
    NEAR_IDLE = "near_idle"
    IDLE = "idle"
    ZOMBIE = "zombie"


class ResourceCategory(StrEnum):
    COMPUTE = "compute"
    DATABASE = "database"
    LOAD_BALANCER = "load_balancer"
    CACHE = "cache"
    QUEUE = "queue"


class RecommendedAction(StrEnum):
    KEEP = "keep"
    DOWNSIZE = "downsize"
    HIBERNATE = "hibernate"
    TERMINATE = "terminate"
    REVIEW = "review"


# --- Models ---


class IdleResourceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_name: str = ""
    category: ResourceCategory = ResourceCategory.COMPUTE
    classification: IdleClassification = IdleClassification.ACTIVE
    recommended_action: RecommendedAction = RecommendedAction.REVIEW
    utilization_pct: float = 0.0
    cost_per_hour: float = 0.0
    idle_hours: float = 0.0
    wasted_cost: float = 0.0
    team: str = ""
    last_active_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class IdleSummary(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team: str = ""
    total_resources: int = 0
    idle_count: int = 0
    total_wasted_cost: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class IdleReport(BaseModel):
    total_resources: int = 0
    idle_count: int = 0
    zombie_count: int = 0
    total_wasted_cost: float = 0.0
    by_classification: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_wasters: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Detector ---


class IdleResourceDetector:
    """Detect resources with zero or near-zero utilization."""

    def __init__(
        self,
        max_records: int = 200000,
        idle_threshold_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._idle_threshold_pct = idle_threshold_pct
        self._records: list[IdleResourceRecord] = []
        logger.info(
            "idle_resource_detector.initialized",
            max_records=max_records,
            idle_threshold_pct=idle_threshold_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_resource(
        self,
        resource_id: str,
        resource_name: str,
        category: ResourceCategory = ResourceCategory.COMPUTE,
        utilization_pct: float = 0.0,
        cost_per_hour: float = 0.0,
        idle_hours: float = 0.0,
        team: str = "",
        last_active_at: float = 0.0,
    ) -> IdleResourceRecord:
        """Record a resource and classify its idle status."""
        classification = self.classify_utilization(utilization_pct)
        wasted_cost = (
            round(idle_hours * cost_per_hour, 2)
            if classification != IdleClassification.ACTIVE
            else 0.0
        )
        action = self._determine_action(classification, idle_hours)
        record = IdleResourceRecord(
            resource_id=resource_id,
            resource_name=resource_name,
            category=category,
            classification=classification,
            recommended_action=action,
            utilization_pct=utilization_pct,
            cost_per_hour=cost_per_hour,
            idle_hours=idle_hours,
            wasted_cost=wasted_cost,
            team=team,
            last_active_at=last_active_at,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "idle_resource_detector.resource_recorded",
            record_id=record.id,
            resource_id=resource_id,
            classification=classification.value,
            wasted_cost=wasted_cost,
        )
        return record

    def get_resource(self, record_id: str) -> IdleResourceRecord | None:
        """Get a single resource record by ID."""
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_resources(
        self,
        category: ResourceCategory | None = None,
        classification: IdleClassification | None = None,
        limit: int = 50,
    ) -> list[IdleResourceRecord]:
        """List resource records with optional filters."""
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.category == category]
        if classification is not None:
            results = [r for r in results if r.classification == classification]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def classify_utilization(
        self,
        utilization_pct: float,
    ) -> IdleClassification:
        """Classify a resource based on its utilization percentage."""
        if utilization_pct >= 50.0:
            return IdleClassification.ACTIVE
        if utilization_pct >= 20.0:
            return IdleClassification.LOW_UTILIZATION
        if utilization_pct >= self._idle_threshold_pct:
            return IdleClassification.NEAR_IDLE
        if utilization_pct > 0:
            return IdleClassification.IDLE
        return IdleClassification.ZOMBIE

    def recommend_action(self, record_id: str) -> dict[str, Any]:
        """Determine recommended action for a specific resource."""
        rec = self.get_resource(record_id)
        if rec is None:
            return {"record_id": record_id, "error": "Record not found"}
        action = self._determine_action(rec.classification, rec.idle_hours)
        rec.recommended_action = action
        logger.info(
            "idle_resource_detector.action_recommended",
            record_id=record_id,
            action=action.value,
        )
        return {
            "record_id": record_id,
            "resource_id": rec.resource_id,
            "resource_name": rec.resource_name,
            "classification": rec.classification.value,
            "recommended_action": action.value,
            "wasted_cost": rec.wasted_cost,
            "idle_hours": rec.idle_hours,
        }

    def calculate_wasted_cost(self) -> dict[str, Any]:
        """Calculate total wasted cost across all idle resources."""
        total = 0.0
        by_category: dict[str, float] = {}
        by_classification: dict[str, float] = {}
        for r in self._records:
            total += r.wasted_cost
            by_category[r.category.value] = round(
                by_category.get(r.category.value, 0.0) + r.wasted_cost,
                2,
            )
            by_classification[r.classification.value] = round(
                by_classification.get(r.classification.value, 0.0) + r.wasted_cost,
                2,
            )
        return {
            "total_wasted_cost": round(total, 2),
            "annual_projected_waste": round(total * 12, 2),
            "by_category": by_category,
            "by_classification": by_classification,
        }

    def summarize_by_team(self) -> list[IdleSummary]:
        """Group resources by team and summarize."""
        team_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            team = r.team or "unassigned"
            if team not in team_data:
                team_data[team] = {
                    "total": 0,
                    "idle": 0,
                    "wasted": 0.0,
                    "by_category": {},
                    "by_action": {},
                }
            entry = team_data[team]
            entry["total"] += 1
            if r.classification not in (
                IdleClassification.ACTIVE,
                IdleClassification.LOW_UTILIZATION,
            ):
                entry["idle"] += 1
            entry["wasted"] += r.wasted_cost
            cat_key = r.category.value
            entry["by_category"][cat_key] = entry["by_category"].get(cat_key, 0) + 1
            act_key = r.recommended_action.value
            entry["by_action"][act_key] = entry["by_action"].get(act_key, 0) + 1

        summaries: list[IdleSummary] = []
        for team, data in sorted(team_data.items()):
            summary = IdleSummary(
                team=team,
                total_resources=data["total"],
                idle_count=data["idle"],
                total_wasted_cost=round(data["wasted"], 2),
                by_category=data["by_category"],
                by_action=data["by_action"],
            )
            summaries.append(summary)
        logger.info(
            "idle_resource_detector.team_summary",
            team_count=len(summaries),
        )
        return summaries

    def rank_by_waste(self) -> list[dict[str, Any]]:
        """Rank resources by wasted_cost descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.wasted_cost > 0:
                results.append(
                    {
                        "record_id": r.id,
                        "resource_id": r.resource_id,
                        "resource_name": r.resource_name,
                        "category": r.category.value,
                        "classification": r.classification.value,
                        "wasted_cost": r.wasted_cost,
                        "idle_hours": r.idle_hours,
                        "recommended_action": r.recommended_action.value,
                    }
                )
        results.sort(key=lambda x: x["wasted_cost"], reverse=True)
        return results

    # -- report / stats ----------------------------------------------

    def generate_idle_report(self) -> IdleReport:
        """Generate a comprehensive idle resource report."""
        by_classification: dict[str, int] = {}
        by_category: dict[str, int] = {}
        total_waste = 0.0
        idle_count = 0
        zombie_count = 0
        for r in self._records:
            by_classification[r.classification.value] = (
                by_classification.get(r.classification.value, 0) + 1
            )
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            total_waste += r.wasted_cost
            if r.classification in (
                IdleClassification.IDLE,
                IdleClassification.ZOMBIE,
                IdleClassification.NEAR_IDLE,
            ):
                idle_count += 1
            if r.classification == IdleClassification.ZOMBIE:
                zombie_count += 1
        ranked = self.rank_by_waste()
        top_wasters = [w["resource_name"] for w in ranked[:5]]
        recs = self._build_recommendations(
            idle_count,
            zombie_count,
            total_waste,
        )
        return IdleReport(
            total_resources=len(self._records),
            idle_count=idle_count,
            zombie_count=zombie_count,
            total_wasted_cost=round(total_waste, 2),
            by_classification=by_classification,
            by_category=by_category,
            top_wasters=top_wasters,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all stored records."""
        self._records.clear()
        logger.info("idle_resource_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        class_dist: dict[str, int] = {}
        for r in self._records:
            key = r.classification.value
            class_dist[key] = class_dist.get(key, 0) + 1
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "idle_threshold_pct": self._idle_threshold_pct,
            "classification_distribution": class_dist,
            "category_distribution": cat_dist,
            "total_wasted_cost": round(
                sum(r.wasted_cost for r in self._records),
                2,
            ),
        }

    # -- internal helpers --------------------------------------------

    def _determine_action(
        self,
        classification: IdleClassification,
        idle_hours: float,
    ) -> RecommendedAction:
        """Determine recommended action based on classification and idle hours."""
        if classification == IdleClassification.ACTIVE:
            return RecommendedAction.KEEP
        if classification == IdleClassification.LOW_UTILIZATION:
            return RecommendedAction.DOWNSIZE
        if classification == IdleClassification.NEAR_IDLE:
            return RecommendedAction.HIBERNATE
        if classification == IdleClassification.IDLE:
            return RecommendedAction.TERMINATE if idle_hours > 168 else RecommendedAction.REVIEW
        if classification == IdleClassification.ZOMBIE:
            return RecommendedAction.TERMINATE
        return RecommendedAction.REVIEW

    def _build_recommendations(
        self,
        idle_count: int,
        zombie_count: int,
        total_waste: float,
    ) -> list[str]:
        """Build recommendations from idle resource analysis."""
        recs: list[str] = []
        if zombie_count > 0:
            recs.append(
                f"{zombie_count} zombie resource(s) with zero utilization — terminate immediately"
            )
        if idle_count > 0:
            recs.append(
                f"{idle_count} idle/near-idle resource(s) — review for termination or hibernation"
            )
        if total_waste > 1000:
            recs.append(f"${total_waste:,.2f} total wasted cost — prioritize cleanup")
        if not recs:
            recs.append("Resource utilization is within acceptable bounds")
        return recs
