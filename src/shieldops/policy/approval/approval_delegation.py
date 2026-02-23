"""Approval Delegation Engine — delegates approval authority by rules."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DelegationReason(StrEnum):
    VACATION = "vacation"
    EXPERTISE = "expertise"
    WORKLOAD = "workload"
    ESCALATION = "escalation"
    SCHEDULED = "scheduled"


class DelegationStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DelegationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    delegator: str
    delegate: str
    reason: DelegationReason
    scope: list[str] = Field(default_factory=list)
    starts_at: float = Field(default_factory=time.time)
    expires_at: float = 0.0
    status: DelegationStatus = DelegationStatus.ACTIVE
    created_at: float = Field(default_factory=time.time)


class DelegationAudit(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    action: str
    original_approver: str
    delegated_to: str
    resource_id: str = ""
    timestamp: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ApprovalDelegationEngine:
    """Delegates approval authority based on expertise and availability."""

    def __init__(
        self,
        max_rules: int = 1000,
        max_audit: int = 50000,
    ) -> None:
        self.max_rules = max_rules
        self.max_audit = max_audit
        self._rules: dict[str, DelegationRule] = {}
        self._audit: list[DelegationAudit] = []
        logger.info(
            "approval_delegation_engine.initialized",
            max_rules=max_rules,
            max_audit=max_audit,
        )

    def create_delegation(
        self,
        delegator: str,
        delegate: str,
        reason: DelegationReason | str,
        scope: list[str] | None = None,
        starts_at: float | None = None,
        expires_at: float | None = None,
    ) -> DelegationRule:
        """Create a new delegation rule."""
        if len(self._rules) >= self.max_rules:
            oldest_key = next(iter(self._rules))
            del self._rules[oldest_key]
        now = time.time()
        rule = DelegationRule(
            delegator=delegator,
            delegate=delegate,
            reason=DelegationReason(reason),
            scope=scope or [],
            starts_at=starts_at if starts_at is not None else now,
            expires_at=expires_at if expires_at is not None else 0.0,
        )
        self._rules[rule.id] = rule
        logger.info(
            "approval_delegation_engine.delegation_created",
            rule_id=rule.id,
            delegator=delegator,
            delegate=delegate,
            reason=str(reason),
        )
        return rule

    def _is_rule_active(self, rule: DelegationRule) -> bool:
        """Check if a rule is currently active (not expired/revoked)."""
        if rule.status == DelegationStatus.REVOKED:
            return False
        if rule.status == DelegationStatus.EXPIRED:
            return False
        now = time.time()
        if now < rule.starts_at:
            return False
        if rule.expires_at > 0 and now > rule.expires_at:
            rule.status = DelegationStatus.EXPIRED
            return False
        return True

    def find_delegate(
        self,
        approver: str,
        scope_item: str = "",
    ) -> str | None:
        """Find an active delegate for an approver matching scope."""
        for rule in self._rules.values():
            if rule.delegator != approver:
                continue
            if not self._is_rule_active(rule):
                continue
            # If rule has a non-empty scope, scope_item must match
            if rule.scope and scope_item and scope_item not in rule.scope:
                continue
            # If rule has scope but no scope_item given, still match
            return rule.delegate
        return None

    def record_delegation_use(
        self,
        rule_id: str,
        resource_id: str = "",
    ) -> DelegationAudit:
        """Record that a delegation rule was exercised."""
        rule = self._rules.get(rule_id)
        action = "delegation_used"
        original = rule.delegator if rule else "unknown"
        delegated_to = rule.delegate if rule else "unknown"
        audit = DelegationAudit(
            rule_id=rule_id,
            action=action,
            original_approver=original,
            delegated_to=delegated_to,
            resource_id=resource_id,
        )
        self._audit.append(audit)
        if len(self._audit) > self.max_audit:
            self._audit = self._audit[-self.max_audit :]
        logger.info(
            "approval_delegation_engine.delegation_used",
            audit_id=audit.id,
            rule_id=rule_id,
            resource_id=resource_id,
        )
        return audit

    def revoke_delegation(self, rule_id: str) -> DelegationRule | None:
        """Revoke a delegation rule."""
        rule = self._rules.get(rule_id)
        if rule is None:
            return None
        rule.status = DelegationStatus.REVOKED
        logger.info(
            "approval_delegation_engine.delegation_revoked",
            rule_id=rule_id,
        )
        return rule

    def get_active_delegations(
        self,
        user: str | None = None,
    ) -> list[DelegationRule]:
        """Return active delegation rules, optionally for a user."""
        results: list[DelegationRule] = []
        for rule in self._rules.values():
            if not self._is_rule_active(rule):
                continue
            if user is not None and rule.delegator != user and rule.delegate != user:
                continue
            results.append(rule)
        return results

    def get_rule(self, rule_id: str) -> DelegationRule | None:
        """Return a delegation rule by ID."""
        return self._rules.get(rule_id)

    def list_rules(
        self,
        delegator: str | None = None,
        delegate: str | None = None,
    ) -> list[DelegationRule]:
        """List delegation rules with optional filters."""
        results = list(self._rules.values())
        if delegator is not None:
            results = [r for r in results if r.delegator == delegator]
        if delegate is not None:
            results = [r for r in results if r.delegate == delegate]
        return results

    def get_audit_log(
        self,
        rule_id: str | None = None,
        limit: int = 100,
    ) -> list[DelegationAudit]:
        """Return audit entries, optionally filtered by rule."""
        results = list(self._audit)
        if rule_id is not None:
            results = [a for a in results if a.rule_id == rule_id]
        return results[-limit:]

    def cleanup_expired(self) -> int:
        """Mark expired rules and return the count."""
        now = time.time()
        count = 0
        for rule in self._rules.values():
            if rule.status != DelegationStatus.ACTIVE:
                continue
            if rule.expires_at > 0 and now > rule.expires_at:
                rule.status = DelegationStatus.EXPIRED
                count += 1
        logger.info(
            "approval_delegation_engine.cleanup_expired",
            expired_count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        rules = list(self._rules.values())
        status_dist: dict[str, int] = {}
        reason_dist: dict[str, int] = {}
        for r in rules:
            status_dist[r.status] = status_dist.get(r.status, 0) + 1
            reason_dist[r.reason] = reason_dist.get(r.reason, 0) + 1
        active = sum(1 for r in rules if self._is_rule_active(r))
        return {
            "total_rules": len(rules),
            "active_rules": active,
            "total_audit_entries": len(self._audit),
            "status_distribution": status_dist,
            "reason_distribution": reason_dist,
        }
