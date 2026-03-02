"""Container Runtime Security — runtime container security monitoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RuntimeEvent(StrEnum):
    PROCESS_EXEC = "process_exec"
    FILE_WRITE = "file_write"
    NETWORK_CONNECT = "network_connect"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    CONTAINER_ESCAPE = "container_escape"


class ContainerStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    CRASHED = "crashed"
    QUARANTINED = "quarantined"
    TERMINATED = "terminated"


class SecurityLevel(StrEnum):
    HARDENED = "hardened"
    STANDARD = "standard"
    PERMISSIVE = "permissive"
    VULNERABLE = "vulnerable"
    COMPROMISED = "compromised"


# --- Models ---


class RuntimeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    container_name: str = ""
    runtime_event: RuntimeEvent = RuntimeEvent.PROCESS_EXEC
    container_status: ContainerStatus = ContainerStatus.RUNNING
    security_level: SecurityLevel = SecurityLevel.HARDENED
    security_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RuntimeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    container_name: str = ""
    runtime_event: RuntimeEvent = RuntimeEvent.PROCESS_EXEC
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RuntimeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_security_count: int = 0
    avg_security_score: float = 0.0
    by_event: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    top_low_security: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ContainerRuntimeSecurity:
    """Runtime container security monitoring and threat detection."""

    def __init__(
        self,
        max_records: int = 200000,
        runtime_security_threshold: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._runtime_security_threshold = runtime_security_threshold
        self._records: list[RuntimeRecord] = []
        self._analyses: list[RuntimeAnalysis] = []
        logger.info(
            "container_runtime_security.initialized",
            max_records=max_records,
            runtime_security_threshold=runtime_security_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_event(
        self,
        container_name: str,
        runtime_event: RuntimeEvent = RuntimeEvent.PROCESS_EXEC,
        container_status: ContainerStatus = ContainerStatus.RUNNING,
        security_level: SecurityLevel = SecurityLevel.HARDENED,
        security_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RuntimeRecord:
        record = RuntimeRecord(
            container_name=container_name,
            runtime_event=runtime_event,
            container_status=container_status,
            security_level=security_level,
            security_score=security_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "container_runtime_security.event_recorded",
            record_id=record.id,
            container_name=container_name,
            runtime_event=runtime_event.value,
            container_status=container_status.value,
        )
        return record

    def get_event(self, record_id: str) -> RuntimeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_events(
        self,
        runtime_event: RuntimeEvent | None = None,
        container_status: ContainerStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RuntimeRecord]:
        results = list(self._records)
        if runtime_event is not None:
            results = [r for r in results if r.runtime_event == runtime_event]
        if container_status is not None:
            results = [r for r in results if r.container_status == container_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        container_name: str,
        runtime_event: RuntimeEvent = RuntimeEvent.PROCESS_EXEC,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RuntimeAnalysis:
        analysis = RuntimeAnalysis(
            container_name=container_name,
            runtime_event=runtime_event,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "container_runtime_security.analysis_added",
            container_name=container_name,
            runtime_event=runtime_event.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_event_distribution(self) -> dict[str, Any]:
        """Group by runtime_event; return count and avg security_score."""
        evt_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.runtime_event.value
            evt_data.setdefault(key, []).append(r.security_score)
        result: dict[str, Any] = {}
        for evt, scores in evt_data.items():
            result[evt] = {
                "count": len(scores),
                "avg_security_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_security_containers(self) -> list[dict[str, Any]]:
        """Return records where security_score < runtime_security_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.security_score < self._runtime_security_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "container_name": r.container_name,
                        "runtime_event": r.runtime_event.value,
                        "security_score": r.security_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["security_score"])

    def rank_by_security_score(self) -> list[dict[str, Any]]:
        """Group by service, avg security_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.security_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_security_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_security_score"])
        return results

    def detect_security_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> RuntimeReport:
        by_event: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_level: dict[str, int] = {}
        for r in self._records:
            by_event[r.runtime_event.value] = by_event.get(r.runtime_event.value, 0) + 1
            by_status[r.container_status.value] = by_status.get(r.container_status.value, 0) + 1
            by_level[r.security_level.value] = by_level.get(r.security_level.value, 0) + 1
        low_security_count = sum(
            1 for r in self._records if r.security_score < self._runtime_security_threshold
        )
        scores = [r.security_score for r in self._records]
        avg_security_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_security_containers()
        top_low_security = [o["container_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_security_count > 0:
            recs.append(
                f"{low_security_count} container(s) below security threshold "
                f"({self._runtime_security_threshold})"
            )
        if self._records and avg_security_score < self._runtime_security_threshold:
            recs.append(
                f"Avg security score {avg_security_score} below threshold "
                f"({self._runtime_security_threshold})"
            )
        if not recs:
            recs.append("Container runtime security is healthy")
        return RuntimeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_security_count=low_security_count,
            avg_security_score=avg_security_score,
            by_event=by_event,
            by_status=by_status,
            by_level=by_level,
            top_low_security=top_low_security,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("container_runtime_security.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        event_dist: dict[str, int] = {}
        for r in self._records:
            key = r.runtime_event.value
            event_dist[key] = event_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "runtime_security_threshold": self._runtime_security_threshold,
            "event_distribution": event_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
