"""Infrastructure Blueprint Intelligence
analyze blueprint adoption, detect blueprint drift,
rank blueprints by reuse value."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BlueprintStatus(StrEnum):
    CURRENT = "current"
    OUTDATED = "outdated"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class AdoptionLevel(StrEnum):
    WIDESPREAD = "widespread"
    MODERATE = "moderate"
    LIMITED = "limited"
    NONE = "none"


class BlueprintType(StrEnum):
    NETWORK = "network"
    COMPUTE = "compute"
    DATABASE = "database"
    SECURITY = "security"


# --- Models ---


class BlueprintIntelligenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    blueprint_id: str = ""
    blueprint_name: str = ""
    blueprint_status: BlueprintStatus = BlueprintStatus.CURRENT
    adoption_level: AdoptionLevel = AdoptionLevel.MODERATE
    blueprint_type: BlueprintType = BlueprintType.COMPUTE
    adoption_count: int = 0
    drift_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BlueprintIntelligenceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    blueprint_id: str = ""
    computed_adoption: float = 0.0
    blueprint_status: BlueprintStatus = BlueprintStatus.CURRENT
    has_drift: bool = False
    reuse_value: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BlueprintIntelligenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_adoption: float = 0.0
    by_blueprint_status: dict[str, int] = Field(default_factory=dict)
    by_adoption_level: dict[str, int] = Field(default_factory=dict)
    by_blueprint_type: dict[str, int] = Field(default_factory=dict)
    top_blueprints: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class InfrastructureBlueprintIntelligence:
    """Analyze blueprint adoption, detect blueprint
    drift, rank blueprints by reuse value."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[BlueprintIntelligenceRecord] = []
        self._analyses: dict[str, BlueprintIntelligenceAnalysis] = {}
        logger.info(
            "infrastructure_blueprint_intel.init",
            max_records=max_records,
        )

    def record_item(
        self,
        blueprint_id: str = "",
        blueprint_name: str = "",
        blueprint_status: BlueprintStatus = (BlueprintStatus.CURRENT),
        adoption_level: AdoptionLevel = (AdoptionLevel.MODERATE),
        blueprint_type: BlueprintType = (BlueprintType.COMPUTE),
        adoption_count: int = 0,
        drift_score: float = 0.0,
        description: str = "",
    ) -> BlueprintIntelligenceRecord:
        record = BlueprintIntelligenceRecord(
            blueprint_id=blueprint_id,
            blueprint_name=blueprint_name,
            blueprint_status=blueprint_status,
            adoption_level=adoption_level,
            blueprint_type=blueprint_type,
            adoption_count=adoption_count,
            drift_score=drift_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "blueprint_intelligence.record_added",
            record_id=record.id,
            blueprint_id=blueprint_id,
        )
        return record

    def process(self, key: str) -> BlueprintIntelligenceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        has_drift = rec.drift_score > 20.0
        reuse = round(
            rec.adoption_count * 10.0 - rec.drift_score,
            2,
        )
        analysis = BlueprintIntelligenceAnalysis(
            blueprint_id=rec.blueprint_id,
            computed_adoption=round(float(rec.adoption_count), 2),
            blueprint_status=rec.blueprint_status,
            has_drift=has_drift,
            reuse_value=max(reuse, 0.0),
            description=(f"Blueprint {rec.blueprint_id} adoption {rec.adoption_count}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> BlueprintIntelligenceReport:
        by_bs: dict[str, int] = {}
        by_al: dict[str, int] = {}
        by_bt: dict[str, int] = {}
        adoptions: list[int] = []
        for r in self._records:
            k = r.blueprint_status.value
            by_bs[k] = by_bs.get(k, 0) + 1
            k2 = r.adoption_level.value
            by_al[k2] = by_al.get(k2, 0) + 1
            k3 = r.blueprint_type.value
            by_bt[k3] = by_bt.get(k3, 0) + 1
            adoptions.append(r.adoption_count)
        avg = round(sum(adoptions) / len(adoptions), 2) if adoptions else 0.0
        top = list(
            {
                r.blueprint_id
                for r in self._records
                if r.adoption_level
                in (
                    AdoptionLevel.WIDESPREAD,
                    AdoptionLevel.MODERATE,
                )
            }
        )[:10]
        recs: list[str] = []
        if top:
            recs.append(f"{len(top)} popular blueprints found")
        if not recs:
            recs.append("No widely adopted blueprints found")
        return BlueprintIntelligenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_adoption=avg,
            by_blueprint_status=by_bs,
            by_adoption_level=by_al,
            by_blueprint_type=by_bt,
            top_blueprints=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        bs_dist: dict[str, int] = {}
        for r in self._records:
            k = r.blueprint_status.value
            bs_dist[k] = bs_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "blueprint_status_distribution": bs_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("infrastructure_blueprint_intel.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def analyze_blueprint_adoption(
        self,
    ) -> list[dict[str, Any]]:
        """Analyze adoption per blueprint."""
        bp_data: dict[str, list[int]] = {}
        bp_types: dict[str, str] = {}
        for r in self._records:
            bp_data.setdefault(r.blueprint_id, []).append(r.adoption_count)
            bp_types[r.blueprint_id] = r.blueprint_type.value
        results: list[dict[str, Any]] = []
        for bid, counts in bp_data.items():
            total = sum(counts)
            results.append(
                {
                    "blueprint_id": bid,
                    "blueprint_type": bp_types[bid],
                    "total_adoption": total,
                    "record_count": len(counts),
                }
            )
        results.sort(
            key=lambda x: x["total_adoption"],
            reverse=True,
        )
        return results

    def detect_blueprint_drift(
        self,
    ) -> list[dict[str, Any]]:
        """Detect blueprints with drift."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.drift_score > 20.0 and r.blueprint_id not in seen:
                seen.add(r.blueprint_id)
                results.append(
                    {
                        "blueprint_id": (r.blueprint_id),
                        "blueprint_name": (r.blueprint_name),
                        "drift_score": (r.drift_score),
                        "status": (r.blueprint_status.value),
                        "adoption_count": (r.adoption_count),
                    }
                )
        results.sort(
            key=lambda x: x["drift_score"],
            reverse=True,
        )
        return results

    def rank_blueprints_by_reuse_value(
        self,
    ) -> list[dict[str, Any]]:
        """Rank blueprints by reuse value."""
        bp_value: dict[str, float] = {}
        for r in self._records:
            val = r.adoption_count * 10.0 - r.drift_score
            bp_value[r.blueprint_id] = bp_value.get(r.blueprint_id, 0.0) + max(val, 0.0)
        results: list[dict[str, Any]] = []
        for bid, total in bp_value.items():
            results.append(
                {
                    "blueprint_id": bid,
                    "reuse_value": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["reuse_value"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
