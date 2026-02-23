"""Toil Measurement Tracker — track repetitive manual work, automation candidates."""

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
    INCIDENT_TRIAGE = "incident_triage"
    CONFIG_UPDATE = "config_update"
    CERTIFICATE_RENEWAL = "certificate_renewal"
    ACCESS_PROVISIONING = "access_provisioning"


class AutomationPotential(StrEnum):
    FULLY_AUTOMATABLE = "fully_automatable"
    PARTIALLY_AUTOMATABLE = "partially_automatable"
    REQUIRES_JUDGMENT = "requires_judgment"
    NOT_AUTOMATABLE = "not_automatable"


class ToilTrend(StrEnum):
    DECREASING = "decreasing"
    STABLE = "stable"
    INCREASING = "increasing"


# --- Models ---


class ToilEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team: str
    category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT
    description: str = ""
    duration_minutes: float = 0.0
    engineer: str = ""
    automated: bool = False
    recorded_at: float = Field(default_factory=time.time)


class ToilSummary(BaseModel):
    team: str
    total_entries: int = 0
    total_minutes: float = 0.0
    category_distribution: dict[str, int] = Field(default_factory=dict)
    avg_duration_minutes: float = 0.0
    trend: ToilTrend = ToilTrend.STABLE


class AutomationCandidate(BaseModel):
    category: ToilCategory
    occurrences: int = 0
    total_minutes: float = 0.0
    potential: AutomationPotential = AutomationPotential.FULLY_AUTOMATABLE
    estimated_savings_minutes: float = 0.0


# --- Engine ---


class ToilMeasurementTracker:
    """Track repetitive manual work, automation candidates, toil reduction trends."""

    def __init__(
        self,
        max_entries: int = 100000,
        automation_min_occurrences: int = 3,
    ) -> None:
        self._max_entries = max_entries
        self._automation_min_occurrences = automation_min_occurrences
        self._entries: list[ToilEntry] = []
        logger.info(
            "toil_tracker.initialized",
            max_entries=max_entries,
            automation_min_occurrences=automation_min_occurrences,
        )

    def record_toil(
        self,
        team: str,
        category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT,
        description: str = "",
        duration_minutes: float = 0.0,
        engineer: str = "",
        automated: bool = False,
    ) -> ToilEntry:
        entry = ToilEntry(
            team=team,
            category=category,
            description=description,
            duration_minutes=duration_minutes,
            engineer=engineer,
            automated=automated,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]
        logger.info(
            "toil_tracker.toil_recorded",
            entry_id=entry.id,
            team=team,
            category=category,
        )
        return entry

    def get_entry(self, entry_id: str) -> ToilEntry | None:
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None

    def list_entries(
        self,
        team: str | None = None,
        category: ToilCategory | None = None,
        limit: int = 100,
    ) -> list[ToilEntry]:
        results = list(self._entries)
        if team is not None:
            results = [e for e in results if e.team == team]
        if category is not None:
            results = [e for e in results if e.category == category]
        return results[-limit:]

    def compute_summary(self, team: str) -> ToilSummary:
        entries = [e for e in self._entries if e.team == team]
        total = len(entries)
        total_min = sum(e.duration_minutes for e in entries)
        cat_dist: dict[str, int] = {}
        for e in entries:
            cat_dist[e.category] = cat_dist.get(e.category, 0) + 1
        avg = round(total_min / total, 1) if total > 0 else 0.0
        # Simple trend: compare first half vs second half
        if total < 4:
            trend = ToilTrend.STABLE
        else:
            mid = total // 2
            first_avg = sum(e.duration_minutes for e in entries[:mid]) / mid
            second_avg = sum(e.duration_minutes for e in entries[mid:]) / (total - mid)
            if second_avg > first_avg * 1.1:
                trend = ToilTrend.INCREASING
            elif second_avg < first_avg * 0.9:
                trend = ToilTrend.DECREASING
            else:
                trend = ToilTrend.STABLE
        return ToilSummary(
            team=team,
            total_entries=total,
            total_minutes=round(total_min, 1),
            category_distribution=cat_dist,
            avg_duration_minutes=avg,
            trend=trend,
        )

    def identify_automation_candidates(self) -> list[AutomationCandidate]:
        cat_counts: dict[ToilCategory, list[ToilEntry]] = {}
        for e in self._entries:
            if not e.automated:
                cat_counts.setdefault(e.category, []).append(e)
        candidates: list[AutomationCandidate] = []
        for cat, entries in cat_counts.items():
            if len(entries) >= self._automation_min_occurrences:
                total_min = sum(e.duration_minutes for e in entries)
                # Estimate 80% savings for fully automatable
                if cat in (ToilCategory.MANUAL_DEPLOYMENT, ToilCategory.CERTIFICATE_RENEWAL):
                    potential = AutomationPotential.FULLY_AUTOMATABLE
                    savings = total_min * 0.8
                elif cat == ToilCategory.CONFIG_UPDATE:
                    potential = AutomationPotential.PARTIALLY_AUTOMATABLE
                    savings = total_min * 0.5
                elif cat == ToilCategory.INCIDENT_TRIAGE:
                    potential = AutomationPotential.REQUIRES_JUDGMENT
                    savings = total_min * 0.3
                else:
                    potential = AutomationPotential.PARTIALLY_AUTOMATABLE
                    savings = total_min * 0.5
                candidates.append(
                    AutomationCandidate(
                        category=cat,
                        occurrences=len(entries),
                        total_minutes=round(total_min, 1),
                        potential=potential,
                        estimated_savings_minutes=round(savings, 1),
                    )
                )
        candidates.sort(key=lambda c: c.estimated_savings_minutes, reverse=True)
        return candidates

    def get_toil_trend(self, team: str) -> ToilTrend:
        summary = self.compute_summary(team)
        return summary.trend

    def get_team_ranking(self) -> list[dict[str, Any]]:
        teams: dict[str, float] = {}
        for e in self._entries:
            teams[e.team] = teams.get(e.team, 0.0) + e.duration_minutes
        ranked = sorted(teams.items(), key=lambda x: x[1], reverse=True)
        return [{"team": t, "total_minutes": round(m, 1)} for t, m in ranked]

    def compute_automation_savings(self) -> dict[str, Any]:
        candidates = self.identify_automation_candidates()
        total_savings = sum(c.estimated_savings_minutes for c in candidates)
        total_toil = sum(e.duration_minutes for e in self._entries if not e.automated)
        return {
            "total_toil_minutes": round(total_toil, 1),
            "potential_savings_minutes": round(total_savings, 1),
            "savings_pct": round((total_savings / total_toil * 100) if total_toil > 0 else 0.0, 1),
            "automation_candidates": len(candidates),
        }

    def clear_entries(self) -> int:
        count = len(self._entries)
        self._entries.clear()
        logger.info("toil_tracker.entries_cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        cat_counts: dict[str, int] = {}
        team_counts: dict[str, int] = {}
        for e in self._entries:
            cat_counts[e.category] = cat_counts.get(e.category, 0) + 1
            team_counts[e.team] = team_counts.get(e.team, 0) + 1
        return {
            "total_entries": len(self._entries),
            "unique_teams": len(team_counts),
            "total_minutes": round(sum(e.duration_minutes for e in self._entries), 1),
            "category_distribution": cat_counts,
            "team_distribution": team_counts,
        }
