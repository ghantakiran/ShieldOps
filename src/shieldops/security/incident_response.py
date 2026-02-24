"""Security Incident Response Tracker — security incident lifecycle, containment, forensics."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SecurityIncidentType(StrEnum):
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_BREACH = "data_breach"
    MALWARE = "malware"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    INSIDER_THREAT = "insider_threat"
    DDOS = "ddos"


class ContainmentStatus(StrEnum):
    DETECTED = "detected"
    ANALYZING = "analyzing"
    CONTAINING = "containing"
    CONTAINED = "contained"
    ERADICATED = "eradicated"
    RECOVERED = "recovered"


class EvidenceType(StrEnum):
    LOG_ENTRY = "log_entry"
    NETWORK_CAPTURE = "network_capture"
    MEMORY_DUMP = "memory_dump"
    FILESYSTEM_ARTIFACT = "filesystem_artifact"
    ACCESS_LOG = "access_log"
    CONFIGURATION_CHANGE = "configuration_change"


# --- Models ---


class SecurityIncident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_type: SecurityIncidentType = SecurityIncidentType.UNAUTHORIZED_ACCESS
    title: str = ""
    description: str = ""
    severity: str = "medium"
    status: ContainmentStatus = ContainmentStatus.DETECTED
    assigned_to: str = ""
    services_affected: list[str] = Field(default_factory=list)
    containment_actions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    escalated: bool = False
    closed: bool = False
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ContainmentAction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    action: str = ""
    performed_by: str = ""
    outcome: str = "pending"
    performed_at: float = Field(default_factory=time.time)


class ForensicEvidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    evidence_type: EvidenceType = EvidenceType.LOG_ENTRY
    description: str = ""
    source: str = ""
    hash_value: str = ""
    collected_by: str = ""
    collected_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityIncidentResponseTracker:
    """Security incident lifecycle, containment actions, evidence chain, forensic timeline."""

    def __init__(
        self,
        max_incidents: int = 50000,
        auto_escalate_minutes: int = 30,
    ) -> None:
        self._max_incidents = max_incidents
        self._auto_escalate_minutes = auto_escalate_minutes
        self._incidents: list[SecurityIncident] = []
        self._actions: list[ContainmentAction] = []
        self._evidence: list[ForensicEvidence] = []
        logger.info(
            "security_incident.initialized",
            max_incidents=max_incidents,
            auto_escalate_minutes=auto_escalate_minutes,
        )

    def create_incident(
        self,
        incident_type: SecurityIncidentType = SecurityIncidentType.UNAUTHORIZED_ACCESS,
        title: str = "",
        description: str = "",
        severity: str = "medium",
        assigned_to: str = "",
        services_affected: list[str] | None = None,
    ) -> SecurityIncident:
        incident = SecurityIncident(
            incident_type=incident_type,
            title=title,
            description=description,
            severity=severity,
            assigned_to=assigned_to,
            services_affected=services_affected or [],
        )
        self._incidents.append(incident)
        if len(self._incidents) > self._max_incidents:
            self._incidents = self._incidents[-self._max_incidents :]
        logger.info(
            "security_incident.created",
            incident_id=incident.id,
            incident_type=incident_type,
            severity=severity,
        )
        return incident

    def get_incident(self, incident_id: str) -> SecurityIncident | None:
        for i in self._incidents:
            if i.id == incident_id:
                return i
        return None

    def list_incidents(
        self,
        incident_type: SecurityIncidentType | None = None,
        status: ContainmentStatus | None = None,
        limit: int = 100,
    ) -> list[SecurityIncident]:
        results = list(self._incidents)
        if incident_type is not None:
            results = [i for i in results if i.incident_type == incident_type]
        if status is not None:
            results = [i for i in results if i.status == status]
        return results[-limit:]

    def add_containment_action(
        self,
        incident_id: str,
        action: str,
        performed_by: str = "",
        outcome: str = "pending",
    ) -> ContainmentAction | None:
        incident = self.get_incident(incident_id)
        if incident is None:
            return None
        ca = ContainmentAction(
            incident_id=incident_id,
            action=action,
            performed_by=performed_by,
            outcome=outcome,
        )
        self._actions.append(ca)
        incident.containment_actions.append(ca.id)
        incident.updated_at = time.time()
        if incident.status == ContainmentStatus.DETECTED:
            incident.status = ContainmentStatus.CONTAINING
        logger.info(
            "security_incident.action_added",
            incident_id=incident_id,
            action_id=ca.id,
        )
        return ca

    def collect_evidence(
        self,
        incident_id: str,
        evidence_type: EvidenceType = EvidenceType.LOG_ENTRY,
        description: str = "",
        source: str = "",
        hash_value: str = "",
        collected_by: str = "",
    ) -> ForensicEvidence | None:
        incident = self.get_incident(incident_id)
        if incident is None:
            return None
        ev = ForensicEvidence(
            incident_id=incident_id,
            evidence_type=evidence_type,
            description=description,
            source=source,
            hash_value=hash_value,
            collected_by=collected_by,
        )
        self._evidence.append(ev)
        incident.evidence_ids.append(ev.id)
        incident.updated_at = time.time()
        logger.info(
            "security_incident.evidence_collected",
            incident_id=incident_id,
            evidence_id=ev.id,
        )
        return ev

    def escalate_incident(self, incident_id: str) -> bool:
        incident = self.get_incident(incident_id)
        if incident is None:
            return False
        incident.escalated = True
        incident.updated_at = time.time()
        logger.info("security_incident.escalated", incident_id=incident_id)
        return True

    def close_incident(self, incident_id: str) -> bool:
        incident = self.get_incident(incident_id)
        if incident is None:
            return False
        incident.closed = True
        incident.status = ContainmentStatus.RECOVERED
        incident.updated_at = time.time()
        logger.info("security_incident.closed", incident_id=incident_id)
        return True

    def get_timeline(self, incident_id: str) -> list[dict[str, Any]]:
        actions = [a for a in self._actions if a.incident_id == incident_id]
        evidence = [e for e in self._evidence if e.incident_id == incident_id]
        timeline: list[dict[str, Any]] = []
        for a in actions:
            timeline.append(
                {
                    "type": "containment_action",
                    "id": a.id,
                    "action": a.action,
                    "outcome": a.outcome,
                    "timestamp": a.performed_at,
                }
            )
        for e in evidence:
            timeline.append(
                {
                    "type": "evidence",
                    "id": e.id,
                    "evidence_type": e.evidence_type.value,
                    "description": e.description,
                    "timestamp": e.collected_at,
                }
            )
        timeline.sort(key=lambda t: t["timestamp"])
        return timeline

    def get_active_incidents(self) -> list[SecurityIncident]:
        return [i for i in self._incidents if not i.closed]

    def get_stats(self) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        active = 0
        escalated = 0
        for i in self._incidents:
            type_counts[i.incident_type] = type_counts.get(i.incident_type, 0) + 1
            status_counts[i.status] = status_counts.get(i.status, 0) + 1
            if not i.closed:
                active += 1
            if i.escalated:
                escalated += 1
        return {
            "total_incidents": len(self._incidents),
            "active_incidents": active,
            "escalated_incidents": escalated,
            "total_actions": len(self._actions),
            "total_evidence": len(self._evidence),
            "type_distribution": type_counts,
            "status_distribution": status_counts,
        }
