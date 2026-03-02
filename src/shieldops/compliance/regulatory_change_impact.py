"""Regulatory Change Impact — regulatory change gap analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChangeType(StrEnum):
    NEW_REGULATION = "new_regulation"
    AMENDMENT = "amendment"
    INTERPRETATION = "interpretation"
    ENFORCEMENT_ACTION = "enforcement_action"
    GUIDELINE_UPDATE = "guideline_update"


class ImpactLevel(StrEnum):
    TRANSFORMATIONAL = "transformational"
    SIGNIFICANT = "significant"
    MODERATE = "moderate"
    MINOR = "minor"
    NEGLIGIBLE = "negligible"


class ReadinessState(StrEnum):
    COMPLIANT = "compliant"
    IN_PROGRESS = "in_progress"
    GAP_IDENTIFIED = "gap_identified"
    NOT_STARTED = "not_started"
    NOT_APPLICABLE = "not_applicable"


# --- Models ---


class RegulatoryChangeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_name: str = ""
    change_type: ChangeType = ChangeType.NEW_REGULATION
    impact_level: ImpactLevel = ImpactLevel.TRANSFORMATIONAL
    readiness_state: ReadinessState = ReadinessState.COMPLIANT
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RegulatoryChangeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_name: str = ""
    change_type: ChangeType = ChangeType.NEW_REGULATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RegulatoryChangeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_impact_count: int = 0
    avg_impact_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    by_readiness: dict[str, int] = Field(default_factory=dict)
    top_high_impact: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RegulatoryChangeImpact:
    """Regulatory change gap analysis and impact assessment."""

    def __init__(
        self,
        max_records: int = 200000,
        regulatory_impact_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._regulatory_impact_threshold = regulatory_impact_threshold
        self._records: list[RegulatoryChangeRecord] = []
        self._analyses: list[RegulatoryChangeAnalysis] = []
        logger.info(
            "regulatory_change_impact.initialized",
            max_records=max_records,
            regulatory_impact_threshold=regulatory_impact_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_change(
        self,
        change_name: str,
        change_type: ChangeType = ChangeType.NEW_REGULATION,
        impact_level: ImpactLevel = ImpactLevel.TRANSFORMATIONAL,
        readiness_state: ReadinessState = ReadinessState.COMPLIANT,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RegulatoryChangeRecord:
        record = RegulatoryChangeRecord(
            change_name=change_name,
            change_type=change_type,
            impact_level=impact_level,
            readiness_state=readiness_state,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "regulatory_change_impact.change_recorded",
            record_id=record.id,
            change_name=change_name,
            change_type=change_type.value,
            impact_level=impact_level.value,
        )
        return record

    def get_change(self, record_id: str) -> RegulatoryChangeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_changes(
        self,
        change_type: ChangeType | None = None,
        impact_level: ImpactLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RegulatoryChangeRecord]:
        results = list(self._records)
        if change_type is not None:
            results = [r for r in results if r.change_type == change_type]
        if impact_level is not None:
            results = [r for r in results if r.impact_level == impact_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        change_name: str,
        change_type: ChangeType = ChangeType.NEW_REGULATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RegulatoryChangeAnalysis:
        analysis = RegulatoryChangeAnalysis(
            change_name=change_name,
            change_type=change_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "regulatory_change_impact.analysis_added",
            change_name=change_name,
            change_type=change_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by change_type; return count and avg impact_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.change_type.value
            type_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for ctype, scores in type_data.items():
            result[ctype] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_impact_changes(self) -> list[dict[str, Any]]:
        """Return records where impact_score > regulatory_impact_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact_score > self._regulatory_impact_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "change_name": r.change_name,
                        "change_type": r.change_type.value,
                        "impact_score": r.impact_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["impact_score"], reverse=True)

    def rank_by_impact_score(self) -> list[dict[str, Any]]:
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

    def detect_impact_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> RegulatoryChangeReport:
        by_type: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        by_readiness: dict[str, int] = {}
        for r in self._records:
            by_type[r.change_type.value] = by_type.get(r.change_type.value, 0) + 1
            by_impact[r.impact_level.value] = by_impact.get(r.impact_level.value, 0) + 1
            by_readiness[r.readiness_state.value] = by_readiness.get(r.readiness_state.value, 0) + 1
        high_impact_count = sum(
            1 for r in self._records if r.impact_score > self._regulatory_impact_threshold
        )
        scores = [r.impact_score for r in self._records]
        avg_impact_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_impact_changes()
        top_high_impact = [o["change_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_impact_count > 0:
            recs.append(
                f"{high_impact_count} change(s) above regulatory impact threshold "
                f"({self._regulatory_impact_threshold})"
            )
        if self._records and avg_impact_score > self._regulatory_impact_threshold:
            recs.append(
                f"Avg impact score {avg_impact_score} above threshold "
                f"({self._regulatory_impact_threshold})"
            )
        if not recs:
            recs.append("Regulatory change impact posture is healthy")
        return RegulatoryChangeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_impact_count=high_impact_count,
            avg_impact_score=avg_impact_score,
            by_type=by_type,
            by_impact=by_impact,
            by_readiness=by_readiness,
            top_high_impact=top_high_impact,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("regulatory_change_impact.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.change_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "regulatory_impact_threshold": self._regulatory_impact_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
