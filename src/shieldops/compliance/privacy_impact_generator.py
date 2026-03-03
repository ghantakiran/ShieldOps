"""Privacy Impact Generator — generate privacy impact assessments for data processing."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class ProcessingActivity(StrEnum):
    COLLECTION = "collection"
    STORAGE = "storage"
    ANALYSIS = "analysis"
    SHARING = "sharing"
    DELETION = "deletion"


class RiskMitigation(StrEnum):
    ENCRYPTION = "encryption"
    ANONYMIZATION = "anonymization"
    ACCESS_CONTROL = "access_control"
    MINIMIZATION = "minimization"
    CONSENT = "consent"


# --- Models ---


class ImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    processing_id: str = ""
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    processing_activity: ProcessingActivity = ProcessingActivity.COLLECTION
    risk_mitigation: RiskMitigation = RiskMitigation.ENCRYPTION
    risk_score: float = 0.0
    business_unit: str = ""
    data_owner: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    processing_id: str = ""
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PrivacyImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_impact_level: dict[str, int] = Field(default_factory=dict)
    by_activity: dict[str, int] = Field(default_factory=dict)
    by_mitigation: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PrivacyImpactGenerator:
    """Generate privacy impact assessments; identify high-risk processing activities."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ImpactRecord] = []
        self._analyses: list[ImpactAnalysis] = []
        logger.info(
            "privacy_impact_generator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_impact(
        self,
        processing_id: str,
        impact_level: ImpactLevel = ImpactLevel.MEDIUM,
        processing_activity: ProcessingActivity = ProcessingActivity.COLLECTION,
        risk_mitigation: RiskMitigation = RiskMitigation.ENCRYPTION,
        risk_score: float = 0.0,
        business_unit: str = "",
        data_owner: str = "",
    ) -> ImpactRecord:
        record = ImpactRecord(
            processing_id=processing_id,
            impact_level=impact_level,
            processing_activity=processing_activity,
            risk_mitigation=risk_mitigation,
            risk_score=risk_score,
            business_unit=business_unit,
            data_owner=data_owner,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "privacy_impact_generator.impact_recorded",
            record_id=record.id,
            processing_id=processing_id,
            impact_level=impact_level.value,
            processing_activity=processing_activity.value,
        )
        return record

    def get_impact(self, record_id: str) -> ImpactRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_impacts(
        self,
        impact_level: ImpactLevel | None = None,
        processing_activity: ProcessingActivity | None = None,
        business_unit: str | None = None,
        limit: int = 50,
    ) -> list[ImpactRecord]:
        results = list(self._records)
        if impact_level is not None:
            results = [r for r in results if r.impact_level == impact_level]
        if processing_activity is not None:
            results = [r for r in results if r.processing_activity == processing_activity]
        if business_unit is not None:
            results = [r for r in results if r.business_unit == business_unit]
        return results[-limit:]

    def add_analysis(
        self,
        processing_id: str,
        impact_level: ImpactLevel = ImpactLevel.MEDIUM,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ImpactAnalysis:
        analysis = ImpactAnalysis(
            processing_id=processing_id,
            impact_level=impact_level,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "privacy_impact_generator.analysis_added",
            processing_id=processing_id,
            impact_level=impact_level.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_impact_distribution(self) -> dict[str, Any]:
        """Group by impact_level; return count and avg risk_score."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.impact_level.value
            level_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_impact_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "processing_id": r.processing_id,
                        "impact_level": r.impact_level.value,
                        "risk_score": r.risk_score,
                        "business_unit": r.business_unit,
                        "data_owner": r.data_owner,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_risk(self) -> list[dict[str, Any]]:
        """Group by business_unit, avg risk_score, sort ascending."""
        unit_scores: dict[str, list[float]] = {}
        for r in self._records:
            unit_scores.setdefault(r.business_unit, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for unit, scores in unit_scores.items():
            results.append(
                {
                    "business_unit": unit,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"])
        return results

    def detect_impact_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> PrivacyImpactReport:
        by_impact_level: dict[str, int] = {}
        by_activity: dict[str, int] = {}
        by_mitigation: dict[str, int] = {}
        for r in self._records:
            by_impact_level[r.impact_level.value] = by_impact_level.get(r.impact_level.value, 0) + 1
            by_activity[r.processing_activity.value] = (
                by_activity.get(r.processing_activity.value, 0) + 1
            )
            by_mitigation[r.risk_mitigation.value] = (
                by_mitigation.get(r.risk_mitigation.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.risk_score < self._threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_impact_gaps()
        top_gaps = [o["processing_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} processing activity(s) below risk threshold ({self._threshold})"
            )
        if self._records and avg_risk_score < self._threshold:
            recs.append(f"Avg risk score {avg_risk_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Privacy impact assessment coverage is healthy")
        return PrivacyImpactReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_impact_level=by_impact_level,
            by_activity=by_activity,
            by_mitigation=by_mitigation,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("privacy_impact_generator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.impact_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "impact_level_distribution": level_dist,
            "unique_units": len({r.business_unit for r in self._records}),
            "unique_owners": len({r.data_owner for r in self._records}),
        }
