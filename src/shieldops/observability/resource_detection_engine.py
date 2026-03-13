"""ResourceDetectionEngine — resource attribute detection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResourceProvider(StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    KUBERNETES = "kubernetes"


class DetectionMethod(StrEnum):
    API_CALL = "api_call"
    ENV_VAR = "env_var"
    METADATA = "metadata"
    FILE_SYSTEM = "file_system"


class ResourceConfidence(StrEnum):
    VERIFIED = "verified"
    PROBABLE = "probable"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


# --- Models ---


class ResourceDetectionEngineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_provider: ResourceProvider = ResourceProvider.AWS
    detection_method: DetectionMethod = DetectionMethod.API_CALL
    resource_confidence: ResourceConfidence = ResourceConfidence.VERIFIED
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ResourceDetectionEngineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_provider: ResourceProvider = ResourceProvider.AWS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResourceDetectionEngineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_resource_provider: dict[str, int] = Field(default_factory=dict)
    by_detection_method: dict[str, int] = Field(default_factory=dict)
    by_resource_confidence: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResourceDetectionEngine:
    """Resource attribute detection engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ResourceDetectionEngineRecord] = []
        self._analyses: list[ResourceDetectionEngineAnalysis] = []
        logger.info(
            "resource.detection.engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        resource_provider: ResourceProvider = (ResourceProvider.AWS),
        detection_method: DetectionMethod = (DetectionMethod.API_CALL),
        resource_confidence: ResourceConfidence = (ResourceConfidence.VERIFIED),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ResourceDetectionEngineRecord:
        record = ResourceDetectionEngineRecord(
            name=name,
            resource_provider=resource_provider,
            detection_method=detection_method,
            resource_confidence=resource_confidence,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "resource.detection.engine.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = ResourceDetectionEngineAnalysis(
                    name=r.name,
                    resource_provider=(r.resource_provider),
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

    def detect_resource_attributes(
        self,
    ) -> dict[str, Any]:
        """Detect resource attributes by provider."""
        provider_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.resource_provider.value
            provider_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in provider_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def compute_detection_coverage(
        self,
    ) -> list[dict[str, Any]]:
        """Compute detection coverage per service."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_coverage": avg,
                }
            )
        results.sort(key=lambda x: x["avg_coverage"])
        return results

    def reconcile_conflicting_attributes(
        self,
    ) -> list[dict[str, Any]]:
        """Find conflicting resource attributes."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.resource_confidence in (
                ResourceConfidence.INFERRED,
                ResourceConfidence.UNKNOWN,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "provider": (r.resource_provider.value),
                        "confidence": (r.resource_confidence.value),
                        "score": r.score,
                        "service": r.service,
                    }
                )
        return results

    # -- report / stats ---

    def generate_report(
        self,
    ) -> ResourceDetectionEngineReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.resource_provider.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.detection_method.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.resource_confidence.value
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
            recs.append("Resource Detection Engine is healthy")
        return ResourceDetectionEngineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_resource_provider=by_e1,
            by_detection_method=by_e2,
            by_resource_confidence=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("resource.detection.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.resource_provider.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "resource_provider_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
