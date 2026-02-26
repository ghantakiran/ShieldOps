"""Audit Intelligence Analyzer — AI-powered audit analysis, anomaly detection, risk scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AuditCategory(StrEnum):
    ACCESS = "access"
    CHANGE = "change"
    COMPLIANCE = "compliance"
    SECURITY = "security"
    FINANCIAL = "financial"


class AuditRiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class AuditPattern(StrEnum):
    NORMAL = "normal"
    UNUSUAL_TIMING = "unusual_timing"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    BULK_OPERATION = "bulk_operation"
    POLICY_BYPASS = "policy_bypass"


# --- Models ---


class AuditFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_name: str = ""
    category: AuditCategory = AuditCategory.COMPLIANCE
    risk_level: AuditRiskLevel = AuditRiskLevel.MEDIUM
    pattern: AuditPattern = AuditPattern.NORMAL
    affected_resource: str = ""
    deviation_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditAnomaly(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_name: str = ""
    category: AuditCategory = AuditCategory.COMPLIANCE
    risk_level: AuditRiskLevel = AuditRiskLevel.MEDIUM
    pattern: AuditPattern = AuditPattern.UNUSUAL_TIMING
    baseline_value: float = 0.0
    observed_value: float = 0.0
    created_at: float = Field(default_factory=time.time)


class AuditIntelligenceReport(BaseModel):
    total_findings: int = 0
    total_anomalies: int = 0
    avg_deviation_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    high_risk_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditIntelligenceAnalyzer:
    """AI-powered audit analysis, anomaly detection, and risk scoring."""

    def __init__(
        self,
        max_records: int = 200000,
        anomaly_threshold_pct: float = 200.0,
    ) -> None:
        self._max_records = max_records
        self._anomaly_threshold_pct = anomaly_threshold_pct
        self._records: list[AuditFinding] = []
        self._anomalies: list[AuditAnomaly] = []
        logger.info(
            "audit_intelligence.initialized",
            max_records=max_records,
            anomaly_threshold_pct=anomaly_threshold_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _deviation_to_risk(self, deviation: float) -> AuditRiskLevel:
        if deviation >= 500:
            return AuditRiskLevel.CRITICAL
        if deviation >= 300:
            return AuditRiskLevel.HIGH
        if deviation >= 150:
            return AuditRiskLevel.MEDIUM
        if deviation >= 50:
            return AuditRiskLevel.LOW
        return AuditRiskLevel.INFORMATIONAL

    # -- record / get / list ---------------------------------------------

    def record_finding(
        self,
        finding_name: str,
        category: AuditCategory = AuditCategory.COMPLIANCE,
        risk_level: AuditRiskLevel | None = None,
        pattern: AuditPattern = AuditPattern.NORMAL,
        affected_resource: str = "",
        deviation_pct: float = 0.0,
        details: str = "",
    ) -> AuditFinding:
        if risk_level is None:
            risk_level = self._deviation_to_risk(deviation_pct)
        record = AuditFinding(
            finding_name=finding_name,
            category=category,
            risk_level=risk_level,
            pattern=pattern,
            affected_resource=affected_resource,
            deviation_pct=deviation_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_intelligence.finding_recorded",
            record_id=record.id,
            finding_name=finding_name,
            risk_level=risk_level.value,
        )
        return record

    def get_finding(self, record_id: str) -> AuditFinding | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_findings(
        self,
        category: AuditCategory | None = None,
        risk_level: AuditRiskLevel | None = None,
        limit: int = 50,
    ) -> list[AuditFinding]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.category == category]
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        return results[-limit:]

    def record_anomaly(
        self,
        anomaly_name: str,
        category: AuditCategory = AuditCategory.COMPLIANCE,
        risk_level: AuditRiskLevel = AuditRiskLevel.MEDIUM,
        pattern: AuditPattern = AuditPattern.UNUSUAL_TIMING,
        baseline_value: float = 0.0,
        observed_value: float = 0.0,
    ) -> AuditAnomaly:
        anomaly = AuditAnomaly(
            anomaly_name=anomaly_name,
            category=category,
            risk_level=risk_level,
            pattern=pattern,
            baseline_value=baseline_value,
            observed_value=observed_value,
        )
        self._anomalies.append(anomaly)
        if len(self._anomalies) > self._max_records:
            self._anomalies = self._anomalies[-self._max_records :]
        logger.info(
            "audit_intelligence.anomaly_recorded",
            anomaly_name=anomaly_name,
            risk_level=risk_level.value,
        )
        return anomaly

    # -- domain operations -----------------------------------------------

    def analyze_audit_patterns(self, category: str) -> dict[str, Any]:
        """Analyze audit patterns for a specific category."""
        records = [r for r in self._records if r.category.value == category]
        if not records:
            return {"category": category, "status": "no_data"}
        latest = records[-1]
        return {
            "category": category,
            "total_findings": len(records),
            "latest_risk_level": latest.risk_level.value,
            "latest_pattern": latest.pattern.value,
            "avg_deviation_pct": round(
                sum(r.deviation_pct for r in records) / len(records),
                2,
            ),
        }

    def identify_high_risk_findings(self) -> list[dict[str, Any]]:
        """Find findings with risk level >= HIGH."""
        high = {AuditRiskLevel.CRITICAL, AuditRiskLevel.HIGH}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_level in high:
                results.append(
                    {
                        "finding_name": r.finding_name,
                        "category": r.category.value,
                        "risk_level": r.risk_level.value,
                        "deviation_pct": r.deviation_pct,
                    }
                )
        results.sort(key=lambda x: x["deviation_pct"], reverse=True)
        return results

    def rank_by_anomaly_deviation(self) -> list[dict[str, Any]]:
        """Rank anomalies by deviation from baseline."""
        results: list[dict[str, Any]] = []
        for a in self._anomalies:
            deviation = (
                abs(a.observed_value - a.baseline_value) / a.baseline_value * 100
                if a.baseline_value > 0
                else 0.0
            )
            results.append(
                {
                    "anomaly_name": a.anomaly_name,
                    "category": a.category.value,
                    "baseline_value": a.baseline_value,
                    "observed_value": a.observed_value,
                    "deviation_pct": round(deviation, 2),
                }
            )
        results.sort(key=lambda x: x["deviation_pct"], reverse=True)
        return results

    def detect_suspicious_patterns(self) -> list[dict[str, Any]]:
        """Detect suspicious audit patterns."""
        suspicious = {
            AuditPattern.PRIVILEGE_ESCALATION,
            AuditPattern.BULK_OPERATION,
            AuditPattern.POLICY_BYPASS,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.pattern in suspicious:
                results.append(
                    {
                        "finding_name": r.finding_name,
                        "pattern": r.pattern.value,
                        "category": r.category.value,
                        "risk_level": r.risk_level.value,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> AuditIntelligenceReport:
        by_category: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_risk[r.risk_level.value] = by_risk.get(r.risk_level.value, 0) + 1
        avg_dev = (
            round(
                sum(r.deviation_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high = {AuditRiskLevel.CRITICAL, AuditRiskLevel.HIGH}
        high_count = sum(1 for r in self._records if r.risk_level in high)
        recs: list[str] = []
        if high_count > 0:
            recs.append(f"{high_count} high/critical risk finding(s)")
        suspicious = sum(
            1
            for r in self._records
            if r.pattern
            in {
                AuditPattern.PRIVILEGE_ESCALATION,
                AuditPattern.BULK_OPERATION,
                AuditPattern.POLICY_BYPASS,
            }
        )
        if suspicious > 0:
            recs.append(f"{suspicious} suspicious pattern(s) detected")
        if not recs:
            recs.append("Audit intelligence within normal parameters")
        return AuditIntelligenceReport(
            total_findings=len(self._records),
            total_anomalies=len(self._anomalies),
            avg_deviation_pct=avg_dev,
            by_category=by_category,
            by_risk_level=by_risk,
            high_risk_count=high_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._anomalies.clear()
        logger.info("audit_intelligence.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_findings": len(self._records),
            "total_anomalies": len(self._anomalies),
            "anomaly_threshold_pct": self._anomaly_threshold_pct,
            "category_distribution": cat_dist,
            "unique_resources": len({r.affected_resource for r in self._records}),
        }
