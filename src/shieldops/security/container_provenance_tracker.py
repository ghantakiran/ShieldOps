"""Container Provenance Tracker — track container image provenance and build lineage."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ProvenanceLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"
    UNKNOWN = "unknown"


class RegistryType(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    MIRROR = "mirror"
    CACHE = "cache"
    INTERNAL = "internal"


class BuildSystem(StrEnum):
    DOCKER = "docker"
    BUILDPACK = "buildpack"
    KANIKO = "kaniko"
    BUILDAH = "buildah"
    CUSTOM = "custom"


# --- Models ---


class ProvenanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    image_name: str = ""
    provenance_level: ProvenanceLevel = ProvenanceLevel.FULL
    registry_type: RegistryType = RegistryType.PRIVATE
    build_system: BuildSystem = BuildSystem.DOCKER
    provenance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ProvenanceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    image_name: str = ""
    provenance_level: ProvenanceLevel = ProvenanceLevel.FULL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContainerProvenanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_provenance_score: float = 0.0
    by_provenance: dict[str, int] = Field(default_factory=dict)
    by_registry: dict[str, int] = Field(default_factory=dict)
    by_build_system: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ContainerProvenanceTracker:
    """Track container image provenance, registry origins, and build system lineage."""

    def __init__(
        self,
        max_records: int = 200000,
        provenance_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._provenance_gap_threshold = provenance_gap_threshold
        self._records: list[ProvenanceRecord] = []
        self._analyses: list[ProvenanceAnalysis] = []
        logger.info(
            "container_provenance_tracker.initialized",
            max_records=max_records,
            provenance_gap_threshold=provenance_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_provenance(
        self,
        image_name: str,
        provenance_level: ProvenanceLevel = ProvenanceLevel.FULL,
        registry_type: RegistryType = RegistryType.PRIVATE,
        build_system: BuildSystem = BuildSystem.DOCKER,
        provenance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ProvenanceRecord:
        record = ProvenanceRecord(
            image_name=image_name,
            provenance_level=provenance_level,
            registry_type=registry_type,
            build_system=build_system,
            provenance_score=provenance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "container_provenance_tracker.provenance_recorded",
            record_id=record.id,
            image_name=image_name,
            provenance_level=provenance_level.value,
            registry_type=registry_type.value,
        )
        return record

    def get_provenance(self, record_id: str) -> ProvenanceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_provenance_records(
        self,
        provenance_level: ProvenanceLevel | None = None,
        registry_type: RegistryType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ProvenanceRecord]:
        results = list(self._records)
        if provenance_level is not None:
            results = [r for r in results if r.provenance_level == provenance_level]
        if registry_type is not None:
            results = [r for r in results if r.registry_type == registry_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        image_name: str,
        provenance_level: ProvenanceLevel = ProvenanceLevel.FULL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ProvenanceAnalysis:
        analysis = ProvenanceAnalysis(
            image_name=image_name,
            provenance_level=provenance_level,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "container_provenance_tracker.analysis_added",
            image_name=image_name,
            provenance_level=provenance_level.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_provenance_distribution(self) -> dict[str, Any]:
        """Group by provenance_level; return count and avg provenance_score."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.provenance_level.value
            level_data.setdefault(key, []).append(r.provenance_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_provenance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_provenance_gaps(self) -> list[dict[str, Any]]:
        """Return records where provenance_score < provenance_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.provenance_score < self._provenance_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "image_name": r.image_name,
                        "provenance_level": r.provenance_level.value,
                        "provenance_score": r.provenance_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["provenance_score"])

    def rank_by_provenance(self) -> list[dict[str, Any]]:
        """Group by service, avg provenance_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.provenance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_provenance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_provenance_score"])
        return results

    def detect_provenance_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
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

    def generate_report(self) -> ContainerProvenanceReport:
        by_provenance: dict[str, int] = {}
        by_registry: dict[str, int] = {}
        by_build_system: dict[str, int] = {}
        for r in self._records:
            by_provenance[r.provenance_level.value] = (
                by_provenance.get(r.provenance_level.value, 0) + 1
            )
            by_registry[r.registry_type.value] = by_registry.get(r.registry_type.value, 0) + 1
            by_build_system[r.build_system.value] = by_build_system.get(r.build_system.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.provenance_score < self._provenance_gap_threshold
        )
        scores = [r.provenance_score for r in self._records]
        avg_provenance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_provenance_gaps()
        top_gaps = [o["image_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} image(s) below provenance threshold "
                f"({self._provenance_gap_threshold})"
            )
        if self._records and avg_provenance_score < self._provenance_gap_threshold:
            recs.append(
                f"Avg provenance score {avg_provenance_score} below threshold "
                f"({self._provenance_gap_threshold})"
            )
        if not recs:
            recs.append("Container provenance is healthy")
        return ContainerProvenanceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_provenance_score=avg_provenance_score,
            by_provenance=by_provenance,
            by_registry=by_registry,
            by_build_system=by_build_system,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("container_provenance_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.provenance_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "provenance_gap_threshold": self._provenance_gap_threshold,
            "provenance_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
