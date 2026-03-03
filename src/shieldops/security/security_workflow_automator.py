"""Security Workflow Automator — automate security workflows across the SOC."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WorkflowType(StrEnum):
    ALERT_TRIAGE = "alert_triage"
    INCIDENT_RESPONSE = "incident_response"
    THREAT_HUNT = "threat_hunt"
    COMPLIANCE_CHECK = "compliance_check"
    VULNERABILITY_SCAN = "vulnerability_scan"


class AutomationLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    ASSISTED = "assisted"
    MANUAL = "manual"
    DISABLED = "disabled"


class WorkflowStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    DEPRECATED = "deprecated"


# --- Models ---


class WorkflowAutomationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str = ""
    workflow_type: WorkflowType = WorkflowType.ALERT_TRIAGE
    automation_level: AutomationLevel = AutomationLevel.PARTIAL
    workflow_status: WorkflowStatus = WorkflowStatus.ACTIVE
    automation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowAutomationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str = ""
    workflow_type: WorkflowType = WorkflowType.ALERT_TRIAGE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowAutomationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityWorkflowAutomator:
    """Automate security workflows across the SOC for faster response and consistency."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[WorkflowAutomationRecord] = []
        self._analyses: list[WorkflowAutomationAnalysis] = []
        logger.info(
            "security_workflow_automator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_workflow(
        self,
        workflow_name: str,
        workflow_type: WorkflowType = WorkflowType.ALERT_TRIAGE,
        automation_level: AutomationLevel = AutomationLevel.PARTIAL,
        workflow_status: WorkflowStatus = WorkflowStatus.ACTIVE,
        automation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> WorkflowAutomationRecord:
        record = WorkflowAutomationRecord(
            workflow_name=workflow_name,
            workflow_type=workflow_type,
            automation_level=automation_level,
            workflow_status=workflow_status,
            automation_score=automation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_workflow_automator.workflow_recorded",
            record_id=record.id,
            workflow_name=workflow_name,
            workflow_type=workflow_type.value,
            automation_level=automation_level.value,
        )
        return record

    def get_record(self, record_id: str) -> WorkflowAutomationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        workflow_type: WorkflowType | None = None,
        automation_level: AutomationLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowAutomationRecord]:
        results = list(self._records)
        if workflow_type is not None:
            results = [r for r in results if r.workflow_type == workflow_type]
        if automation_level is not None:
            results = [r for r in results if r.automation_level == automation_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        workflow_name: str,
        workflow_type: WorkflowType = WorkflowType.ALERT_TRIAGE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WorkflowAutomationAnalysis:
        analysis = WorkflowAutomationAnalysis(
            workflow_name=workflow_name,
            workflow_type=workflow_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_workflow_automator.analysis_added",
            workflow_name=workflow_name,
            workflow_type=workflow_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by workflow_type; return count and avg automation_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.workflow_type.value
            type_data.setdefault(key, []).append(r.automation_score)
        result: dict[str, Any] = {}
        for wtype, scores in type_data.items():
            result[wtype] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where automation_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.automation_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "workflow_name": r.workflow_name,
                        "workflow_type": r.workflow_type.value,
                        "automation_score": r.automation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["automation_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg automation_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.automation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
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

    def generate_report(self) -> WorkflowAutomationReport:
        by_type: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.workflow_type.value] = by_type.get(r.workflow_type.value, 0) + 1
            by_level[r.automation_level.value] = by_level.get(r.automation_level.value, 0) + 1
            by_status[r.workflow_status.value] = by_status.get(r.workflow_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.automation_score < self._threshold)
        scores = [r.automation_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["workflow_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} workflow(s) below automation threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg automation score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Security workflow automation is healthy")
        return WorkflowAutomationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_type=by_type,
            by_level=by_level,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_workflow_automator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.workflow_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
