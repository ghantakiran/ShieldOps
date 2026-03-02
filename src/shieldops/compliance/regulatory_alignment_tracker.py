"""Regulatory Alignment Tracker — track alignment with regulatory requirements."""

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
    CCPA = "ccpa"
    SOX = "sox"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"


class AlignmentStatus(StrEnum):
    ALIGNED = "aligned"
    PARTIALLY_ALIGNED = "partially_aligned"
    NON_ALIGNED = "non_aligned"
    IN_PROGRESS = "in_progress"
    NOT_APPLICABLE = "not_applicable"


class ComplianceRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


# --- Models ---


class AlignmentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requirement_name: str = ""
    regulation: Regulation = Regulation.GDPR
    alignment_status: AlignmentStatus = AlignmentStatus.ALIGNED
    compliance_risk: ComplianceRisk = ComplianceRisk.CRITICAL
    alignment_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AlignmentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requirement_name: str = ""
    regulation: Regulation = Regulation.GDPR
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RegulatoryAlignmentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_alignment_score: float = 0.0
    by_regulation: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RegulatoryAlignmentTracker:
    """Track regulatory alignment, identify compliance gaps, score alignment maturity."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AlignmentRecord] = []
        self._analyses: list[AlignmentAnalysis] = []
        logger.info(
            "regulatory_alignment_tracker.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_alignment(
        self,
        requirement_name: str,
        regulation: Regulation = Regulation.GDPR,
        alignment_status: AlignmentStatus = AlignmentStatus.ALIGNED,
        compliance_risk: ComplianceRisk = ComplianceRisk.CRITICAL,
        alignment_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AlignmentRecord:
        record = AlignmentRecord(
            requirement_name=requirement_name,
            regulation=regulation,
            alignment_status=alignment_status,
            compliance_risk=compliance_risk,
            alignment_score=alignment_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "regulatory_alignment_tracker.alignment_recorded",
            record_id=record.id,
            requirement_name=requirement_name,
            regulation=regulation.value,
            alignment_status=alignment_status.value,
        )
        return record

    def get_record(self, record_id: str) -> AlignmentRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        regulation: Regulation | None = None,
        alignment_status: AlignmentStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AlignmentRecord]:
        results = list(self._records)
        if regulation is not None:
            results = [r for r in results if r.regulation == regulation]
        if alignment_status is not None:
            results = [r for r in results if r.alignment_status == alignment_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        requirement_name: str,
        regulation: Regulation = Regulation.GDPR,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AlignmentAnalysis:
        analysis = AlignmentAnalysis(
            requirement_name=requirement_name,
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
            "regulatory_alignment_tracker.analysis_added",
            requirement_name=requirement_name,
            regulation=regulation.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by regulation; return count and avg alignment_score."""
        reg_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.regulation.value
            reg_data.setdefault(key, []).append(r.alignment_score)
        result: dict[str, Any] = {}
        for reg, scores in reg_data.items():
            result[reg] = {
                "count": len(scores),
                "avg_alignment_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where alignment_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.alignment_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "requirement_name": r.requirement_name,
                        "regulation": r.regulation.value,
                        "alignment_score": r.alignment_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["alignment_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg alignment_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.alignment_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_alignment_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_alignment_score"])
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

    def generate_report(self) -> RegulatoryAlignmentReport:
        by_regulation: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_regulation[r.regulation.value] = by_regulation.get(r.regulation.value, 0) + 1
            by_status[r.alignment_status.value] = by_status.get(r.alignment_status.value, 0) + 1
            by_risk[r.compliance_risk.value] = by_risk.get(r.compliance_risk.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.alignment_score < self._threshold)
        scores = [r.alignment_score for r in self._records]
        avg_alignment_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["requirement_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} requirement(s) below alignment threshold ({self._threshold})")
        if self._records and avg_alignment_score < self._threshold:
            recs.append(
                f"Avg alignment score {avg_alignment_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Regulatory alignment is healthy")
        return RegulatoryAlignmentReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_alignment_score=avg_alignment_score,
            by_regulation=by_regulation,
            by_status=by_status,
            by_risk=by_risk,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("regulatory_alignment_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        reg_dist: dict[str, int] = {}
        for r in self._records:
            key = r.regulation.value
            reg_dist[key] = reg_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "regulation_distribution": reg_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
