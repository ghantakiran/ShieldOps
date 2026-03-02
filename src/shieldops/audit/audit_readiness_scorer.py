"""Audit Readiness Scorer — pre-audit readiness scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AuditType(StrEnum):
    SOC2_TYPE2 = "soc2_type2"
    ISO_27001 = "iso_27001"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    GDPR = "gdpr"


class ReadinessArea(StrEnum):
    DOCUMENTATION = "documentation"
    EVIDENCE = "evidence"
    CONTROLS = "controls"
    PROCESSES = "processes"
    PERSONNEL = "personnel"


class ReadinessGrade(StrEnum):
    AUDIT_READY = "audit_ready"
    MOSTLY_READY = "mostly_ready"
    NEEDS_WORK = "needs_work"
    SIGNIFICANT_GAPS = "significant_gaps"
    NOT_READY = "not_ready"


# --- Models ---


class ReadinessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_name: str = ""
    audit_type: AuditType = AuditType.SOC2_TYPE2
    readiness_area: ReadinessArea = ReadinessArea.DOCUMENTATION
    readiness_grade: ReadinessGrade = ReadinessGrade.AUDIT_READY
    readiness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ReadinessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_name: str = ""
    audit_type: AuditType = AuditType.SOC2_TYPE2
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditReadinessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_readiness_count: int = 0
    avg_readiness_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_area: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    top_low_readiness: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditReadinessScorer:
    """Pre-audit readiness scoring across multiple audit frameworks."""

    def __init__(
        self,
        max_records: int = 200000,
        readiness_threshold: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._readiness_threshold = readiness_threshold
        self._records: list[ReadinessRecord] = []
        self._analyses: list[ReadinessAnalysis] = []
        logger.info(
            "audit_readiness_scorer.initialized",
            max_records=max_records,
            readiness_threshold=readiness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_readiness(
        self,
        audit_name: str,
        audit_type: AuditType = AuditType.SOC2_TYPE2,
        readiness_area: ReadinessArea = ReadinessArea.DOCUMENTATION,
        readiness_grade: ReadinessGrade = ReadinessGrade.AUDIT_READY,
        readiness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ReadinessRecord:
        record = ReadinessRecord(
            audit_name=audit_name,
            audit_type=audit_type,
            readiness_area=readiness_area,
            readiness_grade=readiness_grade,
            readiness_score=readiness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_readiness_scorer.readiness_recorded",
            record_id=record.id,
            audit_name=audit_name,
            audit_type=audit_type.value,
            readiness_area=readiness_area.value,
        )
        return record

    def get_readiness(self, record_id: str) -> ReadinessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_readiness(
        self,
        audit_type: AuditType | None = None,
        readiness_area: ReadinessArea | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ReadinessRecord]:
        results = list(self._records)
        if audit_type is not None:
            results = [r for r in results if r.audit_type == audit_type]
        if readiness_area is not None:
            results = [r for r in results if r.readiness_area == readiness_area]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        audit_name: str,
        audit_type: AuditType = AuditType.SOC2_TYPE2,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ReadinessAnalysis:
        analysis = ReadinessAnalysis(
            audit_name=audit_name,
            audit_type=audit_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "audit_readiness_scorer.analysis_added",
            audit_name=audit_name,
            audit_type=audit_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by audit_type; return count and avg readiness_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.audit_type.value
            type_data.setdefault(key, []).append(r.readiness_score)
        result: dict[str, Any] = {}
        for atype, scores in type_data.items():
            result[atype] = {
                "count": len(scores),
                "avg_readiness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_readiness_audits(self) -> list[dict[str, Any]]:
        """Return records where readiness_score < readiness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.readiness_score < self._readiness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "audit_name": r.audit_name,
                        "audit_type": r.audit_type.value,
                        "readiness_score": r.readiness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["readiness_score"])

    def rank_by_readiness_score(self) -> list[dict[str, Any]]:
        """Group by service, avg readiness_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.readiness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_readiness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_readiness_score"])
        return results

    def detect_readiness_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AuditReadinessReport:
        by_type: dict[str, int] = {}
        by_area: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_type[r.audit_type.value] = by_type.get(r.audit_type.value, 0) + 1
            by_area[r.readiness_area.value] = by_area.get(r.readiness_area.value, 0) + 1
            by_grade[r.readiness_grade.value] = by_grade.get(r.readiness_grade.value, 0) + 1
        low_readiness_count = sum(
            1 for r in self._records if r.readiness_score < self._readiness_threshold
        )
        scores = [r.readiness_score for r in self._records]
        avg_readiness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_readiness_audits()
        top_low_readiness = [o["audit_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_readiness_count > 0:
            recs.append(
                f"{low_readiness_count} audit(s) below readiness threshold "
                f"({self._readiness_threshold})"
            )
        if self._records and avg_readiness_score < self._readiness_threshold:
            recs.append(
                f"Avg readiness score {avg_readiness_score} below threshold "
                f"({self._readiness_threshold})"
            )
        if not recs:
            recs.append("Audit readiness posture is healthy")
        return AuditReadinessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_readiness_count=low_readiness_count,
            avg_readiness_score=avg_readiness_score,
            by_type=by_type,
            by_area=by_area,
            by_grade=by_grade,
            top_low_readiness=top_low_readiness,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("audit_readiness_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.audit_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "readiness_threshold": self._readiness_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
