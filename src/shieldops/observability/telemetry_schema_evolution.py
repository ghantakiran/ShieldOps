"""TelemetrySchemaEvolution — telemetry schema evolution."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SchemaChange(StrEnum):
    FIELD_ADDED = "field_added"
    FIELD_REMOVED = "field_removed"
    TYPE_CHANGED = "type_changed"
    RENAMED = "renamed"


class CompatibilityLevel(StrEnum):
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    NONE = "none"


class MigrationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Models ---


class TelemetrySchemaEvolutionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    schema_change: SchemaChange = SchemaChange.FIELD_ADDED
    compatibility_level: CompatibilityLevel = CompatibilityLevel.BACKWARD
    migration_status: MigrationStatus = MigrationStatus.PENDING
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TelemetrySchemaEvolutionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    schema_change: SchemaChange = SchemaChange.FIELD_ADDED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TelemetrySchemaEvolutionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_schema_change: dict[str, int] = Field(default_factory=dict)
    by_compatibility_level: dict[str, int] = Field(default_factory=dict)
    by_migration_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TelemetrySchemaEvolution:
    """Telemetry schema evolution engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[TelemetrySchemaEvolutionRecord] = []
        self._analyses: list[TelemetrySchemaEvolutionAnalysis] = []
        logger.info(
            "telemetry.schema.evolution.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        schema_change: SchemaChange = (SchemaChange.FIELD_ADDED),
        compatibility_level: CompatibilityLevel = (CompatibilityLevel.BACKWARD),
        migration_status: MigrationStatus = (MigrationStatus.PENDING),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TelemetrySchemaEvolutionRecord:
        record = TelemetrySchemaEvolutionRecord(
            name=name,
            schema_change=schema_change,
            compatibility_level=compatibility_level,
            migration_status=migration_status,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "telemetry.schema.evolution.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = TelemetrySchemaEvolutionAnalysis(
                    name=r.name,
                    schema_change=(r.schema_change),
                    analysis_score=r.score,
                    threshold=self._threshold,
                    breached=(r.score < self._threshold),
                    description=(f"Processed {r.name}"),
                )
                self._analyses.append(analysis)
                return {
                    "status": "processed",
                    "analysis_id": analysis.id,
                    "breached": analysis.breached,
                }
        return {"status": "not_found", "key": key}

    # -- domain methods ---

    def detect_schema_drift(
        self,
    ) -> list[dict[str, Any]]:
        """Detect schema drift across services."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "schema_change": (r.schema_change.value),
                        "compatibility": (r.compatibility_level.value),
                        "score": r.score,
                        "service": r.service,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def compute_compatibility_score(
        self,
    ) -> dict[str, Any]:
        """Compute compatibility score by level."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.compatibility_level.value
            level_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in level_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def generate_migration_plan(
        self,
    ) -> list[dict[str, Any]]:
        """Generate migration plans per service."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_score": avg,
                    "plan": ("migrate_schema" if avg < self._threshold else "no_action"),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    # -- report / stats ---

    def generate_report(
        self,
    ) -> TelemetrySchemaEvolutionReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.schema_change.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.compatibility_level.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.migration_status.value
            by_e3[v3] = by_e3.get(v3, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg < self._threshold:
            recs.append(f"Avg score {avg} below threshold ({self._threshold})")
        if not recs:
            recs.append("Telemetry Schema Evolution is healthy")
        return TelemetrySchemaEvolutionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_schema_change=by_e1,
            by_compatibility_level=by_e2,
            by_migration_status=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("telemetry.schema.evolution.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.schema_change.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "schema_change_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
