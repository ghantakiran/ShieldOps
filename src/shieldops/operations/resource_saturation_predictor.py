"""Resource Saturation Predictor
compute saturation timeline, detect approaching saturation,
rank resources by saturation urgency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SaturationLevel(StrEnum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    CRITICAL = "critical"


class ResourceCategory(StrEnum):
    COMPUTE = "compute"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"


class PredictionConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


# --- Models ---


class ResourceSaturationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    saturation_level: SaturationLevel = SaturationLevel.SAFE
    resource_category: ResourceCategory = ResourceCategory.COMPUTE
    prediction_confidence: PredictionConfidence = PredictionConfidence.MEDIUM
    current_usage_pct: float = 0.0
    predicted_usage_pct: float = 0.0
    hours_to_saturation: float = 0.0
    host: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResourceSaturationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    predicted_saturation_hours: float = 0.0
    saturation_level: SaturationLevel = SaturationLevel.SAFE
    approaching: bool = False
    data_points: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResourceSaturationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_usage_pct: float = 0.0
    by_saturation_level: dict[str, int] = Field(default_factory=dict)
    by_resource_category: dict[str, int] = Field(default_factory=dict)
    by_prediction_confidence: dict[str, int] = Field(default_factory=dict)
    critical_resources: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResourceSaturationPredictor:
    """Compute saturation timeline, detect approaching
    saturation, rank resources by saturation urgency."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ResourceSaturationRecord] = []
        self._analyses: dict[str, ResourceSaturationAnalysis] = {}
        logger.info(
            "resource_saturation_predictor.init",
            max_records=max_records,
        )

    def record_item(
        self,
        resource_id: str = "",
        saturation_level: SaturationLevel = SaturationLevel.SAFE,
        resource_category: ResourceCategory = ResourceCategory.COMPUTE,
        prediction_confidence: PredictionConfidence = PredictionConfidence.MEDIUM,
        current_usage_pct: float = 0.0,
        predicted_usage_pct: float = 0.0,
        hours_to_saturation: float = 0.0,
        host: str = "",
        description: str = "",
    ) -> ResourceSaturationRecord:
        record = ResourceSaturationRecord(
            resource_id=resource_id,
            saturation_level=saturation_level,
            resource_category=resource_category,
            prediction_confidence=prediction_confidence,
            current_usage_pct=current_usage_pct,
            predicted_usage_pct=predicted_usage_pct,
            hours_to_saturation=hours_to_saturation,
            host=host,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "resource_saturation_predictor.record_added",
            record_id=record.id,
            resource_id=resource_id,
        )
        return record

    def process(self, key: str) -> ResourceSaturationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        points = sum(1 for r in self._records if r.resource_id == rec.resource_id)
        approaching = rec.saturation_level in (
            SaturationLevel.DANGER,
            SaturationLevel.CRITICAL,
        )
        analysis = ResourceSaturationAnalysis(
            resource_id=rec.resource_id,
            predicted_saturation_hours=round(rec.hours_to_saturation, 2),
            saturation_level=rec.saturation_level,
            approaching=approaching,
            data_points=points,
            description=f"Resource {rec.resource_id} usage {rec.current_usage_pct}%",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ResourceSaturationReport:
        by_sl: dict[str, int] = {}
        by_rc: dict[str, int] = {}
        by_pc: dict[str, int] = {}
        usages: list[float] = []
        for r in self._records:
            k = r.saturation_level.value
            by_sl[k] = by_sl.get(k, 0) + 1
            k2 = r.resource_category.value
            by_rc[k2] = by_rc.get(k2, 0) + 1
            k3 = r.prediction_confidence.value
            by_pc[k3] = by_pc.get(k3, 0) + 1
            usages.append(r.current_usage_pct)
        avg = round(sum(usages) / len(usages), 2) if usages else 0.0
        critical = list(
            {
                r.resource_id
                for r in self._records
                if r.saturation_level in (SaturationLevel.DANGER, SaturationLevel.CRITICAL)
            }
        )[:10]
        recs: list[str] = []
        if critical:
            recs.append(f"{len(critical)} resources approaching saturation")
        if not recs:
            recs.append("All resources within safe saturation levels")
        return ResourceSaturationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_usage_pct=avg,
            by_saturation_level=by_sl,
            by_resource_category=by_rc,
            by_prediction_confidence=by_pc,
            critical_resources=critical,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        sl_dist: dict[str, int] = {}
        for r in self._records:
            k = r.saturation_level.value
            sl_dist[k] = sl_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "saturation_level_distribution": sl_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("resource_saturation_predictor.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_saturation_timeline(
        self,
    ) -> list[dict[str, Any]]:
        """Compute saturation timeline per resource."""
        res_data: dict[str, list[float]] = {}
        res_cats: dict[str, str] = {}
        for r in self._records:
            res_data.setdefault(r.resource_id, []).append(r.hours_to_saturation)
            res_cats[r.resource_id] = r.resource_category.value
        results: list[dict[str, Any]] = []
        for rid, hours in res_data.items():
            avg = round(sum(hours) / len(hours), 2)
            results.append(
                {
                    "resource_id": rid,
                    "resource_category": res_cats[rid],
                    "avg_hours_to_saturation": avg,
                    "data_points": len(hours),
                }
            )
        results.sort(key=lambda x: x["avg_hours_to_saturation"])
        return results

    def detect_approaching_saturation(
        self,
    ) -> list[dict[str, Any]]:
        """Detect resources approaching saturation."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.saturation_level in (SaturationLevel.DANGER, SaturationLevel.CRITICAL)
                and r.resource_id not in seen
            ):
                seen.add(r.resource_id)
                results.append(
                    {
                        "resource_id": r.resource_id,
                        "resource_category": r.resource_category.value,
                        "current_usage_pct": r.current_usage_pct,
                        "hours_to_saturation": r.hours_to_saturation,
                    }
                )
        results.sort(key=lambda x: x["hours_to_saturation"])
        return results

    def rank_resources_by_saturation_urgency(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all resources by saturation urgency."""
        res_data: dict[str, float] = {}
        res_cats: dict[str, str] = {}
        for r in self._records:
            if r.resource_id not in res_data or r.current_usage_pct > res_data[r.resource_id]:
                res_data[r.resource_id] = r.current_usage_pct
            res_cats[r.resource_id] = r.resource_category.value
        results: list[dict[str, Any]] = []
        for rid, usage in res_data.items():
            results.append(
                {
                    "resource_id": rid,
                    "resource_category": res_cats[rid],
                    "max_usage_pct": round(usage, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["max_usage_pct"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
