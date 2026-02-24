"""Toil Automation Recommender — analyze toil patterns and recommend automation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AutomationDifficulty(StrEnum):
    TRIVIAL = "trivial"
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    REQUIRES_PLATFORM_CHANGE = "requires_platform_change"


class AutomationCategory(StrEnum):
    SCRIPT = "script"
    RUNBOOK = "runbook"
    PIPELINE = "pipeline"
    SELF_SERVICE = "self_service"
    AI_AGENT = "ai_agent"


class ROITimeframe(StrEnum):
    ONE_MONTH = "one_month"
    THREE_MONTHS = "three_months"
    SIX_MONTHS = "six_months"
    ONE_YEAR = "one_year"
    TWO_YEARS = "two_years"


# --- Models ---


class ToilPattern(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_name: str = ""
    team: str = ""
    frequency_per_week: float = 0.0
    time_per_occurrence_minutes: float = 0.0
    automation_difficulty: AutomationDifficulty = AutomationDifficulty.MODERATE
    is_automatable: bool = True
    monthly_hours: float = 0.0
    created_at: float = Field(default_factory=time.time)


class AutomationRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    category: AutomationCategory = AutomationCategory.SCRIPT
    estimated_implementation_hours: float = 0.0
    estimated_monthly_savings_hours: float = 0.0
    roi_multiplier: float = 0.0
    timeframe: ROITimeframe = ROITimeframe.SIX_MONTHS
    rationale: str = ""
    created_at: float = Field(default_factory=time.time)


class ToilRecommenderReport(BaseModel):
    total_patterns: int = 0
    total_monthly_toil_hours: float = 0.0
    automatable_count: int = 0
    total_potential_savings_hours: float = 0.0
    by_difficulty: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    quick_wins: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


_DIFFICULTY_TO_CATEGORY: dict[AutomationDifficulty, AutomationCategory] = {
    AutomationDifficulty.TRIVIAL: AutomationCategory.SCRIPT,
    AutomationDifficulty.EASY: AutomationCategory.RUNBOOK,
    AutomationDifficulty.MODERATE: AutomationCategory.PIPELINE,
    AutomationDifficulty.HARD: AutomationCategory.SELF_SERVICE,
    AutomationDifficulty.REQUIRES_PLATFORM_CHANGE: AutomationCategory.AI_AGENT,
}

_DIFFICULTY_TO_HOURS: dict[AutomationDifficulty, float] = {
    AutomationDifficulty.TRIVIAL: 4.0,
    AutomationDifficulty.EASY: 16.0,
    AutomationDifficulty.MODERATE: 40.0,
    AutomationDifficulty.HARD: 80.0,
    AutomationDifficulty.REQUIRES_PLATFORM_CHANGE: 160.0,
}


class ToilAutomationRecommender:
    """Analyze toil patterns and recommend automation with ROI estimates."""

    def __init__(
        self,
        max_patterns: int = 100000,
        min_roi_multiplier: float = 2.0,
    ) -> None:
        self._max_patterns = max_patterns
        self._min_roi_multiplier = min_roi_multiplier
        self._patterns: list[ToilPattern] = []
        self._recommendations: list[AutomationRecommendation] = []
        logger.info(
            "toil_recommender.initialized",
            max_patterns=max_patterns,
            min_roi_multiplier=min_roi_multiplier,
        )

    def record_toil_pattern(
        self,
        task_name: str = "",
        team: str = "",
        frequency_per_week: float = 0.0,
        time_per_occurrence_minutes: float = 0.0,
        automation_difficulty: AutomationDifficulty = AutomationDifficulty.MODERATE,
        is_automatable: bool = True,
    ) -> ToilPattern:
        monthly_hours = frequency_per_week * 4.33 * time_per_occurrence_minutes / 60.0
        pattern = ToilPattern(
            task_name=task_name,
            team=team,
            frequency_per_week=frequency_per_week,
            time_per_occurrence_minutes=time_per_occurrence_minutes,
            automation_difficulty=automation_difficulty,
            is_automatable=is_automatable,
            monthly_hours=round(monthly_hours, 2),
        )
        self._patterns.append(pattern)
        if len(self._patterns) > self._max_patterns:
            self._patterns = self._patterns[-self._max_patterns :]
        logger.info(
            "toil_recommender.pattern_recorded",
            pattern_id=pattern.id,
            task_name=task_name,
            monthly_hours=round(monthly_hours, 2),
        )
        return pattern

    def get_pattern(self, pattern_id: str) -> ToilPattern | None:
        for p in self._patterns:
            if p.id == pattern_id:
                return p
        return None

    def list_patterns(
        self,
        team: str | None = None,
        is_automatable: bool | None = None,
        difficulty: AutomationDifficulty | None = None,
        limit: int = 100,
    ) -> list[ToilPattern]:
        results = list(self._patterns)
        if team is not None:
            results = [p for p in results if p.team == team]
        if is_automatable is not None:
            results = [p for p in results if p.is_automatable == is_automatable]
        if difficulty is not None:
            results = [p for p in results if p.automation_difficulty == difficulty]
        return results[-limit:]

    def recommend_automation(self, pattern_id: str) -> AutomationRecommendation | None:
        pattern = self.get_pattern(pattern_id)
        if pattern is None:
            return None

        category = _DIFFICULTY_TO_CATEGORY[pattern.automation_difficulty]
        impl_hours = _DIFFICULTY_TO_HOURS[pattern.automation_difficulty]
        monthly_savings = pattern.monthly_hours
        roi_multiplier = round((monthly_savings * 12) / impl_hours, 2) if impl_hours > 0 else 0.0

        # Calculate breakeven months
        breakeven_months = impl_hours / monthly_savings if monthly_savings > 0 else float("inf")

        # Determine timeframe based on breakeven
        if breakeven_months <= 1:
            timeframe = ROITimeframe.ONE_MONTH
        elif breakeven_months <= 3:
            timeframe = ROITimeframe.THREE_MONTHS
        elif breakeven_months <= 6:
            timeframe = ROITimeframe.SIX_MONTHS
        elif breakeven_months <= 12:
            timeframe = ROITimeframe.ONE_YEAR
        else:
            timeframe = ROITimeframe.TWO_YEARS

        rationale = (
            f"Automating '{pattern.task_name}' as {category.value} saves "
            f"{monthly_savings:.1f}h/month with {impl_hours:.0f}h implementation "
            f"(ROI: {roi_multiplier:.1f}x, breakeven: {breakeven_months:.1f} months)"
        )

        rec = AutomationRecommendation(
            pattern_id=pattern_id,
            category=category,
            estimated_implementation_hours=impl_hours,
            estimated_monthly_savings_hours=monthly_savings,
            roi_multiplier=roi_multiplier,
            timeframe=timeframe,
            rationale=rationale,
        )
        self._recommendations.append(rec)
        logger.info(
            "toil_recommender.automation_recommended",
            pattern_id=pattern_id,
            category=category,
            roi_multiplier=roi_multiplier,
        )
        return rec

    def estimate_roi(self, pattern_id: str) -> dict[str, Any]:
        pattern = self.get_pattern(pattern_id)
        if pattern is None:
            return {
                "pattern_id": pattern_id,
                "monthly_savings_hours": 0.0,
                "implementation_hours": 0.0,
                "roi_multiplier": 0.0,
                "breakeven_months": 0.0,
            }
        impl_hours = _DIFFICULTY_TO_HOURS[pattern.automation_difficulty]
        monthly_savings = pattern.monthly_hours
        roi_multiplier = round((monthly_savings * 12) / impl_hours, 2) if impl_hours > 0 else 0.0
        breakeven_months = round(impl_hours / monthly_savings, 2) if monthly_savings > 0 else 0.0
        return {
            "pattern_id": pattern_id,
            "monthly_savings_hours": round(monthly_savings, 2),
            "implementation_hours": impl_hours,
            "roi_multiplier": roi_multiplier,
            "breakeven_months": breakeven_months,
        }

    def rank_by_roi(self) -> list[AutomationRecommendation]:
        automatable = [p for p in self._patterns if p.is_automatable]
        recs: list[AutomationRecommendation] = []
        for p in automatable:
            rec = self.recommend_automation(p.id)
            if rec is not None:
                recs.append(rec)
        recs.sort(key=lambda r: r.roi_multiplier, reverse=True)
        return recs

    def calculate_time_saved(self, team: str | None = None) -> dict[str, Any]:
        targets = self._patterns
        if team is not None:
            targets = [p for p in targets if p.team == team]
        total_monthly = sum(p.monthly_hours for p in targets)
        automatable_hours = sum(p.monthly_hours for p in targets if p.is_automatable)
        savings_pct = (
            round(automatable_hours / total_monthly * 100, 2) if total_monthly > 0 else 0.0
        )
        return {
            "team": team or "all",
            "total_monthly_toil_hours": round(total_monthly, 2),
            "automatable_hours": round(automatable_hours, 2),
            "potential_savings_pct": savings_pct,
        }

    def identify_quick_wins(self) -> list[ToilPattern]:
        return [
            p
            for p in self._patterns
            if p.automation_difficulty in (AutomationDifficulty.TRIVIAL, AutomationDifficulty.EASY)
            and p.monthly_hours > 1.0
        ]

    def generate_recommender_report(self) -> ToilRecommenderReport:
        total_patterns = len(self._patterns)
        total_monthly = sum(p.monthly_hours for p in self._patterns)
        automatable = [p for p in self._patterns if p.is_automatable]
        automatable_count = len(automatable)
        total_savings = sum(p.monthly_hours for p in automatable)

        # By difficulty
        by_difficulty: dict[str, int] = {}
        for p in self._patterns:
            key = p.automation_difficulty.value
            by_difficulty[key] = by_difficulty.get(key, 0) + 1

        # By category (from recommendations)
        by_category: dict[str, int] = {}
        for r in self._recommendations:
            key = r.category.value
            by_category[key] = by_category.get(key, 0) + 1

        # Quick wins
        quick_wins_patterns = self.identify_quick_wins()
        quick_wins = [f"{p.task_name} ({p.monthly_hours:.1f}h/month)" for p in quick_wins_patterns]

        # Recommendations
        recommendations: list[str] = []
        if total_monthly > 100:
            recommendations.append(
                f"Team spends {total_monthly:.0f}h/month on toil — prioritize automation"
            )
        if quick_wins_patterns:
            recommendations.append(
                f"{len(quick_wins_patterns)} quick wins identified — "
                f"start with these for immediate ROI"
            )
        high_roi = [
            r for r in self._recommendations if r.roi_multiplier >= self._min_roi_multiplier
        ]
        if high_roi:
            recommendations.append(
                f"{len(high_roi)} patterns exceed {self._min_roi_multiplier}x ROI threshold"
            )
        non_automatable = [p for p in self._patterns if not p.is_automatable]
        if non_automatable:
            recommendations.append(
                f"{len(non_automatable)} patterns marked non-automatable — "
                f"review for process changes"
            )

        report = ToilRecommenderReport(
            total_patterns=total_patterns,
            total_monthly_toil_hours=round(total_monthly, 2),
            automatable_count=automatable_count,
            total_potential_savings_hours=round(total_savings, 2),
            by_difficulty=by_difficulty,
            by_category=by_category,
            quick_wins=quick_wins,
            recommendations=recommendations,
        )
        logger.info(
            "toil_recommender.report_generated",
            total_patterns=total_patterns,
            total_monthly_toil_hours=round(total_monthly, 2),
            automatable_count=automatable_count,
        )
        return report

    def clear_data(self) -> None:
        self._patterns.clear()
        self._recommendations.clear()
        logger.info("toil_recommender.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        teams: set[str] = set()
        automatable_count = 0
        total_monthly = 0.0
        for p in self._patterns:
            teams.add(p.team)
            if p.is_automatable:
                automatable_count += 1
            total_monthly += p.monthly_hours
        return {
            "total_patterns": len(self._patterns),
            "total_recommendations": len(self._recommendations),
            "unique_teams": len(teams),
            "automatable_count": automatable_count,
            "total_monthly_toil_hours": round(total_monthly, 2),
        }
