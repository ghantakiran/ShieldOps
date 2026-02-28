"""Recovery Coordinator — orchestrate multi-service recovery after outages."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RecoveryPhase(StrEnum):
    ASSESSMENT = "assessment"
    CONTAINMENT = "containment"
    RESTORATION = "restoration"
    VERIFICATION = "verification"
    POST_RECOVERY = "post_recovery"


class RecoveryStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class RecoveryPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DEFERRED = "deferred"


# --- Models ---


class RecoveryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    recovery_phase: RecoveryPhase = RecoveryPhase.ASSESSMENT
    recovery_status: RecoveryStatus = RecoveryStatus.PENDING
    recovery_priority: RecoveryPriority = RecoveryPriority.HIGH
    affected_services: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RecoveryMilestone(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    milestone_name: str = ""
    recovery_phase: RecoveryPhase = RecoveryPhase.RESTORATION
    recovery_status: RecoveryStatus = RecoveryStatus.IN_PROGRESS
    duration_seconds: float = 0.0
    created_at: float = Field(default_factory=time.time)


class RecoveryCoordinatorReport(BaseModel):
    total_recoveries: int = 0
    total_milestones: int = 0
    completion_rate_pct: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    escalation_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RecoveryCoordinator:
    """Orchestrate multi-service recovery after outages."""

    def __init__(
        self,
        max_records: int = 200000,
        max_recovery_hours: float = 24.0,
    ) -> None:
        self._max_records = max_records
        self._max_recovery_hours = max_recovery_hours
        self._records: list[RecoveryRecord] = []
        self._milestones: list[RecoveryMilestone] = []
        logger.info(
            "recovery_coordinator.initialized",
            max_records=max_records,
            max_recovery_hours=max_recovery_hours,
        )

    # -- record / get / list ---------------------------------------------

    def record_recovery(
        self,
        incident_id: str,
        recovery_phase: RecoveryPhase = RecoveryPhase.ASSESSMENT,
        recovery_status: RecoveryStatus = RecoveryStatus.PENDING,
        recovery_priority: RecoveryPriority = RecoveryPriority.HIGH,
        affected_services: int = 0,
        details: str = "",
    ) -> RecoveryRecord:
        record = RecoveryRecord(
            incident_id=incident_id,
            recovery_phase=recovery_phase,
            recovery_status=recovery_status,
            recovery_priority=recovery_priority,
            affected_services=affected_services,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "recovery_coordinator.recovery_recorded",
            record_id=record.id,
            incident_id=incident_id,
            recovery_status=recovery_status.value,
        )
        return record

    def get_recovery(self, record_id: str) -> RecoveryRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_recoveries(
        self,
        incident_id: str | None = None,
        recovery_status: RecoveryStatus | None = None,
        limit: int = 50,
    ) -> list[RecoveryRecord]:
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if recovery_status is not None:
            results = [r for r in results if r.recovery_status == recovery_status]
        return results[-limit:]

    def add_milestone(
        self,
        milestone_name: str,
        recovery_phase: RecoveryPhase = RecoveryPhase.RESTORATION,
        recovery_status: RecoveryStatus = RecoveryStatus.IN_PROGRESS,
        duration_seconds: float = 0.0,
    ) -> RecoveryMilestone:
        milestone = RecoveryMilestone(
            milestone_name=milestone_name,
            recovery_phase=recovery_phase,
            recovery_status=recovery_status,
            duration_seconds=duration_seconds,
        )
        self._milestones.append(milestone)
        if len(self._milestones) > self._max_records:
            self._milestones = self._milestones[-self._max_records :]
        logger.info(
            "recovery_coordinator.milestone_added",
            milestone_name=milestone_name,
            recovery_status=recovery_status.value,
        )
        return milestone

    # -- domain operations -----------------------------------------------

    def analyze_recovery_speed(self, incident_id: str) -> dict[str, Any]:
        """Analyze average recovery duration for an incident and check threshold."""
        inc_records = [r for r in self._records if r.incident_id == incident_id]
        if not inc_records:
            return {"incident_id": incident_id, "status": "no_data"}
        completed = sum(1 for r in inc_records if r.recovery_status == RecoveryStatus.COMPLETED)
        completion_rate = round((completed / len(inc_records)) * 100, 2)
        avg_services = round(sum(r.affected_services for r in inc_records) / len(inc_records), 2)
        return {
            "incident_id": incident_id,
            "completion_rate": completion_rate,
            "record_count": len(inc_records),
            "avg_affected_services": avg_services,
            "max_recovery_hours": self._max_recovery_hours,
        }

    def identify_stalled_recoveries(self) -> list[dict[str, Any]]:
        """Find incidents with more than one FAILED or ESCALATED recovery."""
        inc_counts: dict[str, int] = {}
        for r in self._records:
            if r.recovery_status in (RecoveryStatus.FAILED, RecoveryStatus.ESCALATED):
                inc_counts[r.incident_id] = inc_counts.get(r.incident_id, 0) + 1
        results: list[dict[str, Any]] = []
        for inc, count in inc_counts.items():
            if count > 1:
                results.append({"incident_id": inc, "stalled_count": count})
        results.sort(key=lambda x: x["stalled_count"], reverse=True)
        return results

    def rank_by_recovery_time(self) -> list[dict[str, Any]]:
        """Rank incidents by average affected services descending."""
        inc_services: dict[str, list[int]] = {}
        for r in self._records:
            inc_services.setdefault(r.incident_id, []).append(r.affected_services)
        results: list[dict[str, Any]] = []
        for inc, services in inc_services.items():
            avg = round(sum(services) / len(services), 2)
            results.append(
                {
                    "incident_id": inc,
                    "avg_affected_services": avg,
                    "record_count": len(services),
                }
            )
        results.sort(key=lambda x: x["avg_affected_services"], reverse=True)
        return results

    def detect_recovery_regressions(self) -> list[dict[str, Any]]:
        """Detect incidents with more than 3 recovery records."""
        inc_counts: dict[str, int] = {}
        for r in self._records:
            inc_counts[r.incident_id] = inc_counts.get(r.incident_id, 0) + 1
        results: list[dict[str, Any]] = []
        for inc, count in inc_counts.items():
            if count > 3:
                results.append({"incident_id": inc, "record_count": count})
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RecoveryCoordinatorReport:
        by_phase: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_phase[r.recovery_phase.value] = by_phase.get(r.recovery_phase.value, 0) + 1
            by_status[r.recovery_status.value] = by_status.get(r.recovery_status.value, 0) + 1
        completed = sum(1 for r in self._records if r.recovery_status == RecoveryStatus.COMPLETED)
        completion_rate = round((completed / len(self._records)) * 100, 2) if self._records else 0.0
        escalation_count = sum(
            1 for r in self._records if r.recovery_status == RecoveryStatus.ESCALATED
        )
        recs: list[str] = []
        if escalation_count > 0:
            recs.append(f"{escalation_count} recovery(ies) escalated")
        failed_count = sum(1 for r in self._records if r.recovery_status == RecoveryStatus.FAILED)
        if failed_count > 0:
            recs.append(f"{failed_count} recovery(ies) failed")
        if not recs:
            recs.append("Recovery coordination is healthy")
        return RecoveryCoordinatorReport(
            total_recoveries=len(self._records),
            total_milestones=len(self._milestones),
            completion_rate_pct=completion_rate,
            by_phase=by_phase,
            by_status=by_status,
            escalation_count=escalation_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._milestones.clear()
        logger.info("recovery_coordinator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.recovery_phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_recoveries": len(self._records),
            "total_milestones": len(self._milestones),
            "max_recovery_hours": self._max_recovery_hours,
            "phase_distribution": phase_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
