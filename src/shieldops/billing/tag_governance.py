"""Resource Tag Governance Engine — tag policy enforcement, auto-tagging, compliance scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TagPolicyAction(StrEnum):
    ENFORCE = "enforce"
    WARN = "warn"
    AUDIT = "audit"
    AUTO_TAG = "auto_tag"


class ComplianceLevel(StrEnum):
    FULLY_COMPLIANT = "fully_compliant"
    MOSTLY_COMPLIANT = "mostly_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"


class TagSource(StrEnum):
    MANUAL = "manual"
    AUTO_TAGGED = "auto_tagged"
    INHERITED = "inherited"
    POLICY_DEFAULT = "policy_default"


# --- Models ---


class TagPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    required_tags: list[str] = Field(default_factory=list)
    action: TagPolicyAction = TagPolicyAction.ENFORCE
    default_values: dict[str, str] = Field(default_factory=dict)
    resource_types: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class ResourceTagReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_type: str = ""
    existing_tags: dict[str, str] = Field(default_factory=dict)
    missing_tags: list[str] = Field(default_factory=list)
    compliance: ComplianceLevel = ComplianceLevel.NON_COMPLIANT
    auto_tagged: dict[str, str] = Field(default_factory=dict)
    evaluated_at: float = Field(default_factory=time.time)


class TagComplianceScore(BaseModel):
    total_resources: int = 0
    compliant_resources: int = 0
    score_pct: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    most_missing_tags: list[dict[str, Any]] = Field(default_factory=list)


# --- Engine ---


class ResourceTagGovernanceEngine:
    """Mandatory tag policy enforcement, auto-tagging rules, compliance scoring."""

    def __init__(
        self,
        max_policies: int = 5000,
        max_reports: int = 100000,
    ) -> None:
        self._max_policies = max_policies
        self._max_reports = max_reports
        self._policies: list[TagPolicy] = []
        self._reports: list[ResourceTagReport] = []
        logger.info(
            "tag_governance.initialized",
            max_policies=max_policies,
            max_reports=max_reports,
        )

    def create_policy(
        self,
        name: str,
        required_tags: list[str] | None = None,
        action: TagPolicyAction = TagPolicyAction.ENFORCE,
        default_values: dict[str, str] | None = None,
        resource_types: list[str] | None = None,
    ) -> TagPolicy:
        policy = TagPolicy(
            name=name,
            required_tags=required_tags or [],
            action=action,
            default_values=default_values or {},
            resource_types=resource_types or [],
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_policies:
            self._policies = self._policies[-self._max_policies :]
        logger.info("tag_governance.policy_created", policy_id=policy.id, name=name)
        return policy

    def get_policy(self, policy_id: str) -> TagPolicy | None:
        for p in self._policies:
            if p.id == policy_id:
                return p
        return None

    def list_policies(self, limit: int = 100) -> list[TagPolicy]:
        return self._policies[-limit:]

    def evaluate_resource(
        self,
        resource_id: str,
        resource_type: str = "",
        existing_tags: dict[str, str] | None = None,
    ) -> ResourceTagReport:
        tags = existing_tags or {}
        all_missing: list[str] = []
        auto_tagged: dict[str, str] = {}
        for policy in self._policies:
            if policy.resource_types and resource_type not in policy.resource_types:
                continue
            for tag in policy.required_tags:
                if tag not in tags:
                    if policy.action == TagPolicyAction.AUTO_TAG and tag in policy.default_values:
                        auto_tagged[tag] = policy.default_values[tag]
                    else:
                        all_missing.append(tag)
        # Determine compliance
        total_required = len(all_missing) + len(auto_tagged) + len(tags)
        if total_required == 0 or not all_missing and not auto_tagged:
            compliance = ComplianceLevel.FULLY_COMPLIANT
        elif not all_missing:
            compliance = ComplianceLevel.MOSTLY_COMPLIANT
        elif len(all_missing) <= 2:
            compliance = ComplianceLevel.PARTIALLY_COMPLIANT
        else:
            compliance = ComplianceLevel.NON_COMPLIANT

        report = ResourceTagReport(
            resource_id=resource_id,
            resource_type=resource_type,
            existing_tags=tags,
            missing_tags=all_missing,
            compliance=compliance,
            auto_tagged=auto_tagged,
        )
        self._reports.append(report)
        if len(self._reports) > self._max_reports:
            self._reports = self._reports[-self._max_reports :]
        return report

    def evaluate_bulk(
        self,
        resources: list[dict[str, Any]],
    ) -> list[ResourceTagReport]:
        reports: list[ResourceTagReport] = []
        for res in resources:
            report = self.evaluate_resource(
                resource_id=res.get("resource_id", ""),
                resource_type=res.get("resource_type", ""),
                existing_tags=res.get("tags", {}),
            )
            reports.append(report)
        return reports

    def auto_tag_resource(
        self,
        resource_id: str,
        resource_type: str = "",
        existing_tags: dict[str, str] | None = None,
    ) -> dict[str, str]:
        tags = existing_tags or {}
        applied: dict[str, str] = {}
        for policy in self._policies:
            if policy.action != TagPolicyAction.AUTO_TAG:
                continue
            if policy.resource_types and resource_type not in policy.resource_types:
                continue
            for tag in policy.required_tags:
                if tag not in tags and tag in policy.default_values:
                    applied[tag] = policy.default_values[tag]
        return applied

    def get_compliance_score(self) -> TagComplianceScore:
        if not self._reports:
            return TagComplianceScore()
        level_counts: dict[str, int] = {}
        compliant = 0
        missing_tag_counts: dict[str, int] = {}
        for r in self._reports:
            level_counts[r.compliance] = level_counts.get(r.compliance, 0) + 1
            if r.compliance == ComplianceLevel.FULLY_COMPLIANT:
                compliant += 1
            for tag in r.missing_tags:
                missing_tag_counts[tag] = missing_tag_counts.get(tag, 0) + 1
        total = len(self._reports)
        top_missing = sorted(missing_tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        return TagComplianceScore(
            total_resources=total,
            compliant_resources=compliant,
            score_pct=round(compliant / total * 100, 1) if total > 0 else 0.0,
            by_level=level_counts,
            most_missing_tags=[{"tag": t, "count": c} for t, c in top_missing],
        )

    def get_untagged_resources(self, limit: int = 50) -> list[dict[str, Any]]:
        untagged = [r for r in self._reports if r.compliance == ComplianceLevel.NON_COMPLIANT]
        return [
            {
                "resource_id": r.resource_id,
                "resource_type": r.resource_type,
                "missing_tags": r.missing_tags,
            }
            for r in untagged[-limit:]
        ]

    def list_reports(self, limit: int = 100) -> list[ResourceTagReport]:
        return self._reports[-limit:]

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_policies": len(self._policies),
            "total_reports": len(self._reports),
            "compliance_score": self.get_compliance_score().score_pct,
        }
