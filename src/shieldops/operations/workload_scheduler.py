"""Workload Scheduling Optimizer — batch scheduling, contention, cost-aware."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class JobPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"


class ScheduleStrategy(StrEnum):
    COST_OPTIMIZED = "cost_optimized"
    PERFORMANCE_OPTIMIZED = "performance_optimized"
    BALANCED = "balanced"
    OFF_PEAK = "off_peak"
    SPOT_AWARE = "spot_aware"


class ContentionLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class WorkloadEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workload_name: str = ""
    priority: JobPriority = JobPriority.MEDIUM
    strategy: ScheduleStrategy = ScheduleStrategy.BALANCED
    scheduled_start: float = 0.0
    duration_seconds: int = 3600
    resource_requirements: dict[str, Any] = Field(default_factory=dict)
    estimated_cost: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ScheduleConflict(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workload_a_id: str = ""
    workload_b_id: str = ""
    overlap_seconds: int = 0
    contention_level: ContentionLevel = ContentionLevel.LOW
    recommendation: str = ""
    created_at: float = Field(default_factory=time.time)


class ScheduleOptimizationReport(BaseModel):
    total_workloads: int = 0
    conflict_count: int = 0
    peak_window_start: float = 0.0
    peak_window_end: float = 0.0
    total_estimated_cost: float = 0.0
    potential_savings: float = 0.0
    strategy_breakdown: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class WorkloadSchedulingOptimizer:
    """Batch job scheduling optimization, contention reduction, cost-aware scheduling."""

    def __init__(
        self,
        max_workloads: int = 50000,
        conflict_window_seconds: int = 600,
    ) -> None:
        self._max_workloads = max_workloads
        self._conflict_window_seconds = conflict_window_seconds
        self._workloads: list[WorkloadEntry] = []
        self._conflicts: list[ScheduleConflict] = []
        logger.info(
            "workload_scheduler.initialized",
            max_workloads=max_workloads,
            conflict_window_seconds=conflict_window_seconds,
        )

    def register_workload(
        self,
        workload_name: str,
        priority: JobPriority = JobPriority.MEDIUM,
        strategy: ScheduleStrategy = ScheduleStrategy.BALANCED,
        scheduled_start: float = 0.0,
        duration_seconds: int = 3600,
        resource_requirements: dict[str, Any] | None = None,
        estimated_cost: float = 0.0,
    ) -> WorkloadEntry:
        entry = WorkloadEntry(
            workload_name=workload_name,
            priority=priority,
            strategy=strategy,
            scheduled_start=scheduled_start,
            duration_seconds=duration_seconds,
            resource_requirements=resource_requirements or {},
            estimated_cost=estimated_cost,
        )
        self._workloads.append(entry)
        if len(self._workloads) > self._max_workloads:
            self._workloads = self._workloads[-self._max_workloads :]
        logger.info(
            "workload_scheduler.workload_registered",
            workload_id=entry.id,
            workload_name=workload_name,
            priority=priority,
            strategy=strategy,
        )
        return entry

    def get_workload(self, workload_id: str) -> WorkloadEntry | None:
        for w in self._workloads:
            if w.id == workload_id:
                return w
        return None

    def list_workloads(
        self,
        priority: JobPriority | None = None,
        strategy: ScheduleStrategy | None = None,
        limit: int = 100,
    ) -> list[WorkloadEntry]:
        results = list(self._workloads)
        if priority is not None:
            results = [w for w in results if w.priority == priority]
        if strategy is not None:
            results = [w for w in results if w.strategy == strategy]
        return results[-limit:]

    def update_workload_schedule(
        self,
        workload_id: str,
        scheduled_start: float | None = None,
        duration_seconds: int | None = None,
        strategy: ScheduleStrategy | None = None,
    ) -> bool:
        workload = self.get_workload(workload_id)
        if workload is None:
            return False
        if scheduled_start is not None:
            workload.scheduled_start = scheduled_start
        if duration_seconds is not None:
            workload.duration_seconds = duration_seconds
        if strategy is not None:
            workload.strategy = strategy
        logger.info(
            "workload_scheduler.schedule_updated",
            workload_id=workload_id,
            scheduled_start=workload.scheduled_start,
            duration_seconds=workload.duration_seconds,
            strategy=workload.strategy,
        )
        return True

    def detect_conflicts(self) -> list[ScheduleConflict]:
        new_conflicts: list[ScheduleConflict] = []
        n = len(self._workloads)

        # Track overlaps per workload to determine contention level
        overlap_counts: dict[str, int] = {}

        for i in range(n):
            for j in range(i + 1, n):
                a = self._workloads[i]
                b = self._workloads[j]
                a_start = a.scheduled_start
                a_end = a.scheduled_start + a.duration_seconds
                b_start = b.scheduled_start
                b_end = b.scheduled_start + b.duration_seconds

                # Expand window by conflict_window_seconds
                overlap_start = max(a_start, b_start)
                overlap_end = min(a_end, b_end)
                overlap = overlap_end - overlap_start

                if overlap > -self._conflict_window_seconds:
                    effective_overlap = max(0, int(overlap))
                    overlap_counts[a.id] = overlap_counts.get(a.id, 0) + 1
                    overlap_counts[b.id] = overlap_counts.get(b.id, 0) + 1

                    new_conflicts.append(
                        ScheduleConflict(
                            workload_a_id=a.id,
                            workload_b_id=b.id,
                            overlap_seconds=effective_overlap,
                        )
                    )

        # Assign contention levels based on overlap count
        for conflict in new_conflicts:
            max_overlaps = max(
                overlap_counts.get(conflict.workload_a_id, 0),
                overlap_counts.get(conflict.workload_b_id, 0),
            )
            if max_overlaps > 3:
                conflict.contention_level = ContentionLevel.HIGH
                conflict.recommendation = (
                    "High contention — reschedule lower-priority workloads to off-peak"
                )
            elif max_overlaps >= 2:
                conflict.contention_level = ContentionLevel.MODERATE
                conflict.recommendation = (
                    "Moderate contention — consider staggering workload start times"
                )
            else:
                conflict.contention_level = ContentionLevel.LOW
                conflict.recommendation = "Low contention — monitor resource utilization"

        self._conflicts.extend(new_conflicts)
        logger.info(
            "workload_scheduler.conflicts_detected",
            conflict_count=len(new_conflicts),
        )
        return new_conflicts

    def analyze_peak_windows(self, window_hours: int = 1) -> dict[str, Any]:
        if not self._workloads:
            return {"windows": [], "peak_window": None}

        window_seconds = window_hours * 3600

        # Find the global time range
        all_starts = [w.scheduled_start for w in self._workloads if w.scheduled_start > 0]
        if not all_starts:
            return {"windows": [], "peak_window": None}

        min_start = min(all_starts)
        max_end = max(
            w.scheduled_start + w.duration_seconds for w in self._workloads if w.scheduled_start > 0
        )

        # Slide window across the range
        windows: list[dict[str, Any]] = []
        current = min_start
        peak_count = 0
        peak_start = 0.0
        peak_end = 0.0

        while current < max_end:
            window_end = current + window_seconds
            count = sum(
                1
                for w in self._workloads
                if w.scheduled_start > 0
                and w.scheduled_start < window_end
                and w.scheduled_start + w.duration_seconds > current
            )
            windows.append(
                {
                    "window_start": current,
                    "window_end": window_end,
                    "workload_count": count,
                }
            )
            if count > peak_count:
                peak_count = count
                peak_start = current
                peak_end = window_end
            current += window_seconds

        return {
            "windows": windows,
            "peak_window": {
                "start": peak_start,
                "end": peak_end,
                "workload_count": peak_count,
            }
            if peak_count > 0
            else None,
            "total_windows_analyzed": len(windows),
        }

    def recommend_schedule_shifts(self) -> list[dict[str, Any]]:
        peak_analysis = self.analyze_peak_windows()
        peak_window = peak_analysis.get("peak_window")
        if peak_window is None:
            return []

        peak_start = peak_window["start"]
        peak_end = peak_window["end"]

        recommendations: list[dict[str, Any]] = []
        for w in self._workloads:
            if w.priority not in (JobPriority.LOW, JobPriority.BACKGROUND):
                continue
            # Check if workload falls in peak window
            w_end = w.scheduled_start + w.duration_seconds
            if w.scheduled_start < peak_end and w_end > peak_start:
                # Suggest moving after peak
                suggested_start = peak_end + 300  # 5 minutes after peak
                recommendations.append(
                    {
                        "workload_id": w.id,
                        "workload_name": w.workload_name,
                        "priority": w.priority.value,
                        "current_start": w.scheduled_start,
                        "suggested_start": suggested_start,
                        "reason": (
                            f"Move {w.priority.value}-priority workload out of peak window "
                            f"to reduce contention"
                        ),
                    }
                )

        logger.info(
            "workload_scheduler.shifts_recommended",
            count=len(recommendations),
        )
        return recommendations

    def estimate_cost_savings(self) -> dict[str, Any]:
        total_cost = sum(w.estimated_cost for w in self._workloads)
        off_peak_discount = 0.3  # 30% cheaper off-peak

        # Identify workloads that could be moved to off-peak
        movable = [
            w
            for w in self._workloads
            if w.priority in (JobPriority.LOW, JobPriority.BACKGROUND)
            and w.strategy != ScheduleStrategy.OFF_PEAK
        ]
        movable_cost = sum(w.estimated_cost for w in movable)
        potential_savings = round(movable_cost * off_peak_discount, 2)

        # Already optimized workloads
        already_off_peak = [
            w
            for w in self._workloads
            if w.strategy in (ScheduleStrategy.OFF_PEAK, ScheduleStrategy.COST_OPTIMIZED)
        ]
        already_saved = round(
            sum(w.estimated_cost for w in already_off_peak) * off_peak_discount, 2
        )

        return {
            "total_estimated_cost": round(total_cost, 2),
            "movable_workload_count": len(movable),
            "movable_workload_cost": round(movable_cost, 2),
            "potential_savings": potential_savings,
            "savings_percentage": (
                round(potential_savings / total_cost * 100, 1) if total_cost > 0 else 0.0
            ),
            "already_optimized_count": len(already_off_peak),
            "already_saved": already_saved,
        }

    def generate_optimization_report(self) -> ScheduleOptimizationReport:
        total = len(self._workloads)
        conflicts = self.detect_conflicts()
        peak_analysis = self.analyze_peak_windows()
        cost_analysis = self.estimate_cost_savings()

        peak_window = peak_analysis.get("peak_window")
        peak_start = peak_window["start"] if peak_window else 0.0
        peak_end = peak_window["end"] if peak_window else 0.0

        # Strategy breakdown
        strategy_counts: dict[str, int] = {}
        for w in self._workloads:
            key = w.strategy.value
            strategy_counts[key] = strategy_counts.get(key, 0) + 1

        # Build recommendations
        recommendations: list[str] = []
        if conflicts:
            high_contention = sum(
                1 for c in conflicts if c.contention_level == ContentionLevel.HIGH
            )
            if high_contention > 0:
                recommendations.append(
                    f"{high_contention} high-contention conflict(s) detected — "
                    f"reschedule lower-priority workloads"
                )

        shifts = self.recommend_schedule_shifts()
        if shifts:
            recommendations.append(f"{len(shifts)} workload(s) can be moved to off-peak windows")

        savings = cost_analysis["potential_savings"]
        if savings > 0:
            recommendations.append(
                f"Estimated ${savings:.2f} in potential savings from off-peak scheduling"
            )

        report = ScheduleOptimizationReport(
            total_workloads=total,
            conflict_count=len(conflicts),
            peak_window_start=peak_start,
            peak_window_end=peak_end,
            total_estimated_cost=cost_analysis["total_estimated_cost"],
            potential_savings=savings,
            strategy_breakdown=strategy_counts,
            recommendations=recommendations,
        )
        logger.info(
            "workload_scheduler.report_generated",
            total_workloads=total,
            conflict_count=len(conflicts),
            potential_savings=savings,
        )
        return report

    def delete_workload(self, workload_id: str) -> bool:
        for i, w in enumerate(self._workloads):
            if w.id == workload_id:
                self._workloads.pop(i)
                logger.info(
                    "workload_scheduler.workload_deleted",
                    workload_id=workload_id,
                )
                return True
        return False

    def clear_data(self) -> None:
        self._workloads.clear()
        self._conflicts.clear()
        logger.info("workload_scheduler.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        workload_names = {w.workload_name for w in self._workloads}
        priorities = {w.priority.value for w in self._workloads}
        strategies = {w.strategy.value for w in self._workloads}
        return {
            "total_workloads": len(self._workloads),
            "total_conflicts": len(self._conflicts),
            "unique_workload_names": len(workload_names),
            "priorities": sorted(priorities),
            "strategies": sorted(strategies),
        }
