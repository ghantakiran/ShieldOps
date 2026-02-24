"""Dependency Update Planner — plan safe dependency update order."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class UpdateRisk(StrEnum):
    TRIVIAL = "trivial"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    BREAKING = "breaking"


class UpdateStrategy(StrEnum):
    IMMEDIATE = "immediate"
    STAGED = "staged"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    MANUAL_REVIEW = "manual_review"


class UpdateStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# --- Models ---


class DependencyUpdate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_name: str = ""
    current_version: str = ""
    target_version: str = ""
    risk: UpdateRisk = UpdateRisk.LOW
    strategy: UpdateStrategy = UpdateStrategy.IMMEDIATE
    status: UpdateStatus = UpdateStatus.PLANNED
    dependents: list[str] = Field(default_factory=list)
    test_coverage_pct: float = 0.0
    breaking_changes: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class UpdatePlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    updates: list[str] = Field(default_factory=list)
    total_risk_score: float = 0.0
    estimated_duration_hours: float = 0.0
    execution_order: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class UpdatePlannerReport(BaseModel):
    total_updates: int = 0
    total_plans: int = 0
    avg_risk_score: float = 0.0
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    high_risk_updates: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


_RISK_SCORES: dict[UpdateRisk, float] = {
    UpdateRisk.TRIVIAL: 0.0,
    UpdateRisk.LOW: 1.0,
    UpdateRisk.MODERATE: 2.0,
    UpdateRisk.HIGH: 3.0,
    UpdateRisk.BREAKING: 4.0,
}

_DURATION_PER_STRATEGY: dict[UpdateStrategy, float] = {
    UpdateStrategy.IMMEDIATE: 0.5,
    UpdateStrategy.STAGED: 2.0,
    UpdateStrategy.CANARY: 4.0,
    UpdateStrategy.BLUE_GREEN: 3.0,
    UpdateStrategy.MANUAL_REVIEW: 8.0,
}


class DependencyUpdatePlanner:
    """Plan safe dependency update order based on graph, risk, coverage."""

    def __init__(
        self,
        max_updates: int = 100000,
        max_risk_threshold: int = 3,
    ) -> None:
        self._max_updates = max_updates
        self._max_risk_threshold = max_risk_threshold
        self._items: list[DependencyUpdate] = []
        self._plans: dict[str, UpdatePlan] = {}
        logger.info(
            "dependency_update_planner.initialized",
            max_updates=max_updates,
            max_risk_threshold=max_risk_threshold,
        )

    # -- CRUD -------------------------------------------------------

    def register_update(
        self,
        package_name: str,
        current_version: str = "",
        target_version: str = "",
        risk: UpdateRisk = UpdateRisk.LOW,
        strategy: UpdateStrategy = UpdateStrategy.IMMEDIATE,
        dependents: list[str] | None = None,
        test_coverage_pct: float = 0.0,
        breaking_changes: list[str] | None = None,
    ) -> DependencyUpdate:
        update = DependencyUpdate(
            package_name=package_name,
            current_version=current_version,
            target_version=target_version,
            risk=risk,
            strategy=strategy,
            dependents=dependents or [],
            test_coverage_pct=test_coverage_pct,
            breaking_changes=breaking_changes or [],
        )
        self._items.append(update)
        if len(self._items) > self._max_updates:
            self._items = self._items[-self._max_updates :]
        logger.info(
            "dependency_update_planner.update_registered",
            update_id=update.id,
            package_name=package_name,
            risk=risk,
        )
        return update

    def get_update(self, update_id: str) -> DependencyUpdate | None:
        for u in self._items:
            if u.id == update_id:
                return u
        return None

    def list_updates(
        self,
        risk: UpdateRisk | None = None,
        status: UpdateStatus | None = None,
        limit: int = 50,
    ) -> list[DependencyUpdate]:
        results = list(self._items)
        if risk is not None:
            results = [u for u in results if u.risk == risk]
        if status is not None:
            results = [u for u in results if u.status == status]
        return results[-limit:]

    # -- Plans ------------------------------------------------------

    def create_plan(
        self,
        name: str,
        update_ids: list[str],
    ) -> UpdatePlan:
        valid_ids: list[str] = []
        total_risk = 0.0
        total_duration = 0.0
        for uid in update_ids:
            upd = self.get_update(uid)
            if upd is not None:
                valid_ids.append(uid)
                total_risk += _RISK_SCORES.get(upd.risk, 0.0)
                total_duration += _DURATION_PER_STRATEGY.get(upd.strategy, 1.0)

        plan = UpdatePlan(
            name=name,
            updates=valid_ids,
            total_risk_score=round(total_risk, 2),
            estimated_duration_hours=round(total_duration, 2),
        )
        self._plans[plan.id] = plan
        logger.info(
            "dependency_update_planner.plan_created",
            plan_id=plan.id,
            name=name,
            update_count=len(valid_ids),
        )
        return plan

    def calculate_execution_order(self, plan_id: str) -> list[str]:
        plan = self._plans.get(plan_id)
        if plan is None:
            return []

        # Sort updates: lowest risk first, then by dependents count
        scored: list[tuple[float, int, str]] = []
        for uid in plan.updates:
            upd = self.get_update(uid)
            if upd is not None:
                risk_score = _RISK_SCORES.get(upd.risk, 0.0)
                dep_count = len(upd.dependents)
                scored.append((risk_score, dep_count, uid))

        scored.sort(key=lambda x: (x[0], x[1]))
        order = [s[2] for s in scored]
        plan.execution_order = order
        logger.info(
            "dependency_update_planner.execution_order_calculated",
            plan_id=plan_id,
            order_length=len(order),
        )
        return order

    # -- Analysis ---------------------------------------------------

    def assess_update_risk(self, update_id: str) -> dict[str, Any]:
        upd = self.get_update(update_id)
        if upd is None:
            return {
                "update_id": update_id,
                "risk_score": 0.0,
                "risk_level": UpdateRisk.TRIVIAL.value,
                "factors": [],
            }

        factors: list[str] = []
        base_score = _RISK_SCORES.get(upd.risk, 0.0)

        if upd.breaking_changes:
            factors.append(f"{len(upd.breaking_changes)} breaking change(s)")
            base_score += 1.0

        if upd.test_coverage_pct < 50.0:
            factors.append(f"Low test coverage: {upd.test_coverage_pct}%")
            base_score += 0.5

        if len(upd.dependents) > 5:
            factors.append(f"High dependent count: {len(upd.dependents)}")
            base_score += 0.5

        if base_score >= 4.0:
            level = UpdateRisk.BREAKING
        elif base_score >= 3.0:
            level = UpdateRisk.HIGH
        elif base_score >= 2.0:
            level = UpdateRisk.MODERATE
        elif base_score >= 1.0:
            level = UpdateRisk.LOW
        else:
            level = UpdateRisk.TRIVIAL

        logger.info(
            "dependency_update_planner.risk_assessed",
            update_id=update_id,
            risk_score=round(base_score, 2),
            risk_level=level,
        )
        return {
            "update_id": update_id,
            "package_name": upd.package_name,
            "risk_score": round(base_score, 2),
            "risk_level": level.value,
            "factors": factors,
        }

    def detect_breaking_chains(self) -> list[dict[str, Any]]:
        """Find updates with breaking changes that other updates depend on."""
        pkg_to_update: dict[str, DependencyUpdate] = {}
        for u in self._items:
            pkg_to_update[u.package_name] = u

        chains: list[dict[str, Any]] = []
        for u in self._items:
            if not u.breaking_changes:
                continue
            affected: list[str] = []
            for other in self._items:
                if u.package_name in other.dependents:
                    affected.append(other.package_name)
            if affected:
                chains.append(
                    {
                        "package_name": u.package_name,
                        "update_id": u.id,
                        "breaking_changes": u.breaking_changes,
                        "affected_packages": affected,
                        "chain_length": len(affected),
                    }
                )

        chains.sort(key=lambda x: x["chain_length"], reverse=True)
        logger.info(
            "dependency_update_planner.breaking_chains_detected",
            chain_count=len(chains),
        )
        return chains

    def estimate_plan_duration(self, plan_id: str) -> float:
        plan = self._plans.get(plan_id)
        if plan is None:
            return 0.0

        total = 0.0
        for uid in plan.updates:
            upd = self.get_update(uid)
            if upd is not None:
                total += _DURATION_PER_STRATEGY.get(upd.strategy, 1.0)
        plan.estimated_duration_hours = round(total, 2)
        logger.info(
            "dependency_update_planner.duration_estimated",
            plan_id=plan_id,
            hours=round(total, 2),
        )
        return round(total, 2)

    # -- Report -----------------------------------------------------

    def generate_planner_report(self) -> UpdatePlannerReport:
        total = len(self._items)
        if total == 0:
            return UpdatePlannerReport(
                recommendations=["No dependency updates registered"],
            )

        by_risk: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        by_status: dict[str, int] = {}
        risk_sum = 0.0
        high_risk: list[str] = []

        for u in self._items:
            rk = u.risk.value
            by_risk[rk] = by_risk.get(rk, 0) + 1
            sk = u.strategy.value
            by_strategy[sk] = by_strategy.get(sk, 0) + 1
            st = u.status.value
            by_status[st] = by_status.get(st, 0) + 1
            risk_sum += _RISK_SCORES.get(u.risk, 0.0)
            if u.risk in (UpdateRisk.HIGH, UpdateRisk.BREAKING):
                high_risk.append(u.package_name)

        avg_risk = round(risk_sum / total, 2)

        recs: list[str] = []
        if high_risk:
            recs.append(f"{len(high_risk)} high/breaking-risk update(s) need manual review")
        low_cov = [u for u in self._items if u.test_coverage_pct < 50.0]
        if low_cov:
            recs.append(f"{len(low_cov)} update(s) have test coverage below 50%")
        breaking_chains = self.detect_breaking_chains()
        if breaking_chains:
            recs.append(
                f"{len(breaking_chains)} breaking chain(s) detected — review execution order"
            )

        report = UpdatePlannerReport(
            total_updates=total,
            total_plans=len(self._plans),
            avg_risk_score=avg_risk,
            by_risk=by_risk,
            by_strategy=by_strategy,
            by_status=by_status,
            high_risk_updates=high_risk,
            recommendations=recs,
        )
        logger.info(
            "dependency_update_planner.report_generated",
            total_updates=total,
            total_plans=len(self._plans),
        )
        return report

    # -- Housekeeping -----------------------------------------------

    def clear_data(self) -> None:
        self._items.clear()
        self._plans.clear()
        logger.info("dependency_update_planner.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        packages = {u.package_name for u in self._items}
        risks = {u.risk.value for u in self._items}
        statuses = {u.status.value for u in self._items}
        return {
            "total_updates": len(self._items),
            "total_plans": len(self._plans),
            "unique_packages": len(packages),
            "risk_levels": sorted(risks),
            "statuses": sorted(statuses),
        }
