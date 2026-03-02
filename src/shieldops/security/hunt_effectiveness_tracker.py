"""Hunt Effectiveness Tracker — track hunt outcomes and ROI."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HuntType(StrEnum):
    HYPOTHESIS_DRIVEN = "hypothesis_driven"
    INTEL_DRIVEN = "intel_driven"
    ANOMALY_BASED = "anomaly_based"
    AUTOMATED = "automated"
    AD_HOC = "ad_hoc"


class HuntOutcome(StrEnum):
    THREAT_FOUND = "threat_found"
    FALSE_POSITIVE = "false_positive"
    INCONCLUSIVE = "inconclusive"
    NEW_DETECTION = "new_detection"
    NO_FINDINGS = "no_findings"


class HuntROI(StrEnum):
    HIGH_VALUE = "high_value"
    MODERATE_VALUE = "moderate_value"
    LOW_VALUE = "low_value"
    BREAK_EVEN = "break_even"
    NEGATIVE_ROI = "negative_roi"


# --- Models ---


class HuntRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hunt_name: str = ""
    hunt_type: HuntType = HuntType.HYPOTHESIS_DRIVEN
    hunt_outcome: HuntOutcome = HuntOutcome.THREAT_FOUND
    hunt_roi: HuntROI = HuntROI.HIGH_VALUE
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class HuntAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hunt_name: str = ""
    hunt_type: HuntType = HuntType.HYPOTHESIS_DRIVEN
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class HuntReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_effectiveness_count: int = 0
    avg_effectiveness_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_roi: dict[str, int] = Field(default_factory=dict)
    top_low_effectiveness: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class HuntEffectivenessTracker:
    """Track hunt outcomes and ROI for threat hunting operations."""

    def __init__(
        self,
        max_records: int = 200000,
        hunt_effectiveness_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._hunt_effectiveness_threshold = hunt_effectiveness_threshold
        self._records: list[HuntRecord] = []
        self._analyses: list[HuntAnalysis] = []
        logger.info(
            "hunt_effectiveness_tracker.initialized",
            max_records=max_records,
            hunt_effectiveness_threshold=hunt_effectiveness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_hunt(
        self,
        hunt_name: str,
        hunt_type: HuntType = HuntType.HYPOTHESIS_DRIVEN,
        hunt_outcome: HuntOutcome = HuntOutcome.THREAT_FOUND,
        hunt_roi: HuntROI = HuntROI.HIGH_VALUE,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> HuntRecord:
        record = HuntRecord(
            hunt_name=hunt_name,
            hunt_type=hunt_type,
            hunt_outcome=hunt_outcome,
            hunt_roi=hunt_roi,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "hunt_effectiveness_tracker.hunt_recorded",
            record_id=record.id,
            hunt_name=hunt_name,
            hunt_type=hunt_type.value,
            hunt_outcome=hunt_outcome.value,
        )
        return record

    def get_hunt(self, record_id: str) -> HuntRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_hunts(
        self,
        hunt_type: HuntType | None = None,
        hunt_outcome: HuntOutcome | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[HuntRecord]:
        results = list(self._records)
        if hunt_type is not None:
            results = [r for r in results if r.hunt_type == hunt_type]
        if hunt_outcome is not None:
            results = [r for r in results if r.hunt_outcome == hunt_outcome]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        hunt_name: str,
        hunt_type: HuntType = HuntType.HYPOTHESIS_DRIVEN,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> HuntAnalysis:
        analysis = HuntAnalysis(
            hunt_name=hunt_name,
            hunt_type=hunt_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "hunt_effectiveness_tracker.analysis_added",
            hunt_name=hunt_name,
            hunt_type=hunt_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_hunt_distribution(self) -> dict[str, Any]:
        """Group by hunt_type; return count and avg effectiveness_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.hunt_type.value
            src_data.setdefault(key, []).append(r.effectiveness_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_effectiveness_hunts(self) -> list[dict[str, Any]]:
        """Return records where effectiveness_score < hunt_effectiveness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_score < self._hunt_effectiveness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "hunt_name": r.hunt_name,
                        "hunt_type": r.hunt_type.value,
                        "effectiveness_score": r.effectiveness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["effectiveness_score"])

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        """Group by service, avg effectiveness_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"])
        return results

    def detect_hunt_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> HuntReport:
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        by_roi: dict[str, int] = {}
        for r in self._records:
            by_type[r.hunt_type.value] = by_type.get(r.hunt_type.value, 0) + 1
            by_outcome[r.hunt_outcome.value] = by_outcome.get(r.hunt_outcome.value, 0) + 1
            by_roi[r.hunt_roi.value] = by_roi.get(r.hunt_roi.value, 0) + 1
        low_effectiveness_count = sum(
            1 for r in self._records if r.effectiveness_score < self._hunt_effectiveness_threshold
        )
        scores = [r.effectiveness_score for r in self._records]
        avg_effectiveness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_effectiveness_hunts()
        top_low_effectiveness = [o["hunt_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_effectiveness_count > 0:
            recs.append(
                f"{low_effectiveness_count} hunt(s) below effectiveness threshold "
                f"({self._hunt_effectiveness_threshold})"
            )
        if self._records and avg_effectiveness_score < self._hunt_effectiveness_threshold:
            recs.append(
                f"Avg effectiveness score {avg_effectiveness_score} below threshold "
                f"({self._hunt_effectiveness_threshold})"
            )
        if not recs:
            recs.append("Hunt effectiveness is healthy")
        return HuntReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_effectiveness_count=low_effectiveness_count,
            avg_effectiveness_score=avg_effectiveness_score,
            by_type=by_type,
            by_outcome=by_outcome,
            by_roi=by_roi,
            top_low_effectiveness=top_low_effectiveness,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("hunt_effectiveness_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.hunt_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "hunt_effectiveness_threshold": self._hunt_effectiveness_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
