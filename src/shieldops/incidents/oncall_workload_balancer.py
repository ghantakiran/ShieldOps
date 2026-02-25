"""On-Call Workload Balancer — equity analysis of on-call
burden distribution with rebalancing suggestions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WorkloadBalance(StrEnum):
    EQUITABLE = "equitable"
    SLIGHTLY_UNEVEN = "slightly_uneven"
    MODERATELY_UNEVEN = "moderately_uneven"
    HEAVILY_SKEWED = "heavily_skewed"
    CRITICAL_IMBALANCE = "critical_imbalance"


class LoadFactor(StrEnum):
    PAGE_COUNT = "page_count"
    AFTER_HOURS_PAGES = "after_hours_pages"
    INCIDENT_DURATION = "incident_duration"
    WEEKEND_SHIFTS = "weekend_shifts"
    ESCALATION_COUNT = "escalation_count"


class RebalanceAction(StrEnum):
    NO_CHANGE = "no_change"
    SWAP_SHIFT = "swap_shift"
    ADD_SECONDARY = "add_secondary"
    REDUCE_ROTATION = "reduce_rotation"
    TEMPORARY_RELIEF = "temporary_relief"


# --- Models ---


class WorkloadRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_member: str = ""
    team_name: str = ""
    period_label: str = ""
    page_count: int = 0
    after_hours_pages: int = 0
    incident_duration_minutes: float = 0.0
    weekend_shifts: int = 0
    escalation_count: int = 0
    created_at: float = Field(default_factory=time.time)


class RebalanceSuggestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_name: str = ""
    action: RebalanceAction = RebalanceAction.NO_CHANGE
    from_member: str = ""
    to_member: str = ""
    reason: str = ""
    impact_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class WorkloadReport(BaseModel):
    total_records: int = 0
    total_suggestions: int = 0
    by_balance: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    overloaded_members: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class OnCallWorkloadBalancer:
    """Equity analysis of on-call burden distribution with rebalancing suggestions."""

    def __init__(
        self,
        max_records: int = 200000,
        imbalance_threshold_pct: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._imbalance_threshold_pct = imbalance_threshold_pct
        self._workloads: list[WorkloadRecord] = []
        self._suggestions: list[RebalanceSuggestion] = []
        logger.info(
            "oncall_workload_balancer.initialized",
            max_records=max_records,
            imbalance_threshold_pct=imbalance_threshold_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_workload(
        self,
        team_member: str,
        team_name: str = "",
        period_label: str = "",
        page_count: int = 0,
        after_hours_pages: int = 0,
        incident_duration_minutes: float = 0.0,
        weekend_shifts: int = 0,
        escalation_count: int = 0,
        **kw: Any,
    ) -> WorkloadRecord:
        record = WorkloadRecord(
            team_member=team_member,
            team_name=team_name,
            period_label=period_label,
            page_count=page_count,
            after_hours_pages=after_hours_pages,
            incident_duration_minutes=incident_duration_minutes,
            weekend_shifts=weekend_shifts,
            escalation_count=escalation_count,
            **kw,
        )
        self._workloads.append(record)
        if len(self._workloads) > self._max_records:
            self._workloads = self._workloads[-self._max_records :]
        logger.info(
            "oncall_workload_balancer.workload_recorded",
            record_id=record.id,
            team_member=team_member,
        )
        return record

    def get_workload(self, record_id: str) -> WorkloadRecord | None:
        for w in self._workloads:
            if w.id == record_id:
                return w
        return None

    def list_workloads(
        self,
        team_name: str | None = None,
        team_member: str | None = None,
        limit: int = 50,
    ) -> list[WorkloadRecord]:
        results = list(self._workloads)
        if team_name is not None:
            results = [r for r in results if r.team_name == team_name]
        if team_member is not None:
            results = [r for r in results if r.team_member == team_member]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def compute_balance_score(
        self,
        team_name: str,
    ) -> dict[str, Any]:
        """Compute workload balance score for a team."""
        records = [w for w in self._workloads if w.team_name == team_name]
        if not records:
            return {
                "team_name": team_name,
                "balance": WorkloadBalance.EQUITABLE.value,
                "member_count": 0,
                "score": 100.0,
            }
        by_member: dict[str, float] = {}
        for r in records:
            score = (
                r.page_count + r.after_hours_pages * 2 + r.weekend_shifts * 3 + r.escalation_count
            )
            by_member[r.team_member] = by_member.get(r.team_member, 0) + score
        if not by_member:
            return {
                "team_name": team_name,
                "balance": WorkloadBalance.EQUITABLE.value,
                "member_count": 0,
                "score": 100.0,
            }
        values = list(by_member.values())
        avg = sum(values) / len(values)
        if avg == 0:
            imbalance = 0.0
        else:
            max_dev = max(abs(v - avg) for v in values)
            imbalance = round((max_dev / avg) * 100, 2)
        balance = self._imbalance_to_balance(imbalance)
        return {
            "team_name": team_name,
            "balance": balance.value,
            "member_count": len(by_member),
            "imbalance_pct": imbalance,
            "score": round(max(0, 100 - imbalance), 2),
            "by_member": {k: round(v, 2) for k, v in by_member.items()},
        }

    def suggest_rebalance(
        self,
        team_name: str,
    ) -> RebalanceSuggestion:
        """Suggest rebalancing actions for a team."""
        records = [w for w in self._workloads if w.team_name == team_name]
        if not records:
            suggestion = RebalanceSuggestion(
                team_name=team_name,
                action=RebalanceAction.NO_CHANGE,
                reason="No workload data available",
            )
            self._suggestions.append(suggestion)
            return suggestion
        by_member: dict[str, float] = {}
        for r in records:
            score = r.page_count + r.after_hours_pages * 2 + r.weekend_shifts * 3
            by_member[r.team_member] = by_member.get(r.team_member, 0) + score
        if len(by_member) < 2:
            suggestion = RebalanceSuggestion(
                team_name=team_name,
                action=RebalanceAction.ADD_SECONDARY,
                reason="Only one team member in rotation",
            )
            self._suggestions.append(suggestion)
            return suggestion
        sorted_members = sorted(by_member.items(), key=lambda x: x[1])
        lightest = sorted_members[0]
        heaviest = sorted_members[-1]
        avg = sum(by_member.values()) / len(by_member)
        if avg > 0 and (heaviest[1] - lightest[1]) / avg > self._imbalance_threshold_pct / 100:
            action = RebalanceAction.SWAP_SHIFT
            reason = (
                f"Shift {heaviest[0]} (load={heaviest[1]:.0f}) "
                f"with {lightest[0]} (load={lightest[1]:.0f})"
            )
        else:
            action = RebalanceAction.NO_CHANGE
            reason = "Workload is balanced"
        suggestion = RebalanceSuggestion(
            team_name=team_name,
            action=action,
            from_member=heaviest[0],
            to_member=lightest[0],
            reason=reason,
            impact_score=round(heaviest[1] - lightest[1], 2),
        )
        self._suggestions.append(suggestion)
        if len(self._suggestions) > self._max_records:
            self._suggestions = self._suggestions[-self._max_records :]
        logger.info(
            "oncall_workload_balancer.suggestion_created",
            suggestion_id=suggestion.id,
            team_name=team_name,
        )
        return suggestion

    def list_suggestions(
        self,
        team_name: str | None = None,
        limit: int = 50,
    ) -> list[RebalanceSuggestion]:
        results = list(self._suggestions)
        if team_name is not None:
            results = [r for r in results if r.team_name == team_name]
        return results[-limit:]

    def identify_overloaded_members(self) -> list[dict[str, Any]]:
        """Identify team members with disproportionately high workload."""
        by_member: dict[str, dict[str, Any]] = {}
        for r in self._workloads:
            if r.team_member not in by_member:
                by_member[r.team_member] = {
                    "team_member": r.team_member,
                    "team_name": r.team_name,
                    "total_pages": 0,
                    "total_after_hours": 0,
                    "total_weekend_shifts": 0,
                }
            by_member[r.team_member]["total_pages"] += r.page_count
            by_member[r.team_member]["total_after_hours"] += r.after_hours_pages
            by_member[r.team_member]["total_weekend_shifts"] += r.weekend_shifts
        if not by_member:
            return []
        all_pages = [m["total_pages"] for m in by_member.values()]
        avg_pages = sum(all_pages) / len(all_pages) if all_pages else 0
        threshold = avg_pages * (1 + self._imbalance_threshold_pct / 100)
        overloaded = [
            m for m in by_member.values() if m["total_pages"] > threshold and avg_pages > 0
        ]
        overloaded.sort(key=lambda x: x["total_pages"], reverse=True)
        return overloaded

    def compare_periods(
        self,
        period_labels: list[str],
    ) -> list[dict[str, Any]]:
        """Compare workload distribution across periods."""
        results: list[dict[str, Any]] = []
        for label in period_labels:
            records = [w for w in self._workloads if w.period_label == label]
            total_pages = sum(r.page_count for r in records)
            total_members = len({r.team_member for r in records})
            results.append(
                {
                    "period_label": label,
                    "record_count": len(records),
                    "total_pages": total_pages,
                    "unique_members": total_members,
                    "avg_pages_per_member": (
                        round(total_pages / total_members, 2) if total_members > 0 else 0
                    ),
                }
            )
        return results

    # -- report / stats ----------------------------------------------

    def generate_workload_report(self) -> WorkloadReport:
        teams = {w.team_name for w in self._workloads}
        by_balance: dict[str, int] = {}
        for team in teams:
            score_data = self.compute_balance_score(team)
            balance = score_data.get("balance", "equitable")
            by_balance[balance] = by_balance.get(balance, 0) + 1
        by_action: dict[str, int] = {}
        for s in self._suggestions:
            key = s.action.value
            by_action[key] = by_action.get(key, 0) + 1
        overloaded_members = self.identify_overloaded_members()
        overloaded_names = [m["team_member"] for m in overloaded_members[:5]]
        recs: list[str] = []
        if overloaded_names:
            recs.append(f"{len(overloaded_names)} overloaded team member(s) identified")
        if not recs:
            recs.append("On-call workload distribution is balanced")
        return WorkloadReport(
            total_records=len(self._workloads),
            total_suggestions=len(self._suggestions),
            by_balance=by_balance,
            by_action=by_action,
            overloaded_members=overloaded_names,
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._workloads)
        self._workloads.clear()
        self._suggestions.clear()
        logger.info("oncall_workload_balancer.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        teams = list({w.team_name for w in self._workloads})
        return {
            "total_records": len(self._workloads),
            "total_suggestions": len(self._suggestions),
            "imbalance_threshold_pct": self._imbalance_threshold_pct,
            "unique_teams": len(teams),
        }

    # -- internal helpers --------------------------------------------

    def _imbalance_to_balance(self, pct: float) -> WorkloadBalance:
        if pct <= 10:
            return WorkloadBalance.EQUITABLE
        if pct <= 25:
            return WorkloadBalance.SLIGHTLY_UNEVEN
        if pct <= 50:
            return WorkloadBalance.MODERATELY_UNEVEN
        if pct <= 75:
            return WorkloadBalance.HEAVILY_SKEWED
        return WorkloadBalance.CRITICAL_IMBALANCE
