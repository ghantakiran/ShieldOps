"""Team Toil Quantifier — quantify and track operational toil."""

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
    MANUAL_DEPLOYMENT = "manual_deployment"
    ALERT_HANDLING = "alert_handling"
    TICKET_TRIAGE = "ticket_triage"
    CONFIG_MANAGEMENT = "config_management"
    REPORTING = "reporting"


class ToilImpact(StrEnum):
    SEVERE = "severe"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


class AutomationPotential(StrEnum):
    FULLY_AUTOMATABLE = "fully_automatable"
    MOSTLY_AUTOMATABLE = "mostly_automatable"
    PARTIALLY_AUTOMATABLE = "partially_automatable"
    DIFFICULT = "difficult"
    NOT_AUTOMATABLE = "not_automatable"


# --- Models ---


class ToilRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_name: str = ""
    category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT
    impact: ToilImpact = ToilImpact.MODERATE
    potential: AutomationPotential = AutomationPotential.PARTIALLY_AUTOMATABLE
    hours_spent: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ToilPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT
    impact: ToilImpact = ToilImpact.MODERATE
    max_toil_hours_weekly: float = 10.0
    automation_target_pct: float = 50.0
    created_at: float = Field(default_factory=time.time)


class ToilQuantifierReport(BaseModel):
    total_records: int = 0
    total_policies: int = 0
    low_toil_rate_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    severe_toil_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamToilQuantifier:
    """Quantify and track operational toil."""

    def __init__(
        self,
        max_records: int = 200000,
        max_toil_hours_weekly: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_toil_hours_weekly = max_toil_hours_weekly
        self._records: list[ToilRecord] = []
        self._policies: list[ToilPolicy] = []
        logger.info(
            "toil_quantifier.initialized",
            max_records=max_records,
            max_toil_hours_weekly=max_toil_hours_weekly,
        )

    # -- record / get / list ----------------------------------------

    def record_toil(
        self,
        team_name: str,
        category: ToilCategory = (ToilCategory.MANUAL_DEPLOYMENT),
        impact: ToilImpact = ToilImpact.MODERATE,
        potential: AutomationPotential = (AutomationPotential.PARTIALLY_AUTOMATABLE),
        hours_spent: float = 0.0,
        details: str = "",
    ) -> ToilRecord:
        record = ToilRecord(
            team_name=team_name,
            category=category,
            impact=impact,
            potential=potential,
            hours_spent=hours_spent,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "toil_quantifier.toil_recorded",
            record_id=record.id,
            team_name=team_name,
            category=category.value,
            impact=impact.value,
        )
        return record

    def get_toil(self, record_id: str) -> ToilRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_toils(
        self,
        team_name: str | None = None,
        category: ToilCategory | None = None,
        limit: int = 50,
    ) -> list[ToilRecord]:
        results = list(self._records)
        if team_name is not None:
            results = [r for r in results if r.team_name == team_name]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        category: ToilCategory = (ToilCategory.MANUAL_DEPLOYMENT),
        impact: ToilImpact = ToilImpact.MODERATE,
        max_toil_hours_weekly: float = 10.0,
        automation_target_pct: float = 50.0,
    ) -> ToilPolicy:
        policy = ToilPolicy(
            policy_name=policy_name,
            category=category,
            impact=impact,
            max_toil_hours_weekly=max_toil_hours_weekly,
            automation_target_pct=automation_target_pct,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "toil_quantifier.policy_added",
            policy_name=policy_name,
            category=category.value,
            impact=impact.value,
        )
        return policy

    # -- domain operations ------------------------------------------

    def analyze_toil_burden(self, team_name: str) -> dict[str, Any]:
        """Analyze toil burden for a team."""
        records = [r for r in self._records if r.team_name == team_name]
        if not records:
            return {
                "team_name": team_name,
                "status": "no_data",
            }
        low_count = sum(1 for r in records if r.impact in (ToilImpact.LOW, ToilImpact.MINIMAL))
        low_rate = round(low_count / len(records) * 100, 2)
        avg_hours = round(
            sum(r.hours_spent for r in records) / len(records),
            2,
        )
        return {
            "team_name": team_name,
            "toil_count": len(records),
            "low_count": low_count,
            "low_rate": low_rate,
            "avg_hours": avg_hours,
            "meets_threshold": (avg_hours <= self._max_toil_hours_weekly),
        }

    def identify_high_toil_teams(
        self,
    ) -> list[dict[str, Any]]:
        """Find teams with repeated high toil."""
        high_counts: dict[str, int] = {}
        for r in self._records:
            if r.impact in (
                ToilImpact.SEVERE,
                ToilImpact.HIGH,
            ):
                high_counts[r.team_name] = high_counts.get(r.team_name, 0) + 1
        results: list[dict[str, Any]] = []
        for team, count in high_counts.items():
            if count > 1:
                results.append(
                    {
                        "team_name": team,
                        "high_toil_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["high_toil_count"],
            reverse=True,
        )
        return results

    def rank_by_hours_spent(
        self,
    ) -> list[dict[str, Any]]:
        """Rank teams by avg hours spent descending."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            totals[r.team_name] = totals.get(r.team_name, 0.0) + r.hours_spent
            counts[r.team_name] = counts.get(r.team_name, 0) + 1
        results: list[dict[str, Any]] = []
        for team in totals:
            avg = round(totals[team] / counts[team], 2)
            results.append(
                {
                    "team_name": team,
                    "avg_hours_spent": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_hours_spent"],
            reverse=True,
        )
        return results

    def detect_toil_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Detect teams with >3 non-LOW/MINIMAL."""
        non_low: dict[str, int] = {}
        for r in self._records:
            if r.impact not in (
                ToilImpact.LOW,
                ToilImpact.MINIMAL,
            ):
                non_low[r.team_name] = non_low.get(r.team_name, 0) + 1
        results: list[dict[str, Any]] = []
        for team, count in non_low.items():
            if count > 3:
                results.append(
                    {
                        "team_name": team,
                        "non_low_count": count,
                        "pattern_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_low_count"],
            reverse=True,
        )
        return results

    # -- report / stats ---------------------------------------------

    def generate_report(self) -> ToilQuantifierReport:
        by_category: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_impact[r.impact.value] = by_impact.get(r.impact.value, 0) + 1
        low_count = sum(
            1 for r in self._records if r.impact in (ToilImpact.LOW, ToilImpact.MINIMAL)
        )
        low_rate = (
            round(
                low_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        severe = sum(1 for d in self.identify_high_toil_teams())
        recs: list[str] = []
        if self._records and low_rate < 80.0:
            recs.append(f"Low-toil rate {low_rate}% is below 80.0% threshold")
        if severe > 0:
            recs.append(f"{severe} team(s) with repeated high toil")
        patterns = len(self.detect_toil_patterns())
        if patterns > 0:
            recs.append(f"{patterns} team(s) detected with toil patterns")
        if not recs:
            recs.append("Toil levels are healthy and within targets")
        return ToilQuantifierReport(
            total_records=len(self._records),
            total_policies=len(self._policies),
            low_toil_rate_pct=low_rate,
            by_category=by_category,
            by_impact=by_impact,
            severe_toil_count=severe,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("toil_quantifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_policies": len(self._policies),
            "max_toil_hours_weekly": (self._max_toil_hours_weekly),
            "category_distribution": category_dist,
            "unique_teams": len({r.team_name for r in self._records}),
        }
