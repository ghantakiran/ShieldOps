"""Automated Threat Containment — automatically contain identified threats."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContainmentStrategy(StrEnum):
    ISOLATE_HOST = "isolate_host"
    BLOCK_IP = "block_ip"
    DISABLE_ACCOUNT = "disable_account"
    QUARANTINE_FILE = "quarantine_file"
    RATE_LIMIT = "rate_limit"
    KILL_PROCESS = "kill_process"


class ContainmentResult(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    PENDING = "pending"
    VERIFIED = "verified"


# --- Models ---


class ThreatRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    severity: ThreatSeverity = ThreatSeverity.LOW
    strategy: ContainmentStrategy = ContainmentStrategy.ISOLATE_HOST
    result: ContainmentResult = ContainmentResult.PENDING
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    source_ip: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContainmentAction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_id: str = ""
    strategy: ContainmentStrategy = ContainmentStrategy.ISOLATE_HOST
    result: ContainmentResult = ContainmentResult.PENDING
    duration_ms: float = 0.0
    verified: bool = False
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatContainmentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_threats: int = 0
    total_actions: int = 0
    success_rate: float = 0.0
    avg_risk_score: float = 0.0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    top_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomatedThreatContainment:
    """Automatically contain identified threats."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._threats: list[ThreatRecord] = []
        self._actions: list[ContainmentAction] = []
        logger.info(
            "automated_threat_containment.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    def assess_threat(
        self,
        name: str,
        severity: ThreatSeverity = ThreatSeverity.LOW,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
        source_ip: str = "",
        description: str = "",
    ) -> ThreatRecord:
        """Assess and record a threat."""
        strategy = self._select_default_strategy(severity)
        record = ThreatRecord(
            name=name,
            severity=severity,
            strategy=strategy,
            risk_score=risk_score,
            service=service,
            team=team,
            source_ip=source_ip,
            description=description,
        )
        self._threats.append(record)
        if len(self._threats) > self._max_records:
            self._threats = self._threats[-self._max_records :]
        logger.info(
            "automated_threat_containment.threat_assessed",
            threat_id=record.id,
            name=name,
            severity=severity.value,
        )
        return record

    @staticmethod
    def _select_default_strategy(severity: ThreatSeverity) -> ContainmentStrategy:
        mapping = {
            ThreatSeverity.CRITICAL: ContainmentStrategy.ISOLATE_HOST,
            ThreatSeverity.HIGH: ContainmentStrategy.BLOCK_IP,
            ThreatSeverity.MEDIUM: ContainmentStrategy.RATE_LIMIT,
            ThreatSeverity.LOW: ContainmentStrategy.QUARANTINE_FILE,
        }
        return mapping.get(severity, ContainmentStrategy.ISOLATE_HOST)

    def select_containment_strategy(
        self,
        threat_id: str,
        strategy: ContainmentStrategy,
    ) -> dict[str, Any]:
        """Override the containment strategy for a threat."""
        for t in self._threats:
            if t.id == threat_id:
                t.strategy = strategy
                return {"threat_id": threat_id, "strategy": strategy.value}
        return {"threat_id": threat_id, "error": "not_found"}

    def execute_containment(
        self,
        threat_id: str,
        duration_ms: float = 0.0,
        success: bool = False,
        notes: str = "",
    ) -> ContainmentAction:
        """Execute containment action for a threat."""
        strategy = ContainmentStrategy.ISOLATE_HOST
        for t in self._threats:
            if t.id == threat_id:
                strategy = t.strategy
                t.result = ContainmentResult.SUCCESS if success else ContainmentResult.FAILED
                break
        action = ContainmentAction(
            threat_id=threat_id,
            strategy=strategy,
            result=ContainmentResult.SUCCESS if success else ContainmentResult.FAILED,
            duration_ms=duration_ms,
            notes=notes,
        )
        self._actions.append(action)
        if len(self._actions) > self._max_records:
            self._actions = self._actions[-self._max_records :]
        logger.info(
            "automated_threat_containment.executed",
            threat_id=threat_id,
            success=success,
        )
        return action

    def verify_containment(self, threat_id: str) -> dict[str, Any]:
        """Verify that containment is effective."""
        actions = [a for a in self._actions if a.threat_id == threat_id]
        if not actions:
            return {"verified": False, "reason": "no_actions_found"}
        latest = actions[-1]
        latest.verified = True
        for t in self._threats:
            if t.id == threat_id and latest.result == ContainmentResult.SUCCESS:
                t.result = ContainmentResult.VERIFIED
        return {
            "verified": latest.result == ContainmentResult.SUCCESS,
            "action_id": latest.id,
            "strategy": latest.strategy.value,
        }

    def document_actions(self, threat_id: str) -> list[dict[str, Any]]:
        """Document all containment actions for a threat."""
        actions = [a for a in self._actions if a.threat_id == threat_id]
        return [
            {
                "action_id": a.id,
                "strategy": a.strategy.value,
                "result": a.result.value,
                "duration_ms": a.duration_ms,
                "verified": a.verified,
                "notes": a.notes,
            }
            for a in actions
        ]

    def generate_report(self) -> ThreatContainmentReport:
        """Generate a comprehensive threat containment report."""
        by_sev: dict[str, int] = {}
        by_strat: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for t in self._threats:
            by_sev[t.severity.value] = by_sev.get(t.severity.value, 0) + 1
            by_strat[t.strategy.value] = by_strat.get(t.strategy.value, 0) + 1
            by_result[t.result.value] = by_result.get(t.result.value, 0) + 1
        scores = [t.risk_score for t in self._threats]
        avg_risk = round(sum(scores) / len(scores), 2) if scores else 0.0
        success_count = sum(1 for a in self._actions if a.result == ContainmentResult.SUCCESS)
        success_rate = round(success_count / len(self._actions) * 100, 2) if self._actions else 0.0
        issues = [t.name for t in self._threats if t.risk_score >= self._risk_threshold][:5]
        recs: list[str] = []
        if issues:
            recs.append(f"{len(issues)} high-risk threat(s) detected")
        if avg_risk >= self._risk_threshold:
            recs.append(f"Avg risk {avg_risk} above threshold ({self._risk_threshold})")
        if not recs:
            recs.append("Threat containment metrics within healthy range")
        return ThreatContainmentReport(
            total_threats=len(self._threats),
            total_actions=len(self._actions),
            success_rate=success_rate,
            avg_risk_score=avg_risk,
            by_severity=by_sev,
            by_strategy=by_strat,
            by_result=by_result,
            top_issues=issues,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dist: dict[str, int] = {}
        for t in self._threats:
            key = t.severity.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_threats": len(self._threats),
            "total_actions": len(self._actions),
            "risk_threshold": self._risk_threshold,
            "severity_distribution": dist,
            "unique_teams": len({t.team for t in self._threats}),
            "unique_services": len({t.service for t in self._threats}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._threats.clear()
        self._actions.clear()
        logger.info("automated_threat_containment.cleared")
        return {"status": "cleared"}
