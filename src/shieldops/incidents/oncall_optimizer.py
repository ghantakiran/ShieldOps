"""On-Call Rotation Optimizer — fairness, timezone coverage, and skill matching."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RotationStrategy(StrEnum):
    ROUND_ROBIN = "round_robin"
    TIMEZONE_FOLLOW = "timezone_follow"
    SKILL_BASED = "skill_based"
    LOAD_BALANCED = "load_balanced"
    HYBRID = "hybrid"


class FairnessMetric(StrEnum):
    EQUAL_HOURS = "equal_hours"
    EQUAL_PAGES = "equal_pages"
    EQUAL_SEVERITY = "equal_severity"
    EQUAL_AFTER_HOURS = "equal_after_hours"
    COMPOSITE = "composite"


class CoverageGap(StrEnum):
    TIMEZONE_UNCOVERED = "timezone_uncovered"
    SKILL_MISSING = "skill_missing"
    SINGLE_POINT = "single_point"
    CONSECUTIVE_DAYS = "consecutive_days"
    HOLIDAY_UNCOVERED = "holiday_uncovered"


# --- Models ---


class RotationMember(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    email: str = ""
    timezone: str = "UTC"
    skills: list[str] = Field(default_factory=list)
    total_hours: float = 0.0
    total_pages: int = 0
    consecutive_days: int = 0
    is_available: bool = True
    created_at: float = Field(default_factory=time.time)


class RotationSchedule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy: RotationStrategy = RotationStrategy.ROUND_ROBIN
    members: list[str] = Field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    fairness_score: float = 0.0
    gaps: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class RotationReport(BaseModel):
    total_members: int = 0
    total_schedules: int = 0
    avg_fairness_score: float = 0.0
    gap_count: int = 0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_timezone: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class OnCallRotationOptimizer:
    """Optimize on-call rotations for fairness, timezone coverage, and skill matching."""

    def __init__(
        self,
        max_members: int = 10000,
        max_consecutive_days: int = 7,
    ) -> None:
        self._max_members = max_members
        self._max_consecutive_days = max_consecutive_days
        self._members: list[RotationMember] = []
        self._schedules: list[RotationSchedule] = []
        logger.info(
            "oncall_optimizer.initialized",
            max_members=max_members,
            max_consecutive_days=max_consecutive_days,
        )

    def register_member(
        self,
        name: str,
        email: str = "",
        timezone: str = "UTC",
        skills: list[str] | None = None,
    ) -> RotationMember:
        """Register a new on-call rotation member."""
        member = RotationMember(
            name=name,
            email=email,
            timezone=timezone,
            skills=skills or [],
        )
        self._members.append(member)
        if len(self._members) > self._max_members:
            self._members = self._members[-self._max_members :]
        logger.info(
            "oncall_optimizer.member_registered",
            member_id=member.id,
            name=name,
            timezone=timezone,
        )
        return member

    def get_member(self, member_id: str) -> RotationMember | None:
        """Retrieve a member by ID."""
        for m in self._members:
            if m.id == member_id:
                return m
        return None

    def list_members(
        self,
        timezone: str | None = None,
        is_available: bool | None = None,
        limit: int = 100,
    ) -> list[RotationMember]:
        """List members with optional filtering."""
        results = list(self._members)
        if timezone is not None:
            results = [m for m in results if m.timezone == timezone]
        if is_available is not None:
            results = [m for m in results if m.is_available == is_available]
        return results[-limit:]

    def generate_schedule(
        self,
        strategy: RotationStrategy,
        member_ids: list[str],
        start_date: str = "",
        end_date: str = "",
    ) -> RotationSchedule:
        """Create a schedule, calculate fairness score, and detect gaps."""
        # Gather members for this schedule
        schedule_members = [m for m in self._members if m.id in member_ids]

        # Calculate fairness score based on std dev of total_hours
        fairness_score = 0.0
        if schedule_members:
            hours = [m.total_hours for m in schedule_members]
            mean_hours = sum(hours) / len(hours)
            variance = sum((h - mean_hours) ** 2 for h in hours) / len(hours)
            std_dev = variance**0.5
            fairness_score = max(0.0, round(100.0 - std_dev * 10, 2))

        # Detect gaps
        gaps: list[str] = []
        for m in schedule_members:
            if m.consecutive_days > self._max_consecutive_days:
                gaps.append(f"{CoverageGap.CONSECUTIVE_DAYS}:{m.name}")

        # Check for timezones with only 1 member
        tz_counts: dict[str, int] = {}
        for m in schedule_members:
            tz_counts[m.timezone] = tz_counts.get(m.timezone, 0) + 1
        for tz, count in tz_counts.items():
            if count == 1:
                gaps.append(f"{CoverageGap.SINGLE_POINT}:{tz}")

        schedule = RotationSchedule(
            strategy=strategy,
            members=member_ids,
            start_date=start_date,
            end_date=end_date,
            fairness_score=fairness_score,
            gaps=gaps,
        )
        self._schedules.append(schedule)
        logger.info(
            "oncall_optimizer.schedule_generated",
            schedule_id=schedule.id,
            strategy=strategy,
            member_count=len(member_ids),
            fairness_score=fairness_score,
        )
        return schedule

    def calculate_fairness_score(self, schedule_id: str) -> dict[str, Any]:
        """Calculate detailed fairness score for a schedule."""
        schedule = None
        for s in self._schedules:
            if s.id == schedule_id:
                schedule = s
                break
        if schedule is None:
            return {
                "schedule_id": schedule_id,
                "fairness_score": 0.0,
                "member_hours": {},
                "max_deviation": 0.0,
            }

        schedule_members = [m for m in self._members if m.id in schedule.members]
        member_hours: dict[str, float] = {}
        hours_list: list[float] = []
        for m in schedule_members:
            member_hours[m.name] = m.total_hours
            hours_list.append(m.total_hours)

        if hours_list:
            mean_hours = sum(hours_list) / len(hours_list)
            max_deviation = max(abs(h - mean_hours) for h in hours_list)
            variance = sum((h - mean_hours) ** 2 for h in hours_list) / len(hours_list)
            std_dev = variance**0.5
            fairness_score = max(0.0, round(100.0 - std_dev * 10, 2))
        else:
            max_deviation = 0.0
            fairness_score = 0.0

        schedule.fairness_score = fairness_score
        logger.info(
            "oncall_optimizer.fairness_calculated",
            schedule_id=schedule_id,
            fairness_score=fairness_score,
        )
        return {
            "schedule_id": schedule_id,
            "fairness_score": fairness_score,
            "member_hours": member_hours,
            "max_deviation": round(max_deviation, 2),
        }

    def detect_coverage_gaps(self, schedule_id: str | None = None) -> list[str]:
        """Detect coverage gaps across members or for a specific schedule."""
        gaps: list[str] = []
        if schedule_id is not None:
            # Gaps for specific schedule
            schedule = None
            for s in self._schedules:
                if s.id == schedule_id:
                    schedule = s
                    break
            if schedule is None:
                return gaps
            target_members = [m for m in self._members if m.id in schedule.members]
        else:
            target_members = list(self._members)

        # Check consecutive days
        for m in target_members:
            if m.consecutive_days > self._max_consecutive_days:
                gaps.append(f"{CoverageGap.CONSECUTIVE_DAYS}:{m.name}")

        # Check timezones with only 1 member
        tz_counts: dict[str, int] = {}
        for m in target_members:
            tz_counts[m.timezone] = tz_counts.get(m.timezone, 0) + 1
        for tz, count in tz_counts.items():
            if count == 1:
                gaps.append(f"{CoverageGap.SINGLE_POINT}:{tz}")

        # Check for members missing skills
        all_skills: set[str] = set()
        for m in target_members:
            all_skills.update(m.skills)
        for m in target_members:
            if all_skills and not m.skills:
                gaps.append(f"{CoverageGap.SKILL_MISSING}:{m.name}")

        logger.info(
            "oncall_optimizer.gaps_detected",
            gap_count=len(gaps),
            schedule_id=schedule_id,
        )
        return gaps

    def optimize_handoffs(self) -> list[dict[str, Any]]:
        """Suggest handoff times for adjacent timezone members."""
        handoffs: list[dict[str, Any]] = []
        # Sort members by timezone for adjacency
        tz_members: dict[str, list[RotationMember]] = {}
        for m in self._members:
            if m.is_available:
                tz_members.setdefault(m.timezone, []).append(m)

        sorted_tzs = sorted(tz_members.keys())
        for i in range(len(sorted_tzs) - 1):
            from_tz = sorted_tzs[i]
            to_tz = sorted_tzs[i + 1]
            from_member = tz_members[from_tz][0]
            to_member = tz_members[to_tz][0]
            handoffs.append(
                {
                    "from_member": from_member.name,
                    "to_member": to_member.name,
                    "suggested_time": f"09:00 {to_tz}",
                }
            )
        logger.info(
            "oncall_optimizer.handoffs_optimized",
            handoff_count=len(handoffs),
        )
        return handoffs

    def track_actual_load(
        self,
        member_id: str,
        hours: float = 0.0,
        pages: int = 0,
    ) -> RotationMember | None:
        """Update a member's actual load tracking."""
        for m in self._members:
            if m.id == member_id:
                m.total_hours += hours
                m.total_pages += pages
                logger.info(
                    "oncall_optimizer.load_tracked",
                    member_id=member_id,
                    total_hours=m.total_hours,
                    total_pages=m.total_pages,
                )
                return m
        return None

    def generate_rotation_report(self) -> RotationReport:
        """Generate a comprehensive rotation report."""
        total_members = len(self._members)
        total_schedules = len(self._schedules)

        # Average fairness score
        fairness_scores = [s.fairness_score for s in self._schedules]
        avg_fairness = (
            round(sum(fairness_scores) / len(fairness_scores), 2) if fairness_scores else 0.0
        )

        # Total gaps
        gap_count = sum(len(s.gaps) for s in self._schedules)

        # By strategy
        by_strategy: dict[str, int] = {}
        for s in self._schedules:
            by_strategy[s.strategy] = by_strategy.get(s.strategy, 0) + 1

        # By timezone
        by_timezone: dict[str, int] = {}
        for m in self._members:
            by_timezone[m.timezone] = by_timezone.get(m.timezone, 0) + 1

        # Recommendations
        recommendations: list[str] = []
        if avg_fairness < 70.0 and total_schedules > 0:
            recommendations.append(
                "Average fairness score is below 70 — consider rebalancing on-call loads"
            )
        if gap_count > 0:
            recommendations.append(
                f"{gap_count} coverage gap(s) detected — review timezone and skill coverage"
            )
        single_tz_members = [tz for tz, count in by_timezone.items() if count == 1]
        if single_tz_members:
            recommendations.append(
                f"Single-point timezones: {', '.join(single_tz_members)} — add backup members"
            )

        logger.info(
            "oncall_optimizer.report_generated",
            total_members=total_members,
            total_schedules=total_schedules,
            avg_fairness=avg_fairness,
        )
        return RotationReport(
            total_members=total_members,
            total_schedules=total_schedules,
            avg_fairness_score=avg_fairness,
            gap_count=gap_count,
            by_strategy=by_strategy,
            by_timezone=by_timezone,
            recommendations=recommendations,
        )

    def clear_data(self) -> None:
        """Clear all stored data."""
        self._members.clear()
        self._schedules.clear()
        logger.info("oncall_optimizer.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        tz_counts: dict[str, int] = {}
        skill_counts: dict[str, int] = {}
        for m in self._members:
            tz_counts[m.timezone] = tz_counts.get(m.timezone, 0) + 1
            for s in m.skills:
                skill_counts[s] = skill_counts.get(s, 0) + 1
        return {
            "total_members": len(self._members),
            "total_schedules": len(self._schedules),
            "available_members": sum(1 for m in self._members if m.is_available),
            "timezone_distribution": tz_counts,
            "skill_distribution": skill_counts,
        }
