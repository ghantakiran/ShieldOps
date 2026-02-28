"""Credential Rotation Orchestrator — automated credential rotation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CredentialType(StrEnum):
    API_KEY = "api_key"
    DATABASE_PASSWORD = "database_password"  # noqa: S105
    TLS_CERTIFICATE = "tls_certificate"
    SSH_KEY = "ssh_key"
    SERVICE_TOKEN = "service_token"  # noqa: S105


class RotationStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RotationStrategy(StrEnum):
    ZERO_DOWNTIME = "zero_downtime"
    BLUE_GREEN = "blue_green"
    SEQUENTIAL = "sequential"
    IMMEDIATE = "immediate"
    GRADUAL = "gradual"


# --- Models ---


class RotationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    credential_type: CredentialType = CredentialType.API_KEY
    status: RotationStatus = RotationStatus.SCHEDULED
    strategy: RotationStrategy = RotationStrategy.ZERO_DOWNTIME
    duration_seconds: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RotationPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    credential_type: CredentialType = CredentialType.API_KEY
    strategy: RotationStrategy = RotationStrategy.ZERO_DOWNTIME
    rotation_interval_days: int = 90
    max_age_days: float = 180.0
    created_at: float = Field(default_factory=time.time)


class CredentialRotatorReport(BaseModel):
    total_rotations: int = 0
    total_policies: int = 0
    completion_rate_pct: float = 0.0
    by_credential_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    failed_rotation_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CredentialRotationOrchestrator:
    """Automated credential rotation."""

    def __init__(
        self,
        max_records: int = 200000,
        min_completion_rate_pct: float = 95.0,
    ) -> None:
        self._max_records = max_records
        self._min_completion_rate_pct = min_completion_rate_pct
        self._records: list[RotationRecord] = []
        self._policies: list[RotationPolicy] = []
        logger.info(
            "credential_rotator.initialized",
            max_records=max_records,
            min_completion_rate_pct=min_completion_rate_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_rotation(
        self,
        service_name: str,
        credential_type: CredentialType = (CredentialType.API_KEY),
        status: RotationStatus = RotationStatus.SCHEDULED,
        strategy: RotationStrategy = (RotationStrategy.ZERO_DOWNTIME),
        duration_seconds: float = 0.0,
        details: str = "",
    ) -> RotationRecord:
        record = RotationRecord(
            service_name=service_name,
            credential_type=credential_type,
            status=status,
            strategy=strategy,
            duration_seconds=duration_seconds,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "credential_rotator.rotation_recorded",
            record_id=record.id,
            service_name=service_name,
            credential_type=credential_type.value,
            status=status.value,
        )
        return record

    def get_rotation(self, record_id: str) -> RotationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rotations(
        self,
        service_name: str | None = None,
        credential_type: CredentialType | None = None,
        limit: int = 50,
    ) -> list[RotationRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if credential_type is not None:
            results = [r for r in results if r.credential_type == credential_type]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        credential_type: CredentialType = (CredentialType.API_KEY),
        strategy: RotationStrategy = (RotationStrategy.ZERO_DOWNTIME),
        rotation_interval_days: int = 90,
        max_age_days: float = 180.0,
    ) -> RotationPolicy:
        policy = RotationPolicy(
            policy_name=policy_name,
            credential_type=credential_type,
            strategy=strategy,
            rotation_interval_days=rotation_interval_days,
            max_age_days=max_age_days,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "credential_rotator.policy_added",
            policy_name=policy_name,
            credential_type=credential_type.value,
            strategy=strategy.value,
        )
        return policy

    # -- domain operations -------------------------------------------

    def analyze_rotation_health(self, service_name: str) -> dict[str, Any]:
        """Analyze rotation health for a service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {
                "service_name": service_name,
                "status": "no_data",
            }
        completed = sum(1 for r in records if r.status == RotationStatus.COMPLETED)
        completion_rate = round(completed / len(records) * 100, 2)
        avg_dur = round(
            sum(r.duration_seconds for r in records) / len(records),
            2,
        )
        return {
            "service_name": service_name,
            "rotation_count": len(records),
            "completed_count": completed,
            "completion_rate": completion_rate,
            "avg_duration": avg_dur,
            "meets_threshold": (completion_rate >= self._min_completion_rate_pct),
        }

    def identify_failed_rotations(
        self,
    ) -> list[dict[str, Any]]:
        """Find services with repeated rotation failures."""
        fail_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (
                RotationStatus.FAILED,
                RotationStatus.ROLLED_BACK,
            ):
                fail_counts[r.service_name] = fail_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in fail_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "failure_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["failure_count"],
            reverse=True,
        )
        return results

    def rank_by_rotation_frequency(
        self,
    ) -> list[dict[str, Any]]:
        """Rank services by rotation count descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.service_name] = freq.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in freq.items():
            results.append(
                {
                    "service_name": svc,
                    "rotation_count": count,
                }
            )
        results.sort(
            key=lambda x: x["rotation_count"],
            reverse=True,
        )
        return results

    def detect_stale_credentials(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with >3 non-COMPLETED."""
        svc_non: dict[str, int] = {}
        for r in self._records:
            if r.status != RotationStatus.COMPLETED:
                svc_non[r.service_name] = svc_non.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_non.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "non_completed_count": count,
                        "stale_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_completed_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> CredentialRotatorReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.credential_type.value] = by_type.get(r.credential_type.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        completed = sum(1 for r in self._records if r.status == RotationStatus.COMPLETED)
        rate = round(completed / len(self._records) * 100, 2) if self._records else 0.0
        failed_count = sum(1 for d in self.identify_failed_rotations())
        recs: list[str] = []
        if rate < self._min_completion_rate_pct:
            recs.append(
                f"Completion rate {rate}% is below {self._min_completion_rate_pct}% threshold"
            )
        if failed_count > 0:
            recs.append(f"{failed_count} service(s) with failed rotations")
        stale = len(self.detect_stale_credentials())
        if stale > 0:
            recs.append(f"{stale} service(s) with stale credentials")
        if not recs:
            recs.append("Credential rotation health meets targets")
        return CredentialRotatorReport(
            total_rotations=len(self._records),
            total_policies=len(self._policies),
            completion_rate_pct=rate,
            by_credential_type=by_type,
            by_status=by_status,
            failed_rotation_count=failed_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("credential_rotator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.credential_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_rotations": len(self._records),
            "total_policies": len(self._policies),
            "min_completion_rate_pct": (self._min_completion_rate_pct),
            "credential_type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
