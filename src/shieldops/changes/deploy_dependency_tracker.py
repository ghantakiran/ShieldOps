"""Deploy Dependency Tracker — track deployment dependencies and blocking chains."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DependencyType(StrEnum):
    SERVICE = "service"
    DATABASE = "database"
    CONFIG = "config"
    INFRASTRUCTURE = "infrastructure"
    EXTERNAL_API = "external_api"


class DependencyStatus(StrEnum):
    SATISFIED = "satisfied"
    PENDING = "pending"
    BLOCKED = "blocked"
    FAILED = "failed"
    SKIPPED = "skipped"


class BlockingReason(StrEnum):
    VERSION_MISMATCH = "version_mismatch"
    SCHEMA_CHANGE = "schema_change"
    API_INCOMPATIBLE = "api_incompatible"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    APPROVAL_PENDING = "approval_pending"


# --- Models ---


class DeployDependencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deploy_id: str = ""
    dependency_type: DependencyType = DependencyType.SERVICE
    dependency_status: DependencyStatus = DependencyStatus.PENDING
    blocking_reason: BlockingReason = BlockingReason.VERSION_MISMATCH
    wait_time_minutes: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyChain(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deploy_id: str = ""
    dependency_type: DependencyType = DependencyType.SERVICE
    chain_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeployDependencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_chains: int = 0
    blocked_count: int = 0
    avg_wait_time_minutes: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_reason: dict[str, int] = Field(default_factory=dict)
    top_blocked: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeployDependencyTracker:
    """Track deployment dependencies, detect circular deps, analyze blocking chains."""

    def __init__(
        self,
        max_records: int = 200000,
        max_wait_time_minutes: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._max_wait_time_minutes = max_wait_time_minutes
        self._records: list[DeployDependencyRecord] = []
        self._chains: list[DependencyChain] = []
        logger.info(
            "deploy_dependency_tracker.initialized",
            max_records=max_records,
            max_wait_time_minutes=max_wait_time_minutes,
        )

    # -- record / get / list ------------------------------------------------

    def record_dependency(
        self,
        deploy_id: str,
        dependency_type: DependencyType = DependencyType.SERVICE,
        dependency_status: DependencyStatus = DependencyStatus.PENDING,
        blocking_reason: BlockingReason = BlockingReason.VERSION_MISMATCH,
        wait_time_minutes: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DeployDependencyRecord:
        record = DeployDependencyRecord(
            deploy_id=deploy_id,
            dependency_type=dependency_type,
            dependency_status=dependency_status,
            blocking_reason=blocking_reason,
            wait_time_minutes=wait_time_minutes,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deploy_dependency_tracker.dependency_recorded",
            record_id=record.id,
            deploy_id=deploy_id,
            dependency_type=dependency_type.value,
            dependency_status=dependency_status.value,
        )
        return record

    def get_dependency(self, record_id: str) -> DeployDependencyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_dependencies(
        self,
        dependency_type: DependencyType | None = None,
        dependency_status: DependencyStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DeployDependencyRecord]:
        results = list(self._records)
        if dependency_type is not None:
            results = [r for r in results if r.dependency_type == dependency_type]
        if dependency_status is not None:
            results = [r for r in results if r.dependency_status == dependency_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_chain(
        self,
        deploy_id: str,
        dependency_type: DependencyType = DependencyType.SERVICE,
        chain_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DependencyChain:
        chain = DependencyChain(
            deploy_id=deploy_id,
            dependency_type=dependency_type,
            chain_score=chain_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._chains.append(chain)
        if len(self._chains) > self._max_records:
            self._chains = self._chains[-self._max_records :]
        logger.info(
            "deploy_dependency_tracker.chain_added",
            deploy_id=deploy_id,
            dependency_type=dependency_type.value,
            chain_score=chain_score,
        )
        return chain

    # -- domain operations --------------------------------------------------

    def analyze_dependency_distribution(self) -> dict[str, Any]:
        """Group by dependency_type; return count and avg wait time."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.dependency_type.value
            type_data.setdefault(key, []).append(r.wait_time_minutes)
        result: dict[str, Any] = {}
        for dtype, waits in type_data.items():
            result[dtype] = {
                "count": len(waits),
                "avg_wait_time": round(sum(waits) / len(waits), 2),
            }
        return result

    def identify_blocked_deployments(self) -> list[dict[str, Any]]:
        """Return dependencies where status is BLOCKED or FAILED."""
        blocked_statuses = {
            DependencyStatus.BLOCKED,
            DependencyStatus.FAILED,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.dependency_status in blocked_statuses:
                results.append(
                    {
                        "record_id": r.id,
                        "deploy_id": r.deploy_id,
                        "dependency_status": r.dependency_status.value,
                        "dependency_type": r.dependency_type.value,
                        "blocking_reason": r.blocking_reason.value,
                        "wait_time_minutes": r.wait_time_minutes,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["wait_time_minutes"], reverse=True)
        return results

    def rank_by_wait_time(self) -> list[dict[str, Any]]:
        """Group by service, avg wait_time_minutes, sort desc."""
        svc_waits: dict[str, list[float]] = {}
        for r in self._records:
            svc_waits.setdefault(r.service, []).append(r.wait_time_minutes)
        results: list[dict[str, Any]] = []
        for svc, waits in svc_waits.items():
            results.append(
                {
                    "service": svc,
                    "avg_wait_time": round(sum(waits) / len(waits), 2),
                    "dependency_count": len(waits),
                }
            )
        results.sort(key=lambda x: x["avg_wait_time"], reverse=True)
        return results

    def detect_dependency_trends(self) -> dict[str, Any]:
        """Split-half comparison on chain_score; delta threshold 5.0."""
        if len(self._chains) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [c.chain_score for c in self._chains]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DeployDependencyReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_reason: dict[str, int] = {}
        for r in self._records:
            by_type[r.dependency_type.value] = by_type.get(r.dependency_type.value, 0) + 1
            by_status[r.dependency_status.value] = by_status.get(r.dependency_status.value, 0) + 1
            by_reason[r.blocking_reason.value] = by_reason.get(r.blocking_reason.value, 0) + 1
        blocked_count = sum(
            1
            for r in self._records
            if r.dependency_status in {DependencyStatus.BLOCKED, DependencyStatus.FAILED}
        )
        avg_wait = (
            round(
                sum(r.wait_time_minutes for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        blocked = self.identify_blocked_deployments()
        top_blocked = [b["deploy_id"] for b in blocked]
        recs: list[str] = []
        if blocked:
            recs.append(f"{len(blocked)} blocked deployment(s) detected — review dependency chains")
        over_wait = sum(
            1 for r in self._records if r.wait_time_minutes > self._max_wait_time_minutes
        )
        if over_wait > 0:
            recs.append(
                f"{over_wait} deployment(s) exceeded wait threshold"
                f" ({self._max_wait_time_minutes} min)"
            )
        if not recs:
            recs.append("Deployment dependency levels are acceptable")
        return DeployDependencyReport(
            total_records=len(self._records),
            total_chains=len(self._chains),
            blocked_count=blocked_count,
            avg_wait_time_minutes=avg_wait,
            by_type=by_type,
            by_status=by_status,
            by_reason=by_reason,
            top_blocked=top_blocked,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._chains.clear()
        logger.info("deploy_dependency_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dependency_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_chains": len(self._chains),
            "max_wait_time_minutes": self._max_wait_time_minutes,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_deploys": len({r.deploy_id for r in self._records}),
        }
