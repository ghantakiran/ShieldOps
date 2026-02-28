"""SLO Aggregation Dashboard — aggregate and track SLO compliance across services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AggregationLevel(StrEnum):
    PLATFORM = "platform"
    TEAM = "team"
    SERVICE = "service"
    ENDPOINT = "endpoint"
    CUSTOM = "custom"


class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    BREACHING = "breaching"
    UNKNOWN = "unknown"
    EXEMPT = "exempt"


class AggregationWindow(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# --- Models ---


class AggregationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    level: AggregationLevel = AggregationLevel.PLATFORM
    status: ComplianceStatus = ComplianceStatus.COMPLIANT
    window: AggregationWindow = AggregationWindow.HOURLY
    compliance_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AggregationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    level: AggregationLevel = AggregationLevel.SERVICE
    status: ComplianceStatus = ComplianceStatus.COMPLIANT
    target_compliance_pct: float = 99.9
    evaluation_window_hours: float = 24.0
    created_at: float = Field(default_factory=time.time)


class SLOAggregationReport(BaseModel):
    total_aggregations: int = 0
    total_rules: int = 0
    compliant_rate_pct: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    breaching_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOAggregationDashboard:
    """Aggregate and track SLO compliance across services."""

    def __init__(
        self,
        max_records: int = 200000,
        min_compliance_pct: float = 95.0,
    ) -> None:
        self._max_records = max_records
        self._min_compliance_pct = min_compliance_pct
        self._records: list[AggregationRecord] = []
        self._rules: list[AggregationRule] = []
        logger.info(
            "slo_aggregator.initialized",
            max_records=max_records,
            min_compliance_pct=min_compliance_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_aggregation(
        self,
        service_name: str,
        level: AggregationLevel = AggregationLevel.PLATFORM,
        status: ComplianceStatus = ComplianceStatus.COMPLIANT,
        window: AggregationWindow = AggregationWindow.HOURLY,
        compliance_pct: float = 0.0,
        details: str = "",
    ) -> AggregationRecord:
        record = AggregationRecord(
            service_name=service_name,
            level=level,
            status=status,
            window=window,
            compliance_pct=compliance_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_aggregator.aggregation_recorded",
            record_id=record.id,
            service_name=service_name,
            level=level.value,
            status=status.value,
        )
        return record

    def get_aggregation(self, record_id: str) -> AggregationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_aggregations(
        self,
        service_name: str | None = None,
        level: AggregationLevel | None = None,
        limit: int = 50,
    ) -> list[AggregationRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if level is not None:
            results = [r for r in results if r.level == level]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        level: AggregationLevel = AggregationLevel.SERVICE,
        status: ComplianceStatus = ComplianceStatus.COMPLIANT,
        target_compliance_pct: float = 99.9,
        evaluation_window_hours: float = 24.0,
    ) -> AggregationRule:
        rule = AggregationRule(
            rule_name=rule_name,
            level=level,
            status=status,
            target_compliance_pct=target_compliance_pct,
            evaluation_window_hours=evaluation_window_hours,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "slo_aggregator.rule_added",
            rule_name=rule_name,
            level=level.value,
            status=status.value,
        )
        return rule

    # -- domain operations -----------------------------------------------

    def analyze_compliance_status(self, service_name: str) -> dict[str, Any]:
        """Analyze compliance status for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_compliance = round(sum(r.compliance_pct for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "avg_compliance": avg_compliance,
            "record_count": len(records),
            "meets_threshold": avg_compliance >= self._min_compliance_pct,
        }

    def identify_at_risk_slos(self) -> list[dict[str, Any]]:
        """Find services with >1 AT_RISK or BREACHING status."""
        risk_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (ComplianceStatus.AT_RISK, ComplianceStatus.BREACHING):
                risk_counts[r.service_name] = risk_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in risk_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "risk_count": count,
                    }
                )
        results.sort(key=lambda x: x["risk_count"], reverse=True)
        return results

    def rank_by_compliance_rate(self) -> list[dict[str, Any]]:
        """Rank services by avg compliance_pct descending."""
        scores: dict[str, list[float]] = {}
        for r in self._records:
            scores.setdefault(r.service_name, []).append(r.compliance_pct)
        results: list[dict[str, Any]] = []
        for svc, vals in scores.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_compliance_pct": round(sum(vals) / len(vals), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_pct"], reverse=True)
        return results

    def detect_compliance_trends(self) -> list[dict[str, Any]]:
        """Detect services with >3 aggregation records."""
        counts: dict[str, int] = {}
        for r in self._records:
            counts[r.service_name] = counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "record_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> SLOAggregationReport:
        by_level: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_level[r.level.value] = by_level.get(r.level.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        compliant = sum(1 for r in self._records if r.status == ComplianceStatus.COMPLIANT)
        compliant_rate = round(compliant / len(self._records) * 100, 2) if self._records else 0.0
        breaching_count = sum(1 for d in self.identify_at_risk_slos())
        recs: list[str] = []
        if self._records and compliant_rate < self._min_compliance_pct:
            recs.append(
                f"Compliant rate {compliant_rate}% is below {self._min_compliance_pct}% threshold"
            )
        if breaching_count > 0:
            recs.append(f"{breaching_count} service(s) at risk or breaching")
        trends = len(self.detect_compliance_trends())
        if trends > 0:
            recs.append(f"{trends} service(s) with compliance trends detected")
        if not recs:
            recs.append("SLO compliance meets targets")
        return SLOAggregationReport(
            total_aggregations=len(self._records),
            total_rules=len(self._rules),
            compliant_rate_pct=compliant_rate,
            by_level=by_level,
            by_status=by_status,
            breaching_count=breaching_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("slo_aggregator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_aggregations": len(self._records),
            "total_rules": len(self._rules),
            "min_compliance_pct": self._min_compliance_pct,
            "level_distribution": level_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
