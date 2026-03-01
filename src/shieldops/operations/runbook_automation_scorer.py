"""Runbook Automation Scorer — score runbook automation level and identify opportunities."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AutomationLevel(StrEnum):
    FULLY_AUTOMATED = "fully_automated"
    MOSTLY_AUTOMATED = "mostly_automated"
    PARTIALLY_AUTOMATED = "partially_automated"
    MANUAL_WITH_TOOLING = "manual_with_tooling"
    FULLY_MANUAL = "fully_manual"


class AutomationBarrier(StrEnum):
    COMPLEXITY = "complexity"
    APPROVAL_REQUIRED = "approval_required"
    LEGACY_SYSTEM = "legacy_system"
    RISK_LEVEL = "risk_level"
    RESOURCE_CONSTRAINT = "resource_constraint"


class AutomationBenefit(StrEnum):
    TIME_SAVINGS = "time_savings"
    ERROR_REDUCTION = "error_reduction"
    CONSISTENCY = "consistency"
    SCALABILITY = "scalability"
    COST_REDUCTION = "cost_reduction"


# --- Models ---


class AutomationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    automation_level: AutomationLevel = AutomationLevel.FULLY_MANUAL
    automation_barrier: AutomationBarrier = AutomationBarrier.COMPLEXITY
    automation_benefit: AutomationBenefit = AutomationBenefit.TIME_SAVINGS
    automation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    automation_level: AutomationLevel = AutomationLevel.FULLY_MANUAL
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookAutomationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    manual_count: int = 0
    avg_automation_score: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_barrier: dict[str, int] = Field(default_factory=dict)
    by_benefit: dict[str, int] = Field(default_factory=dict)
    top_manual: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookAutomationScorer:
    """Score runbook automation level, identify automation opportunities, track progress."""

    def __init__(
        self,
        max_records: int = 200000,
        min_automation_score: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_automation_score = min_automation_score
        self._records: list[AutomationRecord] = []
        self._metrics: list[AutomationMetric] = []
        logger.info(
            "runbook_automation_scorer.initialized",
            max_records=max_records,
            min_automation_score=min_automation_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_automation(
        self,
        runbook_id: str,
        automation_level: AutomationLevel = AutomationLevel.FULLY_MANUAL,
        automation_barrier: AutomationBarrier = AutomationBarrier.COMPLEXITY,
        automation_benefit: AutomationBenefit = AutomationBenefit.TIME_SAVINGS,
        automation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AutomationRecord:
        record = AutomationRecord(
            runbook_id=runbook_id,
            automation_level=automation_level,
            automation_barrier=automation_barrier,
            automation_benefit=automation_benefit,
            automation_score=automation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runbook_automation_scorer.automation_recorded",
            record_id=record.id,
            runbook_id=runbook_id,
            automation_level=automation_level.value,
            automation_barrier=automation_barrier.value,
        )
        return record

    def get_automation(self, record_id: str) -> AutomationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_automations(
        self,
        automation_level: AutomationLevel | None = None,
        automation_barrier: AutomationBarrier | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AutomationRecord]:
        results = list(self._records)
        if automation_level is not None:
            results = [r for r in results if r.automation_level == automation_level]
        if automation_barrier is not None:
            results = [r for r in results if r.automation_barrier == automation_barrier]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        runbook_id: str,
        automation_level: AutomationLevel = AutomationLevel.FULLY_MANUAL,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AutomationMetric:
        metric = AutomationMetric(
            runbook_id=runbook_id,
            automation_level=automation_level,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "runbook_automation_scorer.metric_added",
            runbook_id=runbook_id,
            automation_level=automation_level.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_automation_distribution(self) -> dict[str, Any]:
        """Group by automation_level; return count and avg automation_score per level."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.automation_level.value
            level_data.setdefault(key, []).append(r.automation_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_automation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_manual_runbooks(self) -> list[dict[str, Any]]:
        """Return runbooks where level is MANUAL_WITH_TOOLING or FULLY_MANUAL."""
        manual_levels = {
            AutomationLevel.MANUAL_WITH_TOOLING,
            AutomationLevel.FULLY_MANUAL,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.automation_level in manual_levels:
                results.append(
                    {
                        "record_id": r.id,
                        "runbook_id": r.runbook_id,
                        "automation_level": r.automation_level.value,
                        "automation_barrier": r.automation_barrier.value,
                        "automation_score": r.automation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["automation_score"], reverse=False)
        return results

    def rank_by_automation(self) -> list[dict[str, Any]]:
        """Group by service, avg automation_score, sort asc (worst first)."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.automation_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_scores.items():
            results.append(
                {
                    "service": service,
                    "avg_automation_score": round(sum(scores) / len(scores), 2),
                    "runbook_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_automation_score"], reverse=False)
        return results

    def detect_automation_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> RunbookAutomationReport:
        by_level: dict[str, int] = {}
        by_barrier: dict[str, int] = {}
        by_benefit: dict[str, int] = {}
        for r in self._records:
            by_level[r.automation_level.value] = by_level.get(r.automation_level.value, 0) + 1
            by_barrier[r.automation_barrier.value] = (
                by_barrier.get(r.automation_barrier.value, 0) + 1
            )
            by_benefit[r.automation_benefit.value] = (
                by_benefit.get(r.automation_benefit.value, 0) + 1
            )
        manual_count = sum(
            1
            for r in self._records
            if r.automation_level
            in {AutomationLevel.MANUAL_WITH_TOOLING, AutomationLevel.FULLY_MANUAL}
        )
        avg_automation_score = (
            round(
                sum(r.automation_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        manual = self.identify_manual_runbooks()
        top_manual = [m["runbook_id"] for m in manual]
        recs: list[str] = []
        if manual:
            recs.append(
                f"{len(manual)} manual runbook(s) detected — review automation opportunities"
            )
        low_score = sum(1 for r in self._records if r.automation_score < self._min_automation_score)
        if low_score > 0:
            recs.append(
                f"{low_score} runbook(s) below automation threshold ({self._min_automation_score}%)"
            )
        if not recs:
            recs.append("Runbook automation levels are acceptable")
        return RunbookAutomationReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            manual_count=manual_count,
            avg_automation_score=avg_automation_score,
            by_level=by_level,
            by_barrier=by_barrier,
            by_benefit=by_benefit,
            top_manual=top_manual,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("runbook_automation_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.automation_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_automation_score": self._min_automation_score,
            "level_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_runbooks": len({r.runbook_id for r in self._records}),
        }
