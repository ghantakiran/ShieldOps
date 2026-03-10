"""MultiTenantObservabilityEngine — multi-tenant."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TenantTier(StrEnum):
    FREE = "free"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class IsolationLevel(StrEnum):
    SHARED = "shared"
    NAMESPACE = "namespace"
    DEDICATED = "dedicated"
    CUSTOM = "custom"


class QuotaStatus(StrEnum):
    WITHIN_LIMIT = "within_limit"
    WARNING = "warning"
    EXCEEDED = "exceeded"
    SUSPENDED = "suspended"


# --- Models ---


class TenantRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tier: TenantTier = TenantTier.STANDARD
    isolation: IsolationLevel = IsolationLevel.SHARED
    quota_status: QuotaStatus = QuotaStatus.WITHIN_LIMIT
    score: float = 0.0
    usage_pct: float = 0.0
    data_volume_gb: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TenantAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tier: TenantTier = TenantTier.STANDARD
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TenantReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    total_data_volume_gb: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_isolation: dict[str, int] = Field(default_factory=dict)
    by_quota_status: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MultiTenantObservabilityEngine:
    """Multi-Tenant Observability Engine.

    Manages observability across tenants with
    quota enforcement and noisy-neighbor
    detection.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[TenantRecord] = []
        self._analyses: list[TenantAnalysis] = []
        logger.info(
            "multi_tenant_obs_engine.init",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        tier: TenantTier = TenantTier.STANDARD,
        isolation: IsolationLevel = (IsolationLevel.SHARED),
        quota_status: QuotaStatus = (QuotaStatus.WITHIN_LIMIT),
        score: float = 0.0,
        usage_pct: float = 0.0,
        data_volume_gb: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TenantRecord:
        record = TenantRecord(
            name=name,
            tier=tier,
            isolation=isolation,
            quota_status=quota_status,
            score=score,
            usage_pct=usage_pct,
            data_volume_gb=data_volume_gb,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "multi_tenant_obs_engine.added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.name == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        scores = [r.score for r in matching]
        avg = round(sum(scores) / len(scores), 2)
        usage = [r.usage_pct for r in matching]
        avg_usage = round(sum(usage) / len(usage), 2)
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "avg_usage_pct": avg_usage,
        }

    def generate_report(self) -> TenantReport:
        by_t: dict[str, int] = {}
        by_i: dict[str, int] = {}
        by_q: dict[str, int] = {}
        for r in self._records:
            v1 = r.tier.value
            by_t[v1] = by_t.get(v1, 0) + 1
            v2 = r.isolation.value
            by_i[v2] = by_i.get(v2, 0) + 1
            v3 = r.quota_status.value
            by_q[v3] = by_q.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        total_vol = round(
            sum(r.data_volume_gb for r in self._records),
            2,
        )
        recs: list[str] = []
        exceeded = by_q.get("exceeded", 0)
        suspended = by_q.get("suspended", 0)
        if exceeded > 0:
            recs.append(f"{exceeded} tenant(s) exceeded quota")
        if suspended > 0:
            recs.append(f"{suspended} tenant(s) suspended")
        if not recs:
            recs.append("Multi-tenant observability healthy")
        return TenantReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            total_data_volume_gb=total_vol,
            by_tier=by_t,
            by_isolation=by_i,
            by_quota_status=by_q,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        t_dist: dict[str, int] = {}
        for r in self._records:
            k = r.tier.value
            t_dist[k] = t_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "tier_distribution": t_dist,
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("multi_tenant_obs_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def enforce_tenant_quotas(
        self,
    ) -> dict[str, Any]:
        """Enforce quotas per tenant tier."""
        if not self._records:
            return {"status": "no_data"}
        tier_limits = {
            TenantTier.FREE: 10.0,
            TenantTier.STANDARD: 100.0,
            TenantTier.PREMIUM: 1000.0,
            TenantTier.ENTERPRISE: 10000.0,
        }
        tenant_usage: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.name not in tenant_usage:
                tenant_usage[r.name] = {
                    "tier": r.tier,
                    "total_gb": 0.0,
                    "records": 0,
                }
            tenant_usage[r.name]["total_gb"] += r.data_volume_gb
            tenant_usage[r.name]["records"] += 1
        violations: list[dict[str, Any]] = []
        for tenant, data in tenant_usage.items():
            limit = tier_limits.get(data["tier"], 100.0)
            if data["total_gb"] > limit:
                violations.append(
                    {
                        "tenant": tenant,
                        "tier": data["tier"].value,
                        "usage_gb": round(data["total_gb"], 2),
                        "limit_gb": limit,
                        "overage_gb": round(
                            data["total_gb"] - limit,
                            2,
                        ),
                    }
                )
        return {
            "total_tenants": len(tenant_usage),
            "violations": len(violations),
            "violation_details": violations,
        }

    def detect_noisy_neighbors(
        self,
    ) -> list[dict[str, Any]]:
        """Detect noisy neighbor tenants."""
        tenant_data: dict[str, dict[str, float]] = {}
        for r in self._records:
            if r.name not in tenant_data:
                tenant_data[r.name] = {
                    "total_usage": 0.0,
                    "total_volume": 0.0,
                    "count": 0,
                }
            tenant_data[r.name]["total_usage"] += r.usage_pct
            tenant_data[r.name]["total_volume"] += r.data_volume_gb
            tenant_data[r.name]["count"] += 1
        if not tenant_data:
            return []
        all_usages = [d["total_usage"] / d["count"] for d in tenant_data.values()]
        global_avg = sum(all_usages) / len(all_usages) if all_usages else 0.0
        noisy: list[dict[str, Any]] = []
        for tenant, data in tenant_data.items():
            avg_usage = data["total_usage"] / data["count"]
            if avg_usage > global_avg * 2:
                noisy.append(
                    {
                        "tenant": tenant,
                        "avg_usage_pct": round(avg_usage, 2),
                        "global_avg": round(global_avg, 2),
                        "ratio": round(avg_usage / global_avg, 2) if global_avg > 0 else 0.0,
                    }
                )
        noisy.sort(
            key=lambda x: x["avg_usage_pct"],
            reverse=True,
        )
        return noisy

    def compute_tenant_utilization(
        self,
    ) -> dict[str, Any]:
        """Compute utilization per tenant."""
        if not self._records:
            return {"status": "no_data"}
        tier_util: dict[str, dict[str, float]] = {}
        for r in self._records:
            tv = r.tier.value
            if tv not in tier_util:
                tier_util[tv] = {
                    "total_usage": 0.0,
                    "total_volume": 0.0,
                    "count": 0,
                }
            tier_util[tv]["total_usage"] += r.usage_pct
            tier_util[tv]["total_volume"] += r.data_volume_gb
            tier_util[tv]["count"] += 1
        result: dict[str, Any] = {}
        for tv, data in tier_util.items():
            cnt = data["count"]
            result[tv] = {
                "avg_usage_pct": round(data["total_usage"] / cnt, 2),
                "total_volume_gb": round(data["total_volume"], 2),
                "tenant_count": int(cnt),
            }
        return result
