"""Burnout Risk Detector — detect and intervene on engineer burnout risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BurnoutIndicator(StrEnum):
    OVERTIME = "overtime"
    PAGE_FREQUENCY = "page_frequency"
    CONTEXT_SWITCHES = "context_switches"
    MEETING_LOAD = "meeting_load"
    INCIDENT_EXPOSURE = "incident_exposure"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


class InterventionType(StrEnum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    PREVENTIVE = "preventive"


# --- Models ---


class BurnoutRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    team: str = ""
    burnout_indicator: BurnoutIndicator = BurnoutIndicator.OVERTIME
    risk_level: RiskLevel = RiskLevel.MINIMAL
    intervention_type: InterventionType = InterventionType.PREVENTIVE
    risk_score: float = 0.0
    overtime_hours: float = 0.0
    created_at: float = Field(default_factory=time.time)


class BurnoutAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    burnout_indicator: BurnoutIndicator = BurnoutIndicator.OVERTIME
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BurnoutReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_indicator: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    by_intervention: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class BurnoutRiskDetector:
    """Detect burnout risk signals and recommend interventions for engineers."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[BurnoutRecord] = []
        self._analyses: list[BurnoutAnalysis] = []
        logger.info(
            "burnout_risk_detector.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_burnout(
        self,
        engineer: str,
        team: str = "",
        burnout_indicator: BurnoutIndicator = BurnoutIndicator.OVERTIME,
        risk_level: RiskLevel = RiskLevel.MINIMAL,
        intervention_type: InterventionType = InterventionType.PREVENTIVE,
        risk_score: float = 0.0,
        overtime_hours: float = 0.0,
    ) -> BurnoutRecord:
        record = BurnoutRecord(
            engineer=engineer,
            team=team,
            burnout_indicator=burnout_indicator,
            risk_level=risk_level,
            intervention_type=intervention_type,
            risk_score=risk_score,
            overtime_hours=overtime_hours,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "burnout_risk_detector.burnout_recorded",
            record_id=record.id,
            engineer=engineer,
            burnout_indicator=burnout_indicator.value,
            risk_level=risk_level.value,
        )
        return record

    def get_burnout(self, record_id: str) -> BurnoutRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_burnouts(
        self,
        burnout_indicator: BurnoutIndicator | None = None,
        risk_level: RiskLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BurnoutRecord]:
        results = list(self._records)
        if burnout_indicator is not None:
            results = [r for r in results if r.burnout_indicator == burnout_indicator]
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        engineer: str,
        burnout_indicator: BurnoutIndicator = BurnoutIndicator.OVERTIME,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BurnoutAnalysis:
        analysis = BurnoutAnalysis(
            engineer=engineer,
            burnout_indicator=burnout_indicator,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "burnout_risk_detector.analysis_added",
            engineer=engineer,
            burnout_indicator=burnout_indicator.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by burnout_indicator; return count and avg risk_score."""
        ind_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.burnout_indicator.value
            ind_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for ind, scores in ind_data.items():
            result[ind] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_burnout_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score >= threshold (high risk)."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score >= self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "engineer": r.engineer,
                        "burnout_indicator": r.burnout_indicator.value,
                        "risk_score": r.risk_score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"], reverse=True)

    def rank_by_risk(self) -> list[dict[str, Any]]:
        """Group by engineer, avg risk_score, sort descending."""
        eng_scores: dict[str, list[float]] = {}
        for r in self._records:
            eng_scores.setdefault(r.engineer, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for engineer, scores in eng_scores.items():
            results.append(
                {
                    "engineer": engineer,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_burnout_trends(self) -> dict[str, Any]:
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
            trend = "worsening"
        else:
            trend = "improving"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> BurnoutReport:
        by_indicator: dict[str, int] = {}
        by_risk_level: dict[str, int] = {}
        by_intervention: dict[str, int] = {}
        for r in self._records:
            by_indicator[r.burnout_indicator.value] = (
                by_indicator.get(r.burnout_indicator.value, 0) + 1
            )
            by_risk_level[r.risk_level.value] = by_risk_level.get(r.risk_level.value, 0) + 1
            by_intervention[r.intervention_type.value] = (
                by_intervention.get(r.intervention_type.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.risk_score >= self._threshold)
        scores = [r.risk_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_burnout_gaps()
        top_gaps = [o["engineer"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} engineer(s) above burnout threshold ({self._threshold})")
        if self._records and avg_score >= self._threshold:
            recs.append(f"Avg risk score {avg_score} at or above threshold ({self._threshold})")
        if not recs:
            recs.append("Burnout risk is at healthy levels")
        return BurnoutReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_score,
            by_indicator=by_indicator,
            by_risk_level=by_risk_level,
            by_intervention=by_intervention,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("burnout_risk_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        ind_dist: dict[str, int] = {}
        for r in self._records:
            key = r.burnout_indicator.value
            ind_dist[key] = ind_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "indicator_distribution": ind_dist,
            "unique_engineers": len({r.engineer for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
