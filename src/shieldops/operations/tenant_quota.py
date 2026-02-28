"""Tenant Resource Quota Manager — per-tenant resource quotas."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResourceType(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    API_CALLS = "api_calls"


class QuotaStatus(StrEnum):
    WITHIN_LIMIT = "within_limit"
    WARNING = "warning"
    NEAR_LIMIT = "near_limit"
    EXCEEDED = "exceeded"
    SUSPENDED = "suspended"


class EnforcementAction(StrEnum):
    THROTTLE = "throttle"
    NOTIFY = "notify"
    BLOCK = "block"
    SCALE_UP = "scale_up"
    NO_ACTION = "no_action"


# --- Models ---


class QuotaRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_name: str = ""
    resource_type: ResourceType = ResourceType.CPU
    status: QuotaStatus = QuotaStatus.WITHIN_LIMIT
    utilization_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class QuotaPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    resource_type: ResourceType = ResourceType.CPU
    action: EnforcementAction = EnforcementAction.NO_ACTION
    limit_value: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TenantQuotaReport(BaseModel):
    total_records: int = 0
    total_policies: int = 0
    avg_utilization_pct: float = 0.0
    by_resource: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    exceeded_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TenantResourceQuotaManager:
    """Manage and enforce per-tenant resource quotas and utilization tracking."""

    def __init__(
        self,
        max_records: int = 200000,
        max_utilization_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._max_utilization_pct = max_utilization_pct
        self._records: list[QuotaRecord] = []
        self._policies: list[QuotaPolicy] = []
        logger.info(
            "tenant_quota.initialized",
            max_records=max_records,
            max_utilization_pct=max_utilization_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_quota(
        self,
        tenant_name: str,
        resource_type: ResourceType = ResourceType.CPU,
        status: QuotaStatus = QuotaStatus.WITHIN_LIMIT,
        utilization_pct: float = 0.0,
        details: str = "",
    ) -> QuotaRecord:
        record = QuotaRecord(
            tenant_name=tenant_name,
            resource_type=resource_type,
            status=status,
            utilization_pct=utilization_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "tenant_quota.recorded",
            record_id=record.id,
            tenant_name=tenant_name,
            resource_type=resource_type.value,
            status=status.value,
        )
        return record

    def get_quota(self, record_id: str) -> QuotaRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_quotas(
        self,
        tenant_name: str | None = None,
        resource_type: ResourceType | None = None,
        limit: int = 50,
    ) -> list[QuotaRecord]:
        results = list(self._records)
        if tenant_name is not None:
            results = [r for r in results if r.tenant_name == tenant_name]
        if resource_type is not None:
            results = [r for r in results if r.resource_type == resource_type]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        resource_type: ResourceType = ResourceType.CPU,
        action: EnforcementAction = EnforcementAction.NO_ACTION,
        limit_value: float = 0.0,
        description: str = "",
    ) -> QuotaPolicy:
        policy = QuotaPolicy(
            policy_name=policy_name,
            resource_type=resource_type,
            action=action,
            limit_value=limit_value,
            description=description,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "tenant_quota.policy_added",
            policy_name=policy_name,
            resource_type=resource_type.value,
            action=action.value,
        )
        return policy

    # -- domain operations -----------------------------------------------

    def analyze_tenant_utilization(self, tenant_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.tenant_name == tenant_name]
        if not records:
            return {"tenant_name": tenant_name, "status": "no_data"}
        avg_util = round(sum(r.utilization_pct for r in records) / len(records), 2)
        exceeded = sum(
            1 for r in records if r.status in (QuotaStatus.EXCEEDED, QuotaStatus.NEAR_LIMIT)
        )
        return {
            "tenant_name": tenant_name,
            "total_records": len(records),
            "avg_utilization_pct": avg_util,
            "exceeded_count": exceeded,
            "meets_threshold": avg_util <= self._max_utilization_pct,
        }

    def identify_exceeded_quotas(self) -> list[dict[str, Any]]:
        exceeded_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (QuotaStatus.EXCEEDED, QuotaStatus.NEAR_LIMIT):
                exceeded_counts[r.tenant_name] = exceeded_counts.get(r.tenant_name, 0) + 1
        results: list[dict[str, Any]] = []
        for tenant, count in exceeded_counts.items():
            if count > 1:
                results.append({"tenant_name": tenant, "exceeded_count": count})
        results.sort(key=lambda x: x["exceeded_count"], reverse=True)
        return results

    def rank_by_utilization(self) -> list[dict[str, Any]]:
        tenant_utils: dict[str, list[float]] = {}
        for r in self._records:
            tenant_utils.setdefault(r.tenant_name, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for tenant, utils in tenant_utils.items():
            results.append(
                {
                    "tenant_name": tenant,
                    "avg_utilization_pct": round(sum(utils) / len(utils), 2),
                    "record_count": len(utils),
                }
            )
        results.sort(key=lambda x: x["avg_utilization_pct"], reverse=True)
        return results

    def detect_quota_trends(self) -> list[dict[str, Any]]:
        tenant_counts: dict[str, int] = {}
        for r in self._records:
            tenant_counts[r.tenant_name] = tenant_counts.get(r.tenant_name, 0) + 1
        results: list[dict[str, Any]] = []
        for tenant, count in tenant_counts.items():
            if count > 3:
                results.append(
                    {
                        "tenant_name": tenant,
                        "quota_count": count,
                        "recurring": True,
                    }
                )
        results.sort(key=lambda x: x["quota_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> TenantQuotaReport:
        by_resource: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_resource[r.resource_type.value] = by_resource.get(r.resource_type.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        avg_util = (
            round(
                sum(r.utilization_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        exceeded_count = sum(
            1 for r in self._records if r.status in (QuotaStatus.EXCEEDED, QuotaStatus.NEAR_LIMIT)
        )
        recs: list[str] = []
        if avg_util > self._max_utilization_pct:
            recs.append(
                f"Average utilization {avg_util}% exceeds {self._max_utilization_pct}% threshold"
            )
        recurring = len(self.detect_quota_trends())
        if recurring > 0:
            recs.append(f"{recurring} tenant(s) with recurring quota trends")
        if not recs:
            recs.append("Tenant quota management meets targets")
        return TenantQuotaReport(
            total_records=len(self._records),
            total_policies=len(self._policies),
            avg_utilization_pct=avg_util,
            by_resource=by_resource,
            by_status=by_status,
            exceeded_count=exceeded_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("tenant_quota.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        resource_dist: dict[str, int] = {}
        for r in self._records:
            key = r.resource_type.value
            resource_dist[key] = resource_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_policies": len(self._policies),
            "max_utilization_pct": self._max_utilization_pct,
            "resource_distribution": resource_dist,
            "unique_tenants": len({r.tenant_name for r in self._records}),
        }
