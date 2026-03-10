"""Automation Effectiveness Engine — automation ROI and effectiveness analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AutomationType(StrEnum):
    RUNBOOK = "runbook"
    POLICY = "policy"
    WORKFLOW = "workflow"
    SELF_HEALING = "self_healing"


class EffectivenessMetric(StrEnum):
    SUCCESS_RATE = "success_rate"
    TIME_SAVED = "time_saved"
    ERROR_REDUCTION = "error_reduction"
    COST_SAVINGS = "cost_savings"


class MaturityLevel(StrEnum):
    MANUAL = "manual"
    SCRIPTED = "scripted"
    AUTOMATED = "automated"
    AUTONOMOUS = "autonomous"


# --- Models ---


class EffectivenessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    automation_type: AutomationType = AutomationType.RUNBOOK
    effectiveness_metric: EffectivenessMetric = EffectivenessMetric.SUCCESS_RATE
    maturity_level: MaturityLevel = MaturityLevel.MANUAL
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EffectivenessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    automation_type: AutomationType = AutomationType.RUNBOOK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationEffectivenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_automation_type: dict[str, int] = Field(default_factory=dict)
    by_effectiveness_metric: dict[str, int] = Field(default_factory=dict)
    by_maturity_level: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomationEffectivenessEngine:
    """Automation Effectiveness Engine
    for automation ROI and effectiveness analysis.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[EffectivenessRecord] = []
        self._analyses: list[EffectivenessAnalysis] = []
        logger.info(
            "automation_effectiveness_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        automation_type: AutomationType = (AutomationType.RUNBOOK),
        effectiveness_metric: EffectivenessMetric = (EffectivenessMetric.SUCCESS_RATE),
        maturity_level: MaturityLevel = (MaturityLevel.MANUAL),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EffectivenessRecord:
        record = EffectivenessRecord(
            name=name,
            automation_type=automation_type,
            effectiveness_metric=effectiveness_metric,
            maturity_level=maturity_level,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "automation_effectiveness_engine.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> EffectivenessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        automation_type: AutomationType | None = None,
        maturity_level: MaturityLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EffectivenessRecord]:
        results = list(self._records)
        if automation_type is not None:
            results = [r for r in results if r.automation_type == automation_type]
        if maturity_level is not None:
            results = [r for r in results if r.maturity_level == maturity_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        automation_type: AutomationType = (AutomationType.RUNBOOK),
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EffectivenessAnalysis:
        analysis = EffectivenessAnalysis(
            name=name,
            automation_type=automation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "automation_effectiveness_engine.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def compute_automation_roi(self) -> dict[str, Any]:
        """Compute ROI for each automation type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            type_data.setdefault(r.automation_type.value, []).append(r.score)
        roi: dict[str, Any] = {}
        cost_map = {
            "runbook": 1.0,
            "policy": 0.8,
            "workflow": 1.5,
            "self_healing": 2.0,
        }
        for atype, scores in type_data.items():
            avg = round(sum(scores) / len(scores), 2)
            cost = cost_map.get(atype, 1.0)
            roi[atype] = {
                "avg_effectiveness": avg,
                "investment_cost": cost,
                "roi_ratio": round(avg / cost, 2),
                "count": len(scores),
            }
        return {
            "roi_by_type": roi,
            "total_automations": len(self._records),
        }

    def identify_automation_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Identify gaps in automation coverage."""
        svc_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.service not in svc_data:
                svc_data[r.service] = {
                    "types": set(),
                    "scores": [],
                    "maturity_levels": [],
                }
            svc_data[r.service]["types"].add(r.automation_type.value)
            svc_data[r.service]["scores"].append(r.score)
            svc_data[r.service]["maturity_levels"].append(r.maturity_level.value)
        all_types = {t.value for t in AutomationType}
        gaps: list[dict[str, Any]] = []
        for svc, data in svc_data.items():
            missing = all_types - data["types"]
            avg = round(
                sum(data["scores"]) / len(data["scores"]),
                2,
            )
            gaps.append(
                {
                    "service": svc,
                    "missing_types": sorted(missing),
                    "coverage_pct": round(len(data["types"]) / len(all_types) * 100, 2),
                    "avg_score": avg,
                    "has_gaps": len(missing) > 0 or avg < self._threshold,
                }
            )
        gaps.sort(key=lambda x: x["coverage_pct"])
        return gaps

    def benchmark_effectiveness(
        self,
    ) -> dict[str, Any]:
        """Benchmark effectiveness across maturity levels."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            level_data.setdefault(r.maturity_level.value, []).append(r.score)
        benchmarks: dict[str, Any] = {}
        for level, scores in level_data.items():
            avg = round(sum(scores) / len(scores), 2)
            benchmarks[level] = {
                "count": len(scores),
                "avg_score": avg,
                "meets_threshold": avg >= self._threshold,
            }
        return {
            "benchmarks": benchmarks,
            "total_records": len(self._records),
        }

    # -- report / stats -----------------------------------------------

    def generate_report(
        self,
    ) -> AutomationEffectivenessReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.automation_type.value] = by_e1.get(r.automation_type.value, 0) + 1
            by_e2[r.effectiveness_metric.value] = by_e2.get(r.effectiveness_metric.value, 0) + 1
            by_e3[r.maturity_level.value] = by_e3.get(r.maturity_level.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = [r.name for r in self._records if r.score < self._threshold][:5]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Automation Effectiveness Engine is healthy")
        return AutomationEffectivenessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_automation_type=by_e1,
            by_effectiveness_metric=by_e2,
            by_maturity_level=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("automation_effectiveness_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.automation_type.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "automation_type_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
