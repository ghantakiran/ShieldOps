"""Risk Signal Aggregator — unified risk posture from multi-domain signals."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SignalDomain(StrEnum):
    SECURITY = "security"
    RELIABILITY = "reliability"
    COST = "cost"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"


class SignalSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AggregationMethod(StrEnum):
    WEIGHTED_AVERAGE = "weighted_average"
    MAX_SEVERITY = "max_severity"
    BAYESIAN = "bayesian"
    EXPONENTIAL_DECAY = "exponential_decay"
    CUSTOM = "custom"


# --- Models ---


class RiskSignalRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    signal_domain: SignalDomain = SignalDomain.SECURITY
    signal_severity: SignalSeverity = SignalSeverity.MEDIUM
    aggregation_method: AggregationMethod = AggregationMethod.WEIGHTED_AVERAGE
    risk_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AggregatedRiskScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    score_label: str = ""
    signal_domain: SignalDomain = SignalDomain.SECURITY
    signal_severity: SignalSeverity = SignalSeverity.MEDIUM
    weighted_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class RiskSignalReport(BaseModel):
    total_signals: int = 0
    total_scores: int = 0
    critical_rate_pct: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    high_risk_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskSignalAggregator:
    """Unified risk posture from multi-domain signals."""

    def __init__(
        self,
        max_records: int = 200000,
        critical_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._critical_threshold = critical_threshold
        self._records: list[RiskSignalRecord] = []
        self._scores: list[AggregatedRiskScore] = []
        logger.info(
            "risk_aggregator.initialized",
            max_records=max_records,
            critical_threshold=critical_threshold,
        )

    # -- record / get / list ---------------------------------------------

    def record_signal(
        self,
        service_name: str,
        signal_domain: SignalDomain = SignalDomain.SECURITY,
        signal_severity: SignalSeverity = SignalSeverity.MEDIUM,
        aggregation_method: AggregationMethod = AggregationMethod.WEIGHTED_AVERAGE,
        risk_score: float = 0.0,
        details: str = "",
    ) -> RiskSignalRecord:
        record = RiskSignalRecord(
            service_name=service_name,
            signal_domain=signal_domain,
            signal_severity=signal_severity,
            aggregation_method=aggregation_method,
            risk_score=risk_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_aggregator.signal_recorded",
            record_id=record.id,
            service_name=service_name,
            signal_domain=signal_domain.value,
            signal_severity=signal_severity.value,
        )
        return record

    def get_signal(self, record_id: str) -> RiskSignalRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_signals(
        self,
        service_name: str | None = None,
        signal_domain: SignalDomain | None = None,
        limit: int = 50,
    ) -> list[RiskSignalRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if signal_domain is not None:
            results = [r for r in results if r.signal_domain == signal_domain]
        return results[-limit:]

    def add_score(
        self,
        score_label: str,
        signal_domain: SignalDomain = SignalDomain.SECURITY,
        signal_severity: SignalSeverity = SignalSeverity.MEDIUM,
        weighted_score: float = 0.0,
    ) -> AggregatedRiskScore:
        score = AggregatedRiskScore(
            score_label=score_label,
            signal_domain=signal_domain,
            signal_severity=signal_severity,
            weighted_score=weighted_score,
        )
        self._scores.append(score)
        if len(self._scores) > self._max_records:
            self._scores = self._scores[-self._max_records :]
        logger.info(
            "risk_aggregator.score_added",
            score_label=score_label,
            signal_domain=signal_domain.value,
            signal_severity=signal_severity.value,
        )
        return score

    # -- domain operations -----------------------------------------------

    def analyze_service_risk(self, service_name: str) -> dict[str, Any]:
        """Analyze risk posture for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        criticals = sum(1 for r in records if r.signal_severity == SignalSeverity.CRITICAL)
        critical_rate = round(criticals / len(records) * 100, 2)
        avg_score = round(sum(r.risk_score for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total_signals": len(records),
            "critical_count": criticals,
            "critical_rate_pct": critical_rate,
            "avg_risk_score": avg_score,
            "meets_threshold": avg_score >= self._critical_threshold,
        }

    def identify_high_risk_services(self) -> list[dict[str, Any]]:
        """Find services with repeated critical/high severity signals."""
        high_counts: dict[str, int] = {}
        for r in self._records:
            if r.signal_severity in (
                SignalSeverity.CRITICAL,
                SignalSeverity.HIGH,
            ):
                high_counts[r.service_name] = high_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in high_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "high_risk_count": count,
                    }
                )
        results.sort(key=lambda x: x["high_risk_count"], reverse=True)
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Rank services by signal count descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.service_name] = freq.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in freq.items():
            results.append(
                {
                    "service_name": svc,
                    "signal_count": count,
                }
            )
        results.sort(key=lambda x: x["signal_count"], reverse=True)
        return results

    def detect_risk_escalations(self) -> list[dict[str, Any]]:
        """Detect services with risk escalations (>3 non-info signals)."""
        svc_non_info: dict[str, int] = {}
        for r in self._records:
            if r.signal_severity != SignalSeverity.INFO:
                svc_non_info[r.service_name] = svc_non_info.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_non_info.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "non_info_count": count,
                        "escalation_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_info_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RiskSignalReport:
        by_domain: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_domain[r.signal_domain.value] = by_domain.get(r.signal_domain.value, 0) + 1
            by_severity[r.signal_severity.value] = by_severity.get(r.signal_severity.value, 0) + 1
        critical_count = sum(
            1 for r in self._records if r.signal_severity == SignalSeverity.CRITICAL
        )
        critical_rate = (
            round(critical_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        high_risk = sum(1 for d in self.identify_high_risk_services())
        recs: list[str] = []
        if critical_rate > 0:
            recs.append(f"Critical rate {critical_rate}% exceeds 0% baseline")
        if high_risk > 0:
            recs.append(f"{high_risk} service(s) with high risk signals")
        escalations = len(self.detect_risk_escalations())
        if escalations > 0:
            recs.append(f"{escalations} service(s) detected with risk escalations")
        if not recs:
            recs.append("Risk signal aggregation meets targets")
        return RiskSignalReport(
            total_signals=len(self._records),
            total_scores=len(self._scores),
            critical_rate_pct=critical_rate,
            by_domain=by_domain,
            by_severity=by_severity,
            high_risk_count=high_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._scores.clear()
        logger.info("risk_aggregator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.signal_domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_signals": len(self._records),
            "total_scores": len(self._scores),
            "critical_threshold": self._critical_threshold,
            "domain_distribution": domain_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
