"""Autonomous Incident Commander — autonomous incident command and response coordination."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CommandMode(StrEnum):
    FULLY_AUTONOMOUS = "fully_autonomous"
    SEMI_AUTONOMOUS = "semi_autonomous"
    ADVISORY = "advisory"
    MANUAL = "manual"


class IncidentSeverity(StrEnum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"


class EscalationTrigger(StrEnum):
    TIMEOUT = "timeout"
    THRESHOLD = "threshold"
    COMPLEXITY = "complexity"
    POLICY = "policy"


# --- Models ---


class CommandRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    command_mode: CommandMode = CommandMode.ADVISORY
    incident_severity: IncidentSeverity = IncidentSeverity.SEV3
    escalation_trigger: EscalationTrigger = EscalationTrigger.THRESHOLD
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CommandAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    command_mode: CommandMode = CommandMode.ADVISORY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutonomousIncidentCommanderReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_command_mode: dict[str, int] = Field(default_factory=dict)
    by_incident_severity: dict[str, int] = Field(default_factory=dict)
    by_escalation_trigger: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutonomousIncidentCommander:
    """Autonomous Incident Commander
    for incident command and response coordination.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[CommandRecord] = []
        self._analyses: list[CommandAnalysis] = []
        logger.info(
            "autonomous_incident_commander.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------

    def record_item(
        self,
        name: str,
        command_mode: CommandMode = CommandMode.ADVISORY,
        incident_severity: IncidentSeverity = IncidentSeverity.SEV3,
        escalation_trigger: EscalationTrigger = (EscalationTrigger.THRESHOLD),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CommandRecord:
        record = CommandRecord(
            name=name,
            command_mode=command_mode,
            incident_severity=incident_severity,
            escalation_trigger=escalation_trigger,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "autonomous_incident_commander.item_recorded",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> CommandRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        command_mode: CommandMode | None = None,
        incident_severity: IncidentSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CommandRecord]:
        results = list(self._records)
        if command_mode is not None:
            results = [r for r in results if r.command_mode == command_mode]
        if incident_severity is not None:
            results = [r for r in results if r.incident_severity == incident_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        command_mode: CommandMode = CommandMode.ADVISORY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CommandAnalysis:
        analysis = CommandAnalysis(
            name=name,
            command_mode=command_mode,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "autonomous_incident_commander.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def assess_incident_complexity(self) -> list[dict[str, Any]]:
        """Assess complexity of recorded incidents."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            sev_weight = {
                IncidentSeverity.SEV1: 4.0,
                IncidentSeverity.SEV2: 3.0,
                IncidentSeverity.SEV3: 2.0,
                IncidentSeverity.SEV4: 1.0,
            }
            weight = sev_weight.get(r.incident_severity, 1.0)
            complexity = round(weight * (100 - r.score) / 100, 2)
            results.append(
                {
                    "record_id": r.id,
                    "name": r.name,
                    "severity": r.incident_severity.value,
                    "complexity_score": complexity,
                    "service": r.service,
                }
            )
        results.sort(key=lambda x: x["complexity_score"], reverse=True)
        return results

    def select_response_strategy(self) -> dict[str, Any]:
        """Select response strategy based on incident patterns."""
        sev_counts: dict[str, int] = {}
        mode_scores: dict[str, list[float]] = {}
        for r in self._records:
            sev_counts[r.incident_severity.value] = sev_counts.get(r.incident_severity.value, 0) + 1
            mode_scores.setdefault(r.command_mode.value, []).append(r.score)
        best_mode = ""
        best_avg = 0.0
        for mode, scores in mode_scores.items():
            avg = sum(scores) / len(scores)
            if avg > best_avg:
                best_avg = avg
                best_mode = mode
        return {
            "recommended_mode": best_mode or "advisory",
            "avg_effectiveness": round(best_avg, 2),
            "severity_distribution": sev_counts,
            "total_incidents": len(self._records),
        }

    def coordinate_response_teams(self) -> list[dict[str, Any]]:
        """Coordinate teams based on incident assignments."""
        team_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.team not in team_data:
                team_data[r.team] = {
                    "team": r.team,
                    "incident_count": 0,
                    "avg_score": 0.0,
                    "scores": [],
                    "severities": [],
                }
            team_data[r.team]["incident_count"] += 1
            team_data[r.team]["scores"].append(r.score)
            team_data[r.team]["severities"].append(r.incident_severity.value)
        results: list[dict[str, Any]] = []
        for info in team_data.values():
            scores = info.pop("scores")
            info["avg_score"] = round(sum(scores) / len(scores), 2) if scores else 0.0
            results.append(info)
        results.sort(key=lambda x: x["incident_count"], reverse=True)
        return results

    # -- report / stats -----------------------------------------------

    def generate_report(self) -> AutonomousIncidentCommanderReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.command_mode.value] = by_e1.get(r.command_mode.value, 0) + 1
            by_e2[r.incident_severity.value] = by_e2.get(r.incident_severity.value, 0) + 1
            by_e3[r.escalation_trigger.value] = by_e3.get(r.escalation_trigger.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = [r.name for r in self._records if r.score < self._threshold][:5]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Autonomous Incident Commander is healthy")
        return AutonomousIncidentCommanderReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_command_mode=by_e1,
            by_incident_severity=by_e2,
            by_escalation_trigger=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("autonomous_incident_commander.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.command_mode.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "command_mode_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
