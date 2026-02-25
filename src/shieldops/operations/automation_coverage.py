"""Automation Coverage Analyzer — measure automation coverage."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ProcessCategory(StrEnum):
    DEPLOYMENT = "deployment"
    INCIDENT_RESPONSE = "incident_response"
    PROVISIONING = "provisioning"
    MONITORING = "monitoring"
    MAINTENANCE = "maintenance"


class AutomationLevel(StrEnum):
    FULLY_MANUAL = "fully_manual"
    PARTIALLY_AUTOMATED = "partially_automated"
    MOSTLY_AUTOMATED = "mostly_automated"
    FULLY_AUTOMATED = "fully_automated"
    SELF_HEALING = "self_healing"


class CoverageGap(StrEnum):
    NO_RUNBOOK = "no_runbook"
    MANUAL_STEPS = "manual_steps"
    NO_MONITORING = "no_monitoring"
    NO_ROLLBACK = "no_rollback"
    NO_TESTING = "no_testing"


# --- Models ---


class ProcessRecord(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    process_name: str = ""
    category: ProcessCategory = ProcessCategory.DEPLOYMENT
    service_name: str = ""
    automation_level: AutomationLevel = AutomationLevel.FULLY_MANUAL
    manual_steps: int = 0
    automated_steps: int = 0
    coverage_pct: float = 0.0
    gaps: list[str] = Field(
        default_factory=list,
    )
    last_assessed_at: float = Field(
        default_factory=time.time,
    )
    created_at: float = Field(default_factory=time.time)


class AutomationGoal(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    category: ProcessCategory = ProcessCategory.DEPLOYMENT
    target_coverage_pct: float = 80.0
    current_coverage_pct: float = 0.0
    on_track: bool = False
    deadline: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageReport(BaseModel):
    total_processes: int = 0
    avg_coverage_pct: float = 0.0
    fully_automated_count: int = 0
    by_category: dict[str, int] = Field(
        default_factory=dict,
    )
    by_level: dict[str, int] = Field(
        default_factory=dict,
    )
    gap_summary: dict[str, int] = Field(
        default_factory=dict,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Analyzer ---


class AutomationCoverageAnalyzer:
    """Measure and track automation coverage."""

    def __init__(
        self,
        max_processes: int = 100000,
        target_coverage_pct: float = 80.0,
    ) -> None:
        self._max_processes = max_processes
        self._target_coverage_pct = target_coverage_pct
        self._items: list[ProcessRecord] = []
        self._goals: list[AutomationGoal] = []
        logger.info(
            "automation_coverage.initialized",
            max_processes=max_processes,
            target_coverage_pct=target_coverage_pct,
        )

    # -- register / get / list --

    def register_process(
        self,
        process_name: str = "",
        category: ProcessCategory = (ProcessCategory.DEPLOYMENT),
        service_name: str = "",
        automation_level: AutomationLevel = (AutomationLevel.FULLY_MANUAL),
        manual_steps: int = 0,
        automated_steps: int = 0,
        gaps: list[str] | None = None,
        **kw: Any,
    ) -> ProcessRecord:
        """Register an operational process."""
        total_steps = manual_steps + automated_steps
        coverage = 0.0
        if total_steps > 0:
            coverage = round(automated_steps / total_steps * 100, 2)
        record = ProcessRecord(
            process_name=process_name,
            category=category,
            service_name=service_name,
            automation_level=automation_level,
            manual_steps=manual_steps,
            automated_steps=automated_steps,
            coverage_pct=coverage,
            gaps=gaps or [],
            **kw,
        )
        self._items.append(record)
        if len(self._items) > self._max_processes:
            self._items.pop(0)
        logger.info(
            "automation_coverage.process_registered",
            process_id=record.id,
            process_name=process_name,
            coverage_pct=coverage,
        )
        return record

    def get_process(
        self,
        process_id: str,
    ) -> ProcessRecord | None:
        """Get a single process by ID."""
        for item in self._items:
            if item.id == process_id:
                return item
        return None

    def list_processes(
        self,
        category: ProcessCategory | None = None,
        automation_level: AutomationLevel | None = None,
        limit: int = 50,
    ) -> list[ProcessRecord]:
        """List processes with optional filters."""
        results = list(self._items)
        if category is not None:
            results = [r for r in results if r.category == category]
        if automation_level is not None:
            results = [r for r in results if r.automation_level == automation_level]
        return results[-limit:]

    # -- domain operations --

    def create_goal(
        self,
        category: ProcessCategory = (ProcessCategory.DEPLOYMENT),
        target_pct: float = 80.0,
        deadline: str = "",
        **kw: Any,
    ) -> AutomationGoal:
        """Create an automation coverage goal."""
        current = self.calculate_coverage(category)
        current_pct = current.get("coverage_pct", 0.0)
        on_track = current_pct >= target_pct * 0.8
        goal = AutomationGoal(
            category=category,
            target_coverage_pct=target_pct,
            current_coverage_pct=current_pct,
            on_track=on_track,
            deadline=deadline,
            **kw,
        )
        self._goals.append(goal)
        logger.info(
            "automation_coverage.goal_created",
            goal_id=goal.id,
            category=category,
            target_pct=target_pct,
        )
        return goal

    def calculate_coverage(
        self,
        category: ProcessCategory | None = None,
    ) -> dict[str, Any]:
        """Calculate automation coverage percentage."""
        procs = list(self._items)
        if category is not None:
            procs = [p for p in procs if p.category == category]
        if not procs:
            return {
                "category": (category.value if category else "all"),
                "process_count": 0,
                "coverage_pct": 0.0,
            }
        avg = round(
            sum(p.coverage_pct for p in procs) / len(procs),
            2,
        )
        return {
            "category": (category.value if category else "all"),
            "process_count": len(procs),
            "coverage_pct": avg,
        }

    def identify_automation_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Identify processes with automation gaps."""
        results: list[dict[str, Any]] = []
        for p in self._items:
            if p.gaps:
                results.append(
                    {
                        "process_id": p.id,
                        "process_name": p.process_name,
                        "gaps": p.gaps,
                        "coverage_pct": p.coverage_pct,
                    }
                )
        results.sort(
            key=lambda x: x.get("coverage_pct", 0),
        )
        return results

    def rank_by_automation_potential(
        self,
    ) -> list[dict[str, Any]]:
        """Rank processes by automation potential."""
        ranked: list[dict[str, Any]] = []
        for p in self._items:
            total = p.manual_steps + p.automated_steps
            potential = 0.0
            if total > 0:
                potential = round(p.manual_steps / total * 100, 2)
            ranked.append(
                {
                    "process_id": p.id,
                    "process_name": p.process_name,
                    "manual_steps": p.manual_steps,
                    "automation_potential_pct": potential,
                }
            )
        ranked.sort(
            key=lambda x: x.get("automation_potential_pct", 0),
            reverse=True,
        )
        return ranked

    def estimate_automation_roi(
        self,
        process_id: str,
    ) -> dict[str, Any] | None:
        """Estimate ROI for automating a process."""
        proc = self.get_process(process_id)
        if proc is None:
            return None
        manual_cost = proc.manual_steps * 2.0
        automation_cost = proc.manual_steps * 8.0
        savings_per_run = manual_cost
        breakeven_runs = 0
        if savings_per_run > 0:
            breakeven_runs = int(automation_cost / savings_per_run)
        return {
            "process_id": process_id,
            "process_name": proc.process_name,
            "manual_steps": proc.manual_steps,
            "estimated_manual_cost_hrs": manual_cost,
            "estimated_automation_cost_hrs": (automation_cost),
            "savings_per_run_hrs": savings_per_run,
            "breakeven_runs": breakeven_runs,
        }

    # -- report --

    def generate_coverage_report(
        self,
    ) -> CoverageReport:
        """Generate a comprehensive coverage report."""
        by_category: dict[str, int] = {}
        by_level: dict[str, int] = {}
        gap_summary: dict[str, int] = {}
        fully_automated = 0
        for p in self._items:
            cat = p.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            lev = p.automation_level.value
            by_level[lev] = by_level.get(lev, 0) + 1
            if p.automation_level in (
                AutomationLevel.FULLY_AUTOMATED,
                AutomationLevel.SELF_HEALING,
            ):
                fully_automated += 1
            for g in p.gaps:
                gap_summary[g] = gap_summary.get(g, 0) + 1
        avg_coverage = 0.0
        if self._items:
            avg_coverage = round(
                sum(p.coverage_pct for p in self._items) / len(self._items),
                2,
            )
        recs = self._build_recommendations(
            len(self._items),
            avg_coverage,
            fully_automated,
        )
        return CoverageReport(
            total_processes=len(self._items),
            avg_coverage_pct=avg_coverage,
            fully_automated_count=fully_automated,
            by_category=by_category,
            by_level=by_level,
            gap_summary=gap_summary,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all data. Returns records cleared."""
        count = len(self._items)
        self._items.clear()
        self._goals.clear()
        logger.info(
            "automation_coverage.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        level_dist: dict[str, int] = {}
        for p in self._items:
            key = p.automation_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_processes": len(self._items),
            "total_goals": len(self._goals),
            "max_processes": self._max_processes,
            "target_coverage_pct": (self._target_coverage_pct),
            "level_distribution": level_dist,
        }

    # -- internal helpers --

    def _build_recommendations(
        self,
        total: int,
        avg_coverage: float,
        fully_automated: int,
    ) -> list[str]:
        recs: list[str] = []
        if total == 0:
            recs.append("No processes tracked - register operational processes")
        if avg_coverage > 0 and avg_coverage < self._target_coverage_pct:
            recs.append(
                f"Average coverage {avg_coverage}% below target {self._target_coverage_pct}%"
            )
        if total > 0 and fully_automated == 0:
            recs.append("No fully automated processes - prioritize automation")
        if not recs:
            recs.append("Automation coverage within acceptable limits")
        return recs
