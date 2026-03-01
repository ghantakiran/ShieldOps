"""Regulatory Change Tracker — track regulatory changes, analyze compliance impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RegulationType(StrEnum):
    GDPR = "gdpr"
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"


class ChangeImpact(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class ComplianceAction(StrEnum):
    POLICY_UPDATE = "policy_update"
    CONTROL_ADDITION = "control_addition"
    PROCESS_CHANGE = "process_change"
    TRAINING_REQUIRED = "training_required"
    NO_ACTION = "no_action"


# --- Models ---


class RegulatoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    regulation_id: str = ""
    regulation_type: RegulationType = RegulationType.GDPR
    change_impact: ChangeImpact = ChangeImpact.INFORMATIONAL
    compliance_action: ComplianceAction = ComplianceAction.NO_ACTION
    impact_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    analysis_pattern: str = ""
    regulation_type: RegulationType = RegulationType.GDPR
    urgency_score: float = 0.0
    affected_controls: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RegulatoryChangeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_impact_changes: int = 0
    avg_impact_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    urgent: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RegulatoryChangeTracker:
    """Track regulatory changes, analyze compliance impact, prioritize actions."""

    def __init__(
        self,
        max_records: int = 200000,
        max_impact_score: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._max_impact_score = max_impact_score
        self._records: list[RegulatoryRecord] = []
        self._analyses: list[ImpactAnalysis] = []
        logger.info(
            "regulation_tracker.initialized",
            max_records=max_records,
            max_impact_score=max_impact_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_change(
        self,
        regulation_id: str,
        regulation_type: RegulationType = RegulationType.GDPR,
        change_impact: ChangeImpact = ChangeImpact.INFORMATIONAL,
        compliance_action: ComplianceAction = ComplianceAction.NO_ACTION,
        impact_score: float = 0.0,
        team: str = "",
    ) -> RegulatoryRecord:
        record = RegulatoryRecord(
            regulation_id=regulation_id,
            regulation_type=regulation_type,
            change_impact=change_impact,
            compliance_action=compliance_action,
            impact_score=impact_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "regulation_tracker.change_recorded",
            record_id=record.id,
            regulation_id=regulation_id,
            regulation_type=regulation_type.value,
            change_impact=change_impact.value,
        )
        return record

    def get_change(self, record_id: str) -> RegulatoryRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_changes(
        self,
        regulation_type: RegulationType | None = None,
        change_impact: ChangeImpact | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RegulatoryRecord]:
        results = list(self._records)
        if regulation_type is not None:
            results = [r for r in results if r.regulation_type == regulation_type]
        if change_impact is not None:
            results = [r for r in results if r.change_impact == change_impact]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        analysis_pattern: str,
        regulation_type: RegulationType = RegulationType.GDPR,
        urgency_score: float = 0.0,
        affected_controls: int = 0,
        description: str = "",
    ) -> ImpactAnalysis:
        analysis = ImpactAnalysis(
            analysis_pattern=analysis_pattern,
            regulation_type=regulation_type,
            urgency_score=urgency_score,
            affected_controls=affected_controls,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "regulation_tracker.analysis_added",
            analysis_pattern=analysis_pattern,
            regulation_type=regulation_type.value,
            urgency_score=urgency_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_regulatory_impact(self) -> dict[str, Any]:
        """Group by regulation_type; return count and avg impact_score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.regulation_type.value
            type_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for rtype, scores in type_data.items():
            result[rtype] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_impact_changes(self) -> list[dict[str, Any]]:
        """Return records where impact_score >= max_impact_score."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact_score >= self._max_impact_score:
                results.append(
                    {
                        "record_id": r.id,
                        "regulation_id": r.regulation_id,
                        "impact_score": r.impact_score,
                        "regulation_type": r.regulation_type.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_urgency(self) -> list[dict[str, Any]]:
        """Group by team, total impact_score, sort descending."""
        team_scores: dict[str, float] = {}
        for r in self._records:
            team_scores[r.team] = team_scores.get(r.team, 0) + r.impact_score
        results: list[dict[str, Any]] = []
        for team, total in team_scores.items():
            results.append(
                {
                    "team": team,
                    "total_impact": total,
                }
            )
        results.sort(key=lambda x: x["total_impact"], reverse=True)
        return results

    def detect_regulatory_trends(self) -> dict[str, Any]:
        """Split-half on impact_score; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [r.impact_score for r in self._records]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
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
        by_action: dict[str, int] = {}
        for r in self._records:
            by_type[r.regulation_type.value] = by_type.get(r.regulation_type.value, 0) + 1
            by_impact[r.change_impact.value] = by_impact.get(r.change_impact.value, 0) + 1
            by_action[r.compliance_action.value] = by_action.get(r.compliance_action.value, 0) + 1
        high_impact = sum(1 for r in self._records if r.impact_score >= self._max_impact_score)
        avg_score = (
            round(sum(r.impact_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        urgent_ids = [
            r.regulation_id for r in self._records if r.impact_score >= self._max_impact_score
        ][:5]
        recs: list[str] = []
        if high_impact > 0:
            recs.append(
                f"{high_impact} change(s) at or above impact threshold ({self._max_impact_score})"
            )
        if self._records and avg_score >= self._max_impact_score:
            recs.append(
                f"Average impact score {avg_score} exceeds threshold ({self._max_impact_score})"
            )
        if not recs:
            recs.append("Regulatory change levels are healthy")
        return RegulatoryChangeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_impact_changes=high_impact,
            avg_impact_score=avg_score,
            by_type=by_type,
            by_impact=by_impact,
            by_action=by_action,
            urgent=urgent_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("regulation_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.regulation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "max_impact_score": self._max_impact_score,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_regulations": len({r.regulation_id for r in self._records}),
        }
