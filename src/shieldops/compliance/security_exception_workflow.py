"""Security Exception Workflow — manage security policy exceptions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExceptionType(StrEnum):
    POLICY_WAIVER = "policy_waiver"
    RISK_ACCEPTANCE = "risk_acceptance"
    TEMPORARY_EXEMPTION = "temporary_exemption"
    COMPENSATING_CONTROL = "compensating_control"
    LEGACY_SYSTEM = "legacy_system"


class ApprovalStatus(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    PENDING = "pending"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ExceptionRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


# --- Models ---


class ExceptionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exception_id: str = ""
    exception_type: ExceptionType = ExceptionType.POLICY_WAIVER
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED
    exception_risk: ExceptionRisk = ExceptionRisk.CRITICAL
    exception_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ExceptionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exception_id: str = ""
    exception_type: ExceptionType = ExceptionType.POLICY_WAIVER
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecurityExceptionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_exception_score: float = 0.0
    by_exception_type: dict[str, int] = Field(default_factory=dict)
    by_approval_status: dict[str, int] = Field(default_factory=dict)
    by_exception_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityExceptionWorkflow:
    """Manage security exception requests and approvals."""

    def __init__(
        self,
        max_records: int = 200000,
        exception_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._exception_gap_threshold = exception_gap_threshold
        self._records: list[ExceptionRecord] = []
        self._analyses: list[ExceptionAnalysis] = []
        logger.info(
            "security_exception_workflow.initialized",
            max_records=max_records,
            exception_gap_threshold=exception_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_exception(
        self,
        exception_id: str,
        exception_type: ExceptionType = ExceptionType.POLICY_WAIVER,
        approval_status: ApprovalStatus = ApprovalStatus.APPROVED,
        exception_risk: ExceptionRisk = ExceptionRisk.CRITICAL,
        exception_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ExceptionRecord:
        record = ExceptionRecord(
            exception_id=exception_id,
            exception_type=exception_type,
            approval_status=approval_status,
            exception_risk=exception_risk,
            exception_score=exception_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_exception_workflow.recorded",
            record_id=record.id,
            exception_id=exception_id,
            exception_type=exception_type.value,
            approval_status=approval_status.value,
        )
        return record

    def get_exception(self, record_id: str) -> ExceptionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_exceptions(
        self,
        exception_type: ExceptionType | None = None,
        approval_status: ApprovalStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ExceptionRecord]:
        results = list(self._records)
        if exception_type is not None:
            results = [r for r in results if r.exception_type == exception_type]
        if approval_status is not None:
            results = [r for r in results if r.approval_status == approval_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        exception_id: str,
        exception_type: ExceptionType = ExceptionType.POLICY_WAIVER,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ExceptionAnalysis:
        analysis = ExceptionAnalysis(
            exception_id=exception_id,
            exception_type=exception_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_exception_workflow.analysis_added",
            exception_id=exception_id,
            exception_type=exception_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_exception_distribution(self) -> dict[str, Any]:
        data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.exception_type.value
            data.setdefault(key, []).append(r.exception_score)
        result: dict[str, Any] = {}
        for k, scores in data.items():
            result[k] = {
                "count": len(scores),
                "avg_exception_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_exception_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.exception_score < self._exception_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "exception_id": r.exception_id,
                        "exception_type": r.exception_type.value,
                        "exception_score": r.exception_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["exception_score"])

    def rank_by_exception(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.exception_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_exception_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_exception_score"])
        return results

    def detect_exception_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SecurityExceptionReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.exception_type.value] = by_e1.get(r.exception_type.value, 0) + 1
            by_e2[r.approval_status.value] = by_e2.get(r.approval_status.value, 0) + 1
            by_e3[r.exception_risk.value] = by_e3.get(r.exception_risk.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.exception_score < self._exception_gap_threshold
        )
        scores = [r.exception_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_exception_gaps()
        top_gaps = [o["exception_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} record(s) below threshold ({self._exception_gap_threshold})")
        if self._records and avg_score < self._exception_gap_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._exception_gap_threshold})")
        if not recs:
            recs.append("SecurityExceptionWorkflow metrics are healthy")
        return SecurityExceptionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_exception_score=avg_score,
            by_exception_type=by_e1,
            by_approval_status=by_e2,
            by_exception_risk=by_e3,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_exception_workflow.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.exception_type.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "exception_gap_threshold": self._exception_gap_threshold,
            "exception_type_distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
