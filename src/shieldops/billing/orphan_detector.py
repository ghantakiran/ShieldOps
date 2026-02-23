"""Orphaned Resource Detector — detect unattached volumes, unused IPs, idle LBs, stale snapshots."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class OrphanCategory(StrEnum):
    UNATTACHED_VOLUME = "unattached_volume"
    UNUSED_IP = "unused_ip"
    IDLE_LOAD_BALANCER = "idle_load_balancer"
    DANGLING_DNS = "dangling_dns"
    STALE_SNAPSHOT = "stale_snapshot"


class OrphanAction(StrEnum):
    DETECTED = "detected"
    FLAGGED = "flagged"
    CLEANUP_SCHEDULED = "cleanup_scheduled"
    CLEANED = "cleaned"
    EXEMPTED = "exempted"


class CleanupRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class OrphanedResource(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str
    resource_type: str = ""
    category: OrphanCategory = OrphanCategory.UNATTACHED_VOLUME
    action: OrphanAction = OrphanAction.DETECTED
    risk: CleanupRisk = CleanupRisk.LOW
    provider: str = ""
    region: str = ""
    monthly_cost: float = 0.0
    detected_at: float = Field(default_factory=time.time)
    last_used_at: float | None = None


class CleanupJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    orphan_id: str
    scheduled_at: float = Field(default_factory=time.time)
    executed_at: float | None = None
    success: bool = False
    notes: str = ""


class OrphanSummary(BaseModel):
    total_orphans: int = 0
    total_monthly_waste: float = 0.0
    category_distribution: dict[str, int] = Field(default_factory=dict)
    action_distribution: dict[str, int] = Field(default_factory=dict)
    risk_distribution: dict[str, int] = Field(default_factory=dict)


# --- Engine ---


class OrphanedResourceDetector:
    """Detects unattached volumes, unused IPs, idle LBs, stale snapshots; schedules cleanup."""

    def __init__(
        self,
        max_resources: int = 50000,
        stale_days: int = 30,
    ) -> None:
        self._max_resources = max_resources
        self._stale_days = stale_days
        self._orphans: dict[str, OrphanedResource] = {}
        self._cleanups: dict[str, CleanupJob] = {}
        logger.info(
            "orphan_detector.initialized",
            max_resources=max_resources,
            stale_days=stale_days,
        )

    def report_orphan(
        self,
        resource_id: str,
        category: OrphanCategory = OrphanCategory.UNATTACHED_VOLUME,
        **kw: Any,
    ) -> OrphanedResource:
        orphan = OrphanedResource(resource_id=resource_id, category=category, **kw)
        self._orphans[orphan.id] = orphan
        if len(self._orphans) > self._max_resources:
            oldest = next(iter(self._orphans))
            del self._orphans[oldest]
        logger.info(
            "orphan_detector.orphan_reported",
            orphan_id=orphan.id,
            resource_id=resource_id,
            category=category,
        )
        return orphan

    def get_orphan(self, orphan_id: str) -> OrphanedResource | None:
        return self._orphans.get(orphan_id)

    def list_orphans(
        self,
        category: OrphanCategory | None = None,
        action: OrphanAction | None = None,
        provider: str | None = None,
    ) -> list[OrphanedResource]:
        results = list(self._orphans.values())
        if category is not None:
            results = [o for o in results if o.category == category]
        if action is not None:
            results = [o for o in results if o.action == action]
        if provider is not None:
            results = [o for o in results if o.provider == provider]
        return results

    def flag_for_cleanup(self, orphan_id: str) -> OrphanedResource | None:
        orphan = self._orphans.get(orphan_id)
        if orphan is None:
            return None
        orphan.action = OrphanAction.FLAGGED
        logger.info("orphan_detector.flagged", orphan_id=orphan_id)
        return orphan

    def exempt_resource(self, orphan_id: str) -> OrphanedResource | None:
        orphan = self._orphans.get(orphan_id)
        if orphan is None:
            return None
        orphan.action = OrphanAction.EXEMPTED
        logger.info("orphan_detector.exempted", orphan_id=orphan_id)
        return orphan

    def schedule_cleanup(self, orphan_id: str) -> CleanupJob | None:
        orphan = self._orphans.get(orphan_id)
        if orphan is None:
            return None
        orphan.action = OrphanAction.CLEANUP_SCHEDULED
        job = CleanupJob(orphan_id=orphan_id)
        self._cleanups[job.id] = job
        logger.info("orphan_detector.cleanup_scheduled", job_id=job.id, orphan_id=orphan_id)
        return job

    def execute_cleanup(
        self,
        job_id: str,
        success: bool = True,
        notes: str = "",
    ) -> CleanupJob | None:
        job = self._cleanups.get(job_id)
        if job is None:
            return None
        job.executed_at = time.time()
        job.success = success
        job.notes = notes
        orphan = self._orphans.get(job.orphan_id)
        if orphan is not None and success:
            orphan.action = OrphanAction.CLEANED
        logger.info("orphan_detector.cleanup_executed", job_id=job_id, success=success)
        return job

    def get_monthly_waste(self) -> dict[str, Any]:
        active = [
            o
            for o in self._orphans.values()
            if o.action not in (OrphanAction.CLEANED, OrphanAction.EXEMPTED)
        ]
        total = sum(o.monthly_cost for o in active)
        by_category: dict[str, float] = {}
        for o in active:
            by_category[o.category] = by_category.get(o.category, 0.0) + o.monthly_cost
        return {
            "total_monthly_waste": round(total, 2),
            "by_category": {k: round(v, 2) for k, v in by_category.items()},
            "active_orphan_count": len(active),
        }

    def get_summary(self) -> OrphanSummary:
        cat_dist: dict[str, int] = {}
        act_dist: dict[str, int] = {}
        risk_dist: dict[str, int] = {}
        total_waste = 0.0
        for o in self._orphans.values():
            cat_dist[o.category] = cat_dist.get(o.category, 0) + 1
            act_dist[o.action] = act_dist.get(o.action, 0) + 1
            risk_dist[o.risk] = risk_dist.get(o.risk, 0) + 1
            if o.action not in (OrphanAction.CLEANED, OrphanAction.EXEMPTED):
                total_waste += o.monthly_cost
        return OrphanSummary(
            total_orphans=len(self._orphans),
            total_monthly_waste=round(total_waste, 2),
            category_distribution=cat_dist,
            action_distribution=act_dist,
            risk_distribution=risk_dist,
        )

    def get_stats(self) -> dict[str, Any]:
        summary = self.get_summary()
        return {
            "total_orphans": summary.total_orphans,
            "total_monthly_waste": summary.total_monthly_waste,
            "total_cleanup_jobs": len(self._cleanups),
            "category_distribution": summary.category_distribution,
            "action_distribution": summary.action_distribution,
        }
