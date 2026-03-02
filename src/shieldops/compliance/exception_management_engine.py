"""Exception Management Engine — manage policy exceptions and risk acceptances."""

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
    RISK_ACCEPTANCE = "risk_acceptance"
    COMPENSATING_CONTROL = "compensating_control"
    TEMPORARY_WAIVER = "temporary_waiver"
    PERMANENT_EXEMPTION = "permanent_exemption"
    DEFERRED_REMEDIATION = "deferred_remediation"


class ExceptionStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ApprovalLevel(StrEnum):
    CISO = "ciso"
    SECURITY_LEAD = "security_lead"
    MANAGER = "manager"
    AUTOMATED = "automated"
    COMMITTEE = "committee"


# --- Models ---


class ExceptionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exception_name: str = ""
    exception_type: ExceptionType = ExceptionType.RISK_ACCEPTANCE
    exception_status: ExceptionStatus = ExceptionStatus.REQUESTED
    approval_level: ApprovalLevel = ApprovalLevel.CISO
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ExceptionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exception_name: str = ""
    exception_type: ExceptionType = ExceptionType.RISK_ACCEPTANCE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ExceptionManagementReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_approval: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ExceptionManagementEngine:
    """Manage policy exceptions, risk acceptances, waivers, and exemption lifecycle."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ExceptionRecord] = []
        self._analyses: list[ExceptionAnalysis] = []
        logger.info(
            "exception_management_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_exception(
        self,
        exception_name: str,
        exception_type: ExceptionType = ExceptionType.RISK_ACCEPTANCE,
        exception_status: ExceptionStatus = ExceptionStatus.REQUESTED,
        approval_level: ApprovalLevel = ApprovalLevel.CISO,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ExceptionRecord:
        record = ExceptionRecord(
            exception_name=exception_name,
            exception_type=exception_type,
            exception_status=exception_status,
            approval_level=approval_level,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "exception_management_engine.exception_recorded",
            record_id=record.id,
            exception_name=exception_name,
            exception_type=exception_type.value,
            exception_status=exception_status.value,
        )
        return record

    def get_record(self, record_id: str) -> ExceptionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        exception_type: ExceptionType | None = None,
        exception_status: ExceptionStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ExceptionRecord]:
        results = list(self._records)
        if exception_type is not None:
            results = [r for r in results if r.exception_type == exception_type]
        if exception_status is not None:
            results = [r for r in results if r.exception_status == exception_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        exception_name: str,
        exception_type: ExceptionType = ExceptionType.RISK_ACCEPTANCE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ExceptionAnalysis:
        analysis = ExceptionAnalysis(
            exception_name=exception_name,
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
            "exception_management_engine.analysis_added",
            exception_name=exception_name,
            exception_type=exception_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by exception_type; return count and avg risk_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.exception_type.value
            type_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for exc_type, scores in type_data.items():
            result[exc_type] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "exception_name": r.exception_name,
                        "exception_type": r.exception_type.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"])
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

    def generate_report(self) -> ExceptionManagementReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_approval: dict[str, int] = {}
        for r in self._records:
            by_type[r.exception_type.value] = by_type.get(r.exception_type.value, 0) + 1
            by_status[r.exception_status.value] = by_status.get(r.exception_status.value, 0) + 1
            by_approval[r.approval_level.value] = by_approval.get(r.approval_level.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.risk_score < self._threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["exception_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} exception(s) below risk threshold ({self._threshold})")
        if self._records and avg_risk_score < self._threshold:
            recs.append(f"Avg risk score {avg_risk_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Exception management is healthy")
        return ExceptionManagementReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_type=by_type,
            by_status=by_status,
            by_approval=by_approval,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("exception_management_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.exception_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
