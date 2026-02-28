"""Security Response Automator — automated containment and response playbook execution."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResponseAction(StrEnum):
    ISOLATE_HOST = "isolate_host"
    BLOCK_IP = "block_ip"
    REVOKE_CREDENTIALS = "revoke_credentials"
    QUARANTINE = "quarantine"
    ESCALATE = "escalate"


class ResponseOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    TIMEOUT = "timeout"


class ResponseUrgency(StrEnum):
    IMMEDIATE = "immediate"
    HIGH = "high"
    STANDARD = "standard"
    LOW = "low"
    SCHEDULED = "scheduled"


# --- Models ---


class ResponseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    response_action: ResponseAction = ResponseAction.ISOLATE_HOST
    response_outcome: ResponseOutcome = ResponseOutcome.SUCCESS
    response_urgency: ResponseUrgency = ResponseUrgency.STANDARD
    execution_time_seconds: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponsePlaybook(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    playbook_name: str = ""
    response_action: ResponseAction = ResponseAction.BLOCK_IP
    response_urgency: ResponseUrgency = ResponseUrgency.HIGH
    step_count: int = 0
    created_at: float = Field(default_factory=time.time)


class ResponseAutomatorReport(BaseModel):
    total_responses: int = 0
    total_playbooks: int = 0
    success_rate_pct: float = 0.0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    failure_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityResponseAutomator:
    """Automated containment and response playbook execution."""

    def __init__(
        self,
        max_records: int = 200000,
        min_success_rate_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_success_rate_pct = min_success_rate_pct
        self._records: list[ResponseRecord] = []
        self._playbooks: list[ResponsePlaybook] = []
        logger.info(
            "response_automator.initialized",
            max_records=max_records,
            min_success_rate_pct=min_success_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_response(
        self,
        incident_id: str,
        response_action: ResponseAction = ResponseAction.ISOLATE_HOST,
        response_outcome: ResponseOutcome = ResponseOutcome.SUCCESS,
        response_urgency: ResponseUrgency = ResponseUrgency.STANDARD,
        execution_time_seconds: float = 0.0,
        details: str = "",
    ) -> ResponseRecord:
        record = ResponseRecord(
            incident_id=incident_id,
            response_action=response_action,
            response_outcome=response_outcome,
            response_urgency=response_urgency,
            execution_time_seconds=execution_time_seconds,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "response_automator.response_recorded",
            record_id=record.id,
            incident_id=incident_id,
            response_action=response_action.value,
            response_outcome=response_outcome.value,
        )
        return record

    def get_response(self, record_id: str) -> ResponseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_responses(
        self,
        incident_id: str | None = None,
        response_action: ResponseAction | None = None,
        limit: int = 50,
    ) -> list[ResponseRecord]:
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if response_action is not None:
            results = [r for r in results if r.response_action == response_action]
        return results[-limit:]

    def add_playbook(
        self,
        playbook_name: str,
        response_action: ResponseAction = ResponseAction.BLOCK_IP,
        response_urgency: ResponseUrgency = ResponseUrgency.HIGH,
        step_count: int = 0,
    ) -> ResponsePlaybook:
        playbook = ResponsePlaybook(
            playbook_name=playbook_name,
            response_action=response_action,
            response_urgency=response_urgency,
            step_count=step_count,
        )
        self._playbooks.append(playbook)
        if len(self._playbooks) > self._max_records:
            self._playbooks = self._playbooks[-self._max_records :]
        logger.info(
            "response_automator.playbook_added",
            playbook_name=playbook_name,
            response_action=response_action.value,
            response_urgency=response_urgency.value,
        )
        return playbook

    # -- domain operations -----------------------------------------------

    def analyze_response_effectiveness(self, incident_id: str) -> dict[str, Any]:
        """Analyze response effectiveness for a specific incident."""
        records = [r for r in self._records if r.incident_id == incident_id]
        if not records:
            return {"incident_id": incident_id, "status": "no_data"}
        successes = sum(1 for r in records if r.response_outcome == ResponseOutcome.SUCCESS)
        success_rate = round(successes / len(records) * 100, 2)
        avg_time = round(sum(r.execution_time_seconds for r in records) / len(records), 2)
        return {
            "incident_id": incident_id,
            "total_responses": len(records),
            "success_count": successes,
            "success_rate_pct": success_rate,
            "avg_execution_time_seconds": avg_time,
            "meets_threshold": success_rate >= self._min_success_rate_pct,
        }

    def identify_failed_responses(self) -> list[dict[str, Any]]:
        """Find incidents with failed responses."""
        failure_counts: dict[str, int] = {}
        for r in self._records:
            if r.response_outcome in (
                ResponseOutcome.FAILED,
                ResponseOutcome.ROLLED_BACK,
                ResponseOutcome.TIMEOUT,
            ):
                failure_counts[r.incident_id] = failure_counts.get(r.incident_id, 0) + 1
        results: list[dict[str, Any]] = []
        for incident, count in failure_counts.items():
            if count > 1:
                results.append(
                    {
                        "incident_id": incident,
                        "failure_count": count,
                    }
                )
        results.sort(key=lambda x: x["failure_count"], reverse=True)
        return results

    def rank_by_execution_speed(self) -> list[dict[str, Any]]:
        """Rank incidents by average execution time ascending (fastest first)."""
        totals: dict[str, list[float]] = {}
        for r in self._records:
            totals.setdefault(r.incident_id, []).append(r.execution_time_seconds)
        results: list[dict[str, Any]] = []
        for incident, times in totals.items():
            results.append(
                {
                    "incident_id": incident,
                    "avg_execution_time_seconds": round(sum(times) / len(times), 2),
                }
            )
        results.sort(key=lambda x: x["avg_execution_time_seconds"])
        return results

    def detect_response_loops(self) -> list[dict[str, Any]]:
        """Detect incidents caught in response loops (>3 non-success)."""
        svc_non_success: dict[str, int] = {}
        for r in self._records:
            if r.response_outcome != ResponseOutcome.SUCCESS:
                svc_non_success[r.incident_id] = svc_non_success.get(r.incident_id, 0) + 1
        results: list[dict[str, Any]] = []
        for incident, count in svc_non_success.items():
            if count > 3:
                results.append(
                    {
                        "incident_id": incident,
                        "non_success_count": count,
                        "loop_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_success_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ResponseAutomatorReport:
        by_action: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_action[r.response_action.value] = by_action.get(r.response_action.value, 0) + 1
            by_outcome[r.response_outcome.value] = by_outcome.get(r.response_outcome.value, 0) + 1
        success_count = sum(
            1 for r in self._records if r.response_outcome == ResponseOutcome.SUCCESS
        )
        success_rate = round(success_count / len(self._records) * 100, 2) if self._records else 0.0
        failure_count = sum(
            1
            for r in self._records
            if r.response_outcome
            in (
                ResponseOutcome.FAILED,
                ResponseOutcome.ROLLED_BACK,
                ResponseOutcome.TIMEOUT,
            )
        )
        recs: list[str] = []
        if success_rate < self._min_success_rate_pct:
            recs.append(
                f"Success rate {success_rate}% is below {self._min_success_rate_pct}% threshold"
            )
        failed_incidents = sum(1 for d in self.identify_failed_responses())
        if failed_incidents > 0:
            recs.append(f"{failed_incidents} incident(s) with repeated failures")
        loops = len(self.detect_response_loops())
        if loops > 0:
            recs.append(f"{loops} incident(s) detected in response loops")
        if not recs:
            recs.append("Response automation effectiveness meets targets")
        return ResponseAutomatorReport(
            total_responses=len(self._records),
            total_playbooks=len(self._playbooks),
            success_rate_pct=success_rate,
            by_action=by_action,
            by_outcome=by_outcome,
            failure_count=failure_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._playbooks.clear()
        logger.info("response_automator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        action_dist: dict[str, int] = {}
        for r in self._records:
            key = r.response_action.value
            action_dist[key] = action_dist.get(key, 0) + 1
        return {
            "total_responses": len(self._records),
            "total_playbooks": len(self._playbooks),
            "min_success_rate_pct": self._min_success_rate_pct,
            "action_distribution": action_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
