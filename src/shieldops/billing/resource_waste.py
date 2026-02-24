"""Resource Waste Detector — idle, underutilized, and orphaned resources."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WasteCategory(StrEnum):
    IDLE = "idle"
    UNDERUTILIZED = "underutilized"
    ORPHANED = "orphaned"
    OVERSIZED = "oversized"
    UNATTACHED = "unattached"


class ResourceType(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    DATABASE = "database"
    NETWORK = "network"
    CONTAINER = "container"


class WasteSeverity(StrEnum):
    NEGLIGIBLE = "negligible"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class WasteRecord(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    resource_id: str = ""
    resource_type: ResourceType = ResourceType.COMPUTE
    waste_category: WasteCategory = WasteCategory.IDLE
    severity: WasteSeverity = WasteSeverity.LOW
    utilization_pct: float = 0.0
    estimated_monthly_waste: float = 0.0
    service_name: str = ""
    region: str = ""
    last_active: float = 0.0
    created_at: float = Field(default_factory=time.time)


class WasteSummary(BaseModel):
    resource_type: ResourceType = ResourceType.COMPUTE
    waste_category: WasteCategory = WasteCategory.IDLE
    total_resources: int = 0
    total_monthly_waste: float = 0.0
    avg_utilization_pct: float = 0.0
    severity: WasteSeverity = WasteSeverity.LOW
    created_at: float = Field(default_factory=time.time)


class WasteReport(BaseModel):
    total_resources_scanned: int = 0
    total_waste_detected: int = 0
    total_monthly_waste: float = 0.0
    by_category: dict[str, int] = Field(
        default_factory=dict,
    )
    by_type: dict[str, int] = Field(
        default_factory=dict,
    )
    by_severity: dict[str, int] = Field(
        default_factory=dict,
    )
    top_wasters: list[dict[str, Any]] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Detector ---


class ResourceWasteDetector:
    """Detect idle, underutilized, and orphaned resources."""

    def __init__(
        self,
        max_records: int = 200000,
        idle_threshold_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._idle_threshold_pct = idle_threshold_pct
        self._items: list[WasteRecord] = []
        self._summaries: dict[str, WasteSummary] = {}
        logger.info(
            "resource_waste.initialized",
            max_records=max_records,
            idle_threshold_pct=idle_threshold_pct,
        )

    # -- record --

    def record_waste(
        self,
        resource_id: str,
        resource_type: ResourceType = ResourceType.COMPUTE,
        waste_category: WasteCategory = WasteCategory.IDLE,
        utilization_pct: float = 0.0,
        estimated_monthly_waste: float = 0.0,
        service_name: str = "",
        region: str = "",
        last_active: float = 0.0,
        **kw: Any,
    ) -> WasteRecord:
        """Record a waste detection."""
        severity = self._compute_severity(
            estimated_monthly_waste,
            utilization_pct,
        )
        record = WasteRecord(
            resource_id=resource_id,
            resource_type=resource_type,
            waste_category=waste_category,
            severity=severity,
            utilization_pct=utilization_pct,
            estimated_monthly_waste=estimated_monthly_waste,
            service_name=service_name,
            region=region,
            last_active=last_active,
            **kw,
        )
        self._items.append(record)
        if len(self._items) > self._max_records:
            self._items = self._items[-self._max_records :]
        logger.info(
            "resource_waste.recorded",
            record_id=record.id,
            resource_id=resource_id,
            severity=severity,
        )
        return record

    # -- get / list --

    def get_waste(
        self,
        record_id: str,
    ) -> WasteRecord | None:
        """Get a single waste record by ID."""
        for item in self._items:
            if item.id == record_id:
                return item
        return None

    def list_waste(
        self,
        resource_type: ResourceType | None = None,
        waste_category: WasteCategory | None = None,
        limit: int = 50,
    ) -> list[WasteRecord]:
        """List waste records with optional filters."""
        results = list(self._items)
        if resource_type is not None:
            results = [r for r in results if r.resource_type == resource_type]
        if waste_category is not None:
            results = [r for r in results if r.waste_category == waste_category]
        return results[-limit:]

    # -- domain operations --

    def calculate_total_waste(self) -> float:
        """Calculate total estimated monthly waste."""
        total = sum(r.estimated_monthly_waste for r in self._items)
        return round(total, 2)

    def rank_by_waste_cost(
        self,
        limit: int = 20,
    ) -> list[WasteRecord]:
        """Rank resources by waste cost descending."""
        sorted_items = sorted(
            self._items,
            key=lambda r: r.estimated_monthly_waste,
            reverse=True,
        )
        return sorted_items[:limit]

    def detect_idle_resources(
        self,
        threshold_pct: float = 5.0,
    ) -> list[WasteRecord]:
        """Detect resources below utilization threshold."""
        return [r for r in self._items if r.utilization_pct <= threshold_pct]

    def identify_orphaned_resources(
        self,
    ) -> list[WasteRecord]:
        """Identify orphaned resources."""
        return [r for r in self._items if r.waste_category == WasteCategory.ORPHANED]

    def estimate_savings_potential(
        self,
    ) -> dict[str, Any]:
        """Estimate potential monthly savings."""
        total_waste = self.calculate_total_waste()
        by_category: dict[str, float] = {}
        for r in self._items:
            key = r.waste_category.value
            by_category[key] = by_category.get(key, 0.0) + r.estimated_monthly_waste
        by_type: dict[str, float] = {}
        for r in self._items:
            key = r.resource_type.value
            by_type[key] = by_type.get(key, 0.0) + r.estimated_monthly_waste
        return {
            "total_monthly_savings": round(total_waste, 2),
            "annual_savings": round(total_waste * 12, 2),
            "by_category": {k: round(v, 2) for k, v in by_category.items()},
            "by_type": {k: round(v, 2) for k, v in by_type.items()},
        }

    # -- report --

    def generate_waste_report(self) -> WasteReport:
        """Generate a comprehensive waste report."""
        total_waste = self.calculate_total_waste()
        by_category: dict[str, int] = {}
        for r in self._items:
            key = r.waste_category.value
            by_category[key] = by_category.get(key, 0) + 1
        by_type: dict[str, int] = {}
        for r in self._items:
            key = r.resource_type.value
            by_type[key] = by_type.get(key, 0) + 1
        by_severity: dict[str, int] = {}
        for r in self._items:
            key = r.severity.value
            by_severity[key] = by_severity.get(key, 0) + 1
        top = self.rank_by_waste_cost(limit=5)
        top_wasters = [
            {
                "resource_id": r.resource_id,
                "monthly_waste": r.estimated_monthly_waste,
                "type": r.resource_type.value,
                "category": r.waste_category.value,
            }
            for r in top
        ]
        recs = self._build_recommendations(
            total_waste,
            by_category,
        )
        return WasteReport(
            total_resources_scanned=len(self._items),
            total_waste_detected=len(self._items),
            total_monthly_waste=total_waste,
            by_category=by_category,
            by_type=by_type,
            by_severity=by_severity,
            top_wasters=top_wasters,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all records. Returns count cleared."""
        count = len(self._items)
        self._items.clear()
        self._summaries.clear()
        logger.info(
            "resource_waste.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        cat_dist: dict[str, int] = {}
        for r in self._items:
            key = r.waste_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        type_dist: dict[str, int] = {}
        for r in self._items:
            key = r.resource_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._items),
            "total_monthly_waste": self.calculate_total_waste(),
            "idle_threshold_pct": self._idle_threshold_pct,
            "category_distribution": cat_dist,
            "type_distribution": type_dist,
        }

    # -- internal helpers --

    def _compute_severity(
        self,
        monthly_waste: float,
        utilization_pct: float,
    ) -> WasteSeverity:
        if monthly_waste >= 10000:
            return WasteSeverity.CRITICAL
        if monthly_waste >= 5000:
            return WasteSeverity.HIGH
        if monthly_waste >= 1000:
            return WasteSeverity.MODERATE
        if monthly_waste >= 100:
            return WasteSeverity.LOW
        return WasteSeverity.NEGLIGIBLE

    def _build_recommendations(
        self,
        total_waste: float,
        by_category: dict[str, int],
    ) -> list[str]:
        recs: list[str] = []
        if total_waste > 10000:
            recs.append(f"${total_waste:,.2f}/mo total waste - prioritize cleanup")
        idle_count = by_category.get("idle", 0)
        if idle_count > 0:
            recs.append(f"{idle_count} idle resource(s) - consider termination")
        orphan_count = by_category.get("orphaned", 0)
        if orphan_count > 0:
            recs.append(f"{orphan_count} orphaned resource(s) - verify ownership")
        if not recs:
            recs.append("Resource waste within acceptable limits")
        return recs
