"""CyberInsuranceRiskAssessor — assess cyber insurance risk and coverage requirements."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CyberInsuranceType(StrEnum):
    CONTROL = "control"
    POLICY = "policy"
    REGULATION = "regulation"
    STANDARD = "standard"
    FRAMEWORK = "framework"


class CyberInsuranceSource(StrEnum):
    AUDIT = "audit"
    AUTOMATED_SCAN = "automated_scan"
    MANUAL_REVIEW = "manual_review"
    CONTINUOUS_MONITOR = "continuous_monitor"
    THIRD_PARTY = "third_party"


class CyberInsuranceLevel(StrEnum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_ASSESSED = "not_assessed"
    EXEMPT = "exempt"


# --- Models ---


class CyberInsuranceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    record_type: CyberInsuranceType = CyberInsuranceType.CONTROL
    source: CyberInsuranceSource = CyberInsuranceSource.AUDIT
    level: CyberInsuranceLevel = CyberInsuranceLevel.NON_COMPLIANT
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CyberInsuranceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    analysis_type: CyberInsuranceType = CyberInsuranceType.CONTROL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CyberInsuranceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CyberInsuranceRiskAssessor:
    """Assess cyber insurance risk and coverage requirements."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[CyberInsuranceRecord] = []
        self._analyses: list[CyberInsuranceAnalysis] = []
        logger.info(
            "cyber_insurance_risk_assessor.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record(
        self,
        name: str,
        record_type: CyberInsuranceType = CyberInsuranceType.CONTROL,
        source: CyberInsuranceSource = CyberInsuranceSource.AUDIT,
        level: CyberInsuranceLevel = CyberInsuranceLevel.NON_COMPLIANT,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CyberInsuranceRecord:
        rec = CyberInsuranceRecord(
            name=name,
            record_type=record_type,
            source=source,
            level=level,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(rec)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cyber_insurance_risk_assessor.recorded",
            record_id=rec.id,
            name=name,
        )
        return rec

    def get_record(self, record_id: str) -> CyberInsuranceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        record_type: CyberInsuranceType | None = None,
        source: CyberInsuranceSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CyberInsuranceRecord]:
        results = list(self._records)
        if record_type is not None:
            results = [r for r in results if r.record_type == record_type]
        if source is not None:
            results = [r for r in results if r.source == source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        analysis_type: CyberInsuranceType = CyberInsuranceType.CONTROL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CyberInsuranceAnalysis:
        analysis = CyberInsuranceAnalysis(
            name=name,
            analysis_type=analysis_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "cyber_insurance_risk_assessor.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by record_type; return count and avg score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.record_type.value
            type_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for rtype, scores in type_data.items():
            result[rtype] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "record_type": r.record_type.value,
                        "score": r.score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg score, sort ascending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
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

    def generate_report(self) -> CyberInsuranceReport:
        by_type: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_level: dict[str, int] = {}
        for r in self._records:
            by_type[r.record_type.value] = by_type.get(r.record_type.value, 0) + 1
            by_source[r.source.value] = by_source.get(r.source.value, 0) + 1
            by_level[r.level.value] = by_level.get(r.level.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} record(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("CyberInsuranceRiskAssessor posture is healthy")
        return CyberInsuranceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_type=by_type,
            by_source=by_source,
            by_level=by_level,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cyber_insurance_risk_assessor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.record_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
