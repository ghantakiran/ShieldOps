"""War Room Orchestrator — coordinate incident war rooms with role assignment."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WarRoomRole(StrEnum):
    INCIDENT_COMMANDER = "incident_commander"
    COMMUNICATIONS_LEAD = "communications_lead"
    TECHNICAL_LEAD = "technical_lead"
    SCRIBE = "scribe"
    OBSERVER = "observer"


class WarRoomStatus(StrEnum):
    ASSEMBLING = "assembling"
    ACTIVE = "active"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    POST_MORTEM = "post_mortem"


class WarRoomPriority(StrEnum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"
    SEV5 = "sev5"


# --- Models ---


class WarRoomRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_name: str = ""
    role: WarRoomRole = WarRoomRole.INCIDENT_COMMANDER
    status: WarRoomStatus = WarRoomStatus.ASSEMBLING
    priority: WarRoomPriority = WarRoomPriority.SEV3
    participant_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class WarRoomTemplate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    template_name: str = ""
    role: WarRoomRole = WarRoomRole.INCIDENT_COMMANDER
    priority: WarRoomPriority = WarRoomPriority.SEV3
    auto_escalate: bool = True
    escalation_minutes: float = 30.0
    created_at: float = Field(default_factory=time.time)


class WarRoomOrchestratorReport(BaseModel):
    total_war_rooms: int = 0
    total_templates: int = 0
    active_rate_pct: float = 0.0
    by_role: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    escalation_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentWarRoomOrchestrator:
    """Coordinate incident war rooms with role assignment."""

    def __init__(
        self,
        max_records: int = 200000,
        min_resolution_rate_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_resolution_rate_pct = min_resolution_rate_pct
        self._records: list[WarRoomRecord] = []
        self._templates: list[WarRoomTemplate] = []
        logger.info(
            "war_room_orchestrator.initialized",
            max_records=max_records,
            min_resolution_rate_pct=min_resolution_rate_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_war_room(
        self,
        incident_name: str,
        role: WarRoomRole = WarRoomRole.INCIDENT_COMMANDER,
        status: WarRoomStatus = WarRoomStatus.ASSEMBLING,
        priority: WarRoomPriority = WarRoomPriority.SEV3,
        participant_count: int = 0,
        details: str = "",
    ) -> WarRoomRecord:
        record = WarRoomRecord(
            incident_name=incident_name,
            role=role,
            status=status,
            priority=priority,
            participant_count=participant_count,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "war_room_orchestrator.recorded",
            record_id=record.id,
            incident_name=incident_name,
            role=role.value,
            status=status.value,
        )
        return record

    def get_war_room(self, record_id: str) -> WarRoomRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_war_rooms(
        self,
        incident_name: str | None = None,
        role: WarRoomRole | None = None,
        limit: int = 50,
    ) -> list[WarRoomRecord]:
        results = list(self._records)
        if incident_name is not None:
            results = [r for r in results if r.incident_name == incident_name]
        if role is not None:
            results = [r for r in results if r.role == role]
        return results[-limit:]

    def add_template(
        self,
        template_name: str,
        role: WarRoomRole = WarRoomRole.INCIDENT_COMMANDER,
        priority: WarRoomPriority = WarRoomPriority.SEV3,
        auto_escalate: bool = True,
        escalation_minutes: float = 30.0,
    ) -> WarRoomTemplate:
        template = WarRoomTemplate(
            template_name=template_name,
            role=role,
            priority=priority,
            auto_escalate=auto_escalate,
            escalation_minutes=escalation_minutes,
        )
        self._templates.append(template)
        if len(self._templates) > self._max_records:
            self._templates = self._templates[-self._max_records :]
        logger.info(
            "war_room_orchestrator.template_added",
            template_name=template_name,
            role=role.value,
            priority=priority.value,
        )
        return template

    # -- domain operations -------------------------------------------

    def analyze_war_room_effectiveness(self, incident_name: str) -> dict[str, Any]:
        """Analyze war room effectiveness for an incident."""
        records = [r for r in self._records if r.incident_name == incident_name]
        if not records:
            return {
                "incident_name": incident_name,
                "status": "no_data",
            }
        resolved = sum(1 for r in records if r.status == WarRoomStatus.RESOLVED)
        resolution_rate = round(resolved / len(records) * 100, 2)
        avg_participants = round(
            sum(r.participant_count for r in records) / len(records),
            2,
        )
        return {
            "incident_name": incident_name,
            "war_room_count": len(records),
            "resolved_count": resolved,
            "resolution_rate": resolution_rate,
            "avg_participant_count": avg_participants,
            "meets_threshold": (resolution_rate >= self._min_resolution_rate_pct),
        }

    def identify_stalled_war_rooms(
        self,
    ) -> list[dict[str, Any]]:
        """Find incidents with stalled (non-resolved) war rooms."""
        stall_counts: dict[str, int] = {}
        for r in self._records:
            if r.status != WarRoomStatus.RESOLVED:
                stall_counts[r.incident_name] = stall_counts.get(r.incident_name, 0) + 1
        results: list[dict[str, Any]] = []
        for inc, count in stall_counts.items():
            if count > 1:
                results.append(
                    {
                        "incident_name": inc,
                        "stalled_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["stalled_count"],
            reverse=True,
        )
        return results

    def rank_by_participant_count(
        self,
    ) -> list[dict[str, Any]]:
        """Rank incidents by avg participant count desc."""
        totals: dict[str, list[int]] = {}
        for r in self._records:
            totals.setdefault(r.incident_name, []).append(r.participant_count)
        results: list[dict[str, Any]] = []
        for inc, counts in totals.items():
            avg = round(sum(counts) / len(counts), 2)
            results.append(
                {
                    "incident_name": inc,
                    "avg_participant_count": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_participant_count"],
            reverse=True,
        )
        return results

    def detect_escalation_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Detect incidents with escalation patterns (>3)."""
        non_resolved: dict[str, int] = {}
        for r in self._records:
            if r.status != WarRoomStatus.RESOLVED:
                non_resolved[r.incident_name] = non_resolved.get(r.incident_name, 0) + 1
        results: list[dict[str, Any]] = []
        for inc, count in non_resolved.items():
            if count > 3:
                results.append(
                    {
                        "incident_name": inc,
                        "non_resolved_count": count,
                        "escalation_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_resolved_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> WarRoomOrchestratorReport:
        by_role: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_role[r.role.value] = by_role.get(r.role.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        resolved = sum(1 for r in self._records if r.status == WarRoomStatus.RESOLVED)
        active_rate = round(resolved / len(self._records) * 100, 2) if self._records else 0.0
        stalled = sum(1 for d in self.identify_stalled_war_rooms())
        recs: list[str] = []
        if active_rate < self._min_resolution_rate_pct:
            recs.append(
                f"Resolution rate {active_rate}% is below "
                f"{self._min_resolution_rate_pct}% "
                f"threshold"
            )
        if stalled > 0:
            recs.append(f"{stalled} incident(s) with stalled war rooms")
        esc = len(self.detect_escalation_patterns())
        if esc > 0:
            recs.append(f"{esc} incident(s) with escalation patterns")
        if not recs:
            recs.append("War room orchestration is healthy")
        return WarRoomOrchestratorReport(
            total_war_rooms=len(self._records),
            total_templates=len(self._templates),
            active_rate_pct=active_rate,
            by_role=by_role,
            by_status=by_status,
            escalation_count=esc,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._templates.clear()
        logger.info("war_room_orchestrator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        role_dist: dict[str, int] = {}
        for r in self._records:
            key = r.role.value
            role_dist[key] = role_dist.get(key, 0) + 1
        return {
            "total_war_rooms": len(self._records),
            "total_templates": len(self._templates),
            "min_resolution_rate_pct": (self._min_resolution_rate_pct),
            "role_distribution": role_dist,
            "unique_incidents": len({r.incident_name for r in self._records}),
        }
