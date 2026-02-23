"""Error budget tracking with burn-rate alerting and deployment gating.

Tracks error budgets derived from SLO targets, computes remaining budget
fractions, and gates deployments when budgets are exhausted or critically low.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class BudgetStatus(enum.StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


class BudgetPeriod(enum.StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# -- Models --------------------------------------------------------------------


class ErrorBudgetPolicy(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    slo_target: float
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    warning_threshold: float = 0.3
    critical_threshold: float = 0.1
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class BudgetConsumption(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    policy_id: str
    error_minutes: float
    total_minutes: float
    description: str = ""
    recorded_at: float = Field(default_factory=time.time)


class BudgetAlert(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    policy_id: str
    service: str
    status: BudgetStatus
    remaining_fraction: float
    message: str
    created_at: float = Field(default_factory=time.time)


# -- Tracker -------------------------------------------------------------------


class ErrorBudgetTracker:
    """Track error budgets and gate deployments based on remaining budget.

    Parameters
    ----------
    warning_threshold:
        Default remaining budget fraction below which a warning is raised.
    critical_threshold:
        Default remaining budget fraction below which a critical alert is raised.
    """

    def __init__(
        self,
        warning_threshold: float = 0.3,
        critical_threshold: float = 0.1,
    ) -> None:
        self._policies: dict[str, ErrorBudgetPolicy] = {}
        self._consumptions: list[BudgetConsumption] = []
        self._alerts: list[BudgetAlert] = []
        self._default_warning = warning_threshold
        self._default_critical = critical_threshold

    def create_policy(
        self,
        service: str,
        slo_target: float,
        period: BudgetPeriod = BudgetPeriod.MONTHLY,
        warning_threshold: float | None = None,
        critical_threshold: float | None = None,
        created_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ErrorBudgetPolicy:
        policy = ErrorBudgetPolicy(
            service=service,
            slo_target=slo_target,
            period=period,
            warning_threshold=(
                warning_threshold if warning_threshold is not None else self._default_warning
            ),
            critical_threshold=(
                critical_threshold if critical_threshold is not None else self._default_critical
            ),
            created_by=created_by,
            metadata=metadata or {},
        )
        self._policies[policy.id] = policy
        logger.info("error_budget_policy_created", policy_id=policy.id, service=service)
        return policy

    def record_consumption(
        self,
        policy_id: str,
        error_minutes: float,
        total_minutes: float,
        description: str = "",
    ) -> BudgetConsumption:
        if policy_id not in self._policies:
            raise ValueError(f"Policy not found: {policy_id}")
        consumption = BudgetConsumption(
            policy_id=policy_id,
            error_minutes=error_minutes,
            total_minutes=total_minutes,
            description=description,
        )
        self._consumptions.append(consumption)
        logger.info(
            "budget_consumption_recorded",
            policy_id=policy_id,
            error_minutes=error_minutes,
        )
        return consumption

    def get_remaining_budget(self, service: str) -> dict[str, Any]:
        policy = self._find_policy_by_service(service)
        if policy is None:
            return {
                "service": service,
                "status": BudgetStatus.HEALTHY,
                "remaining_fraction": 1.0,
                "error": "No policy found for service",
            }

        total_minutes = 0.0
        error_minutes = 0.0
        for c in self._consumptions:
            if c.policy_id == policy.id:
                total_minutes += c.total_minutes
                error_minutes += c.error_minutes

        if total_minutes == 0.0:
            return {
                "service": service,
                "policy_id": policy.id,
                "slo_target": policy.slo_target,
                "total_error_budget": 0.0,
                "consumed": 0.0,
                "remaining_fraction": 1.0,
                "status": BudgetStatus.HEALTHY,
            }

        total_error_budget = (1 - policy.slo_target) * total_minutes
        consumed = error_minutes
        if total_error_budget > 0:
            remaining_fraction = max(0.0, (total_error_budget - consumed) / total_error_budget)
        else:
            remaining_fraction = 0.0

        status = self._compute_status(remaining_fraction, policy)

        # Generate alert if not healthy
        if status != BudgetStatus.HEALTHY:
            alert = BudgetAlert(
                policy_id=policy.id,
                service=service,
                status=status,
                remaining_fraction=remaining_fraction,
                message=f"Error budget {status}: {remaining_fraction:.1%} remaining for {service}",
            )
            self._alerts.append(alert)

        return {
            "service": service,
            "policy_id": policy.id,
            "slo_target": policy.slo_target,
            "total_error_budget": total_error_budget,
            "consumed": consumed,
            "remaining_fraction": remaining_fraction,
            "status": status,
        }

    def check_deployment_gate(self, service: str) -> dict[str, Any]:
        budget = self.get_remaining_budget(service)
        status = budget.get("status", BudgetStatus.HEALTHY)
        remaining = budget.get("remaining_fraction", 1.0)

        if status == BudgetStatus.EXHAUSTED:
            allowed = False
            reason = f"Error budget exhausted for {service} ({remaining:.1%} remaining)"
        elif status == BudgetStatus.CRITICAL:
            allowed = False
            reason = f"Error budget critically low for {service} ({remaining:.1%} remaining)"
        else:
            allowed = True
            reason = f"Error budget sufficient for {service} ({remaining:.1%} remaining)"

        return {
            "allowed": allowed,
            "remaining_fraction": remaining,
            "status": status,
            "reason": reason,
        }

    def list_policies(self) -> list[ErrorBudgetPolicy]:
        return list(self._policies.values())

    def get_policy(self, policy_id: str) -> ErrorBudgetPolicy | None:
        return self._policies.get(policy_id)

    def delete_policy(self, policy_id: str) -> bool:
        return self._policies.pop(policy_id, None) is not None

    def get_stats(self) -> dict[str, Any]:
        services_with_budget: set[str] = set()
        for policy in self._policies.values():
            services_with_budget.add(policy.service)
        return {
            "total_policies": len(self._policies),
            "total_consumptions": len(self._consumptions),
            "total_alerts": len(self._alerts),
            "services_tracked": len(services_with_budget),
        }

    def _find_policy_by_service(self, service: str) -> ErrorBudgetPolicy | None:
        for policy in self._policies.values():
            if policy.service == service:
                return policy
        return None

    def _compute_status(
        self,
        remaining_fraction: float,
        policy: ErrorBudgetPolicy,
    ) -> BudgetStatus:
        if remaining_fraction <= 0.0:
            return BudgetStatus.EXHAUSTED
        if remaining_fraction <= policy.critical_threshold:
            return BudgetStatus.CRITICAL
        if remaining_fraction <= policy.warning_threshold:
            return BudgetStatus.WARNING
        return BudgetStatus.HEALTHY
