"""Runbook Effectiveness Scorer — score runbook effectiveness and outcomes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EffectivenessLevel(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    INEFFECTIVE = "ineffective"


class ExecutionOutcome(StrEnum):
    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    FAILED = "failed"
    SKIPPED = "skipped"
    ESCALATED = "escalated"


class RunbookCategory(StrEnum):
    INCIDENT_RESPONSE = "incident_response"
    MAINTENANCE = "maintenance"
    SCALING = "scaling"
    RECOVERY = "recovery"
    DIAGNOSTIC = "diagnostic"


# --- Models ---


class EffectivenessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    effectiveness_level: EffectivenessLevel = EffectivenessLevel.ADEQUATE
    execution_outcome: ExecutionOutcome = ExecutionOutcome.RESOLVED
    runbook_category: RunbookCategory = RunbookCategory.INCIDENT_RESPONSE
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EffectivenessMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    effectiveness_level: EffectivenessLevel = EffectivenessLevel.ADEQUATE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookEffectivenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    poor_runbooks: int = 0
    avg_effectiveness_score: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_poor_runbooks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookEffectivenessScorer:
    """Score runbook effectiveness, track execution outcomes, detect underperforming."""

    def __init__(
        self,
        max_records: int = 200000,
        min_effectiveness_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_effectiveness_score = min_effectiveness_score
        self._records: list[EffectivenessRecord] = []
        self._metrics: list[EffectivenessMetric] = []
        logger.info(
            "runbook_effectiveness_scorer.initialized",
            max_records=max_records,
            min_effectiveness_score=min_effectiveness_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_effectiveness(
        self,
        runbook_id: str,
        effectiveness_level: EffectivenessLevel = EffectivenessLevel.ADEQUATE,
        execution_outcome: ExecutionOutcome = ExecutionOutcome.RESOLVED,
        runbook_category: RunbookCategory = RunbookCategory.INCIDENT_RESPONSE,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EffectivenessRecord:
        record = EffectivenessRecord(
            runbook_id=runbook_id,
            effectiveness_level=effectiveness_level,
            execution_outcome=execution_outcome,
            runbook_category=runbook_category,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runbook_effectiveness_scorer.effectiveness_recorded",
            record_id=record.id,
            runbook_id=runbook_id,
            effectiveness_level=effectiveness_level.value,
            execution_outcome=execution_outcome.value,
        )
        return record

    def get_effectiveness(self, record_id: str) -> EffectivenessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_effectiveness(
        self,
        effectiveness_level: EffectivenessLevel | None = None,
        execution_outcome: ExecutionOutcome | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EffectivenessRecord]:
        results = list(self._records)
        if effectiveness_level is not None:
            results = [r for r in results if r.effectiveness_level == effectiveness_level]
        if execution_outcome is not None:
            results = [r for r in results if r.execution_outcome == execution_outcome]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        runbook_id: str,
        effectiveness_level: EffectivenessLevel = EffectivenessLevel.ADEQUATE,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EffectivenessMetric:
        metric = EffectivenessMetric(
            runbook_id=runbook_id,
            effectiveness_level=effectiveness_level,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "runbook_effectiveness_scorer.metric_added",
            runbook_id=runbook_id,
            effectiveness_level=effectiveness_level.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_effectiveness_distribution(self) -> dict[str, Any]:
        """Group by effectiveness_level; return count and avg score."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.effectiveness_level.value
            level_data.setdefault(key, []).append(r.effectiveness_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_poor_runbooks(self) -> list[dict[str, Any]]:
        """Return records where level is POOR or INEFFECTIVE."""
        poor_levels = {
            EffectivenessLevel.POOR,
            EffectivenessLevel.INEFFECTIVE,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_level in poor_levels:
                results.append(
                    {
                        "record_id": r.id,
                        "runbook_id": r.runbook_id,
                        "effectiveness_level": r.effectiveness_level.value,
                        "execution_outcome": r.execution_outcome.value,
                        "runbook_category": r.runbook_category.value,
                        "effectiveness_score": r.effectiveness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["effectiveness_score"], reverse=False)
        return results

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        """Group by service, avg effectiveness_score, sort asc (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_effectiveness": round(sum(scores) / len(scores), 2),
                    "runbook_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness"], reverse=False)
        return results

    def detect_effectiveness_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [m.metric_score for m in self._metrics]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> RunbookEffectivenessReport:
        by_level: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_level[r.effectiveness_level.value] = by_level.get(r.effectiveness_level.value, 0) + 1
            by_outcome[r.execution_outcome.value] = by_outcome.get(r.execution_outcome.value, 0) + 1
            by_category[r.runbook_category.value] = by_category.get(r.runbook_category.value, 0) + 1
        poor_runbooks = sum(
            1
            for r in self._records
            if r.effectiveness_level in {EffectivenessLevel.POOR, EffectivenessLevel.INEFFECTIVE}
        )
        avg_score = (
            round(
                sum(r.effectiveness_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        poor = self.identify_poor_runbooks()
        top_poor_runbooks = [p["runbook_id"] for p in poor]
        recs: list[str] = []
        if poor:
            recs.append(f"{len(poor)} poor/ineffective runbook(s) detected — review and update")
        low_score = sum(
            1 for r in self._records if r.effectiveness_score < self._min_effectiveness_score
        )
        if low_score > 0:
            recs.append(
                f"{low_score} runbook(s) below effectiveness threshold"
                f" ({self._min_effectiveness_score}%)"
            )
        if not recs:
            recs.append("Runbook effectiveness levels are acceptable")
        return RunbookEffectivenessReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            poor_runbooks=poor_runbooks,
            avg_effectiveness_score=avg_score,
            by_level=by_level,
            by_outcome=by_outcome,
            by_category=by_category,
            top_poor_runbooks=top_poor_runbooks,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("runbook_effectiveness_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.effectiveness_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_effectiveness_score": self._min_effectiveness_score,
            "level_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_runbooks": len({r.runbook_id for r in self._records}),
        }
