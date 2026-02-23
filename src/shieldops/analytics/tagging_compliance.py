"""Cloud resource tagging compliance tracking and enforcement.

Evaluates cloud resources against tagging policies to ensure consistent labeling,
identifies non-compliant resources, and suggests remediation tags.
"""

from __future__ import annotations

import enum
import time
import uuid
from collections import Counter
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class TagComplianceStatus(enum.StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    EXEMPT = "exempt"


class ResourceProvider(enum.StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    KUBERNETES = "kubernetes"
    ON_PREM = "on_prem"


# -- Models --------------------------------------------------------------------


class TagPolicy(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    required_tags: list[str] = Field(default_factory=list)
    optional_tags: list[str] = Field(default_factory=list)
    allowed_values: dict[str, list[str]] = Field(default_factory=dict)
    provider: ResourceProvider | None = None
    created_at: float = Field(default_factory=time.time)


class ResourceTagRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    resource_id: str
    resource_type: str
    provider: ResourceProvider
    tags: dict[str, str] = Field(default_factory=dict)
    missing_tags: list[str] = Field(default_factory=list)
    invalid_tags: list[str] = Field(default_factory=list)
    status: TagComplianceStatus = TagComplianceStatus.NON_COMPLIANT
    scanned_at: float = Field(default_factory=time.time)


class TagComplianceReport(BaseModel):
    total_resources: int = 0
    compliant: int = 0
    non_compliant: int = 0
    partially_compliant: int = 0
    compliance_pct: float = 0.0
    top_missing_tags: list[str] = Field(default_factory=list)


# -- Engine --------------------------------------------------------------------


class TaggingComplianceEngine:
    """Evaluate cloud resources against tagging policies.

    Parameters
    ----------
    max_policies:
        Maximum number of tagging policies to store.
    max_records:
        Maximum number of resource tag records to store.
    """

    def __init__(
        self,
        max_policies: int = 100,
        max_records: int = 50000,
    ) -> None:
        self._policies: dict[str, TagPolicy] = {}
        self._records: dict[str, ResourceTagRecord] = {}
        self._max_policies = max_policies
        self._max_records = max_records

    def create_policy(
        self,
        name: str,
        required_tags: list[str],
        optional_tags: list[str] | None = None,
        allowed_values: dict[str, list[str]] | None = None,
        provider: ResourceProvider | None = None,
    ) -> TagPolicy:
        if len(self._policies) >= self._max_policies:
            raise ValueError(f"Maximum policies limit reached: {self._max_policies}")
        policy = TagPolicy(
            name=name,
            required_tags=required_tags,
            optional_tags=optional_tags or [],
            allowed_values=allowed_values or {},
            provider=provider,
        )
        self._policies[policy.id] = policy
        logger.info("tag_policy_created", policy_id=policy.id, name=name)
        return policy

    def scan_resource(
        self,
        resource_id: str,
        resource_type: str,
        provider: ResourceProvider,
        tags: dict[str, str],
    ) -> ResourceTagRecord:
        if len(self._records) >= self._max_records:
            raise ValueError(f"Maximum records limit reached: {self._max_records}")

        # Find matching policies (provider-specific + global)
        matching_policies = [
            p for p in self._policies.values() if p.provider is None or p.provider == provider
        ]

        missing_tags: list[str] = []
        invalid_tags: list[str] = []

        for policy in matching_policies:
            for tag in policy.required_tags:
                if tag not in tags and tag not in missing_tags:
                    missing_tags.append(tag)
            for tag_key, allowed in policy.allowed_values.items():
                if tag_key in tags and tags[tag_key] not in allowed and tag_key not in invalid_tags:
                    invalid_tags.append(tag_key)

        # Determine compliance status
        if not missing_tags and not invalid_tags:
            status = TagComplianceStatus.COMPLIANT
        elif (
            missing_tags
            and not invalid_tags
            and len(missing_tags) < len({t for p in matching_policies for t in p.required_tags})
        ):
            status = TagComplianceStatus.PARTIALLY_COMPLIANT
        else:
            status = TagComplianceStatus.NON_COMPLIANT

        record = ResourceTagRecord(
            resource_id=resource_id,
            resource_type=resource_type,
            provider=provider,
            tags=tags,
            missing_tags=missing_tags,
            invalid_tags=invalid_tags,
            status=status,
        )
        self._records[record.id] = record
        logger.info(
            "resource_scanned",
            record_id=record.id,
            resource_id=resource_id,
            status=status,
        )
        return record

    def get_record(self, resource_id: str) -> ResourceTagRecord | None:
        for record in self._records.values():
            if record.resource_id == resource_id:
                return record
        return None

    def list_records(
        self,
        status: TagComplianceStatus | None = None,
        provider: ResourceProvider | None = None,
    ) -> list[ResourceTagRecord]:
        records = list(self._records.values())
        if status:
            records = [r for r in records if r.status == status]
        if provider:
            records = [r for r in records if r.provider == provider]
        return records

    def get_compliance_report(
        self,
        provider: ResourceProvider | None = None,
    ) -> TagComplianceReport:
        records = list(self._records.values())
        if provider:
            records = [r for r in records if r.provider == provider]

        total = len(records)
        compliant = sum(1 for r in records if r.status == TagComplianceStatus.COMPLIANT)
        non_compliant = sum(1 for r in records if r.status == TagComplianceStatus.NON_COMPLIANT)
        partially = sum(1 for r in records if r.status == TagComplianceStatus.PARTIALLY_COMPLIANT)
        compliance_pct = (compliant / total * 100) if total > 0 else 0.0

        # Find top missing tags
        missing_counter: Counter[str] = Counter()
        for r in records:
            for tag in r.missing_tags:
                missing_counter[tag] += 1
        top_missing = [tag for tag, _ in missing_counter.most_common(10)]

        return TagComplianceReport(
            total_resources=total,
            compliant=compliant,
            non_compliant=non_compliant,
            partially_compliant=partially,
            compliance_pct=round(compliance_pct, 2),
            top_missing_tags=top_missing,
        )

    def list_policies(self) -> list[TagPolicy]:
        return list(self._policies.values())

    def delete_policy(self, policy_id: str) -> bool:
        return self._policies.pop(policy_id, None) is not None

    def suggest_tags(
        self,
        resource_id: str,
        resource_type: str,
    ) -> dict[str, str]:
        suggestions: dict[str, str] = {}

        # Suggest environment based on resource_id pattern
        resource_lower = resource_id.lower()
        if "prod" in resource_lower:
            suggestions["environment"] = "production"
        elif "staging" in resource_lower or "stg" in resource_lower:
            suggestions["environment"] = "staging"
        elif "dev" in resource_lower:
            suggestions["environment"] = "development"

        # Suggest service tag from resource_type
        type_lower = resource_type.lower()
        if "db" in type_lower or "database" in type_lower or "rds" in type_lower:
            suggestions["tier"] = "data"
        elif "lb" in type_lower or "balancer" in type_lower or "elb" in type_lower:
            suggestions["tier"] = "network"
        elif "instance" in type_lower or "vm" in type_lower or "ec2" in type_lower:
            suggestions["tier"] = "compute"
        elif "bucket" in type_lower or "s3" in type_lower or "storage" in type_lower:
            suggestions["tier"] = "storage"

        # Suggest owner from existing records of same resource_type
        for record in self._records.values():
            if record.resource_type == resource_type and "owner" in record.tags:
                suggestions["owner"] = record.tags["owner"]
                break

        logger.info(
            "tags_suggested",
            resource_id=resource_id,
            resource_type=resource_type,
            suggestion_count=len(suggestions),
        )
        return suggestions

    def get_stats(self) -> dict[str, Any]:
        compliant = sum(
            1 for r in self._records.values() if r.status == TagComplianceStatus.COMPLIANT
        )
        return {
            "total_policies": len(self._policies),
            "total_records": len(self._records),
            "compliant_records": compliant,
            "non_compliant_records": len(self._records) - compliant,
        }
