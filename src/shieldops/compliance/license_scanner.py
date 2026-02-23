"""Dependency License Compliance Scanner — license classification, policy enforcement."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LicenseCategory(StrEnum):
    PERMISSIVE = "permissive"
    WEAK_COPYLEFT = "weak_copyleft"
    STRONG_COPYLEFT = "strong_copyleft"
    PROPRIETARY = "proprietary"
    UNKNOWN = "unknown"


class LicenseRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyAction(StrEnum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    REVIEW = "review"


# --- Models ---


class DependencyLicense(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    version: str = ""
    spdx_id: str = ""
    category: LicenseCategory = LicenseCategory.UNKNOWN
    risk: LicenseRisk = LicenseRisk.LOW
    project: str = ""
    detected_at: float = Field(default_factory=time.time)


class LicensePolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    spdx_pattern: str = ""
    category: LicenseCategory | None = None
    action: PolicyAction = PolicyAction.ALLOW
    created_at: float = Field(default_factory=time.time)


class LicenseViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dependency_id: str
    policy_id: str
    dependency_name: str = ""
    spdx_id: str = ""
    action: PolicyAction = PolicyAction.BLOCK
    project: str = ""
    detected_at: float = Field(default_factory=time.time)


# --- License classification map ---

_LICENSE_MAP: dict[str, LicenseCategory] = {
    "MIT": LicenseCategory.PERMISSIVE,
    "Apache-2.0": LicenseCategory.PERMISSIVE,
    "BSD-2-Clause": LicenseCategory.PERMISSIVE,
    "BSD-3-Clause": LicenseCategory.PERMISSIVE,
    "ISC": LicenseCategory.PERMISSIVE,
    "LGPL-2.1": LicenseCategory.WEAK_COPYLEFT,
    "LGPL-3.0": LicenseCategory.WEAK_COPYLEFT,
    "MPL-2.0": LicenseCategory.WEAK_COPYLEFT,
    "EPL-2.0": LicenseCategory.WEAK_COPYLEFT,
    "GPL-2.0": LicenseCategory.STRONG_COPYLEFT,
    "GPL-3.0": LicenseCategory.STRONG_COPYLEFT,
    "AGPL-3.0": LicenseCategory.STRONG_COPYLEFT,
}

_RISK_MAP: dict[LicenseCategory, LicenseRisk] = {
    LicenseCategory.PERMISSIVE: LicenseRisk.LOW,
    LicenseCategory.WEAK_COPYLEFT: LicenseRisk.MEDIUM,
    LicenseCategory.STRONG_COPYLEFT: LicenseRisk.HIGH,
    LicenseCategory.PROPRIETARY: LicenseRisk.CRITICAL,
    LicenseCategory.UNKNOWN: LicenseRisk.MEDIUM,
}


# --- Engine ---


class DependencyLicenseScanner:
    """License classification, copyleft detection, policy enforcement, violation tracking."""

    def __init__(
        self,
        max_dependencies: int = 100000,
        max_violations: int = 50000,
    ) -> None:
        self._max_dependencies = max_dependencies
        self._max_violations = max_violations
        self._dependencies: dict[str, DependencyLicense] = {}
        self._policies: dict[str, LicensePolicy] = {}
        self._violations: list[LicenseViolation] = []
        logger.info(
            "license_scanner.initialized",
            max_dependencies=max_dependencies,
            max_violations=max_violations,
        )

    def register_dependency(
        self,
        name: str,
        version: str = "",
        spdx_id: str = "",
        project: str = "",
    ) -> DependencyLicense:
        category = self.classify_license(spdx_id)
        risk = _RISK_MAP.get(category, LicenseRisk.MEDIUM)
        dep = DependencyLicense(
            name=name,
            version=version,
            spdx_id=spdx_id,
            category=category,
            risk=risk,
            project=project,
        )
        self._dependencies[dep.id] = dep
        if len(self._dependencies) > self._max_dependencies:
            oldest = next(iter(self._dependencies))
            del self._dependencies[oldest]
        logger.info(
            "license_scanner.dependency_registered",
            dep_id=dep.id,
            name=name,
            spdx_id=spdx_id,
            category=category,
        )
        return dep

    def classify_license(self, spdx_id: str) -> LicenseCategory:
        return _LICENSE_MAP.get(spdx_id, LicenseCategory.UNKNOWN)

    def assess_risk(self, spdx_id: str) -> LicenseRisk:
        category = self.classify_license(spdx_id)
        return _RISK_MAP.get(category, LicenseRisk.MEDIUM)

    def create_policy(
        self,
        name: str,
        spdx_pattern: str = "",
        category: LicenseCategory | None = None,
        action: PolicyAction = PolicyAction.ALLOW,
    ) -> LicensePolicy:
        policy = LicensePolicy(
            name=name,
            spdx_pattern=spdx_pattern,
            category=category,
            action=action,
        )
        self._policies[policy.id] = policy
        logger.info("license_scanner.policy_created", policy_id=policy.id, name=name)
        return policy

    def evaluate_project(self, project: str) -> list[LicenseViolation]:
        deps = [d for d in self._dependencies.values() if d.project == project]
        violations: list[LicenseViolation] = []
        for dep in deps:
            for policy in self._policies.values():
                matched = False
                if policy.spdx_pattern and policy.spdx_pattern in dep.spdx_id:
                    matched = True
                if policy.category is not None and dep.category == policy.category:
                    matched = True
                if matched and policy.action in (PolicyAction.BLOCK, PolicyAction.WARN):
                    violation = LicenseViolation(
                        dependency_id=dep.id,
                        policy_id=policy.id,
                        dependency_name=dep.name,
                        spdx_id=dep.spdx_id,
                        action=policy.action,
                        project=project,
                    )
                    violations.append(violation)
                    self._violations.append(violation)
        if len(self._violations) > self._max_violations:
            self._violations = self._violations[-self._max_violations :]
        logger.info(
            "license_scanner.project_evaluated",
            project=project,
            violations_found=len(violations),
        )
        return violations

    def list_dependencies(
        self,
        project: str | None = None,
        category: LicenseCategory | None = None,
    ) -> list[DependencyLicense]:
        results = list(self._dependencies.values())
        if project is not None:
            results = [d for d in results if d.project == project]
        if category is not None:
            results = [d for d in results if d.category == category]
        return results

    def list_violations(
        self,
        project: str | None = None,
        action: PolicyAction | None = None,
    ) -> list[LicenseViolation]:
        results = list(self._violations)
        if project is not None:
            results = [v for v in results if v.project == project]
        if action is not None:
            results = [v for v in results if v.action == action]
        return results

    def get_policy(self, policy_id: str) -> LicensePolicy | None:
        return self._policies.get(policy_id)

    def list_policies(self) -> list[LicensePolicy]:
        return list(self._policies.values())

    def get_stats(self) -> dict[str, Any]:
        cat_counts: dict[str, int] = {}
        risk_counts: dict[str, int] = {}
        for d in self._dependencies.values():
            cat_counts[d.category] = cat_counts.get(d.category, 0) + 1
            risk_counts[d.risk] = risk_counts.get(d.risk, 0) + 1
        return {
            "total_dependencies": len(self._dependencies),
            "total_policies": len(self._policies),
            "total_violations": len(self._violations),
            "category_distribution": cat_counts,
            "risk_distribution": risk_counts,
        }
