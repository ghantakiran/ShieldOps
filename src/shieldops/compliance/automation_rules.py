"""Compliance Automation Rule Engine — auto-remediate violations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RuleAction(StrEnum):
    NOTIFY = "notify"
    AUTO_REMEDIATE = "auto_remediate"
    QUARANTINE = "quarantine"
    ESCALATE = "escalate"
    LOG_ONLY = "log_only"


class RuleStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    TESTING = "testing"


class ExecutionResult(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"


# --- Models ---


class ComplianceRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    framework: str = ""
    condition: str = ""
    action: RuleAction = RuleAction.NOTIFY
    status: RuleStatus = RuleStatus.ACTIVE
    severity: str = "medium"
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ViolationEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str
    resource_type: str = ""
    rule_id: str = ""
    description: str = ""
    severity: str = "medium"
    detected_at: float = Field(default_factory=time.time)


class RuleExecution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    violation_id: str
    action: RuleAction
    result: ExecutionResult
    details: str = ""
    executed_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceAutomationEngine:
    """Auto-remediates compliance violations with declarative rules."""

    def __init__(
        self,
        max_rules: int = 500,
        max_executions: int = 50000,
    ) -> None:
        self._max_rules = max_rules
        self._max_executions = max_executions
        self._rules: dict[str, ComplianceRule] = {}
        self._violations: list[ViolationEvent] = []
        self._executions: list[RuleExecution] = []
        logger.info(
            "compliance_automation.initialized",
            max_rules=max_rules,
            max_executions=max_executions,
        )

    def create_rule(
        self,
        name: str,
        action: RuleAction = RuleAction.NOTIFY,
        **kw: Any,
    ) -> ComplianceRule:
        """Create a compliance automation rule."""
        rule = ComplianceRule(name=name, action=action, **kw)
        self._rules[rule.id] = rule
        if len(self._rules) > self._max_rules:
            oldest = next(iter(self._rules))
            del self._rules[oldest]
        logger.info(
            "compliance_automation.rule_created",
            rule_id=rule.id,
            name=name,
            action=action,
        )
        return rule

    def update_rule(
        self,
        rule_id: str,
        **updates: Any,
    ) -> ComplianceRule | None:
        """Update a compliance rule."""
        rule = self._rules.get(rule_id)
        if rule is None:
            return None
        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        rule.updated_at = time.time()
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a compliance rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info("compliance_automation.rule_deleted", rule_id=rule_id)
            return True
        return False

    def report_violation(
        self,
        resource_id: str,
        resource_type: str = "",
        description: str = "",
        severity: str = "medium",
        **kw: Any,
    ) -> ViolationEvent:
        """Report a compliance violation."""
        violation = ViolationEvent(
            resource_id=resource_id,
            resource_type=resource_type,
            description=description,
            severity=severity,
            **kw,
        )
        self._violations.append(violation)
        logger.info(
            "compliance_automation.violation_reported",
            violation_id=violation.id,
            resource_id=resource_id,
        )
        return violation

    def evaluate_violation(
        self,
        violation_id: str,
    ) -> list[RuleExecution]:
        """Evaluate a violation against all active rules."""
        violation: ViolationEvent | None = None
        for v in self._violations:
            if v.id == violation_id:
                violation = v
                break
        if violation is None:
            return []
        executions: list[RuleExecution] = []
        for rule in self._rules.values():
            if rule.status != RuleStatus.ACTIVE:
                continue
            if rule.id and violation.rule_id and rule.id != violation.rule_id:
                continue
            result = self._execute_rule(rule, violation)
            executions.append(result)
        return executions

    def _execute_rule(
        self,
        rule: ComplianceRule,
        violation: ViolationEvent,
    ) -> RuleExecution:
        """Execute a rule against a violation."""
        if rule.status == RuleStatus.TESTING:
            result = ExecutionResult.DRY_RUN
        elif rule.action in (RuleAction.AUTO_REMEDIATE, RuleAction.QUARANTINE):
            result = ExecutionResult.SUCCESS
        else:
            result = ExecutionResult.SUCCESS
        execution = RuleExecution(
            rule_id=rule.id,
            violation_id=violation.id,
            action=rule.action,
            result=result,
            details=f"Rule '{rule.name}' executed: {rule.action}",
        )
        self._executions.append(execution)
        if len(self._executions) > self._max_executions:
            self._executions = self._executions[-self._max_executions :]
        return execution

    def list_rules(
        self,
        status: RuleStatus | None = None,
        action: RuleAction | None = None,
    ) -> list[ComplianceRule]:
        """List rules with optional filters."""
        results = list(self._rules.values())
        if status is not None:
            results = [r for r in results if r.status == status]
        if action is not None:
            results = [r for r in results if r.action == action]
        return results

    def list_executions(
        self,
        rule_id: str | None = None,
        result: ExecutionResult | None = None,
        limit: int = 100,
    ) -> list[RuleExecution]:
        """List executions with optional filters."""
        results = list(self._executions)
        if rule_id is not None:
            results = [e for e in results if e.rule_id == rule_id]
        if result is not None:
            results = [e for e in results if e.result == result]
        return results[-limit:]

    def list_violations(
        self,
        resource_type: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[ViolationEvent]:
        """List violations with optional filters."""
        results = list(self._violations)
        if resource_type is not None:
            results = [v for v in results if v.resource_type == resource_type]
        if severity is not None:
            results = [v for v in results if v.severity == severity]
        return results[-limit:]

    def get_effectiveness(self) -> dict[str, Any]:
        """Get rule effectiveness metrics."""
        rule_stats: dict[str, dict[str, int]] = {}
        for ex in self._executions:
            if ex.rule_id not in rule_stats:
                rule_stats[ex.rule_id] = {"total": 0, "success": 0}
            rule_stats[ex.rule_id]["total"] += 1
            if ex.result == ExecutionResult.SUCCESS:
                rule_stats[ex.rule_id]["success"] += 1
        effectiveness: list[dict[str, Any]] = []
        for rule_id, stats in rule_stats.items():
            rule = self._rules.get(rule_id)
            effectiveness.append(
                {
                    "rule_id": rule_id,
                    "rule_name": rule.name if rule else "unknown",
                    "total_executions": stats["total"],
                    "successful": stats["success"],
                    "success_rate": (
                        round(stats["success"] / stats["total"], 4) if stats["total"] else 0.0
                    ),
                }
            )
        return {"rules": effectiveness, "total_rules_evaluated": len(rule_stats)}

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        action_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for r in self._rules.values():
            action_counts[r.action] = action_counts.get(r.action, 0) + 1
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
        result_counts: dict[str, int] = {}
        for e in self._executions:
            result_counts[e.result] = result_counts.get(e.result, 0) + 1
        return {
            "total_rules": len(self._rules),
            "total_violations": len(self._violations),
            "total_executions": len(self._executions),
            "rule_action_distribution": action_counts,
            "rule_status_distribution": status_counts,
            "execution_result_distribution": result_counts,
        }
