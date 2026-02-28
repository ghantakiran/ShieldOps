"""Deployment Impact Analyzer — analyze deployment impact on services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactScope(StrEnum):
    SINGLE_SERVICE = "single_service"
    SERVICE_GROUP = "service_group"
    AVAILABILITY_ZONE = "availability_zone"
    REGION = "region"
    GLOBAL = "global"


class ImpactType(StrEnum):
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    ERROR_RATE = "error_rate"
    LATENCY = "latency"
    RESOURCE_USAGE = "resource_usage"


class ImpactSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    NONE = "none"


# --- Models ---


class ImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_name: str = ""
    scope: ImpactScope = ImpactScope.SINGLE_SERVICE
    impact_type: ImpactType = ImpactType.PERFORMANCE
    severity: ImpactSeverity = ImpactSeverity.MINOR
    impact_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    scope: ImpactScope = ImpactScope.SINGLE_SERVICE
    impact_type: ImpactType = ImpactType.PERFORMANCE
    max_impact_score: float = 50.0
    auto_rollback: bool = False
    created_at: float = Field(default_factory=time.time)


class DeploymentImpactReport(BaseModel):
    total_impacts: int = 0
    total_rules: int = 0
    low_impact_rate_pct: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentImpactAnalyzer:
    """Analyze deployment impact on services."""

    def __init__(
        self,
        max_records: int = 200000,
        max_impact_score: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._max_impact_score = max_impact_score
        self._records: list[ImpactRecord] = []
        self._policies: list[ImpactRule] = []
        logger.info(
            "deployment_impact.initialized",
            max_records=max_records,
            max_impact_score=max_impact_score,
        )

    # -- record / get / list -----------------------------------------

    def record_impact(
        self,
        deployment_name: str,
        scope: ImpactScope = ImpactScope.SINGLE_SERVICE,
        impact_type: ImpactType = ImpactType.PERFORMANCE,
        severity: ImpactSeverity = ImpactSeverity.MINOR,
        impact_score: float = 0.0,
        details: str = "",
    ) -> ImpactRecord:
        record = ImpactRecord(
            deployment_name=deployment_name,
            scope=scope,
            impact_type=impact_type,
            severity=severity,
            impact_score=impact_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deployment_impact.impact_recorded",
            record_id=record.id,
            deployment_name=deployment_name,
            scope=scope.value,
            severity=severity.value,
        )
        return record

    def get_impact(self, record_id: str) -> ImpactRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_impacts(
        self,
        deployment_name: str | None = None,
        scope: ImpactScope | None = None,
        limit: int = 50,
    ) -> list[ImpactRecord]:
        results = list(self._records)
        if deployment_name is not None:
            results = [r for r in results if r.deployment_name == deployment_name]
        if scope is not None:
            results = [r for r in results if r.scope == scope]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        scope: ImpactScope = ImpactScope.SINGLE_SERVICE,
        impact_type: ImpactType = ImpactType.PERFORMANCE,
        max_impact_score: float = 50.0,
        auto_rollback: bool = False,
    ) -> ImpactRule:
        rule = ImpactRule(
            rule_name=rule_name,
            scope=scope,
            impact_type=impact_type,
            max_impact_score=max_impact_score,
            auto_rollback=auto_rollback,
        )
        self._policies.append(rule)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "deployment_impact.rule_added",
            rule_name=rule_name,
            scope=scope.value,
            impact_type=impact_type.value,
        )
        return rule

    # -- domain operations -------------------------------------------

    def analyze_impact_trends(self, deployment_name: str) -> dict[str, Any]:
        """Analyze impact trends for a deployment."""
        records = [r for r in self._records if r.deployment_name == deployment_name]
        if not records:
            return {
                "deployment_name": deployment_name,
                "status": "no_data",
            }
        low_count = sum(
            1
            for r in records
            if r.severity
            in (
                ImpactSeverity.MINOR,
                ImpactSeverity.NONE,
            )
        )
        low_rate = round(low_count / len(records) * 100, 2)
        avg_impact = round(
            sum(r.impact_score for r in records) / len(records),
            2,
        )
        return {
            "deployment_name": deployment_name,
            "impact_count": len(records),
            "low_count": low_count,
            "low_rate": low_rate,
            "avg_impact": avg_impact,
            "meets_threshold": (avg_impact <= self._max_impact_score),
        }

    def identify_high_impact_deployments(
        self,
    ) -> list[dict[str, Any]]:
        """Find deployments with repeated high impact."""
        high_counts: dict[str, int] = {}
        for r in self._records:
            if r.severity in (
                ImpactSeverity.CRITICAL,
                ImpactSeverity.MAJOR,
            ):
                high_counts[r.deployment_name] = high_counts.get(r.deployment_name, 0) + 1
        results: list[dict[str, Any]] = []
        for deploy, count in high_counts.items():
            if count > 1:
                results.append(
                    {
                        "deployment_name": deploy,
                        "high_impact_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["high_impact_count"],
            reverse=True,
        )
        return results

    def rank_by_impact_score(
        self,
    ) -> list[dict[str, Any]]:
        """Rank deployments by avg impact score desc."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            totals[r.deployment_name] = totals.get(r.deployment_name, 0.0) + r.impact_score
            counts[r.deployment_name] = counts.get(r.deployment_name, 0) + 1
        results: list[dict[str, Any]] = []
        for deploy, total in totals.items():
            avg = round(total / counts[deploy], 2)
            results.append(
                {
                    "deployment_name": deploy,
                    "avg_impact_score": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_impact_score"],
            reverse=True,
        )
        return results

    def detect_impact_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Detect deployments with >3 non-MINOR/NONE."""
        non_low: dict[str, int] = {}
        for r in self._records:
            if r.severity not in (
                ImpactSeverity.MINOR,
                ImpactSeverity.NONE,
            ):
                non_low[r.deployment_name] = non_low.get(r.deployment_name, 0) + 1
        results: list[dict[str, Any]] = []
        for deploy, count in non_low.items():
            if count > 3:
                results.append(
                    {
                        "deployment_name": deploy,
                        "non_low_count": count,
                        "pattern_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_low_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(
        self,
    ) -> DeploymentImpactReport:
        by_scope: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_scope[r.scope.value] = by_scope.get(r.scope.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        low_count = sum(
            1
            for r in self._records
            if r.severity
            in (
                ImpactSeverity.MINOR,
                ImpactSeverity.NONE,
            )
        )
        low_rate = (
            round(
                low_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        high_impacts = sum(1 for d in self.identify_high_impact_deployments())
        recs: list[str] = []
        if low_rate < 100.0 and self._records:
            recs.append(f"Low impact rate {low_rate}% is below 100% threshold")
        if high_impacts > 0:
            recs.append(f"{high_impacts} deployment(s) with high impact")
        patterns = len(self.detect_impact_patterns())
        if patterns > 0:
            recs.append(f"{patterns} deployment(s) with impact patterns detected")
        if not recs:
            recs.append("Deployment impact is healthy across all services")
        return DeploymentImpactReport(
            total_impacts=len(self._records),
            total_rules=len(self._policies),
            low_impact_rate_pct=low_rate,
            by_scope=by_scope,
            by_severity=by_severity,
            critical_count=high_impacts,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("deployment_impact.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scope_dist: dict[str, int] = {}
        for r in self._records:
            key = r.scope.value
            scope_dist[key] = scope_dist.get(key, 0) + 1
        return {
            "total_impacts": len(self._records),
            "total_rules": len(self._policies),
            "max_impact_score": (self._max_impact_score),
            "scope_distribution": scope_dist,
            "unique_deployments": len({r.deployment_name for r in self._records}),
        }
