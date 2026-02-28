"""Agent Swarm Coordinator — coordinate multiple agents on the same incident."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SwarmRole(StrEnum):
    LEADER = "leader"
    INVESTIGATOR = "investigator"
    REMEDIATOR = "remediator"
    OBSERVER = "observer"
    VALIDATOR = "validator"


class SwarmStatus(StrEnum):
    FORMING = "forming"
    ACTIVE = "active"
    CONVERGING = "converging"
    COMPLETED = "completed"
    DISSOLVED = "dissolved"


class ConflictResolution(StrEnum):
    LEADER_DECIDES = "leader_decides"
    MAJORITY_VOTE = "majority_vote"
    PRIORITY_BASED = "priority_based"
    ROUND_ROBIN = "round_robin"
    ESCALATE = "escalate"


# --- Models ---


class SwarmRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    swarm_role: SwarmRole = SwarmRole.LEADER
    swarm_status: SwarmStatus = SwarmStatus.FORMING
    conflict_resolution: ConflictResolution = ConflictResolution.LEADER_DECIDES
    agent_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AgentAssignment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    swarm_role: SwarmRole = SwarmRole.INVESTIGATOR
    swarm_status: SwarmStatus = SwarmStatus.ACTIVE
    utilization_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class SwarmCoordinatorReport(BaseModel):
    total_swarms: int = 0
    total_assignments: int = 0
    completion_rate_pct: float = 0.0
    by_role: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    conflict_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentSwarmCoordinator:
    """Coordinate multiple agents on the same incident."""

    def __init__(
        self,
        max_records: int = 200000,
        max_agents: int = 10,
    ) -> None:
        self._max_records = max_records
        self._max_agents = max_agents
        self._records: list[SwarmRecord] = []
        self._assignments: list[AgentAssignment] = []
        logger.info(
            "swarm_coordinator.initialized",
            max_records=max_records,
            max_agents=max_agents,
        )

    # -- record / get / list ---------------------------------------------

    def record_swarm(
        self,
        incident_id: str,
        swarm_role: SwarmRole = SwarmRole.LEADER,
        swarm_status: SwarmStatus = SwarmStatus.FORMING,
        conflict_resolution: ConflictResolution = ConflictResolution.LEADER_DECIDES,
        agent_count: int = 0,
        details: str = "",
    ) -> SwarmRecord:
        record = SwarmRecord(
            incident_id=incident_id,
            swarm_role=swarm_role,
            swarm_status=swarm_status,
            conflict_resolution=conflict_resolution,
            agent_count=agent_count,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "swarm_coordinator.swarm_recorded",
            record_id=record.id,
            incident_id=incident_id,
            swarm_role=swarm_role.value,
            swarm_status=swarm_status.value,
        )
        return record

    def get_swarm(self, record_id: str) -> SwarmRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_swarms(
        self,
        incident_id: str | None = None,
        swarm_status: SwarmStatus | None = None,
        limit: int = 50,
    ) -> list[SwarmRecord]:
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if swarm_status is not None:
            results = [r for r in results if r.swarm_status == swarm_status]
        return results[-limit:]

    def add_assignment(
        self,
        agent_name: str,
        swarm_role: SwarmRole = SwarmRole.INVESTIGATOR,
        swarm_status: SwarmStatus = SwarmStatus.ACTIVE,
        utilization_pct: float = 0.0,
    ) -> AgentAssignment:
        assignment = AgentAssignment(
            agent_name=agent_name,
            swarm_role=swarm_role,
            swarm_status=swarm_status,
            utilization_pct=utilization_pct,
        )
        self._assignments.append(assignment)
        if len(self._assignments) > self._max_records:
            self._assignments = self._assignments[-self._max_records :]
        logger.info(
            "swarm_coordinator.assignment_added",
            agent_name=agent_name,
            swarm_role=swarm_role.value,
            swarm_status=swarm_status.value,
        )
        return assignment

    # -- domain operations -----------------------------------------------

    def analyze_swarm_effectiveness(self, incident_id: str) -> dict[str, Any]:
        """Analyze swarm effectiveness for a specific incident."""
        records = [r for r in self._records if r.incident_id == incident_id]
        if not records:
            return {"incident_id": incident_id, "status": "no_data"}
        completed = sum(1 for r in records if r.swarm_status == SwarmStatus.COMPLETED)
        completion_rate = round(completed / len(records) * 100, 2)
        avg_agents = round(sum(r.agent_count for r in records) / len(records), 2)
        return {
            "incident_id": incident_id,
            "total_swarms": len(records),
            "completed_count": completed,
            "completion_rate_pct": completion_rate,
            "avg_agent_count": avg_agents,
            "meets_threshold": completion_rate >= (100.0 - self._max_agents * 5),
        }

    def identify_idle_agents(self) -> list[dict[str, Any]]:
        """Find agents with repeated idle or dissolved swarms."""
        failure_counts: dict[str, int] = {}
        for r in self._records:
            if r.swarm_status in (
                SwarmStatus.DISSOLVED,
                SwarmStatus.FORMING,
                SwarmStatus.CONVERGING,
            ):
                failure_counts[r.incident_id] = failure_counts.get(r.incident_id, 0) + 1
        results: list[dict[str, Any]] = []
        for incident, count in failure_counts.items():
            if count > 1:
                results.append(
                    {
                        "incident_id": incident,
                        "idle_count": count,
                    }
                )
        results.sort(key=lambda x: x["idle_count"], reverse=True)
        return results

    def rank_by_completion_rate(self) -> list[dict[str, Any]]:
        """Rank incidents by swarm count descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.incident_id] = freq.get(r.incident_id, 0) + 1
        results: list[dict[str, Any]] = []
        for incident, count in freq.items():
            results.append(
                {
                    "incident_id": incident,
                    "swarm_count": count,
                }
            )
        results.sort(key=lambda x: x["swarm_count"], reverse=True)
        return results

    def detect_coordination_conflicts(self) -> list[dict[str, Any]]:
        """Detect incidents with coordination conflicts (>3 non-completed)."""
        non_completed: dict[str, int] = {}
        for r in self._records:
            if r.swarm_status != SwarmStatus.COMPLETED:
                non_completed[r.incident_id] = non_completed.get(r.incident_id, 0) + 1
        results: list[dict[str, Any]] = []
        for incident, count in non_completed.items():
            if count > 3:
                results.append(
                    {
                        "incident_id": incident,
                        "non_completed_count": count,
                        "conflict_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_completed_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> SwarmCoordinatorReport:
        by_role: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_role[r.swarm_role.value] = by_role.get(r.swarm_role.value, 0) + 1
            by_status[r.swarm_status.value] = by_status.get(r.swarm_status.value, 0) + 1
        completed_count = sum(1 for r in self._records if r.swarm_status == SwarmStatus.COMPLETED)
        completion_rate = (
            round(completed_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        idle_agents = sum(1 for d in self.identify_idle_agents())
        recs: list[str] = []
        if completion_rate < 80.0:
            recs.append(f"Completion rate {completion_rate}% is below 80.0% threshold")
        if idle_agents > 0:
            recs.append(f"{idle_agents} incident(s) with idle agents")
        conflicts = len(self.detect_coordination_conflicts())
        if conflicts > 0:
            recs.append(f"{conflicts} incident(s) detected with coordination conflicts")
        if not recs:
            recs.append("Swarm coordination effectiveness meets targets")
        return SwarmCoordinatorReport(
            total_swarms=len(self._records),
            total_assignments=len(self._assignments),
            completion_rate_pct=completion_rate,
            by_role=by_role,
            by_status=by_status,
            conflict_count=conflicts,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assignments.clear()
        logger.info("swarm_coordinator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        role_dist: dict[str, int] = {}
        for r in self._records:
            key = r.swarm_role.value
            role_dist[key] = role_dist.get(key, 0) + 1
        return {
            "total_swarms": len(self._records),
            "total_assignments": len(self._assignments),
            "max_agents": self._max_agents,
            "role_distribution": role_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
