"""API Versioning Lifecycle Engine.

Track version adoption, detect stale version usage,
and forecast deprecation readiness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VersionStatus(StrEnum):
    CURRENT = "current"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    RETIRED = "retired"


class AdoptionPhase(StrEnum):
    EARLY = "early"
    GROWING = "growing"
    MATURE = "mature"
    DECLINING = "declining"


class MigrationReadiness(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


# --- Models ---


class ApiVersionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str = ""
    version: str = ""
    version_status: VersionStatus = VersionStatus.CURRENT
    adoption_phase: AdoptionPhase = AdoptionPhase.EARLY
    migration_readiness: MigrationReadiness = MigrationReadiness.UNKNOWN
    consumer_count: int = 0
    request_share_pct: float = 0.0
    days_since_release: int = 0
    created_at: float = Field(default_factory=time.time)


class ApiVersionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str = ""
    version: str = ""
    is_stale: bool = False
    adoption_pct: float = 0.0
    migration_ready: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ApiVersionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_consumer_count: float = 0.0
    by_version_status: dict[str, int] = Field(default_factory=dict)
    by_adoption_phase: dict[str, int] = Field(default_factory=dict)
    by_migration_readiness: dict[str, int] = Field(default_factory=dict)
    stale_versions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ApiVersioningLifecycleEngine:
    """Track version adoption, detect stale usage,
    and forecast deprecation readiness."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ApiVersionRecord] = []
        self._analyses: dict[str, ApiVersionAnalysis] = {}
        logger.info(
            "api_versioning_lifecycle.init",
            max_records=max_records,
        )

    def record_item(
        self,
        api_name: str = "",
        version: str = "",
        version_status: VersionStatus = (VersionStatus.CURRENT),
        adoption_phase: AdoptionPhase = (AdoptionPhase.EARLY),
        migration_readiness: MigrationReadiness = (MigrationReadiness.UNKNOWN),
        consumer_count: int = 0,
        request_share_pct: float = 0.0,
        days_since_release: int = 0,
    ) -> ApiVersionRecord:
        record = ApiVersionRecord(
            api_name=api_name,
            version=version,
            version_status=version_status,
            adoption_phase=adoption_phase,
            migration_readiness=migration_readiness,
            consumer_count=consumer_count,
            request_share_pct=request_share_pct,
            days_since_release=days_since_release,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "api_versioning.record_added",
            record_id=record.id,
            api_name=api_name,
        )
        return record

    def process(self, key: str) -> ApiVersionAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_stale = rec.version_status in (
            VersionStatus.DEPRECATED,
            VersionStatus.SUNSET,
            VersionStatus.RETIRED,
        )
        mig_ready = rec.migration_readiness == MigrationReadiness.READY
        analysis = ApiVersionAnalysis(
            api_name=rec.api_name,
            version=rec.version,
            is_stale=is_stale,
            adoption_pct=round(rec.request_share_pct, 2),
            migration_ready=mig_ready,
            description=(f"API {rec.api_name} v{rec.version} share {rec.request_share_pct}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ApiVersionReport:
        by_vs: dict[str, int] = {}
        by_ap: dict[str, int] = {}
        by_mr: dict[str, int] = {}
        counts: list[int] = []
        for r in self._records:
            k = r.version_status.value
            by_vs[k] = by_vs.get(k, 0) + 1
            k2 = r.adoption_phase.value
            by_ap[k2] = by_ap.get(k2, 0) + 1
            k3 = r.migration_readiness.value
            by_mr[k3] = by_mr.get(k3, 0) + 1
            counts.append(r.consumer_count)
        avg = round(sum(counts) / len(counts), 2) if counts else 0.0
        stale = list(
            {
                f"{r.api_name}:{r.version}"
                for r in self._records
                if r.version_status
                in (
                    VersionStatus.DEPRECATED,
                    VersionStatus.SUNSET,
                )
            }
        )[:10]
        recs: list[str] = []
        if stale:
            recs.append(f"{len(stale)} stale API versions")
        if not recs:
            recs.append("All versions current")
        return ApiVersionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_consumer_count=avg,
            by_version_status=by_vs,
            by_adoption_phase=by_ap,
            by_migration_readiness=by_mr,
            stale_versions=stale,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.version_status.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "version_status_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("api_versioning_lifecycle.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def track_version_adoption(
        self,
    ) -> list[dict[str, Any]]:
        """Track adoption rates per API version."""
        ver_data: dict[str, list[float]] = {}
        ver_meta: dict[str, dict[str, Any]] = {}
        for r in self._records:
            k = f"{r.api_name}:{r.version}"
            ver_data.setdefault(k, []).append(r.request_share_pct)
            ver_meta[k] = {
                "api_name": r.api_name,
                "version": r.version,
                "phase": r.adoption_phase.value,
            }
        results: list[dict[str, Any]] = []
        for ver, shares in ver_data.items():
            avg = round(sum(shares) / len(shares), 2)
            results.append(
                {
                    "api_version": ver,
                    "api_name": (ver_meta[ver]["api_name"]),
                    "version": (ver_meta[ver]["version"]),
                    "phase": ver_meta[ver]["phase"],
                    "avg_share_pct": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_share_pct"],
            reverse=True,
        )
        return results

    def detect_stale_version_usage(
        self,
    ) -> list[dict[str, Any]]:
        """Detect deprecated versions still in use."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            k = f"{r.api_name}:{r.version}"
            if (
                r.version_status
                in (
                    VersionStatus.DEPRECATED,
                    VersionStatus.SUNSET,
                )
                and r.consumer_count > 0
                and k not in seen
            ):
                seen.add(k)
                results.append(
                    {
                        "api_name": r.api_name,
                        "version": r.version,
                        "status": (r.version_status.value),
                        "consumer_count": (r.consumer_count),
                        "share_pct": (r.request_share_pct),
                    }
                )
        results.sort(
            key=lambda x: x["consumer_count"],
            reverse=True,
        )
        return results

    def forecast_deprecation_readiness(
        self,
    ) -> list[dict[str, Any]]:
        """Forecast readiness to deprecate versions."""
        ver_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            k = f"{r.api_name}:{r.version}"
            if k not in ver_data:
                ver_data[k] = {
                    "api_name": r.api_name,
                    "version": r.version,
                    "readiness": (r.migration_readiness.value),
                    "consumers": r.consumer_count,
                    "share": r.request_share_pct,
                }
        results = list(ver_data.values())
        results.sort(
            key=lambda x: x["consumers"],
        )
        return results
