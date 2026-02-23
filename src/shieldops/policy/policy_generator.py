"""Policy-as-Code generator for OPA Rego policies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────────────


class PolicyCategory(StrEnum):
    """Category of a policy requirement."""

    SECURITY = "security"
    COMPLIANCE = "compliance"
    COST = "cost"
    OPERATIONAL = "operational"
    CUSTOM = "custom"


class PolicySeverity(StrEnum):
    """Severity level of a policy violation."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ── Models ───────────────────────────────────────────────────────────────────


class PolicyRequirement(BaseModel):
    """High-level requirement for policy generation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    category: PolicyCategory = PolicyCategory.CUSTOM
    severity: PolicySeverity = PolicySeverity.WARNING
    conditions: list[str] = Field(default_factory=list)
    created_by: str = ""
    created_at: float = Field(default_factory=time.time)


class GeneratedPolicy(BaseModel):
    """A generated OPA Rego policy."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requirement_id: str = ""
    name: str = ""
    rego_code: str = ""
    category: PolicyCategory = PolicyCategory.CUSTOM
    severity: PolicySeverity = PolicySeverity.WARNING
    version: int = 1
    is_active: bool = False
    validated: bool = False
    created_at: float = Field(default_factory=time.time)
    updated_at: float | None = None


# ── Engine ───────────────────────────────────────────────────────────────────


