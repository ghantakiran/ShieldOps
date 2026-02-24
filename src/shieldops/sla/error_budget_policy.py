"""Error Budget Policy Engine — define and enforce error budget policies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BudgetStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"
    FROZEN = "frozen"


class PolicyAction(StrEnum):
    NOTIFY = "notify"
    SLOW_DOWN = "slow_down"
    FREEZE_DEPLOYS = "freeze_deploys"
    ESCALATE = "escalate"
    AUTO_ROLLBACK = "auto_rollback"


class BudgetWindow(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# --- Models ---


class ErrorBudgetPolicy(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    service_name: str = ""
    slo_target_pct: float = 99.9
    window: BudgetWindow = BudgetWindow.MONTHLY
    remaining_budget_pct: float = 100.0
    status: BudgetStatus = BudgetStatus.HEALTHY
    actions: list[str] = Field(default_factory=list)
    consumed_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class BudgetViolation(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    policy_id: str = ""
    service_name: str = ""
    consumed_pct: float = 0.0
    threshold_pct: float = 0.0
    action_taken: str = ""
    violated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class BudgetPolicyReport(BaseModel):
    total_policies: int = 0
    total_violations: int = 0
    avg_remaining_budget: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_window: dict[str, int] = Field(default_factory=dict)
    critical_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ErrorBudgetPolicyEngine:
    """Define and enforce error budget policies with escalation."""

    def __init__(
        self,
        max_policies: int = 50000,
        warning_threshold_pct: float = 50.0,
    ) -> None:
        self._max_policies = max_policies
        self._warning_threshold_pct = warning_threshold_pct
        self._policies: list[ErrorBudgetPolicy] = []
        self._violations: list[BudgetViolation] = []
        logger.info(
            "error_budget_policy.initialized",
            max_policies=max_policies,
            warning_threshold_pct=warning_threshold_pct,
        )

    # -- CRUD --

    def create_policy(
        self,
        service_name: str,
        slo_target_pct: float = 99.9,
        window: BudgetWindow = BudgetWindow.MONTHLY,
    ) -> ErrorBudgetPolicy:
        policy = ErrorBudgetPolicy(
            service_name=service_name,
            slo_target_pct=slo_target_pct,
            window=window,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_policies:
            self._policies = self._policies[-self._max_policies :]
        logger.info(
            "error_budget_policy.created",
            policy_id=policy.id,
            service=service_name,
        )
        return policy

    def get_policy(self, policy_id: str) -> ErrorBudgetPolicy | None:
        for p in self._policies:
            if p.id == policy_id:
                return p
        return None

    def list_policies(
        self,
        service_name: str | None = None,
        status: BudgetStatus | None = None,
        limit: int = 50,
    ) -> list[ErrorBudgetPolicy]:
        results = list(self._policies)
        if service_name is not None:
            results = [p for p in results if p.service_name == service_name]
        if status is not None:
            results = [p for p in results if p.status == status]
        return results[-limit:]

    # -- Domain operations --

    def consume_budget(
        self,
        policy_id: str,
        error_pct: float,
    ) -> dict[str, Any]:
        policy = self.get_policy(policy_id)
        if policy is None:
            return {"error": "policy_not_found"}
        policy.consumed_pct = min(100.0, policy.consumed_pct + error_pct)
        policy.remaining_budget_pct = max(0.0, 100.0 - policy.consumed_pct)
        self._update_status(policy)
        logger.info(
            "error_budget_policy.budget_consumed",
            policy_id=policy_id,
            consumed_pct=policy.consumed_pct,
        )
        return {
            "policy_id": policy_id,
            "consumed_pct": policy.consumed_pct,
            "remaining_pct": policy.remaining_budget_pct,
            "status": policy.status,
        }

    def evaluate_policy(self, policy_id: str) -> dict[str, Any]:
        policy = self.get_policy(policy_id)
        if policy is None:
            return {"error": "policy_not_found"}
        self._update_status(policy)
        actions = self._determine_actions(policy)
        policy.actions = [a.value for a in actions]
        for action in actions:
            self._record_violation(policy, action)
        return {
            "policy_id": policy_id,
            "status": policy.status,
            "actions": policy.actions,
            "remaining_pct": policy.remaining_budget_pct,
        }

    def trigger_action(
        self,
        policy_id: str,
        action: PolicyAction,
    ) -> dict[str, Any]:
        policy = self.get_policy(policy_id)
        if policy is None:
            return {"error": "policy_not_found"}
        self._record_violation(policy, action)
        logger.info(
            "error_budget_policy.action_triggered",
            policy_id=policy_id,
            action=action.value,
        )
        return {
            "policy_id": policy_id,
            "action": action.value,
            "triggered": True,
        }

    def calculate_burn_rate(self, policy_id: str) -> dict[str, Any]:
        policy = self.get_policy(policy_id)
        if policy is None:
            return {"error": "policy_not_found"}
        elapsed = time.time() - policy.created_at
        hours = max(elapsed / 3600.0, 0.001)
        burn_rate = round(policy.consumed_pct / hours, 4)
        budget_pct = 100.0 - policy.slo_target_pct
        hours_remaining = (
            round(policy.remaining_budget_pct / burn_rate, 2) if burn_rate > 0 else None
        )
        return {
            "policy_id": policy_id,
            "burn_rate_pct_per_hour": burn_rate,
            "budget_pct": budget_pct,
            "hours_remaining": hours_remaining,
        }

    def reset_budget(self, policy_id: str) -> dict[str, Any]:
        policy = self.get_policy(policy_id)
        if policy is None:
            return {"error": "policy_not_found"}
        policy.consumed_pct = 0.0
        policy.remaining_budget_pct = 100.0
        policy.status = BudgetStatus.HEALTHY
        policy.actions = []
        logger.info(
            "error_budget_policy.budget_reset",
            policy_id=policy_id,
        )
        return {
            "policy_id": policy_id,
            "status": policy.status,
            "remaining_pct": 100.0,
        }

    # -- Reports --

    def generate_budget_report(self) -> BudgetPolicyReport:
        by_status: dict[str, int] = {}
        by_window: dict[str, int] = {}
        critical: list[str] = []
        remaining_vals: list[float] = []
        for p in self._policies:
            by_status[p.status] = by_status.get(p.status, 0) + 1
            by_window[p.window] = by_window.get(p.window, 0) + 1
            remaining_vals.append(p.remaining_budget_pct)
            if p.status in (
                BudgetStatus.CRITICAL,
                BudgetStatus.EXHAUSTED,
            ):
                critical.append(p.service_name)
        avg_remaining = (
            round(sum(remaining_vals) / len(remaining_vals), 2) if remaining_vals else 0.0
        )
        recs: list[str] = []
        if critical:
            recs.append(f"Review {len(critical)} critical services")
        exhausted_count = by_status.get(BudgetStatus.EXHAUSTED, 0)
        if exhausted_count > 0:
            recs.append(f"Freeze deployments for {exhausted_count} exhausted budgets")
        if avg_remaining < self._warning_threshold_pct:
            recs.append("Average budget low — tighten SLOs")
        return BudgetPolicyReport(
            total_policies=len(self._policies),
            total_violations=len(self._violations),
            avg_remaining_budget=avg_remaining,
            by_status=by_status,
            by_window=by_window,
            critical_services=critical,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._policies.clear()
        self._violations.clear()
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        statuses = [p.status for p in self._policies]
        return {
            "total_policies": len(self._policies),
            "total_violations": len(self._violations),
            "healthy": sum(1 for s in statuses if s == BudgetStatus.HEALTHY),
            "warning": sum(1 for s in statuses if s == BudgetStatus.WARNING),
            "critical": sum(1 for s in statuses if s == BudgetStatus.CRITICAL),
            "exhausted": sum(1 for s in statuses if s == BudgetStatus.EXHAUSTED),
        }

    # -- Internal helpers --

    def _update_status(self, policy: ErrorBudgetPolicy) -> None:
        consumed = policy.consumed_pct
        if consumed >= 100.0:
            policy.status = BudgetStatus.EXHAUSTED
        elif consumed >= 80.0:
            policy.status = BudgetStatus.CRITICAL
        elif consumed >= self._warning_threshold_pct:
            policy.status = BudgetStatus.WARNING
        else:
            policy.status = BudgetStatus.HEALTHY

    def _determine_actions(self, policy: ErrorBudgetPolicy) -> list[PolicyAction]:
        actions: list[PolicyAction] = []
        if policy.status == BudgetStatus.EXHAUSTED:
            actions = [
                PolicyAction.FREEZE_DEPLOYS,
                PolicyAction.ESCALATE,
                PolicyAction.AUTO_ROLLBACK,
            ]
        elif policy.status == BudgetStatus.CRITICAL:
            actions = [
                PolicyAction.SLOW_DOWN,
                PolicyAction.ESCALATE,
            ]
        elif policy.status == BudgetStatus.WARNING:
            actions = [PolicyAction.NOTIFY]
        return actions

    def _record_violation(
        self,
        policy: ErrorBudgetPolicy,
        action: PolicyAction,
    ) -> None:
        violation = BudgetViolation(
            policy_id=policy.id,
            service_name=policy.service_name,
            consumed_pct=policy.consumed_pct,
            threshold_pct=self._warning_threshold_pct,
            action_taken=action.value,
        )
        self._violations.append(violation)
