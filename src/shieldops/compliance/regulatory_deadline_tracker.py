"""Regulatory Deadline Tracker — track regulatory deadlines across frameworks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class Regulation(StrEnum):
    GDPR = "gdpr"
    SOX = "sox"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    SOC2 = "soc2"


class DeadlineType(StrEnum):
    FILING = "filing"
    AUDIT = "audit"
    REMEDIATION = "remediation"
    CERTIFICATION = "certification"
    RENEWAL = "renewal"


class DeadlineStatus(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OVERDUE = "overdue"
    COMPLETED = "completed"
    WAIVED = "waived"


# --- Models ---


class DeadlineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deadline_id: str = ""
    regulation: Regulation = Regulation.GDPR
    deadline_type: DeadlineType = DeadlineType.FILING
    deadline_status: DeadlineStatus = DeadlineStatus.ON_TRACK
    compliance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DeadlineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deadline_id: str = ""
    regulation: Regulation = Regulation.GDPR
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeadlineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_regulation: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RegulatoryDeadlineTracker:
    """Track regulatory deadlines across frameworks and ensure timely compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        compliance_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._compliance_threshold = compliance_threshold
        self._records: list[DeadlineRecord] = []
        self._analyses: list[DeadlineAnalysis] = []
        logger.info(
            "regulatory_deadline_tracker.initialized",
            max_records=max_records,
            compliance_threshold=compliance_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_deadline(
        self,
        deadline_id: str,
        regulation: Regulation = Regulation.GDPR,
        deadline_type: DeadlineType = DeadlineType.FILING,
        deadline_status: DeadlineStatus = DeadlineStatus.ON_TRACK,
        compliance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DeadlineRecord:
        record = DeadlineRecord(
            deadline_id=deadline_id,
            regulation=regulation,
            deadline_type=deadline_type,
            deadline_status=deadline_status,
            compliance_score=compliance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "regulatory_deadline_tracker.deadline_recorded",
            record_id=record.id,
            deadline_id=deadline_id,
            regulation=regulation.value,
            deadline_type=deadline_type.value,
        )
        return record

    def get_deadline(self, record_id: str) -> DeadlineRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_deadlines(
        self,
        regulation: Regulation | None = None,
        deadline_type: DeadlineType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DeadlineRecord]:
        results = list(self._records)
        if regulation is not None:
            results = [r for r in results if r.regulation == regulation]
        if deadline_type is not None:
            results = [r for r in results if r.deadline_type == deadline_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        deadline_id: str,
        regulation: Regulation = Regulation.GDPR,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DeadlineAnalysis:
        analysis = DeadlineAnalysis(
            deadline_id=deadline_id,
            regulation=regulation,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "regulatory_deadline_tracker.analysis_added",
            deadline_id=deadline_id,
            regulation=regulation.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_regulation_distribution(self) -> dict[str, Any]:
        regulation_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.regulation.value
            regulation_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for regulation, scores in regulation_data.items():
            result[regulation] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_deadline_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._compliance_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "deadline_id": r.deadline_id,
                        "regulation": r.regulation.value,
                        "compliance_score": r.compliance_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["compliance_score"])

    def rank_by_compliance(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_compliance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_score"])
        return results

    def detect_deadline_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DeadlineReport:
        by_regulation: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_regulation[r.regulation.value] = by_regulation.get(r.regulation.value, 0) + 1
            by_type[r.deadline_type.value] = by_type.get(r.deadline_type.value, 0) + 1
            by_status[r.deadline_status.value] = by_status.get(r.deadline_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.compliance_score < self._compliance_threshold)
        scores = [r.compliance_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_deadline_gaps()
        top_gaps = [o["deadline_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} deadline(s) below compliance threshold ({self._compliance_threshold})"
            )
        if self._records and avg_score < self._compliance_threshold:
            recs.append(
                f"Avg compliance score {avg_score} below threshold ({self._compliance_threshold})"
            )
        if not recs:
            recs.append("Regulatory deadline tracking is healthy")
        return DeadlineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_compliance_score=avg_score,
            by_regulation=by_regulation,
            by_type=by_type,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("regulatory_deadline_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        regulation_dist: dict[str, int] = {}
        for r in self._records:
            key = r.regulation.value
            regulation_dist[key] = regulation_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "compliance_threshold": self._compliance_threshold,
            "regulation_distribution": regulation_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
