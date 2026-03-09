"""SRE Toil Intelligence

Toil classification, automation ROI scoring, effort tracking, and
elimination prioritization for SRE operational efficiency.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ToilCategory(StrEnum):
    MANUAL_REMEDIATION = "manual_remediation"
    ALERT_RESPONSE = "alert_response"
    DEPLOYMENT = "deployment"
    CONFIGURATION = "configuration"
    ACCESS_MANAGEMENT = "access_management"
    CAPACITY_PLANNING = "capacity_planning"
    INCIDENT_MANAGEMENT = "incident_management"
    MONITORING_TUNING = "monitoring_tuning"
    OTHER = "other"


class AutomationFeasibility(StrEnum):
    FULLY_AUTOMATABLE = "fully_automatable"
    PARTIALLY_AUTOMATABLE = "partially_automatable"
    REQUIRES_TOOLING = "requires_tooling"
    NOT_AUTOMATABLE = "not_automatable"
    ALREADY_AUTOMATED = "already_automated"


class EffortLevel(StrEnum):
    TRIVIAL = "trivial"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# --- Models ---


class ToilRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_name: str = ""
    toil_category: ToilCategory = ToilCategory.OTHER
    automation_feasibility: AutomationFeasibility = AutomationFeasibility.NOT_AUTOMATABLE
    effort_level: EffortLevel = EffortLevel.MEDIUM
    time_spent_minutes: float = 0.0
    frequency_per_week: float = 0.0
    people_involved: int = 1
    is_repetitive: bool = True
    is_automatable: bool = False
    automation_cost_hours: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ToilAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_name: str = ""
    toil_category: ToilCategory = ToilCategory.OTHER
    annual_hours_spent: float = 0.0
    automation_roi_score: float = 0.0
    payback_period_weeks: float = 0.0
    priority_rank: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ToilIntelligenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_weekly_hours: float = 0.0
    total_annual_hours: float = 0.0
    automatable_pct: float = 0.0
    potential_savings_hours: float = 0.0
    avg_roi_score: float = 0.0
    by_toil_category: dict[str, int] = Field(default_factory=dict)
    by_automation_feasibility: dict[str, int] = Field(default_factory=dict)
    by_effort_level: dict[str, int] = Field(default_factory=dict)
    top_elimination_targets: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SreToilIntelligence:
    """SRE Toil Intelligence

    Toil classification, automation ROI scoring, effort tracking, and
    elimination prioritization.
    """

    def __init__(
        self,
        max_records: int = 200000,
        toil_budget_pct: float = 50.0,
        engineer_hourly_cost: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._toil_budget_pct = toil_budget_pct
        self._hourly_cost = engineer_hourly_cost
        self._records: list[ToilRecord] = []
        self._analyses: list[ToilAnalysis] = []
        logger.info(
            "sre_toil_intelligence.initialized",
            max_records=max_records,
            toil_budget_pct=toil_budget_pct,
        )

    def add_record(
        self,
        task_name: str,
        toil_category: ToilCategory = ToilCategory.OTHER,
        automation_feasibility: AutomationFeasibility = AutomationFeasibility.NOT_AUTOMATABLE,
        effort_level: EffortLevel = EffortLevel.MEDIUM,
        time_spent_minutes: float = 0.0,
        frequency_per_week: float = 0.0,
        people_involved: int = 1,
        is_repetitive: bool = True,
        automation_cost_hours: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ToilRecord:
        is_automatable = automation_feasibility in (
            AutomationFeasibility.FULLY_AUTOMATABLE,
            AutomationFeasibility.PARTIALLY_AUTOMATABLE,
        )
        record = ToilRecord(
            task_name=task_name,
            toil_category=toil_category,
            automation_feasibility=automation_feasibility,
            effort_level=effort_level,
            time_spent_minutes=time_spent_minutes,
            frequency_per_week=frequency_per_week,
            people_involved=people_involved,
            is_repetitive=is_repetitive,
            is_automatable=is_automatable,
            automation_cost_hours=automation_cost_hours,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "sre_toil_intelligence.record_added",
            record_id=record.id,
            task_name=task_name,
            toil_category=toil_category.value,
            is_automatable=is_automatable,
        )
        return record

    def get_record(self, record_id: str) -> ToilRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        toil_category: ToilCategory | None = None,
        automation_feasibility: AutomationFeasibility | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ToilRecord]:
        results = list(self._records)
        if toil_category is not None:
            results = [r for r in results if r.toil_category == toil_category]
        if automation_feasibility is not None:
            results = [r for r in results if r.automation_feasibility == automation_feasibility]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def compute_roi(self, task_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.task_name == task_name]
        if not matching:
            return {"task_name": task_name, "status": "no_data"}
        latest = matching[-1]
        weekly_hours = (
            latest.time_spent_minutes / 60.0 * latest.frequency_per_week * latest.people_involved
        )
        annual_hours = weekly_hours * 52
        annual_cost = round(annual_hours * self._hourly_cost, 2)
        automation_cost = round(latest.automation_cost_hours * self._hourly_cost, 2)
        if automation_cost > 0:
            roi_score = round(annual_cost / automation_cost, 2)
            payback_weeks = round(automation_cost / max(1, weekly_hours * self._hourly_cost), 1)
        else:
            roi_score = 0.0
            payback_weeks = 0.0
        return {
            "task_name": task_name,
            "weekly_hours": round(weekly_hours, 2),
            "annual_hours": round(annual_hours, 2),
            "annual_cost_usd": annual_cost,
            "automation_cost_usd": automation_cost,
            "roi_score": roi_score,
            "payback_period_weeks": payback_weeks,
            "is_automatable": latest.is_automatable,
        }

    def prioritize_elimination(self, top_n: int = 10) -> list[dict[str, Any]]:
        task_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.task_name not in task_data:
                task_data[r.task_name] = {
                    "task_name": r.task_name,
                    "category": r.toil_category.value,
                    "total_weekly_hours": 0.0,
                    "automation_cost_hours": r.automation_cost_hours,
                    "is_automatable": r.is_automatable,
                    "feasibility": r.automation_feasibility.value,
                }
            weekly = r.time_spent_minutes / 60.0 * r.frequency_per_week * r.people_involved
            task_data[r.task_name]["total_weekly_hours"] += weekly
        results: list[dict[str, Any]] = []
        for entry in task_data.values():
            annual = entry["total_weekly_hours"] * 52
            auto_cost = entry["automation_cost_hours"] * self._hourly_cost
            annual_cost = annual * self._hourly_cost
            roi = round(annual_cost / max(1, auto_cost), 2) if entry["is_automatable"] else 0.0
            results.append(
                {
                    "task_name": entry["task_name"],
                    "category": entry["category"],
                    "weekly_hours": round(entry["total_weekly_hours"], 2),
                    "annual_cost_usd": round(annual_cost, 2),
                    "roi_score": roi,
                    "is_automatable": entry["is_automatable"],
                    "feasibility": entry["feasibility"],
                }
            )
        return sorted(results, key=lambda x: x["roi_score"], reverse=True)[:top_n]

    def compute_toil_budget(self, team: str = "") -> dict[str, Any]:
        matching = list(self._records)
        if team:
            matching = [r for r in matching if r.team == team]
        if not matching:
            return {"team": team or "all", "status": "no_data"}
        total_weekly = sum(
            r.time_spent_minutes / 60.0 * r.frequency_per_week * r.people_involved for r in matching
        )
        unique_people = len({r.team for r in matching}) * 2
        available_hours = unique_people * 40
        toil_pct = round(total_weekly / max(1, available_hours) * 100, 2)
        return {
            "team": team or "all",
            "total_weekly_toil_hours": round(total_weekly, 2),
            "estimated_team_hours": available_hours,
            "toil_percentage": toil_pct,
            "budget_limit_pct": self._toil_budget_pct,
            "within_budget": toil_pct <= self._toil_budget_pct,
            "overage_pct": round(max(0, toil_pct - self._toil_budget_pct), 2),
        }

    def process(self, task_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.task_name == task_name]
        if not matching:
            return {"task_name": task_name, "status": "no_data"}
        roi_data = self.compute_roi(task_name)
        analysis = ToilAnalysis(
            task_name=task_name,
            toil_category=matching[-1].toil_category,
            annual_hours_spent=roi_data.get("annual_hours", 0.0),
            automation_roi_score=roi_data.get("roi_score", 0.0),
            payback_period_weeks=roi_data.get("payback_period_weeks", 0.0),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return {
            "task_name": task_name,
            "record_count": len(matching),
            "category": matching[-1].toil_category.value,
            "weekly_hours": roi_data.get("weekly_hours", 0.0),
            "annual_cost_usd": roi_data.get("annual_cost_usd", 0.0),
            "roi_score": roi_data.get("roi_score", 0.0),
            "is_automatable": matching[-1].is_automatable,
        }

    def generate_report(self) -> ToilIntelligenceReport:
        by_cat: dict[str, int] = {}
        by_feas: dict[str, int] = {}
        by_eff: dict[str, int] = {}
        for r in self._records:
            by_cat[r.toil_category.value] = by_cat.get(r.toil_category.value, 0) + 1
            by_feas[r.automation_feasibility.value] = (
                by_feas.get(r.automation_feasibility.value, 0) + 1
            )
            by_eff[r.effort_level.value] = by_eff.get(r.effort_level.value, 0) + 1
        total_weekly = sum(
            r.time_spent_minutes / 60.0 * r.frequency_per_week * r.people_involved
            for r in self._records
        )
        total_annual = total_weekly * 52
        automatable = sum(1 for r in self._records if r.is_automatable)
        automatable_pct = round(automatable / max(1, len(self._records)) * 100, 2)
        automatable_weekly = sum(
            r.time_spent_minutes / 60.0 * r.frequency_per_week * r.people_involved
            for r in self._records
            if r.is_automatable
        )
        potential_savings = round(automatable_weekly * 52, 2)
        targets = self.prioritize_elimination(5)
        roi_scores = [t["roi_score"] for t in targets if t["roi_score"] > 0]
        avg_roi = round(sum(roi_scores) / max(1, len(roi_scores)), 2)
        recs: list[str] = []
        if total_annual > 1000:
            recs.append(
                f"{total_annual:.0f} annual toil hours — "
                f"${total_annual * self._hourly_cost:,.0f} cost"
            )
        if potential_savings > 0:
            recs.append(f"{potential_savings:.0f} hours/year saveable through automation")
        if automatable_pct < 30:
            recs.append("Low automation coverage — invest in tooling")
        if targets:
            recs.append(
                f"Top target: '{targets[0]['task_name']}' (ROI: {targets[0]['roi_score']}x)"
            )
        if not recs:
            recs.append("Toil levels are within budget — continue monitoring")
        return ToilIntelligenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_weekly_hours=round(total_weekly, 2),
            total_annual_hours=round(total_annual, 2),
            automatable_pct=automatable_pct,
            potential_savings_hours=potential_savings,
            avg_roi_score=avg_roi,
            by_toil_category=by_cat,
            by_automation_feasibility=by_feas,
            by_effort_level=by_eff,
            top_elimination_targets=targets,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            cat_dist[r.toil_category.value] = cat_dist.get(r.toil_category.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "toil_budget_pct": self._toil_budget_pct,
            "engineer_hourly_cost": self._hourly_cost,
            "category_distribution": cat_dist,
            "unique_tasks": len({r.task_name for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("sre_toil_intelligence.cleared")
        return {"status": "cleared"}
