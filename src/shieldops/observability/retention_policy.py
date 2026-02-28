"""Data Retention Policy Manager — manage retention policies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DataCategory(StrEnum):
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"
    EVENTS = "events"
    BACKUPS = "backups"


class RetentionTier(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"
    DELETED = "deleted"


class ComplianceRequirement(StrEnum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    GDPR = "gdpr"
    PCI_DSS = "pci_dss"
    INTERNAL = "internal"


# --- Models ---


class RetentionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    data_category: DataCategory = DataCategory.METRICS
    tier: RetentionTier = RetentionTier.HOT
    compliance: ComplianceRequirement = ComplianceRequirement.INTERNAL
    retention_days: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RetentionRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    data_category: DataCategory = DataCategory.METRICS
    tier: RetentionTier = RetentionTier.HOT
    max_days: int = 365
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RetentionPolicyReport(BaseModel):
    total_records: int = 0
    total_rules: int = 0
    avg_retention_days: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    violation_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataRetentionPolicyManager:
    """Manage data retention policies, compliance requirements, and lifecycle rules."""

    def __init__(
        self,
        max_records: int = 200000,
        max_retention_days: int = 365,
    ) -> None:
        self._max_records = max_records
        self._max_retention_days = max_retention_days
        self._records: list[RetentionRecord] = []
        self._rules: list[RetentionRule] = []
        logger.info(
            "retention_policy.initialized",
            max_records=max_records,
            max_retention_days=max_retention_days,
        )

    # -- record / get / list ---------------------------------------------

    def record_retention(
        self,
        service_name: str,
        data_category: DataCategory = DataCategory.METRICS,
        tier: RetentionTier = RetentionTier.HOT,
        compliance: ComplianceRequirement = ComplianceRequirement.INTERNAL,
        retention_days: int = 0,
        details: str = "",
    ) -> RetentionRecord:
        record = RetentionRecord(
            service_name=service_name,
            data_category=data_category,
            tier=tier,
            compliance=compliance,
            retention_days=retention_days,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "retention_policy.recorded",
            record_id=record.id,
            service_name=service_name,
            data_category=data_category.value,
            tier=tier.value,
        )
        return record

    def get_retention(self, record_id: str) -> RetentionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_retentions(
        self,
        service_name: str | None = None,
        data_category: DataCategory | None = None,
        limit: int = 50,
    ) -> list[RetentionRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if data_category is not None:
            results = [r for r in results if r.data_category == data_category]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        data_category: DataCategory = DataCategory.METRICS,
        tier: RetentionTier = RetentionTier.HOT,
        max_days: int = 365,
        description: str = "",
    ) -> RetentionRule:
        rule = RetentionRule(
            rule_name=rule_name,
            data_category=data_category,
            tier=tier,
            max_days=max_days,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "retention_policy.rule_added",
            rule_name=rule_name,
            data_category=data_category.value,
            tier=tier.value,
        )
        return rule

    # -- domain operations -----------------------------------------------

    def analyze_retention_compliance(self, service_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_days = round(sum(r.retention_days for r in records) / len(records), 2)
        violations = sum(1 for r in records if r.retention_days > self._max_retention_days)
        return {
            "service_name": service_name,
            "total_records": len(records),
            "avg_retention_days": avg_days,
            "violation_count": violations,
            "meets_threshold": avg_days <= self._max_retention_days,
        }

    def identify_retention_violations(self) -> list[dict[str, Any]]:
        violation_counts: dict[str, int] = {}
        for r in self._records:
            if r.retention_days > self._max_retention_days:
                violation_counts[r.service_name] = violation_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in violation_counts.items():
            if count > 1:
                results.append({"service_name": svc, "violation_count": count})
        results.sort(key=lambda x: x["violation_count"], reverse=True)
        return results

    def rank_by_retention_days(self) -> list[dict[str, Any]]:
        svc_days: dict[str, list[int]] = {}
        for r in self._records:
            svc_days.setdefault(r.service_name, []).append(r.retention_days)
        results: list[dict[str, Any]] = []
        for svc, days in svc_days.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_retention_days": round(sum(days) / len(days), 2),
                    "record_count": len(days),
                }
            )
        results.sort(key=lambda x: x["avg_retention_days"], reverse=True)
        return results

    def detect_retention_trends(self) -> list[dict[str, Any]]:
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "retention_count": count,
                        "recurring": True,
                    }
                )
        results.sort(key=lambda x: x["retention_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RetentionPolicyReport:
        by_category: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        for r in self._records:
            by_category[r.data_category.value] = by_category.get(r.data_category.value, 0) + 1
            by_tier[r.tier.value] = by_tier.get(r.tier.value, 0) + 1
        avg_days = (
            round(
                sum(r.retention_days for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        violation_count = sum(
            1 for r in self._records if r.retention_days > self._max_retention_days
        )
        recs: list[str] = []
        if avg_days > self._max_retention_days:
            recs.append(
                f"Average retention {avg_days} days exceeds {self._max_retention_days} day limit"
            )
        recurring = len(self.detect_retention_trends())
        if recurring > 0:
            recs.append(f"{recurring} service(s) with recurring retention trends")
        if not recs:
            recs.append("Data retention policy management meets targets")
        return RetentionPolicyReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            avg_retention_days=avg_days,
            by_category=by_category,
            by_tier=by_tier,
            violation_count=violation_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("retention_policy.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.data_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "max_retention_days": self._max_retention_days,
            "category_distribution": category_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
