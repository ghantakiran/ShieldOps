"""Automated Response Playbook Engine.

Execute response playbooks based on threat classification.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatClassification(StrEnum):
    MALWARE = "malware"
    PHISHING = "phishing"
    RANSOMWARE = "ransomware"
    DATA_EXFILTRATION = "data_exfiltration"
    INSIDER_THREAT = "insider_threat"
    BRUTE_FORCE = "brute_force"
    DENIAL_OF_SERVICE = "denial_of_service"


class PlaybookStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class PlaybookPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class PlaybookRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    threat_classification: ThreatClassification = ThreatClassification.MALWARE
    status: PlaybookStatus = PlaybookStatus.PENDING
    priority: PlaybookPriority = PlaybookPriority.MEDIUM
    score: float = 0.0
    service: str = ""
    team: str = ""
    steps_total: int = 0
    steps_completed: int = 0
    created_at: float = Field(default_factory=time.time)


class PlaybookExecution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    playbook_id: str = ""
    threat_classification: ThreatClassification = ThreatClassification.MALWARE
    execution_time_ms: float = 0.0
    success: bool = False
    rollback_available: bool = True
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PlaybookReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_playbooks: int = 0
    total_executions: int = 0
    success_rate: float = 0.0
    avg_score: float = 0.0
    by_threat: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    top_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomatedResponsePlaybookEngine:
    """Execute response playbooks automatically based on threat classification."""

    def __init__(
        self,
        max_records: int = 200000,
        score_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._score_threshold = score_threshold
        self._playbooks: list[PlaybookRecord] = []
        self._executions: list[PlaybookExecution] = []
        logger.info(
            "automated_response_playbook_engine.initialized",
            max_records=max_records,
            score_threshold=score_threshold,
        )

    def select_playbook(
        self,
        name: str,
        threat_classification: ThreatClassification = ThreatClassification.MALWARE,
        priority: PlaybookPriority = PlaybookPriority.MEDIUM,
        score: float = 0.0,
        service: str = "",
        team: str = "",
        steps_total: int = 0,
    ) -> PlaybookRecord:
        """Select and register a playbook for a given threat classification."""
        record = PlaybookRecord(
            name=name,
            threat_classification=threat_classification,
            priority=priority,
            score=score,
            service=service,
            team=team,
            steps_total=steps_total,
        )
        self._playbooks.append(record)
        if len(self._playbooks) > self._max_records:
            self._playbooks = self._playbooks[-self._max_records :]
        logger.info(
            "automated_response_playbook_engine.playbook_selected",
            playbook_id=record.id,
            name=name,
            threat=threat_classification.value,
        )
        return record

    def execute_playbook(
        self,
        playbook_id: str,
        execution_time_ms: float = 0.0,
        success: bool = False,
        description: str = "",
    ) -> PlaybookExecution:
        """Record a playbook execution result."""
        threat = ThreatClassification.MALWARE
        for p in self._playbooks:
            if p.id == playbook_id:
                threat = p.threat_classification
                if success:
                    p.status = PlaybookStatus.COMPLETED
                    p.steps_completed = p.steps_total
                else:
                    p.status = PlaybookStatus.FAILED
                break
        execution = PlaybookExecution(
            playbook_id=playbook_id,
            threat_classification=threat,
            execution_time_ms=execution_time_ms,
            success=success,
            description=description,
        )
        self._executions.append(execution)
        if len(self._executions) > self._max_records:
            self._executions = self._executions[-self._max_records :]
        logger.info(
            "automated_response_playbook_engine.executed",
            playbook_id=playbook_id,
            success=success,
        )
        return execution

    def validate_execution(self, playbook_id: str) -> dict[str, Any]:
        """Validate whether a playbook execution completed successfully."""
        execs = [e for e in self._executions if e.playbook_id == playbook_id]
        if not execs:
            return {"valid": False, "reason": "no_executions_found"}
        latest = execs[-1]
        return {
            "valid": latest.success,
            "execution_id": latest.id,
            "execution_time_ms": latest.execution_time_ms,
            "reason": "success" if latest.success else "execution_failed",
        }

    def rollback_playbook(self, playbook_id: str) -> dict[str, Any]:
        """Roll back a playbook execution."""
        for p in self._playbooks:
            if p.id == playbook_id:
                p.status = PlaybookStatus.ROLLED_BACK
                logger.info(
                    "automated_response_playbook_engine.rolled_back",
                    playbook_id=playbook_id,
                )
                return {"status": "rolled_back", "playbook_id": playbook_id}
        return {"status": "not_found", "playbook_id": playbook_id}

    def get_playbook_effectiveness(self) -> dict[str, Any]:
        """Compute effectiveness metrics across all playbooks."""
        if not self._playbooks:
            return {"total": 0, "avg_score": 0.0, "success_rate": 0.0}
        scores = [p.score for p in self._playbooks]
        avg_score = round(sum(scores) / len(scores), 2)
        completed = sum(1 for p in self._playbooks if p.status == PlaybookStatus.COMPLETED)
        success_rate = round(completed / len(self._playbooks) * 100, 2)
        by_threat: dict[str, list[float]] = {}
        for p in self._playbooks:
            by_threat.setdefault(p.threat_classification.value, []).append(p.score)
        threat_avg = {k: round(sum(v) / len(v), 2) for k, v in by_threat.items()}
        return {
            "total": len(self._playbooks),
            "avg_score": avg_score,
            "success_rate": success_rate,
            "by_threat_avg_score": threat_avg,
        }

    def list_playbooks(
        self,
        threat_classification: ThreatClassification | None = None,
        status: PlaybookStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PlaybookRecord]:
        """List playbooks with optional filters."""
        results = list(self._playbooks)
        if threat_classification is not None:
            results = [r for r in results if r.threat_classification == threat_classification]
        if status is not None:
            results = [r for r in results if r.status == status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def generate_report(self) -> PlaybookReport:
        """Generate a comprehensive playbook report."""
        by_threat: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for p in self._playbooks:
            by_threat[p.threat_classification.value] = (
                by_threat.get(p.threat_classification.value, 0) + 1
            )
            by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
            by_priority[p.priority.value] = by_priority.get(p.priority.value, 0) + 1
        scores = [p.score for p in self._playbooks]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        success_count = sum(1 for e in self._executions if e.success)
        success_rate = (
            round(success_count / len(self._executions) * 100, 2) if self._executions else 0.0
        )
        issues = [p.name for p in self._playbooks if p.score < self._score_threshold][:5]
        recs: list[str] = []
        if issues:
            recs.append(f"{len(issues)} playbook(s) below score threshold")
        if avg_score < self._score_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._score_threshold})")
        if not recs:
            recs.append("Playbook metrics within healthy range")
        return PlaybookReport(
            total_playbooks=len(self._playbooks),
            total_executions=len(self._executions),
            success_rate=success_rate,
            avg_score=avg_score,
            by_threat=by_threat,
            by_status=by_status,
            by_priority=by_priority,
            top_issues=issues,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dist: dict[str, int] = {}
        for p in self._playbooks:
            key = p.threat_classification.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_playbooks": len(self._playbooks),
            "total_executions": len(self._executions),
            "score_threshold": self._score_threshold,
            "threat_distribution": dist,
            "unique_teams": len({p.team for p in self._playbooks}),
            "unique_services": len({p.service for p in self._playbooks}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._playbooks.clear()
        self._executions.clear()
        logger.info("automated_response_playbook_engine.cleared")
        return {"status": "cleared"}
