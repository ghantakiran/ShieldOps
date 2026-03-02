"""Cloud Exposure Scanner — scan cloud resources for public exposure and misconfigurations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CloudProvider(StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    MULTI_CLOUD = "multi_cloud"
    PRIVATE = "private"


class ExposureCategory(StrEnum):
    STORAGE_BUCKET = "storage_bucket"
    DATABASE = "database"
    API_GATEWAY = "api_gateway"
    COMPUTE_INSTANCE = "compute_instance"
    NETWORK = "network"


class RemediationStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"
    DEFERRED = "deferred"


# --- Models ---


class CloudExposureRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_name: str = ""
    cloud_provider: CloudProvider = CloudProvider.AWS
    exposure_category: ExposureCategory = ExposureCategory.STORAGE_BUCKET
    remediation_status: RemediationStatus = RemediationStatus.OPEN
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CloudExposureAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_name: str = ""
    cloud_provider: CloudProvider = CloudProvider.AWS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CloudExposureReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CloudExposureScanner:
    """Scan cloud resources for public exposure and misconfigurations."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._records: list[CloudExposureRecord] = []
        self._analyses: list[CloudExposureAnalysis] = []
        logger.info(
            "cloud_exposure_scanner.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_exposure(
        self,
        resource_name: str,
        cloud_provider: CloudProvider = CloudProvider.AWS,
        exposure_category: ExposureCategory = ExposureCategory.STORAGE_BUCKET,
        remediation_status: RemediationStatus = RemediationStatus.OPEN,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CloudExposureRecord:
        record = CloudExposureRecord(
            resource_name=resource_name,
            cloud_provider=cloud_provider,
            exposure_category=exposure_category,
            remediation_status=remediation_status,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cloud_exposure_scanner.exposure_recorded",
            record_id=record.id,
            resource_name=resource_name,
            cloud_provider=cloud_provider.value,
            exposure_category=exposure_category.value,
        )
        return record

    def get_exposure(self, record_id: str) -> CloudExposureRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_exposures(
        self,
        cloud_provider: CloudProvider | None = None,
        exposure_category: ExposureCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CloudExposureRecord]:
        results = list(self._records)
        if cloud_provider is not None:
            results = [r for r in results if r.cloud_provider == cloud_provider]
        if exposure_category is not None:
            results = [r for r in results if r.exposure_category == exposure_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        resource_name: str,
        cloud_provider: CloudProvider = CloudProvider.AWS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CloudExposureAnalysis:
        analysis = CloudExposureAnalysis(
            resource_name=resource_name,
            cloud_provider=cloud_provider,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "cloud_exposure_scanner.analysis_added",
            resource_name=resource_name,
            cloud_provider=cloud_provider.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by cloud_provider; return count and avg risk_score."""
        provider_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.cloud_provider.value
            provider_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for provider, scores in provider_data.items():
            result[provider] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score < risk_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._risk_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "resource_name": r.resource_name,
                        "cloud_provider": r.cloud_provider.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> CloudExposureReport:
        by_provider: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_provider[r.cloud_provider.value] = by_provider.get(r.cloud_provider.value, 0) + 1
            by_category[r.exposure_category.value] = (
                by_category.get(r.exposure_category.value, 0) + 1
            )
            by_status[r.remediation_status.value] = by_status.get(r.remediation_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.risk_score < self._risk_threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["resource_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} cloud exposure(s) below risk threshold ({self._risk_threshold})"
            )
        if self._records and avg_risk_score < self._risk_threshold:
            recs.append(f"Avg risk score {avg_risk_score} below threshold ({self._risk_threshold})")
        if not recs:
            recs.append("Cloud exposure scanning is healthy")
        return CloudExposureReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_provider=by_provider,
            by_category=by_category,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cloud_exposure_scanner.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        provider_dist: dict[str, int] = {}
        for r in self._records:
            key = r.cloud_provider.value
            provider_dist[key] = provider_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_threshold": self._risk_threshold,
            "provider_distribution": provider_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
