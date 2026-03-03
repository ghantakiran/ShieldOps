"""Governance Framework Mapper — map controls to governance frameworks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class Framework(StrEnum):
    NIST_CSF = "nist_csf"
    ISO_27001 = "iso_27001"
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"


class MappingStatus(StrEnum):
    MAPPED = "mapped"
    PARTIAL = "partial"
    UNMAPPED = "unmapped"
    NOT_APPLICABLE = "not_applicable"
    IN_PROGRESS = "in_progress"


class ControlMaturity(StrEnum):
    OPTIMIZED = "optimized"
    MANAGED = "managed"
    DEFINED = "defined"
    REPEATABLE = "repeatable"
    INITIAL = "initial"


# --- Models ---


class FrameworkRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    framework: Framework = Framework.NIST_CSF
    mapping_status: MappingStatus = MappingStatus.MAPPED
    control_maturity: ControlMaturity = ControlMaturity.OPTIMIZED
    mapping_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FrameworkAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    framework: Framework = Framework.NIST_CSF
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FrameworkMappingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_mapping_score: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_maturity: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class GovernanceFrameworkMapper:
    """Map controls to governance frameworks, track maturity, identify mapping gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[FrameworkRecord] = []
        self._analyses: list[FrameworkAnalysis] = []
        logger.info(
            "governance_framework_mapper.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_mapping(
        self,
        control_name: str,
        framework: Framework = Framework.NIST_CSF,
        mapping_status: MappingStatus = MappingStatus.MAPPED,
        control_maturity: ControlMaturity = ControlMaturity.OPTIMIZED,
        mapping_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FrameworkRecord:
        record = FrameworkRecord(
            control_name=control_name,
            framework=framework,
            mapping_status=mapping_status,
            control_maturity=control_maturity,
            mapping_score=mapping_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "governance_framework_mapper.mapping_recorded",
            record_id=record.id,
            control_name=control_name,
            framework=framework.value,
            mapping_status=mapping_status.value,
        )
        return record

    def get_record(self, record_id: str) -> FrameworkRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        framework: Framework | None = None,
        mapping_status: MappingStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FrameworkRecord]:
        results = list(self._records)
        if framework is not None:
            results = [r for r in results if r.framework == framework]
        if mapping_status is not None:
            results = [r for r in results if r.mapping_status == mapping_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        control_name: str,
        framework: Framework = Framework.NIST_CSF,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FrameworkAnalysis:
        analysis = FrameworkAnalysis(
            control_name=control_name,
            framework=framework,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "governance_framework_mapper.analysis_added",
            control_name=control_name,
            framework=framework.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by framework; return count and avg mapping_score."""
        framework_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.framework.value
            framework_data.setdefault(key, []).append(r.mapping_score)
        result: dict[str, Any] = {}
        for framework, scores in framework_data.items():
            result[framework] = {
                "count": len(scores),
                "avg_mapping_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where mapping_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.mapping_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "control_name": r.control_name,
                        "framework": r.framework.value,
                        "mapping_score": r.mapping_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["mapping_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg mapping_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.mapping_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_mapping_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_mapping_score"])
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

    def generate_report(self) -> FrameworkMappingReport:
        by_framework: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_maturity: dict[str, int] = {}
        for r in self._records:
            by_framework[r.framework.value] = by_framework.get(r.framework.value, 0) + 1
            by_status[r.mapping_status.value] = by_status.get(r.mapping_status.value, 0) + 1
            by_maturity[r.control_maturity.value] = by_maturity.get(r.control_maturity.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.mapping_score < self._threshold)
        scores = [r.mapping_score for r in self._records]
        avg_mapping_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["control_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} control(s) below mapping threshold ({self._threshold})")
        if self._records and avg_mapping_score < self._threshold:
            recs.append(
                f"Avg mapping score {avg_mapping_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Governance framework mapping is healthy")
        return FrameworkMappingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_mapping_score=avg_mapping_score,
            by_framework=by_framework,
            by_status=by_status,
            by_maturity=by_maturity,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("governance_framework_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        framework_dist: dict[str, int] = {}
        for r in self._records:
            key = r.framework.value
            framework_dist[key] = framework_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "framework_distribution": framework_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
