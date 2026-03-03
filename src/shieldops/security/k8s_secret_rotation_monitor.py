"""K8s Secret Rotation Monitor — monitor Kubernetes secret rotation status and compliance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SecretType(StrEnum):
    TLS_CERT = "tls_cert"
    API_KEY = "api_key"
    DATABASE_CRED = "database_cred"
    TOKEN = "token"  # noqa: S105
    CUSTOM = "custom"


class RotationStatus(StrEnum):
    CURRENT = "current"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    ROTATING = "rotating"
    FAILED = "failed"


class RotationPolicy(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"
    DISABLED = "disabled"


# --- Models ---


class SecretRotationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rotation_id: str = ""
    secret_type: SecretType = SecretType.TLS_CERT
    rotation_status: RotationStatus = RotationStatus.CURRENT
    rotation_policy: RotationPolicy = RotationPolicy.AUTOMATIC
    rotation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SecretRotationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rotation_id: str = ""
    secret_type: SecretType = SecretType.TLS_CERT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class K8sSecretRotationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_rotation_score: float = 0.0
    by_secret_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_policy: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class K8sSecretRotationMonitor:
    """Monitor Kubernetes secret rotation status, expiry, and compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        rotation_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._rotation_gap_threshold = rotation_gap_threshold
        self._records: list[SecretRotationRecord] = []
        self._analyses: list[SecretRotationAnalysis] = []
        logger.info(
            "k8s_secret_rotation_monitor.initialized",
            max_records=max_records,
            rotation_gap_threshold=rotation_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_rotation(
        self,
        rotation_id: str,
        secret_type: SecretType = SecretType.TLS_CERT,
        rotation_status: RotationStatus = RotationStatus.CURRENT,
        rotation_policy: RotationPolicy = RotationPolicy.AUTOMATIC,
        rotation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SecretRotationRecord:
        record = SecretRotationRecord(
            rotation_id=rotation_id,
            secret_type=secret_type,
            rotation_status=rotation_status,
            rotation_policy=rotation_policy,
            rotation_score=rotation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "k8s_secret_rotation_monitor.rotation_recorded",
            record_id=record.id,
            rotation_id=rotation_id,
            secret_type=secret_type.value,
            rotation_status=rotation_status.value,
        )
        return record

    def get_rotation(self, record_id: str) -> SecretRotationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rotations(
        self,
        secret_type: SecretType | None = None,
        rotation_status: RotationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SecretRotationRecord]:
        results = list(self._records)
        if secret_type is not None:
            results = [r for r in results if r.secret_type == secret_type]
        if rotation_status is not None:
            results = [r for r in results if r.rotation_status == rotation_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        rotation_id: str,
        secret_type: SecretType = SecretType.TLS_CERT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SecretRotationAnalysis:
        analysis = SecretRotationAnalysis(
            rotation_id=rotation_id,
            secret_type=secret_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "k8s_secret_rotation_monitor.analysis_added",
            rotation_id=rotation_id,
            secret_type=secret_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_secret_type_distribution(self) -> dict[str, Any]:
        """Group by secret_type; return count and avg rotation_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.secret_type.value
            type_data.setdefault(key, []).append(r.rotation_score)
        result: dict[str, Any] = {}
        for secret_type, scores in type_data.items():
            result[secret_type] = {
                "count": len(scores),
                "avg_rotation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_rotation_gaps(self) -> list[dict[str, Any]]:
        """Return records where rotation_score < rotation_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.rotation_score < self._rotation_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "rotation_id": r.rotation_id,
                        "secret_type": r.secret_type.value,
                        "rotation_score": r.rotation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["rotation_score"])

    def rank_by_rotation(self) -> list[dict[str, Any]]:
        """Group by service, avg rotation_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.rotation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_rotation_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_rotation_score"])
        return results

    def detect_rotation_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> K8sSecretRotationReport:
        by_secret_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_policy: dict[str, int] = {}
        for r in self._records:
            by_secret_type[r.secret_type.value] = by_secret_type.get(r.secret_type.value, 0) + 1
            by_status[r.rotation_status.value] = by_status.get(r.rotation_status.value, 0) + 1
            by_policy[r.rotation_policy.value] = by_policy.get(r.rotation_policy.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.rotation_score < self._rotation_gap_threshold)
        scores = [r.rotation_score for r in self._records]
        avg_rotation_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_rotation_gaps()
        top_gaps = [o["rotation_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} rotation(s) below threshold ({self._rotation_gap_threshold})")
        if self._records and avg_rotation_score < self._rotation_gap_threshold:
            recs.append(
                f"Avg rotation score {avg_rotation_score} below threshold "
                f"({self._rotation_gap_threshold})"
            )
        if not recs:
            recs.append("K8s secret rotation monitoring is healthy")
        return K8sSecretRotationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_rotation_score=avg_rotation_score,
            by_secret_type=by_secret_type,
            by_status=by_status,
            by_policy=by_policy,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("k8s_secret_rotation_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.secret_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "rotation_gap_threshold": self._rotation_gap_threshold,
            "secret_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
