"""Log Retention Optimizer — optimize log retention policies based on value and cost."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RetentionTier(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"
    DELETE = "delete"


class LogValueLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class ComplianceRequirement(StrEnum):
    REGULATORY = "regulatory"
    SECURITY = "security"
    OPERATIONAL = "operational"
    AUDIT = "audit"
    NONE = "none"


# --- Models ---


class LogRetentionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    current_tier: RetentionTier = RetentionTier.HOT
    value_level: LogValueLevel = LogValueLevel.MEDIUM
    compliance: ComplianceRequirement = ComplianceRequirement.NONE
    retention_days: int = 90
    daily_volume_gb: float = 0.0
    cost_per_gb_month: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RetentionPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_pattern: str = ""
    recommended_tier: RetentionTier = RetentionTier.WARM
    recommended_days: int = 90
    compliance: ComplianceRequirement = ComplianceRequirement.NONE
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class LogRetentionReport(BaseModel):
    total_sources: int = 0
    total_policies: int = 0
    avg_retention_days: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_value: dict[str, int] = Field(default_factory=dict)
    estimated_savings_pct: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class LogRetentionOptimizer:
    """Optimize log retention policies based on value, compliance, and cost."""

    def __init__(
        self,
        max_records: int = 200000,
        default_retention_days: int = 90,
    ) -> None:
        self._max_records = max_records
        self._default_retention_days = default_retention_days
        self._records: list[LogRetentionRecord] = []
        self._policies: list[RetentionPolicy] = []
        logger.info(
            "log_retention_optimizer.initialized",
            max_records=max_records,
            default_retention_days=default_retention_days,
        )

    # -- internal helpers ------------------------------------------------

    def _value_to_days(self, value: LogValueLevel) -> int:
        return {
            LogValueLevel.CRITICAL: 365,
            LogValueLevel.HIGH: 180,
            LogValueLevel.MEDIUM: 90,
            LogValueLevel.LOW: 30,
            LogValueLevel.NEGLIGIBLE: 7,
        }.get(value, self._default_retention_days)

    def _value_to_tier(self, value: LogValueLevel) -> RetentionTier:
        return {
            LogValueLevel.CRITICAL: RetentionTier.HOT,
            LogValueLevel.HIGH: RetentionTier.WARM,
            LogValueLevel.MEDIUM: RetentionTier.WARM,
            LogValueLevel.LOW: RetentionTier.COLD,
            LogValueLevel.NEGLIGIBLE: RetentionTier.DELETE,
        }.get(value, RetentionTier.WARM)

    # -- record / get / list ---------------------------------------------

    def record_log_source(
        self,
        source: str,
        current_tier: RetentionTier = RetentionTier.HOT,
        value_level: LogValueLevel = LogValueLevel.MEDIUM,
        compliance: ComplianceRequirement = ComplianceRequirement.NONE,
        retention_days: int = 90,
        daily_volume_gb: float = 0.0,
        cost_per_gb_month: float = 0.0,
        details: str = "",
    ) -> LogRetentionRecord:
        record = LogRetentionRecord(
            source=source,
            current_tier=current_tier,
            value_level=value_level,
            compliance=compliance,
            retention_days=retention_days,
            daily_volume_gb=daily_volume_gb,
            cost_per_gb_month=cost_per_gb_month,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "log_retention_optimizer.source_recorded",
            record_id=record.id,
            source=source,
            value_level=value_level.value,
        )
        return record

    def get_log_source(self, record_id: str) -> LogRetentionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_log_sources(
        self,
        source: str | None = None,
        value_level: LogValueLevel | None = None,
        limit: int = 50,
    ) -> list[LogRetentionRecord]:
        results = list(self._records)
        if source is not None:
            results = [r for r in results if r.source == source]
        if value_level is not None:
            results = [r for r in results if r.value_level == value_level]
        return results[-limit:]

    def add_policy(
        self,
        source_pattern: str,
        recommended_tier: RetentionTier = RetentionTier.WARM,
        recommended_days: int = 90,
        compliance: ComplianceRequirement = ComplianceRequirement.NONE,
        reason: str = "",
    ) -> RetentionPolicy:
        policy = RetentionPolicy(
            source_pattern=source_pattern,
            recommended_tier=recommended_tier,
            recommended_days=recommended_days,
            compliance=compliance,
            reason=reason,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "log_retention_optimizer.policy_added",
            policy_id=policy.id,
            source_pattern=source_pattern,
            recommended_tier=recommended_tier.value,
        )
        return policy

    # -- domain operations -----------------------------------------------

    def recommend_retention(self, source: str) -> dict[str, Any]:
        """Recommend retention settings for a log source."""
        source_records = [r for r in self._records if r.source == source]
        if not source_records:
            return {"source": source, "recommendation": "no_data"}
        latest = source_records[-1]
        rec_days = self._value_to_days(latest.value_level)
        rec_tier = self._value_to_tier(latest.value_level)
        # Compliance overrides
        if latest.compliance in (
            ComplianceRequirement.REGULATORY,
            ComplianceRequirement.SECURITY,
        ):
            rec_days = max(rec_days, 365)
            rec_tier = RetentionTier.WARM
        return {
            "source": source,
            "current_tier": latest.current_tier.value,
            "recommended_tier": rec_tier.value,
            "current_retention_days": latest.retention_days,
            "recommended_retention_days": rec_days,
            "value_level": latest.value_level.value,
            "compliance": latest.compliance.value,
        }

    def identify_over_retained(self) -> list[dict[str, Any]]:
        """Find log sources retained longer than their value justifies."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            ideal_days = self._value_to_days(r.value_level)
            if r.retention_days > ideal_days * 1.5:
                results.append(
                    {
                        "source": r.source,
                        "current_days": r.retention_days,
                        "recommended_days": ideal_days,
                        "excess_days": r.retention_days - ideal_days,
                        "value_level": r.value_level.value,
                    }
                )
        results.sort(key=lambda x: x["excess_days"], reverse=True)
        return results

    def calculate_cost_savings(self) -> dict[str, Any]:
        """Estimate cost savings from optimizing retention."""
        total_current = 0.0
        total_optimized = 0.0
        for r in self._records:
            monthly_cost = r.daily_volume_gb * 30 * r.cost_per_gb_month
            current_months = r.retention_days / 30
            ideal_days = self._value_to_days(r.value_level)
            ideal_months = ideal_days / 30
            total_current += monthly_cost * current_months
            total_optimized += monthly_cost * ideal_months
        savings = total_current - total_optimized
        savings_pct = round((savings / max(total_current, 0.01)) * 100, 2)
        return {
            "current_estimated_cost": round(total_current, 2),
            "optimized_estimated_cost": round(total_optimized, 2),
            "estimated_savings": round(savings, 2),
            "savings_pct": savings_pct,
        }

    def analyze_compliance_gaps(self) -> list[dict[str, Any]]:
        """Find sources not meeting compliance retention requirements."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance in (
                ComplianceRequirement.REGULATORY,
                ComplianceRequirement.SECURITY,
            ):
                if r.retention_days < 365:
                    results.append(
                        {
                            "source": r.source,
                            "compliance": r.compliance.value,
                            "current_days": r.retention_days,
                            "required_days": 365,
                            "gap_days": 365 - r.retention_days,
                        }
                    )
            elif r.compliance == ComplianceRequirement.AUDIT and r.retention_days < 180:
                results.append(
                    {
                        "source": r.source,
                        "compliance": r.compliance.value,
                        "current_days": r.retention_days,
                        "required_days": 180,
                        "gap_days": 180 - r.retention_days,
                    }
                )
        results.sort(key=lambda x: x["gap_days"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> LogRetentionReport:
        by_tier: dict[str, int] = {}
        by_value: dict[str, int] = {}
        for r in self._records:
            by_tier[r.current_tier.value] = by_tier.get(r.current_tier.value, 0) + 1
            by_value[r.value_level.value] = by_value.get(r.value_level.value, 0) + 1
        avg_days = (
            round(sum(r.retention_days for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        savings = self.calculate_cost_savings()
        recs: list[str] = []
        over_retained = self.identify_over_retained()
        if over_retained:
            recs.append(f"{len(over_retained)} source(s) over-retained")
        gaps = self.analyze_compliance_gaps()
        if gaps:
            recs.append(f"{len(gaps)} source(s) not meeting compliance requirements")
        if not recs:
            recs.append("Log retention policies are well-optimized")
        return LogRetentionReport(
            total_sources=len(self._records),
            total_policies=len(self._policies),
            avg_retention_days=avg_days,
            by_tier=by_tier,
            by_value=by_value,
            estimated_savings_pct=savings["savings_pct"],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("log_retention_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.current_tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_sources": len(self._records),
            "total_policies": len(self._policies),
            "default_retention_days": self._default_retention_days,
            "tier_distribution": tier_dist,
            "unique_sources": len({r.source for r in self._records}),
        }
