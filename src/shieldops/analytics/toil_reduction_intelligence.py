"""Toil Reduction Intelligence
compute toil reduction trend, detect toil regression,
rank teams by toil burden."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ToilType(StrEnum):
    MANUAL_OPS = "manual_ops"
    REPETITIVE_TASK = "repetitive_task"
    INTERRUPT_DRIVEN = "interrupt_driven"
    PROCESS_OVERHEAD = "process_overhead"


class AutomationStatus(StrEnum):
    AUTOMATED = "automated"
    PARTIALLY_AUTOMATED = "partially_automated"
    MANUAL = "manual"
    PLANNED = "planned"


class ToilSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class ToilReductionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    toil_type: ToilType = ToilType.MANUAL_OPS
    automation_status: AutomationStatus = AutomationStatus.MANUAL
    toil_severity: ToilSeverity = ToilSeverity.MEDIUM
    hours_spent: float = 0.0
    hours_saved: float = 0.0
    task_count: int = 0
    category: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ToilReductionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    reduction_pct: float = 0.0
    toil_severity: ToilSeverity = ToilSeverity.MEDIUM
    regression_detected: bool = False
    data_points: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ToilReductionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_hours_spent: float = 0.0
    by_toil_type: dict[str, int] = Field(default_factory=dict)
    by_automation_status: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    high_toil_teams: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ToilReductionIntelligence:
    """Compute toil reduction trend, detect toil
    regression, rank teams by toil burden."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ToilReductionRecord] = []
        self._analyses: dict[str, ToilReductionAnalysis] = {}
        logger.info(
            "toil_reduction_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        team_id: str = "",
        toil_type: ToilType = ToilType.MANUAL_OPS,
        automation_status: AutomationStatus = AutomationStatus.MANUAL,
        toil_severity: ToilSeverity = ToilSeverity.MEDIUM,
        hours_spent: float = 0.0,
        hours_saved: float = 0.0,
        task_count: int = 0,
        category: str = "",
        description: str = "",
    ) -> ToilReductionRecord:
        record = ToilReductionRecord(
            team_id=team_id,
            toil_type=toil_type,
            automation_status=automation_status,
            toil_severity=toil_severity,
            hours_spent=hours_spent,
            hours_saved=hours_saved,
            task_count=task_count,
            category=category,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "toil_reduction_intelligence.record_added",
            record_id=record.id,
            team_id=team_id,
        )
        return record

    def process(self, key: str) -> ToilReductionAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        points = sum(1 for r in self._records if r.team_id == rec.team_id)
        reduction = round((rec.hours_saved / rec.hours_spent * 100) if rec.hours_spent else 0.0, 2)
        regression = rec.hours_saved < 0
        analysis = ToilReductionAnalysis(
            team_id=rec.team_id,
            reduction_pct=reduction,
            toil_severity=rec.toil_severity,
            regression_detected=regression,
            data_points=points,
            description=f"Team {rec.team_id} toil reduction {reduction}%",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ToilReductionReport:
        by_tt: dict[str, int] = {}
        by_as: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        hours: list[float] = []
        for r in self._records:
            k = r.toil_type.value
            by_tt[k] = by_tt.get(k, 0) + 1
            k2 = r.automation_status.value
            by_as[k2] = by_as.get(k2, 0) + 1
            k3 = r.toil_severity.value
            by_sev[k3] = by_sev.get(k3, 0) + 1
            hours.append(r.hours_spent)
        avg = round(sum(hours) / len(hours), 2) if hours else 0.0
        high_toil = list(
            {
                r.team_id
                for r in self._records
                if r.toil_severity in (ToilSeverity.CRITICAL, ToilSeverity.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if high_toil:
            recs.append(f"{len(high_toil)} teams with high toil burden")
        if not recs:
            recs.append("Toil levels within acceptable range")
        return ToilReductionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_hours_spent=avg,
            by_toil_type=by_tt,
            by_automation_status=by_as,
            by_severity=by_sev,
            high_toil_teams=high_toil,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        tt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.toil_type.value
            tt_dist[k] = tt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "toil_type_distribution": tt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("toil_reduction_intelligence.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_toil_reduction_trend(
        self,
    ) -> list[dict[str, Any]]:
        """Compute toil reduction trend per team."""
        team_data: dict[str, dict[str, float]] = {}
        for r in self._records:
            if r.team_id not in team_data:
                team_data[r.team_id] = {"spent": 0.0, "saved": 0.0, "count": 0}
            team_data[r.team_id]["spent"] += r.hours_spent
            team_data[r.team_id]["saved"] += r.hours_saved
            team_data[r.team_id]["count"] += 1
        results: list[dict[str, Any]] = []
        for tid, data in team_data.items():
            reduction = round((data["saved"] / data["spent"] * 100) if data["spent"] else 0.0, 2)
            results.append(
                {
                    "team_id": tid,
                    "total_hours_spent": round(data["spent"], 2),
                    "total_hours_saved": round(data["saved"], 2),
                    "reduction_pct": reduction,
                    "data_points": int(data["count"]),
                }
            )
        results.sort(key=lambda x: x["reduction_pct"], reverse=True)
        return results

    def detect_toil_regression(
        self,
    ) -> list[dict[str, Any]]:
        """Detect teams with toil regression."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.hours_saved < 0 and r.team_id not in seen:
                seen.add(r.team_id)
                results.append(
                    {
                        "team_id": r.team_id,
                        "toil_type": r.toil_type.value,
                        "hours_spent": r.hours_spent,
                        "hours_saved": r.hours_saved,
                        "regression_amount": round(abs(r.hours_saved), 2),
                    }
                )
        results.sort(key=lambda x: x["regression_amount"], reverse=True)
        return results

    def rank_teams_by_toil_burden(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all teams by toil burden."""
        team_data: dict[str, float] = {}
        for r in self._records:
            team_data[r.team_id] = team_data.get(r.team_id, 0.0) + r.hours_spent
        results: list[dict[str, Any]] = []
        for tid, total in team_data.items():
            results.append(
                {
                    "team_id": tid,
                    "total_hours_spent": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_hours_spent"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
