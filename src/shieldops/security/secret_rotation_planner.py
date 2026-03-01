"""Secret Rotation Planner — plan and schedule secret rotations, track compliance."""

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
    API_KEY = "api_key"  # noqa: S105
    DATABASE_CREDENTIAL = "database_credential"  # noqa: S105
    CERTIFICATE = "certificate"
    SSH_KEY = "ssh_key"  # noqa: S105
    ENCRYPTION_KEY = "encryption_key"  # noqa: S105


class RotationStatus(StrEnum):
    ON_SCHEDULE = "on_schedule"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    ROTATING = "rotating"
    COMPLETED = "completed"


class RotationRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


# --- Models ---


class RotationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    secret_id: str = ""
    secret_type: SecretType = SecretType.API_KEY  # noqa: S105
    rotation_status: RotationStatus = RotationStatus.ON_SCHEDULE
    rotation_risk: RotationRisk = RotationRisk.LOW
    days_until_rotation: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RotationSchedule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    secret_id: str = ""
    secret_type: SecretType = SecretType.API_KEY  # noqa: S105
    schedule_days: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecretRotationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_schedules: int = 0
    overdue_count: int = 0
    avg_days_until_rotation: float = 0.0
    by_secret_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_overdue: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecretRotationPlanner:
    """Plan and schedule secret rotations, track rotation compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        max_overdue_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_overdue_pct = max_overdue_pct
        self._records: list[RotationRecord] = []
        self._schedules: list[RotationSchedule] = []
        logger.info(
            "secret_rotation.initialized",
            max_records=max_records,
            max_overdue_pct=max_overdue_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_rotation(
        self,
        secret_id: str,
        secret_type: SecretType = SecretType.API_KEY,  # noqa: S107
        rotation_status: RotationStatus = RotationStatus.ON_SCHEDULE,
        rotation_risk: RotationRisk = RotationRisk.LOW,
        days_until_rotation: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RotationRecord:
        record = RotationRecord(
            secret_id=secret_id,
            secret_type=secret_type,
            rotation_status=rotation_status,
            rotation_risk=rotation_risk,
            days_until_rotation=days_until_rotation,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "secret_rotation.rotation_recorded",
            record_id=record.id,
            secret_id=secret_id,
            secret_type=secret_type.value,
            rotation_status=rotation_status.value,
        )
        return record

    def get_rotation(self, record_id: str) -> RotationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rotations(
        self,
        secret_type: SecretType | None = None,
        status: RotationStatus | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RotationRecord]:
        results = list(self._records)
        if secret_type is not None:
            results = [r for r in results if r.secret_type == secret_type]
        if status is not None:
            results = [r for r in results if r.rotation_status == status]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_schedule(
        self,
        secret_id: str,
        secret_type: SecretType = SecretType.API_KEY,  # noqa: S107
        schedule_days: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RotationSchedule:
        schedule = RotationSchedule(
            secret_id=secret_id,
            secret_type=secret_type,
            schedule_days=schedule_days,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._schedules.append(schedule)
        if len(self._schedules) > self._max_records:
            self._schedules = self._schedules[-self._max_records :]
        logger.info(
            "secret_rotation.schedule_added",
            secret_id=secret_id,
            secret_type=secret_type.value,
            schedule_days=schedule_days,
        )
        return schedule

    # -- domain operations --------------------------------------------------

    def analyze_rotation_compliance(self) -> dict[str, Any]:
        """Group by secret type; return count and avg days until rotation per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.secret_type.value
            type_data.setdefault(key, []).append(r.days_until_rotation)
        result: dict[str, Any] = {}
        for stype, days in type_data.items():
            result[stype] = {
                "count": len(days),
                "avg_days_until_rotation": round(sum(days) / len(days), 2),
            }
        return result

    def identify_overdue_rotations(self) -> list[dict[str, Any]]:
        """Return records where rotation_status is OVERDUE or DUE_SOON."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.rotation_status in (
                RotationStatus.OVERDUE,
                RotationStatus.DUE_SOON,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "secret_id": r.secret_id,
                        "secret_type": r.secret_type.value,
                        "rotation_status": r.rotation_status.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_urgency(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg days until rotation."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.days_until_rotation)
        results: list[dict[str, Any]] = []
        for service, days in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(days),
                    "avg_days_until_rotation": round(sum(days) / len(days), 2),
                }
            )
        results.sort(key=lambda x: x["avg_days_until_rotation"], reverse=True)
        return results

    def detect_rotation_trends(self) -> dict[str, Any]:
        """Split-half on schedule_days; delta threshold 5.0."""
        if len(self._schedules) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [s.schedule_days for s in self._schedules]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> SecretRotationReport:
        by_secret_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_secret_type[r.secret_type.value] = by_secret_type.get(r.secret_type.value, 0) + 1
            by_status[r.rotation_status.value] = by_status.get(r.rotation_status.value, 0) + 1
            by_risk[r.rotation_risk.value] = by_risk.get(r.rotation_risk.value, 0) + 1
        overdue_count = sum(
            1
            for r in self._records
            if r.rotation_status in (RotationStatus.OVERDUE, RotationStatus.DUE_SOON)
        )
        days = [r.days_until_rotation for r in self._records]
        avg_days = round(sum(days) / len(days), 2) if days else 0.0
        rankings = self.rank_by_urgency()
        top_overdue = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        overdue_rate = round(overdue_count / len(self._records) * 100, 2) if self._records else 0.0
        if overdue_rate > self._max_overdue_pct:
            recs.append(
                f"Overdue rotation rate {overdue_rate}% exceeds threshold"
                f" ({self._max_overdue_pct}%)"
            )
        if overdue_count > 0:
            recs.append(f"{overdue_count} overdue rotation(s) detected — schedule immediately")
        if not recs:
            recs.append("Secret rotation compliance is acceptable")
        return SecretRotationReport(
            total_records=len(self._records),
            total_schedules=len(self._schedules),
            overdue_count=overdue_count,
            avg_days_until_rotation=avg_days,
            by_secret_type=by_secret_type,
            by_status=by_status,
            by_risk=by_risk,
            top_overdue=top_overdue,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._schedules.clear()
        logger.info("secret_rotation.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.secret_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_schedules": len(self._schedules),
            "max_overdue_pct": self._max_overdue_pct,
            "secret_type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_secrets": len({r.secret_id for r in self._records}),
        }
