"""Threat Surface Analyzer — analyze threat surface area and identify exposure vectors."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SurfaceVector(StrEnum):
    NETWORK_EXPOSURE = "network_exposure"
    API_ENDPOINT = "api_endpoint"
    DATA_STORE = "data_store"
    CREDENTIAL_STORE = "credential_store"
    ADMIN_PANEL = "admin_panel"


class ThreatLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    ACCEPTABLE = "acceptable"


class MitigationStatus(StrEnum):
    MITIGATED = "mitigated"
    PARTIALLY_MITIGATED = "partially_mitigated"
    UNMITIGATED = "unmitigated"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"


# --- Models ---


class SurfaceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    surface_id: str = ""
    surface_vector: SurfaceVector = SurfaceVector.NETWORK_EXPOSURE
    threat_level: ThreatLevel = ThreatLevel.MODERATE
    mitigation_status: MitigationStatus = MitigationStatus.UNMITIGATED
    exposure_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SurfaceMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    surface_id: str = ""
    surface_vector: SurfaceVector = SurfaceVector.NETWORK_EXPOSURE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatSurfaceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    unmitigated_count: int = 0
    avg_exposure_score: float = 0.0
    by_vector: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_exposed: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatSurfaceAnalyzer:
    """Analyze threat surface area, identify exposure vectors, track surface reduction."""

    def __init__(
        self,
        max_records: int = 200000,
        max_exposure_score: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_exposure_score = max_exposure_score
        self._records: list[SurfaceRecord] = []
        self._metrics: list[SurfaceMetric] = []
        logger.info(
            "threat_surface_analyzer.initialized",
            max_records=max_records,
            max_exposure_score=max_exposure_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_surface(
        self,
        surface_id: str,
        surface_vector: SurfaceVector = SurfaceVector.NETWORK_EXPOSURE,
        threat_level: ThreatLevel = ThreatLevel.MODERATE,
        mitigation_status: MitigationStatus = MitigationStatus.UNMITIGATED,
        exposure_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SurfaceRecord:
        record = SurfaceRecord(
            surface_id=surface_id,
            surface_vector=surface_vector,
            threat_level=threat_level,
            mitigation_status=mitigation_status,
            exposure_score=exposure_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_surface_analyzer.surface_recorded",
            record_id=record.id,
            surface_id=surface_id,
            surface_vector=surface_vector.value,
            threat_level=threat_level.value,
        )
        return record

    def get_surface(self, record_id: str) -> SurfaceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_surfaces(
        self,
        surface_vector: SurfaceVector | None = None,
        threat_level: ThreatLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SurfaceRecord]:
        results = list(self._records)
        if surface_vector is not None:
            results = [r for r in results if r.surface_vector == surface_vector]
        if threat_level is not None:
            results = [r for r in results if r.threat_level == threat_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        surface_id: str,
        surface_vector: SurfaceVector = SurfaceVector.NETWORK_EXPOSURE,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SurfaceMetric:
        metric = SurfaceMetric(
            surface_id=surface_id,
            surface_vector=surface_vector,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "threat_surface_analyzer.metric_added",
            surface_id=surface_id,
            surface_vector=surface_vector.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_surface_distribution(self) -> dict[str, Any]:
        """Group by surface_vector; return count and avg exposure_score per vector."""
        vector_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.surface_vector.value
            vector_data.setdefault(key, []).append(r.exposure_score)
        result: dict[str, Any] = {}
        for vector, scores in vector_data.items():
            result[vector] = {
                "count": len(scores),
                "avg_exposure_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_exposed_surfaces(self) -> list[dict[str, Any]]:
        """Return surfaces where exposure_score > max_exposure_score."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.exposure_score > self._max_exposure_score:
                results.append(
                    {
                        "record_id": r.id,
                        "surface_id": r.surface_id,
                        "surface_vector": r.surface_vector.value,
                        "threat_level": r.threat_level.value,
                        "exposure_score": r.exposure_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["exposure_score"], reverse=True)
        return results

    def rank_by_exposure(self) -> list[dict[str, Any]]:
        """Group by service, avg exposure_score, sort desc (most exposed first)."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.exposure_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_scores.items():
            results.append(
                {
                    "service": service,
                    "avg_exposure_score": round(sum(scores) / len(scores), 2),
                    "surface_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_exposure_score"], reverse=True)
        return results

    def detect_surface_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [m.metric_score for m in self._metrics]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> ThreatSurfaceReport:
        by_vector: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_vector[r.surface_vector.value] = by_vector.get(r.surface_vector.value, 0) + 1
            by_level[r.threat_level.value] = by_level.get(r.threat_level.value, 0) + 1
            by_status[r.mitigation_status.value] = by_status.get(r.mitigation_status.value, 0) + 1
        unmitigated_count = sum(
            1 for r in self._records if r.exposure_score > self._max_exposure_score
        )
        avg_exposure_score = (
            round(
                sum(r.exposure_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        exposed = self.identify_exposed_surfaces()
        top_exposed = [e["surface_id"] for e in exposed]
        recs: list[str] = []
        if exposed:
            recs.append(
                f"{len(exposed)} exposed surface(s) detected — review mitigation strategies"
            )
        high_exp = sum(1 for r in self._records if r.exposure_score > self._max_exposure_score)
        if high_exp > 0:
            recs.append(
                f"{high_exp} surface(s) above exposure threshold ({self._max_exposure_score})"
            )
        if not recs:
            recs.append("Threat surface levels are acceptable")
        return ThreatSurfaceReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            unmitigated_count=unmitigated_count,
            avg_exposure_score=avg_exposure_score,
            by_vector=by_vector,
            by_level=by_level,
            by_status=by_status,
            top_exposed=top_exposed,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("threat_surface_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        vector_dist: dict[str, int] = {}
        for r in self._records:
            key = r.surface_vector.value
            vector_dist[key] = vector_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "max_exposure_score": self._max_exposure_score,
            "vector_distribution": vector_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_surfaces": len({r.surface_id for r in self._records}),
        }
