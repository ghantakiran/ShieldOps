"""Cost Allocation Tag Enforcer — enforce mandatory cost tags."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EnforcementMode(StrEnum):
    AUDIT = "audit"
    WARN = "warn"
    BLOCK = "block"
    AUTO_TAG = "auto_tag"


class TagRequirement(StrEnum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


class ResourceStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    REMEDIATED = "remediated"
    EXEMPTED = "exempted"


# --- Models ---


class CostTagPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    required_tags: list[str] = Field(default_factory=list)
    tag_requirements: dict[str, TagRequirement] = Field(default_factory=dict)
    enforcement_mode: EnforcementMode = EnforcementMode.AUDIT
    resource_types: list[str] = Field(default_factory=list)
    default_values: dict[str, str] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ResourceTagCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str
    resource_type: str = ""
    policy_id: str = ""
    existing_tags: dict[str, str] = Field(default_factory=dict)
    missing_tags: list[str] = Field(default_factory=list)
    status: ResourceStatus = ResourceStatus.COMPLIANT
    checked_at: float = Field(default_factory=time.time)


class EnforcementAction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    check_id: str
    resource_id: str
    action_taken: EnforcementMode
    tags_applied: dict[str, str] = Field(default_factory=dict)
    success: bool = True
    details: str = ""
    executed_at: float = Field(default_factory=time.time)


# --- Enforcer ---


class CostAllocationTagEnforcer:
    """Enforces mandatory cost tags with violation tracking and auto-tagging."""

    def __init__(
        self,
        max_policies: int = 200,
        max_checks: int = 100000,
    ) -> None:
        self._max_policies = max_policies
        self._max_checks = max_checks
        self._policies: dict[str, CostTagPolicy] = {}
        self._checks: list[ResourceTagCheck] = []
        self._actions: list[EnforcementAction] = []
        logger.info(
            "cost_tag_enforcer.initialized",
            max_policies=max_policies,
            max_checks=max_checks,
        )

    def create_policy(
        self,
        name: str,
        required_tags: list[str] | None = None,
        enforcement_mode: EnforcementMode = EnforcementMode.AUDIT,
        **kw: Any,
    ) -> CostTagPolicy:
        """Create a cost tag policy."""
        policy = CostTagPolicy(
            name=name,
            required_tags=required_tags or [],
            enforcement_mode=enforcement_mode,
            **kw,
        )
        self._policies[policy.id] = policy
        if len(self._policies) > self._max_policies:
            oldest = next(iter(self._policies))
            del self._policies[oldest]
        logger.info(
            "cost_tag_enforcer.policy_created",
            policy_id=policy.id,
            name=name,
        )
        return policy

    def update_policy(
        self,
        policy_id: str,
        **updates: Any,
    ) -> CostTagPolicy | None:
        """Update a cost tag policy."""
        policy = self._policies.get(policy_id)
        if policy is None:
            return None
        for key, value in updates.items():
            if hasattr(policy, key):
                setattr(policy, key, value)
        policy.updated_at = time.time()
        return policy

    def delete_policy(self, policy_id: str) -> bool:
        """Delete a cost tag policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            logger.info("cost_tag_enforcer.policy_deleted", policy_id=policy_id)
            return True
        return False

    def check_resource(
        self,
        resource_id: str,
        resource_type: str = "",
        existing_tags: dict[str, str] | None = None,
        policy_id: str | None = None,
    ) -> ResourceTagCheck:
        """Check a resource against tag policies."""
        tags = existing_tags or {}
        missing: list[str] = []
        target_policy_id = ""
        if policy_id and policy_id in self._policies:
            policies = [self._policies[policy_id]]
        else:
            policies = list(self._policies.values())
        for policy in policies:
            target_policy_id = policy.id
            for tag in policy.required_tags:
                if tag not in tags and tag not in missing:
                    missing.append(tag)
        status = ResourceStatus.COMPLIANT if not missing else ResourceStatus.NON_COMPLIANT
        check = ResourceTagCheck(
            resource_id=resource_id,
            resource_type=resource_type,
            policy_id=target_policy_id,
            existing_tags=tags,
            missing_tags=missing,
            status=status,
        )
        self._checks.append(check)
        if len(self._checks) > self._max_checks:
            self._checks = self._checks[-self._max_checks :]
        return check

    def enforce(self, check_id: str) -> EnforcementAction | None:
        """Enforce tag policy on a non-compliant resource."""
        check: ResourceTagCheck | None = None
        for c in self._checks:
            if c.id == check_id:
                check = c
                break
        if check is None:
            return None
        policy = self._policies.get(check.policy_id)
        if policy is None:
            return None
        tags_applied: dict[str, str] = {}
        if policy.enforcement_mode == EnforcementMode.AUTO_TAG:
            for tag in check.missing_tags:
                tags_applied[tag] = policy.default_values.get(tag, "auto-assigned")
            check.status = ResourceStatus.REMEDIATED
        action = EnforcementAction(
            check_id=check_id,
            resource_id=check.resource_id,
            action_taken=policy.enforcement_mode,
            tags_applied=tags_applied,
            success=True,
            details=f"Enforcement action: {policy.enforcement_mode}",
        )
        self._actions.append(action)
        return action

    def list_policies(self) -> list[CostTagPolicy]:
        """List all policies."""
        return list(self._policies.values())

    def list_checks(
        self,
        status: ResourceStatus | None = None,
        resource_type: str | None = None,
        limit: int = 100,
    ) -> list[ResourceTagCheck]:
        """List checks with optional filters."""
        results = list(self._checks)
        if status is not None:
            results = [c for c in results if c.status == status]
        if resource_type is not None:
            results = [c for c in results if c.resource_type == resource_type]
        return results[-limit:]

    def list_actions(self, limit: int = 100) -> list[EnforcementAction]:
        """List enforcement actions."""
        return self._actions[-limit:]

    def get_compliance_summary(self) -> dict[str, Any]:
        """Get overall compliance summary."""
        total = len(self._checks)
        compliant = sum(1 for c in self._checks if c.status == ResourceStatus.COMPLIANT)
        non_compliant = sum(1 for c in self._checks if c.status == ResourceStatus.NON_COMPLIANT)
        remediated = sum(1 for c in self._checks if c.status == ResourceStatus.REMEDIATED)
        return {
            "total_checks": total,
            "compliant": compliant,
            "non_compliant": non_compliant,
            "remediated": remediated,
            "compliance_rate": round(compliant / total, 4) if total else 0.0,
        }

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        mode_counts: dict[str, int] = {}
        for p in self._policies.values():
            mode_counts[p.enforcement_mode] = mode_counts.get(p.enforcement_mode, 0) + 1
        status_counts: dict[str, int] = {}
        for c in self._checks:
            status_counts[c.status] = status_counts.get(c.status, 0) + 1
        return {
            "total_policies": len(self._policies),
            "total_checks": len(self._checks),
            "total_actions": len(self._actions),
            "enforcement_mode_distribution": mode_counts,
            "check_status_distribution": status_counts,
        }
