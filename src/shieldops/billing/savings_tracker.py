"""Cloud Savings Tracker — track realized vs projected savings with ROI attribution."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SavingsSource(StrEnum):
    RIGHT_SIZING = "right_sizing"
    RESERVED_INSTANCES = "reserved_instances"
    SPOT_USAGE = "spot_usage"
    WASTE_ELIMINATION = "waste_elimination"
    RATE_NEGOTIATION = "rate_negotiation"


class SavingsStatus(StrEnum):
    PROJECTED = "projected"
    IN_PROGRESS = "in_progress"
    REALIZED = "realized"
    PARTIALLY_REALIZED = "partially_realized"
    MISSED = "missed"


class TrackingPeriod(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    CUSTOM = "custom"


# --- Models ---


class SavingsRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: SavingsSource = SavingsSource.RIGHT_SIZING
    service_name: str = ""
    team: str = ""
    projected_savings: float = 0.0
    realized_savings: float = 0.0
    status: SavingsStatus = SavingsStatus.PROJECTED
    period: TrackingPeriod = TrackingPeriod.MONTHLY
    start_date: str = ""
    end_date: str = ""
    created_at: float = Field(default_factory=time.time)


class SavingsGoal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team: str = ""
    target_amount: float = 0.0
    current_amount: float = 0.0
    period: TrackingPeriod = TrackingPeriod.MONTHLY
    progress_pct: float = 0.0
    on_track: bool = False
    created_at: float = Field(default_factory=time.time)


class SavingsReport(BaseModel):
    total_projected: float = 0.0
    total_realized: float = 0.0
    realization_rate_pct: float = 0.0
    by_source: dict[str, float] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_team: dict[str, float] = Field(default_factory=dict)
    top_savers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CloudSavingsTracker:
    """Track realized vs projected savings from optimization actions."""

    def __init__(
        self,
        max_records: int = 200000,
        realization_target_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._realization_target_pct = realization_target_pct
        self._items: list[SavingsRecord] = []
        self._goals: list[SavingsGoal] = []
        logger.info(
            "savings_tracker.initialized",
            max_records=max_records,
            realization_target_pct=realization_target_pct,
        )

    def record_savings(
        self,
        source: SavingsSource,
        service_name: str,
        team: str,
        projected_savings: float,
        realized_savings: float = 0.0,
        period: TrackingPeriod = TrackingPeriod.MONTHLY,
        start_date: str = "",
        end_date: str = "",
        **kw: Any,
    ) -> SavingsRecord:
        """Record a savings entry."""
        status = SavingsStatus.PROJECTED
        if realized_savings >= projected_savings > 0:
            status = SavingsStatus.REALIZED
        elif realized_savings > 0:
            status = SavingsStatus.IN_PROGRESS

        record = SavingsRecord(
            source=source,
            service_name=service_name,
            team=team,
            projected_savings=projected_savings,
            realized_savings=realized_savings,
            status=status,
            period=period,
            start_date=start_date,
            end_date=end_date,
            **kw,
        )
        self._items.append(record)
        if len(self._items) > self._max_records:
            self._items = self._items[-self._max_records :]
        logger.info(
            "savings_tracker.record_created",
            record_id=record.id,
            source=source,
            service_name=service_name,
            projected=projected_savings,
        )
        return record

    def get_record(
        self,
        record_id: str,
    ) -> SavingsRecord | None:
        """Retrieve a single record by ID."""
        for r in self._items:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        source: SavingsSource | None = None,
        status: SavingsStatus | None = None,
        limit: int = 50,
    ) -> list[SavingsRecord]:
        """List records with optional filtering."""
        results = list(self._items)
        if source is not None:
            results = [r for r in results if r.source == source]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    def create_goal(
        self,
        team: str,
        target_amount: float,
        period: TrackingPeriod,
    ) -> SavingsGoal:
        """Create a savings goal for a team."""
        # Calculate current realized for this team
        current = sum(r.realized_savings for r in self._items if r.team == team)
        progress = 0.0
        if target_amount > 0:
            progress = round(current / target_amount * 100, 2)
        on_track = progress >= 50.0  # heuristic

        goal = SavingsGoal(
            team=team,
            target_amount=target_amount,
            current_amount=round(current, 2),
            period=period,
            progress_pct=progress,
            on_track=on_track,
        )
        self._goals.append(goal)
        logger.info(
            "savings_tracker.goal_created",
            goal_id=goal.id,
            team=team,
            target_amount=target_amount,
            progress_pct=progress,
        )
        return goal

    def update_realized(
        self,
        record_id: str,
        amount: float,
    ) -> SavingsRecord | None:
        """Update the realized savings for a record."""
        record = self.get_record(record_id)
        if record is None:
            return None
        record.realized_savings = amount
        if amount >= record.projected_savings > 0:
            record.status = SavingsStatus.REALIZED
        elif amount > 0:
            record.status = SavingsStatus.PARTIALLY_REALIZED
        logger.info(
            "savings_tracker.realized_updated",
            record_id=record_id,
            amount=amount,
            status=record.status,
        )
        return record

    def calculate_realization_rate(self) -> float:
        """Calculate overall realization rate."""
        total_projected = sum(r.projected_savings for r in self._items)
        total_realized = sum(r.realized_savings for r in self._items)
        if total_projected <= 0:
            return 0.0
        return round(total_realized / total_projected * 100, 2)

    def rank_teams_by_savings(
        self,
    ) -> list[dict[str, Any]]:
        """Rank teams by total realized savings."""
        team_data: dict[str, dict[str, Any]] = {}
        for r in self._items:
            if r.team not in team_data:
                team_data[r.team] = {
                    "team": r.team,
                    "total_projected": 0.0,
                    "total_realized": 0.0,
                    "record_count": 0,
                }
            entry = team_data[r.team]
            entry["total_projected"] += r.projected_savings
            entry["total_realized"] += r.realized_savings
            entry["record_count"] += 1

        for entry in team_data.values():
            proj = entry["total_projected"]
            entry["total_projected"] = round(proj, 2)
            real = entry["total_realized"]
            entry["total_realized"] = round(real, 2)
            entry["realization_rate_pct"] = round(real / proj * 100, 2) if proj > 0 else 0.0

        ranked = sorted(
            team_data.values(),
            key=lambda x: x["total_realized"],
            reverse=True,
        )
        return ranked

    def identify_missed_opportunities(
        self,
    ) -> list[SavingsRecord]:
        """Find records with low or no realization."""
        missed: list[SavingsRecord] = []
        for r in self._items:
            if r.projected_savings > 0:
                rate = r.realized_savings / r.projected_savings
                if rate < 0.5:
                    missed.append(r)
        return missed

    def generate_savings_report(self) -> SavingsReport:
        """Generate a comprehensive savings report."""
        total_proj = sum(r.projected_savings for r in self._items)
        total_real = sum(r.realized_savings for r in self._items)
        rate = 0.0
        if total_proj > 0:
            rate = round(total_real / total_proj * 100, 2)

        by_source: dict[str, float] = {}
        by_status: dict[str, int] = {}
        by_team: dict[str, float] = {}
        for r in self._items:
            by_source[r.source.value] = round(
                by_source.get(r.source.value, 0.0) + r.realized_savings,
                2,
            )
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_team[r.team] = round(
                by_team.get(r.team, 0.0) + r.realized_savings,
                2,
            )

        ranked = self.rank_teams_by_savings()
        top_savers = [t["team"] for t in ranked[:5] if t["team"]]

        recommendations: list[str] = []
        if rate < self._realization_target_pct:
            recommendations.append(
                f"Realization rate {rate:.1f}% is below"
                f" {self._realization_target_pct}% target"
                " — accelerate in-progress items"
            )
        missed = self.identify_missed_opportunities()
        if missed:
            recommendations.append(
                f"{len(missed)} record(s) below 50% realization — review and remediate"
            )
        if ranked:
            worst = ranked[-1]
            if worst["realization_rate_pct"] < 50:
                recommendations.append(
                    f"Team '{worst['team']}' has"
                    f" {worst['realization_rate_pct']}%"
                    " realization — needs attention"
                )

        report = SavingsReport(
            total_projected=round(total_proj, 2),
            total_realized=round(total_real, 2),
            realization_rate_pct=rate,
            by_source=by_source,
            by_status=by_status,
            by_team=by_team,
            top_savers=top_savers,
            recommendations=recommendations,
        )
        logger.info(
            "savings_tracker.report_generated",
            total_projected=round(total_proj, 2),
            total_realized=round(total_real, 2),
            realization_rate_pct=rate,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored records and goals."""
        self._items.clear()
        self._goals.clear()
        logger.info("savings_tracker.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        source_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for r in self._items:
            source_counts[r.source.value] = source_counts.get(r.source.value, 0) + 1
            status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1
        return {
            "total_records": len(self._items),
            "total_goals": len(self._goals),
            "source_distribution": source_counts,
            "status_distribution": status_counts,
            "max_records": self._max_records,
            "realization_target_pct": (self._realization_target_pct),
        }
