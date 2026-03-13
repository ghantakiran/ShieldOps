"""Event Schema Registry Intelligence —
detect schema conflicts, compute evolution velocity,
rank schemas by compatibility risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SchemaFormat(StrEnum):
    AVRO = "avro"
    PROTOBUF = "protobuf"
    JSON_SCHEMA = "json_schema"
    CUSTOM = "custom"


class CompatibilityMode(StrEnum):
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    NONE = "none"


class EvolutionRisk(StrEnum):
    BREAKING = "breaking"
    MAJOR = "major"
    MINOR = "minor"
    SAFE = "safe"


# --- Models ---


class SchemaRegistryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_id: str = ""
    schema_format: SchemaFormat = SchemaFormat.AVRO
    compatibility_mode: CompatibilityMode = CompatibilityMode.BACKWARD
    evolution_risk: EvolutionRisk = EvolutionRisk.SAFE
    version: int = 1
    field_count: int = 0
    topic: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SchemaRegistryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_id: str = ""
    schema_format: SchemaFormat = SchemaFormat.AVRO
    conflict_count: int = 0
    evolution_velocity: float = 0.0
    compatibility_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SchemaRegistryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_version: float = 0.0
    by_format: dict[str, int] = Field(default_factory=dict)
    by_compatibility: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    high_risk_schemas: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EventSchemaRegistryIntelligence:
    """Detect schema conflicts, compute evolution
    velocity, rank schemas by compatibility risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SchemaRegistryRecord] = []
        self._analyses: dict[str, SchemaRegistryAnalysis] = {}
        logger.info(
            "event_schema_registry_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        schema_id: str = "",
        schema_format: SchemaFormat = SchemaFormat.AVRO,
        compatibility_mode: CompatibilityMode = (CompatibilityMode.BACKWARD),
        evolution_risk: EvolutionRisk = (EvolutionRisk.SAFE),
        version: int = 1,
        field_count: int = 0,
        topic: str = "",
        description: str = "",
    ) -> SchemaRegistryRecord:
        record = SchemaRegistryRecord(
            schema_id=schema_id,
            schema_format=schema_format,
            compatibility_mode=compatibility_mode,
            evolution_risk=evolution_risk,
            version=version,
            field_count=field_count,
            topic=topic,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "schema_registry.record_added",
            record_id=record.id,
            schema_id=schema_id,
        )
        return record

    def process(self, key: str) -> SchemaRegistryAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        conflicts = sum(
            1 for r in self._records if r.schema_id == rec.schema_id and r.version != rec.version
        )
        versions = [r.version for r in self._records if r.schema_id == rec.schema_id]
        velocity = round(max(versions) - min(versions), 2) if versions else 0.0
        analysis = SchemaRegistryAnalysis(
            schema_id=rec.schema_id,
            schema_format=rec.schema_format,
            conflict_count=conflicts,
            evolution_velocity=velocity,
            compatibility_score=round(100.0 - (conflicts * 10), 2),
            description=(f"Schema {rec.schema_id} v{rec.version}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> SchemaRegistryReport:
        by_fmt: dict[str, int] = {}
        by_compat: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        versions: list[int] = []
        for r in self._records:
            k = r.schema_format.value
            by_fmt[k] = by_fmt.get(k, 0) + 1
            k2 = r.compatibility_mode.value
            by_compat[k2] = by_compat.get(k2, 0) + 1
            k3 = r.evolution_risk.value
            by_risk[k3] = by_risk.get(k3, 0) + 1
            versions.append(r.version)
        avg_v = round(sum(versions) / len(versions), 2) if versions else 0.0
        high = list(
            {
                r.schema_id
                for r in self._records
                if r.evolution_risk in (EvolutionRisk.BREAKING, EvolutionRisk.MAJOR)
            }
        )[:10]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} high-risk schemas detected")
        if not recs:
            recs.append("No significant risk detected")
        return SchemaRegistryReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_version=avg_v,
            by_format=by_fmt,
            by_compatibility=by_compat,
            by_risk=by_risk,
            high_risk_schemas=high,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        fmt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.schema_format.value
            fmt_dist[k] = fmt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "format_distribution": fmt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("event_schema_registry_intelligence.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def detect_schema_conflicts(
        self,
    ) -> list[dict[str, Any]]:
        """Detect schemas with version conflicts."""
        schema_versions: dict[str, set[int]] = {}
        for r in self._records:
            schema_versions.setdefault(r.schema_id, set()).add(r.version)
        results: list[dict[str, Any]] = []
        for sid, vers in schema_versions.items():
            if len(vers) > 1:
                results.append(
                    {
                        "schema_id": sid,
                        "version_count": len(vers),
                        "versions": sorted(vers),
                        "conflict_severity": ("high" if len(vers) > 3 else "medium"),
                    }
                )
        results.sort(
            key=lambda x: x["version_count"],
            reverse=True,
        )
        return results

    def compute_schema_evolution_velocity(
        self,
    ) -> list[dict[str, Any]]:
        """Compute evolution velocity per schema."""
        schema_data: dict[str, list[int]] = {}
        for r in self._records:
            schema_data.setdefault(r.schema_id, []).append(r.version)
        results: list[dict[str, Any]] = []
        for sid, vers in schema_data.items():
            velocity = max(vers) - min(vers)
            results.append(
                {
                    "schema_id": sid,
                    "min_version": min(vers),
                    "max_version": max(vers),
                    "velocity": velocity,
                    "record_count": len(vers),
                }
            )
        results.sort(
            key=lambda x: x["velocity"],
            reverse=True,
        )
        return results

    def rank_schemas_by_compatibility_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank schemas by compatibility risk."""
        risk_weights = {
            "breaking": 4,
            "major": 3,
            "minor": 2,
            "safe": 1,
        }
        schema_risk: dict[str, float] = {}
        schema_fmt: dict[str, str] = {}
        for r in self._records:
            w = risk_weights.get(r.evolution_risk.value, 1)
            schema_risk[r.schema_id] = schema_risk.get(r.schema_id, 0.0) + w
            schema_fmt[r.schema_id] = r.schema_format.value
        results: list[dict[str, Any]] = []
        for sid, score in schema_risk.items():
            results.append(
                {
                    "schema_id": sid,
                    "format": schema_fmt[sid],
                    "risk_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["risk_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