class PolicyCodeGenerator:
    """Generates OPA Rego policies from requirements."""

    def __init__(
        self,
        max_requirements: int = 1000,
        max_policies: int = 5000,
    ) -> None:
        self.max_requirements = max_requirements
        self.max_policies = max_policies

        self._requirements: dict[str, PolicyRequirement] = {}
        self._policies: dict[str, GeneratedPolicy] = {}

        logger.info(
            "policy_generator.init",
            max_requirements=max_requirements,
            max_policies=max_policies,
        )

    # ── Rego generation helpers ──────────────────────────────────────

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert a name to a valid Rego identifier."""
        return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")

    def _generate_rego(self, name: str, requirement: PolicyRequirement) -> str:
        """Build a Rego policy stub from a requirement."""
        pkg = self._sanitize_name(name)
        lines = [
            f"package shieldops.{pkg}",
            "",
            "# Auto-generated policy",
            f"# Category: {requirement.category.value}",
            f"# Severity: {requirement.severity.value}",
            f"# Description: {requirement.description[:80]}",
            "",
            "default allow := false",
            "",
        ]

        if requirement.conditions:
            for i, condition in enumerate(requirement.conditions):
                safe = self._sanitize_name(
                    condition.split()[0] if condition.split() else f"rule_{i}"
                )
                lines.append(f"# Condition: {condition}")
                lines.append(f"{safe} {{")
                lines.append(f"    input.{safe} == true")
                lines.append("}")
                lines.append("")

            # Combine into allow rule
            lines.append("allow {")
            for i, condition in enumerate(requirement.conditions):
                safe = self._sanitize_name(
                    condition.split()[0] if condition.split() else f"rule_{i}"
                )
                lines.append(f"    {safe}")
            lines.append("}")
        else:
            lines.append("allow {")
            lines.append("    input.authorized == true")
            lines.append("}")

        return "\n".join(lines)

    # ── Requirements ─────────────────────────────────────────────────

    def create_requirement(
        self,
        description: str,
        category: PolicyCategory,
        **kw: Any,
    ) -> PolicyRequirement:
        """Create a new policy requirement."""
        if len(self._requirements) >= self.max_requirements:
            oldest = next(iter(self._requirements))
            del self._requirements[oldest]

        req = PolicyRequirement(
            description=description,
            category=category,
            **kw,
        )
        self._requirements[req.id] = req
        logger.info(
            "policy_generator.create_requirement",
            requirement_id=req.id,
            category=category.value,
        )
        return req

    def get_requirement(self, requirement_id: str) -> PolicyRequirement | None:
        """Get a requirement by ID."""
        return self._requirements.get(requirement_id)

    def list_requirements(self, category: PolicyCategory | None = None) -> list[PolicyRequirement]:
        """List requirements with optional category filter."""
        results = list(self._requirements.values())
        if category is not None:
            results = [r for r in results if r.category == category]
        return results

    # ── Policy generation ────────────────────────────────────────────

    def generate_policy(self, requirement_id: str, name: str) -> GeneratedPolicy:
        """Generate a Rego policy from a requirement."""
        req = self._requirements.get(requirement_id)
        if req is None:
            raise ValueError(f"Requirement not found: {requirement_id}")

        if len(self._policies) >= self.max_policies:
            oldest = next(iter(self._policies))
            del self._policies[oldest]

        rego_code = self._generate_rego(name, req)

        policy = GeneratedPolicy(
            requirement_id=requirement_id,
            name=name,
            rego_code=rego_code,
            category=req.category,
            severity=req.severity,
        )
        self._policies[policy.id] = policy
        logger.info(
            "policy_generator.generate",
            policy_id=policy.id,
            name=name,
        )
        return policy

    def validate_policy(self, policy_id: str) -> dict[str, Any]:
        """Basic syntax validation of a generated policy."""
        policy = self._policies.get(policy_id)
        if policy is None:
            return {"valid": False, "errors": ["Policy not found"]}

        errors: list[str] = []
        code = policy.rego_code

        if "package " not in code:
            errors.append("Missing 'package' declaration")

        has_rule = "allow" in code or "deny" in code or "violation" in code
        if not has_rule:
            errors.append("No rule found (allow, deny, or violation)")

        if "{" not in code or "}" not in code:
            errors.append("Missing rule body (braces)")

        valid = len(errors) == 0
        if valid:
            policy.validated = True

        logger.info(
            "policy_generator.validate",
            policy_id=policy_id,
            valid=valid,
            error_count=len(errors),
        )
        return {"valid": valid, "errors": errors}

    # ── Policy lifecycle ─────────────────────────────────────────────

    def activate_policy(self, policy_id: str) -> GeneratedPolicy | None:
        """Activate a policy for enforcement."""
        policy = self._policies.get(policy_id)
        if policy is None:
            return None
        policy.is_active = True
        policy.updated_at = time.time()
        logger.info("policy_generator.activate", policy_id=policy_id)
        return policy

    def deactivate_policy(self, policy_id: str) -> GeneratedPolicy | None:
        """Deactivate a policy."""
        policy = self._policies.get(policy_id)
        if policy is None:
            return None
        policy.is_active = False
        policy.updated_at = time.time()
        logger.info("policy_generator.deactivate", policy_id=policy_id)
        return policy

    def update_policy(self, policy_id: str, rego_code: str) -> GeneratedPolicy | None:
        """Update policy Rego code, incrementing version."""
        policy = self._policies.get(policy_id)
        if policy is None:
            return None
        policy.rego_code = rego_code
        policy.version += 1
        policy.validated = False
        policy.updated_at = time.time()
        logger.info(
            "policy_generator.update",
            policy_id=policy_id,
            version=policy.version,
        )
        return policy

    def get_policy(self, policy_id: str) -> GeneratedPolicy | None:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    def list_policies(
        self,
        category: PolicyCategory | None = None,
        active_only: bool = False,
    ) -> list[GeneratedPolicy]:
        """List policies with optional filters."""
        results = list(self._policies.values())
        if category is not None:
            results = [p for p in results if p.category == category]
        if active_only:
            results = [p for p in results if p.is_active]
        return results

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        policies = list(self._policies.values())
        return {
            "total_requirements": len(self._requirements),
            "total_policies": len(self._policies),
            "active_policies": sum(1 for p in policies if p.is_active),
            "validated_policies": sum(1 for p in policies if p.validated),
            "policies_by_category": {
                c.value: sum(1 for p in policies if p.category == c) for c in PolicyCategory
            },
            "policies_by_severity": {
                s.value: sum(1 for p in policies if p.severity == s) for s in PolicySeverity
            },
        }
