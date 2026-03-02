"""Data Privacy Impact Assessor — DPIA for GDPR Article 35 compliance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ProcessingType(StrEnum):
    LARGE_SCALE_PROFILING = "large_scale_profiling"
    AUTOMATED_DECISION = "automated_decision"
    SENSITIVE_DATA = "sensitive_data"
    PUBLIC_MONITORING = "public_monitoring"
    CROSS_BORDER = "cross_border"


class PrivacyRisk(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class MitigationStatus(StrEnum):
    MITIGATED = "mitigated"
    PARTIALLY_MITIGATED = "partially_mitigated"
    PLANNED = "planned"
    UNMITIGATED = "unmitigated"
    NOT_APPLICABLE = "not_applicable"


# --- Models ---


class PrivacyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_name: str = ""
    processing_type: ProcessingType = ProcessingType.LARGE_SCALE_PROFILING
    privacy_risk: PrivacyRisk = PrivacyRisk.VERY_HIGH
    mitigation_status: MitigationStatus = MitigationStatus.MITIGATED
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PrivacyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_name: str = ""
    processing_type: ProcessingType = ProcessingType.LARGE_SCALE_PROFILING
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PrivacyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_impact_count: int = 0
    avg_impact_score: float = 0.0
    by_processing: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_mitigation: dict[str, int] = Field(default_factory=dict)
    top_high_impact: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataPrivacyImpactAssessor:
    """Assess data privacy impact for GDPR Article 35 compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        privacy_impact_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._privacy_impact_threshold = privacy_impact_threshold
        self._records: list[PrivacyRecord] = []
        self._analyses: list[PrivacyAnalysis] = []
        logger.info(
            "data_privacy_impact_assessor.initialized",
            max_records=max_records,
            privacy_impact_threshold=privacy_impact_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_assessment(
        self,
        assessment_name: str,
        processing_type: ProcessingType = ProcessingType.LARGE_SCALE_PROFILING,
        privacy_risk: PrivacyRisk = PrivacyRisk.VERY_HIGH,
        mitigation_status: MitigationStatus = MitigationStatus.MITIGATED,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PrivacyRecord:
        record = PrivacyRecord(
            assessment_name=assessment_name,
            processing_type=processing_type,
            privacy_risk=privacy_risk,
            mitigation_status=mitigation_status,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_privacy_impact_assessor.assessment_recorded",
            record_id=record.id,
            assessment_name=assessment_name,
            processing_type=processing_type.value,
            privacy_risk=privacy_risk.value,
        )
        return record

    def get_assessment(self, record_id: str) -> PrivacyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_assessments(
        self,
        processing_type: ProcessingType | None = None,
        privacy_risk: PrivacyRisk | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PrivacyRecord]:
        results = list(self._records)
        if processing_type is not None:
            results = [r for r in results if r.processing_type == processing_type]
        if privacy_risk is not None:
            results = [r for r in results if r.privacy_risk == privacy_risk]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        assessment_name: str,
        processing_type: ProcessingType = ProcessingType.LARGE_SCALE_PROFILING,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PrivacyAnalysis:
        analysis = PrivacyAnalysis(
            assessment_name=assessment_name,
            processing_type=processing_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_privacy_impact_assessor.analysis_added",
            assessment_name=assessment_name,
            processing_type=processing_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_assessment_distribution(self) -> dict[str, Any]:
        """Group by processing_type; return count and avg impact_score."""
        proc_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.processing_type.value
            proc_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for proc, scores in proc_data.items():
            result[proc] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_impact_assessments(self) -> list[dict[str, Any]]:
        """Return records where impact_score > privacy_impact_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact_score > self._privacy_impact_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "assessment_name": r.assessment_name,
                        "processing_type": r.processing_type.value,
                        "impact_score": r.impact_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["impact_score"], reverse=True)

    def rank_by_impact(self) -> list[dict[str, Any]]:
        """Group by service, avg impact_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_assessment_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> PrivacyReport:
        by_processing: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_mitigation: dict[str, int] = {}
        for r in self._records:
            by_processing[r.processing_type.value] = (
                by_processing.get(r.processing_type.value, 0) + 1
            )
            by_risk[r.privacy_risk.value] = by_risk.get(r.privacy_risk.value, 0) + 1
            by_mitigation[r.mitigation_status.value] = (
                by_mitigation.get(r.mitigation_status.value, 0) + 1
            )
        high_impact_count = sum(
            1 for r in self._records if r.impact_score > self._privacy_impact_threshold
        )
        scores = [r.impact_score for r in self._records]
        avg_impact_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_impact_assessments()
        top_high_impact = [o["assessment_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_impact_count > 0:
            recs.append(
                f"{high_impact_count} assessment(s) above privacy impact threshold "
                f"({self._privacy_impact_threshold})"
            )
        if self._records and avg_impact_score > self._privacy_impact_threshold:
            recs.append(
                f"Avg impact score {avg_impact_score} above threshold "
                f"({self._privacy_impact_threshold})"
            )
        if not recs:
            recs.append("Data privacy impact levels are healthy")
        return PrivacyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_impact_count=high_impact_count,
            avg_impact_score=avg_impact_score,
            by_processing=by_processing,
            by_risk=by_risk,
            by_mitigation=by_mitigation,
            top_high_impact=top_high_impact,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_privacy_impact_assessor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        processing_dist: dict[str, int] = {}
        for r in self._records:
            key = r.processing_type.value
            processing_dist[key] = processing_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "privacy_impact_threshold": self._privacy_impact_threshold,
            "processing_distribution": processing_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
