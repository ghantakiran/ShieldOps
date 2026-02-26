"""Attack Surface Monitor — track and analyze external attack surface exposure."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SurfaceType(StrEnum):
    PUBLIC_API = "public_api"
    EXPOSED_PORT = "exposed_port"
    CLOUD_STORAGE = "cloud_storage"
    DATABASE_ENDPOINT = "database_endpoint"
    ADMIN_INTERFACE = "admin_interface"


class ExposureLevel(StrEnum):
    INTERNET_FACING = "internet_facing"
    VPN_ONLY = "vpn_only"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    AIR_GAPPED = "air_gapped"


class SurfaceRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    ACCEPTABLE = "acceptable"


# --- Models ---


class SurfaceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    surface_type: SurfaceType = SurfaceType.PUBLIC_API
    exposure: ExposureLevel = ExposureLevel.INTERNAL
    risk: SurfaceRisk = SurfaceRisk.LOW
    risk_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ExposureDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exposure_name: str = ""
    surface_type: SurfaceType = SurfaceType.PUBLIC_API
    exposure: ExposureLevel = ExposureLevel.INTERNAL
    severity_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AttackSurfaceReport(BaseModel):
    total_surfaces: int = 0
    total_exposures: int = 0
    avg_risk_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_exposure: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AttackSurfaceMonitor:
    """Track and analyze external attack surface exposure."""

    def __init__(
        self,
        max_records: int = 200000,
        max_critical_exposures: int = 5,
    ) -> None:
        self._max_records = max_records
        self._max_critical_exposures = max_critical_exposures
        self._records: list[SurfaceRecord] = []
        self._exposures: list[ExposureDetail] = []
        logger.info(
            "attack_surface.initialized",
            max_records=max_records,
            max_critical_exposures=max_critical_exposures,
        )

    # -- record / get / list ---------------------------------------------

    def record_surface(
        self,
        service_name: str,
        surface_type: SurfaceType = SurfaceType.PUBLIC_API,
        exposure: ExposureLevel = ExposureLevel.INTERNAL,
        risk: SurfaceRisk = SurfaceRisk.LOW,
        risk_score: float = 0.0,
        details: str = "",
    ) -> SurfaceRecord:
        record = SurfaceRecord(
            service_name=service_name,
            surface_type=surface_type,
            exposure=exposure,
            risk=risk,
            risk_score=risk_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "attack_surface.surface_recorded",
            record_id=record.id,
            service_name=service_name,
            surface_type=surface_type.value,
            risk=risk.value,
        )
        return record

    def get_surface(self, record_id: str) -> SurfaceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_surfaces(
        self,
        service_name: str | None = None,
        surface_type: SurfaceType | None = None,
        limit: int = 50,
    ) -> list[SurfaceRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if surface_type is not None:
            results = [r for r in results if r.surface_type == surface_type]
        return results[-limit:]

    def add_exposure(
        self,
        exposure_name: str,
        surface_type: SurfaceType = SurfaceType.PUBLIC_API,
        exposure: ExposureLevel = ExposureLevel.INTERNAL,
        severity_score: float = 0.0,
        description: str = "",
    ) -> ExposureDetail:
        detail = ExposureDetail(
            exposure_name=exposure_name,
            surface_type=surface_type,
            exposure=exposure,
            severity_score=severity_score,
            description=description,
        )
        self._exposures.append(detail)
        if len(self._exposures) > self._max_records:
            self._exposures = self._exposures[-self._max_records :]
        logger.info(
            "attack_surface.exposure_added",
            exposure_id=detail.id,
            exposure_name=exposure_name,
            surface_type=surface_type.value,
        )
        return detail

    # -- domain operations -----------------------------------------------

    def analyze_surface_risk(self, service_name: str) -> dict[str, Any]:
        """Analyze attack surface risk for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        critical_count = sum(1 for r in records if r.risk == SurfaceRisk.CRITICAL)
        avg_risk = round(sum(r.risk_score for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total": len(records),
            "avg_risk": avg_risk,
            "meets_threshold": critical_count <= self._max_critical_exposures,
        }

    def identify_critical_exposures(self) -> list[dict[str, Any]]:
        """Find services with >1 CRITICAL or HIGH risk surfaces, sorted desc."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.risk in (SurfaceRisk.CRITICAL, SurfaceRisk.HIGH):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 1:
                results.append({"service_name": svc, "critical_high_count": count})
        results.sort(key=lambda x: x["critical_high_count"], reverse=True)
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Average risk score per service, sorted desc."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service_name, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append({"service_name": svc, "avg_risk_score": avg})
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_surface_expansion(self) -> list[dict[str, Any]]:
        """Detect services with >3 surface records (expanding attack surface)."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append({"service_name": svc, "surface_count": count})
        results.sort(key=lambda x: x["surface_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> AttackSurfaceReport:
        by_type: dict[str, int] = {}
        by_exposure: dict[str, int] = {}
        for r in self._records:
            by_type[r.surface_type.value] = by_type.get(r.surface_type.value, 0) + 1
            by_exposure[r.exposure.value] = by_exposure.get(r.exposure.value, 0) + 1
        avg_risk = (
            round(
                sum(r.risk_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        critical = sum(1 for r in self._records if r.risk == SurfaceRisk.CRITICAL)
        recs: list[str] = []
        if critical > 0:
            recs.append(f"{critical} critical risk surface(s) detected")
        internet_facing = sum(
            1 for r in self._records if r.exposure == ExposureLevel.INTERNET_FACING
        )
        if internet_facing > 0:
            recs.append(f"{internet_facing} internet-facing surface(s) require review")
        if not recs:
            recs.append("Attack surface within acceptable risk levels")
        return AttackSurfaceReport(
            total_surfaces=len(self._records),
            total_exposures=len(self._exposures),
            avg_risk_score=avg_risk,
            by_type=by_type,
            by_exposure=by_exposure,
            critical_count=critical,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._exposures.clear()
        logger.info("attack_surface.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.surface_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_surfaces": len(self._records),
            "total_exposures": len(self._exposures),
            "max_critical_exposures": self._max_critical_exposures,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
