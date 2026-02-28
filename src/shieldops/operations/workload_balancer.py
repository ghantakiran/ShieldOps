"""Team Workload Balancer — balance and monitor team workload distribution."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WorkloadType(StrEnum):
    INCIDENTS = "incidents"
    DEPLOYMENTS = "deployments"
    ON_CALL = "on_call"
    PROJECTS = "projects"
    MAINTENANCE = "maintenance"


class BalanceStatus(StrEnum):
    BALANCED = "balanced"
    SLIGHTLY_UNBALANCED = "slightly_unbalanced"
    UNBALANCED = "unbalanced"
    HEAVILY_UNBALANCED = "heavily_unbalanced"
    CRITICAL = "critical"


class RebalanceAction(StrEnum):
    REDISTRIBUTE = "redistribute"
    DEFER = "defer"
    ESCALATE = "escalate"
    AUTOMATE = "automate"
    NO_ACTION = "no_action"


# --- Models ---


class WorkloadRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    team_name: str = ""
    workload_type: WorkloadType = WorkloadType.INCIDENTS
    status: BalanceStatus = BalanceStatus.BALANCED
    workload_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkloadAssignment(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    assignment_name: str = ""
    workload_type: WorkloadType = WorkloadType.INCIDENTS
    action: RebalanceAction = RebalanceAction.NO_ACTION
    impact_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkloadBalancerReport(BaseModel):
    total_workloads: int = 0
    total_assignments: int = 0
    avg_workload_score_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    overloaded_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamWorkloadBalancer:
    """Balance team workloads, detect imbalances, and recommend rebalance actions."""

    def __init__(
        self,
        max_records: int = 200000,
        max_imbalance_pct: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_imbalance_pct = max_imbalance_pct
        self._records: list[WorkloadRecord] = []
        self._assignments: list[WorkloadAssignment] = []
        logger.info(
            "workload_balancer.initialized",
            max_records=max_records,
            max_imbalance_pct=max_imbalance_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_workload(
        self,
        team_name: str,
        workload_type: WorkloadType = WorkloadType.INCIDENTS,
        status: BalanceStatus = BalanceStatus.BALANCED,
        workload_score: float = 0.0,
        details: str = "",
    ) -> WorkloadRecord:
        record = WorkloadRecord(
            team_name=team_name,
            workload_type=workload_type,
            status=status,
            workload_score=workload_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "workload_balancer.recorded",
            record_id=record.id,
            team_name=team_name,
            workload_type=workload_type.value,
            status=status.value,
        )
        return record

    def get_workload(self, record_id: str) -> WorkloadRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_workloads(
        self,
        team_name: str | None = None,
        workload_type: WorkloadType | None = None,
        limit: int = 50,
    ) -> list[WorkloadRecord]:
        results = list(self._records)
        if team_name is not None:
            results = [r for r in results if r.team_name == team_name]
        if workload_type is not None:
            results = [r for r in results if r.workload_type == workload_type]
        return results[-limit:]

    def add_assignment(
        self,
        assignment_name: str,
        workload_type: WorkloadType = WorkloadType.INCIDENTS,
        action: RebalanceAction = RebalanceAction.NO_ACTION,
        impact_score: float = 0.0,
        description: str = "",
    ) -> WorkloadAssignment:
        assignment = WorkloadAssignment(
            assignment_name=assignment_name,
            workload_type=workload_type,
            action=action,
            impact_score=impact_score,
            description=description,
        )
        self._assignments.append(assignment)
        if len(self._assignments) > self._max_records:
            self._assignments = self._assignments[-self._max_records :]
        logger.info(
            "workload_balancer.assignment_added",
            assignment_name=assignment_name,
            workload_type=workload_type.value,
            action=action.value,
        )
        return assignment

    # -- domain operations -----------------------------------------------

    def analyze_workload_by_team(self, team_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.team_name == team_name]
        if not records:
            return {"team_name": team_name, "status": "no_data"}
        avg_score = round(sum(r.workload_score for r in records) / len(records), 2)
        overloaded = sum(
            1
            for r in records
            if r.status in (BalanceStatus.HEAVILY_UNBALANCED, BalanceStatus.CRITICAL)
        )
        return {
            "team_name": team_name,
            "total_records": len(records),
            "avg_workload_score": avg_score,
            "overloaded_count": overloaded,
            "exceeds_threshold": avg_score >= self._max_imbalance_pct,
        }

    def identify_overloaded_teams(self) -> list[dict[str, Any]]:
        overload_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (BalanceStatus.HEAVILY_UNBALANCED, BalanceStatus.CRITICAL):
                overload_counts[r.team_name] = overload_counts.get(r.team_name, 0) + 1
        results: list[dict[str, Any]] = []
        for team, count in overload_counts.items():
            if count > 1:
                results.append({"team_name": team, "overloaded_count": count})
        results.sort(key=lambda x: x["overloaded_count"], reverse=True)
        return results

    def rank_by_workload_score(self) -> list[dict[str, Any]]:
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team_name, []).append(r.workload_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team_name": team,
                    "avg_workload_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_workload_score"], reverse=True)
        return results

    def detect_workload_imbalance(self) -> list[dict[str, Any]]:
        team_counts: dict[str, int] = {}
        for r in self._records:
            team_counts[r.team_name] = team_counts.get(r.team_name, 0) + 1
        results: list[dict[str, Any]] = []
        for team, count in team_counts.items():
            if count > 3:
                results.append(
                    {
                        "team_name": team,
                        "workload_count": count,
                        "imbalance_detected": True,
                    }
                )
        results.sort(key=lambda x: x["workload_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> WorkloadBalancerReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.workload_type.value] = by_type.get(r.workload_type.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        avg_score = (
            round(sum(r.workload_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        overloaded = sum(
            1
            for r in self._records
            if r.status in (BalanceStatus.HEAVILY_UNBALANCED, BalanceStatus.CRITICAL)
        )
        recs: list[str] = []
        if avg_score >= self._max_imbalance_pct:
            recs.append(
                f"Average workload score {avg_score}% exceeds {self._max_imbalance_pct}% threshold"
            )
        imbalances = len(self.detect_workload_imbalance())
        if imbalances > 0:
            recs.append(f"{imbalances} team(s) with recurring workload imbalances detected")
        if not recs:
            recs.append("Workload distribution within acceptable balance range")
        return WorkloadBalancerReport(
            total_workloads=len(self._records),
            total_assignments=len(self._assignments),
            avg_workload_score_pct=avg_score,
            by_type=by_type,
            by_status=by_status,
            overloaded_count=overloaded,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assignments.clear()
        logger.info("workload_balancer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.workload_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_workloads": len(self._records),
            "total_assignments": len(self._assignments),
            "max_imbalance_pct": self._max_imbalance_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team_name for r in self._records}),
        }
