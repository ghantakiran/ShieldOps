"""SOAR Playbook Engine — define, execute, track automated security response."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PlaybookStatus(StrEnum):
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    TESTING = "testing"
    DISABLED = "disabled"


class ActionType(StrEnum):
    CONTAINMENT = "containment"
    ERADICATION = "eradication"
    RECOVERY = "recovery"
    INVESTIGATION = "investigation"
    NOTIFICATION = "notification"


class ExecutionResult(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


# --- Models ---


class PlaybookRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    playbook_name: str = ""
    playbook_status: PlaybookStatus = PlaybookStatus.ACTIVE
    action_type: ActionType = ActionType.CONTAINMENT
    execution_result: ExecutionResult = ExecutionResult.SUCCESS
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PlaybookExecution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    playbook_name: str = ""
    playbook_status: PlaybookStatus = PlaybookStatus.ACTIVE
    execution_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SOARPlaybookReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_executions: int = 0
    low_effectiveness_count: int = 0
    avg_effectiveness_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    top_low_effectiveness: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SOARPlaybookEngine:
    """SOAR playbook runtime — define, execute, track automated security response."""

    def __init__(
        self,
        max_records: int = 200000,
        effectiveness_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._effectiveness_threshold = effectiveness_threshold
        self._records: list[PlaybookRecord] = []
        self._executions: list[PlaybookExecution] = []
        logger.info(
            "soar_playbook_engine.initialized",
            max_records=max_records,
            effectiveness_threshold=effectiveness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_playbook(
        self,
        playbook_name: str,
        playbook_status: PlaybookStatus = PlaybookStatus.ACTIVE,
        action_type: ActionType = ActionType.CONTAINMENT,
        execution_result: ExecutionResult = ExecutionResult.SUCCESS,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PlaybookRecord:
        record = PlaybookRecord(
            playbook_name=playbook_name,
            playbook_status=playbook_status,
            action_type=action_type,
            execution_result=execution_result,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "soar_playbook_engine.playbook_recorded",
            record_id=record.id,
            playbook_name=playbook_name,
            playbook_status=playbook_status.value,
            action_type=action_type.value,
        )
        return record

    def get_playbook(self, record_id: str) -> PlaybookRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_playbooks(
        self,
        playbook_status: PlaybookStatus | None = None,
        action_type: ActionType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PlaybookRecord]:
        results = list(self._records)
        if playbook_status is not None:
            results = [r for r in results if r.playbook_status == playbook_status]
        if action_type is not None:
            results = [r for r in results if r.action_type == action_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_execution(
        self,
        playbook_name: str,
        playbook_status: PlaybookStatus = PlaybookStatus.ACTIVE,
        execution_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PlaybookExecution:
        execution = PlaybookExecution(
            playbook_name=playbook_name,
            playbook_status=playbook_status,
            execution_score=execution_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._executions.append(execution)
        if len(self._executions) > self._max_records:
            self._executions = self._executions[-self._max_records :]
        logger.info(
            "soar_playbook_engine.execution_added",
            playbook_name=playbook_name,
            playbook_status=playbook_status.value,
            execution_score=execution_score,
        )
        return execution

    # -- domain operations --------------------------------------------------

    def analyze_playbook_distribution(self) -> dict[str, Any]:
        """Group by playbook_status; return count and avg effectiveness_score."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.playbook_status.value
            status_data.setdefault(key, []).append(r.effectiveness_score)
        result: dict[str, Any] = {}
        for status, scores in status_data.items():
            result[status] = {
                "count": len(scores),
                "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_effectiveness_playbooks(self) -> list[dict[str, Any]]:
        """Return records where effectiveness_score < effectiveness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_score < self._effectiveness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "playbook_name": r.playbook_name,
                        "playbook_status": r.playbook_status.value,
                        "effectiveness_score": r.effectiveness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["effectiveness_score"])

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        """Group by service, avg effectiveness_score, sort ascending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"])
        return results

    def detect_execution_trends(self) -> dict[str, Any]:
        """Split-half comparison on execution_score; delta threshold 5.0."""
        if len(self._executions) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [e.execution_score for e in self._executions]
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

    def generate_report(self) -> SOARPlaybookReport:
        by_status: dict[str, int] = {}
        by_action: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for r in self._records:
            by_status[r.playbook_status.value] = by_status.get(r.playbook_status.value, 0) + 1
            by_action[r.action_type.value] = by_action.get(r.action_type.value, 0) + 1
            by_result[r.execution_result.value] = by_result.get(r.execution_result.value, 0) + 1
        low_effectiveness_count = sum(
            1 for r in self._records if r.effectiveness_score < self._effectiveness_threshold
        )
        scores = [r.effectiveness_score for r in self._records]
        avg_effectiveness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_effectiveness_playbooks()
        top_low_effectiveness = [o["playbook_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_effectiveness_count > 0:
            recs.append(
                f"{low_effectiveness_count} playbook(s) below effectiveness threshold "
                f"({self._effectiveness_threshold})"
            )
        if self._records and avg_effectiveness_score < self._effectiveness_threshold:
            recs.append(
                f"Avg effectiveness score {avg_effectiveness_score} below threshold "
                f"({self._effectiveness_threshold})"
            )
        if not recs:
            recs.append("SOAR playbook effectiveness is healthy")
        return SOARPlaybookReport(
            total_records=len(self._records),
            total_executions=len(self._executions),
            low_effectiveness_count=low_effectiveness_count,
            avg_effectiveness_score=avg_effectiveness_score,
            by_status=by_status,
            by_action=by_action,
            by_result=by_result,
            top_low_effectiveness=top_low_effectiveness,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._executions.clear()
        logger.info("soar_playbook_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.playbook_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_executions": len(self._executions),
            "effectiveness_threshold": self._effectiveness_threshold,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
