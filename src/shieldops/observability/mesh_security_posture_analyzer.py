"""Mesh Security Posture Analyzer.

Assess mTLS coverage, detect authorization gaps,
and monitor certificate health in service meshes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MtlsStatus(StrEnum):
    ENFORCED = "enforced"
    PERMISSIVE = "permissive"
    DISABLED = "disabled"
    MIXED = "mixed"


class AuthzGapSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CertHealth(StrEnum):
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    INVALID = "invalid"


# --- Models ---


class SecurityPostureRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    mesh_name: str = ""
    mtls_status: MtlsStatus = MtlsStatus.ENFORCED
    authz_gap_severity: AuthzGapSeverity = AuthzGapSeverity.LOW
    cert_health: CertHealth = CertHealth.VALID
    policy_count: int = 0
    days_to_expiry: int = 365
    open_ports: int = 0
    created_at: float = Field(default_factory=time.time)


class SecurityPostureAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    is_secure: bool = True
    has_authz_gap: bool = False
    cert_risk: bool = False
    posture_score: float = 100.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecurityPostureReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_posture_score: float = 0.0
    by_mtls_status: dict[str, int] = Field(default_factory=dict)
    by_authz_gap_severity: dict[str, int] = Field(default_factory=dict)
    by_cert_health: dict[str, int] = Field(default_factory=dict)
    insecure_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MeshSecurityPostureAnalyzer:
    """Assess mTLS coverage, detect authorization gaps,
    monitor certificate health."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SecurityPostureRecord] = []
        self._analyses: dict[str, SecurityPostureAnalysis] = {}
        logger.info(
            "mesh_security_posture_analyzer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        service: str = "",
        mesh_name: str = "",
        mtls_status: MtlsStatus = (MtlsStatus.ENFORCED),
        authz_gap_severity: AuthzGapSeverity = (AuthzGapSeverity.LOW),
        cert_health: CertHealth = CertHealth.VALID,
        policy_count: int = 0,
        days_to_expiry: int = 365,
        open_ports: int = 0,
    ) -> SecurityPostureRecord:
        record = SecurityPostureRecord(
            service=service,
            mesh_name=mesh_name,
            mtls_status=mtls_status,
            authz_gap_severity=authz_gap_severity,
            cert_health=cert_health,
            policy_count=policy_count,
            days_to_expiry=days_to_expiry,
            open_ports=open_ports,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_posture.record_added",
            record_id=record.id,
            service=service,
        )
        return record

    def process(self, key: str) -> SecurityPostureAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_secure = rec.mtls_status == MtlsStatus.ENFORCED and rec.cert_health == CertHealth.VALID
        has_gap = rec.authz_gap_severity in (
            AuthzGapSeverity.CRITICAL,
            AuthzGapSeverity.HIGH,
        )
        cert_risk = rec.cert_health in (
            CertHealth.EXPIRED,
            CertHealth.EXPIRING_SOON,
        )
        score = 100.0
        if not is_secure:
            score -= 30.0
        if has_gap:
            score -= 30.0
        if cert_risk:
            score -= 20.0
        analysis = SecurityPostureAnalysis(
            service=rec.service,
            is_secure=is_secure,
            has_authz_gap=has_gap,
            cert_risk=cert_risk,
            posture_score=round(score, 2),
            description=(f"Service {rec.service} posture score {score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> SecurityPostureReport:
        by_ms: dict[str, int] = {}
        by_ag: dict[str, int] = {}
        by_ch: dict[str, int] = {}
        for r in self._records:
            k = r.mtls_status.value
            by_ms[k] = by_ms.get(k, 0) + 1
            k2 = r.authz_gap_severity.value
            by_ag[k2] = by_ag.get(k2, 0) + 1
            k3 = r.cert_health.value
            by_ch[k3] = by_ch.get(k3, 0) + 1
        insecure = list({r.service for r in self._records if r.mtls_status != MtlsStatus.ENFORCED})[
            :10
        ]
        total_score = 0.0
        for r in self._records:
            s = 100.0
            if r.mtls_status != MtlsStatus.ENFORCED:
                s -= 30.0
            if r.authz_gap_severity in (
                AuthzGapSeverity.CRITICAL,
                AuthzGapSeverity.HIGH,
            ):
                s -= 30.0
            total_score += s
        avg = (
            round(
                total_score / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        recs: list[str] = []
        if insecure:
            recs.append(f"{len(insecure)} insecure services")
        if not recs:
            recs.append("Security posture healthy")
        return SecurityPostureReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_posture_score=avg,
            by_mtls_status=by_ms,
            by_authz_gap_severity=by_ag,
            by_cert_health=by_ch,
            insecure_services=insecure,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.mtls_status.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "mtls_status_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("mesh_security_posture_analyzer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def assess_mtls_coverage(
        self,
    ) -> list[dict[str, Any]]:
        """Assess mTLS coverage per mesh."""
        mesh_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            mesh_data.setdefault(r.mesh_name, {})
            s = r.mtls_status.value
            mesh_data[r.mesh_name][s] = mesh_data[r.mesh_name].get(s, 0) + 1
        results: list[dict[str, Any]] = []
        for mesh, statuses in mesh_data.items():
            total = sum(statuses.values())
            enforced = statuses.get("enforced", 0)
            coverage = round(enforced / max(total, 1) * 100, 2)
            results.append(
                {
                    "mesh_name": mesh,
                    "coverage_pct": coverage,
                    "status_counts": statuses,
                }
            )
        results.sort(
            key=lambda x: x["coverage_pct"],
            reverse=True,
        )
        return results

    def detect_authorization_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with authorization gaps."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.authz_gap_severity
                in (
                    AuthzGapSeverity.CRITICAL,
                    AuthzGapSeverity.HIGH,
                )
                and r.service not in seen
            ):
                seen.add(r.service)
                results.append(
                    {
                        "service": r.service,
                        "mesh_name": r.mesh_name,
                        "severity": (r.authz_gap_severity.value),
                        "policy_count": (r.policy_count),
                    }
                )
        results.sort(
            key=lambda x: x["policy_count"],
        )
        return results

    def monitor_certificate_health(
        self,
    ) -> list[dict[str, Any]]:
        """Monitor certificate health per service."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.cert_health
                in (
                    CertHealth.EXPIRED,
                    CertHealth.EXPIRING_SOON,
                    CertHealth.INVALID,
                )
                and r.service not in seen
            ):
                seen.add(r.service)
                results.append(
                    {
                        "service": r.service,
                        "cert_health": (r.cert_health.value),
                        "days_to_expiry": (r.days_to_expiry),
                        "mesh_name": r.mesh_name,
                    }
                )
        results.sort(
            key=lambda x: x["days_to_expiry"],
        )
        return results
