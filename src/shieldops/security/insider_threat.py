"""Insider Threat Detector — track insider threats, signals, and escalation patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatIndicator(StrEnum):
    UNUSUAL_ACCESS = "unusual_access"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ABUSE = "privilege_abuse"
    POLICY_VIOLATION = "policy_violation"
    AFTER_HOURS_ACTIVITY = "after_hours_activity"


class ThreatLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    BASELINE = "baseline"


class ThreatCategory(StrEnum):
    MALICIOUS_INSIDER = "malicious_insider"
    COMPROMISED_ACCOUNT = "compromised_account"
    NEGLIGENT_USER = "negligent_user"
    DEPARTING_EMPLOYEE = "departing_employee"
    THIRD_PARTY = "third_party"


# --- Models ---


class ThreatRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    threat_indicator: ThreatIndicator = ThreatIndicator.UNUSUAL_ACCESS
    threat_level: ThreatLevel = ThreatLevel.LOW
    threat_category: ThreatCategory = ThreatCategory.NEGLIGENT_USER
    threat_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    threat_indicator: ThreatIndicator = ThreatIndicator.UNUSUAL_ACCESS
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InsiderThreatReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_signals: int = 0
    high_risk_users: int = 0
    avg_threat_score: float = 0.0
    by_indicator: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_risky: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class InsiderThreatDetector:
    """Track insider threats, identify high-risk users, and detect escalation patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        min_threat_confidence_pct: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._min_threat_confidence_pct = min_threat_confidence_pct
        self._records: list[ThreatRecord] = []
        self._signals: list[ThreatSignal] = []
        logger.info(
            "insider_threat.initialized",
            max_records=max_records,
            min_threat_confidence_pct=min_threat_confidence_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_threat(
        self,
        user_id: str,
        threat_indicator: ThreatIndicator = ThreatIndicator.UNUSUAL_ACCESS,
        threat_level: ThreatLevel = ThreatLevel.LOW,
        threat_category: ThreatCategory = ThreatCategory.NEGLIGENT_USER,
        threat_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ThreatRecord:
        record = ThreatRecord(
            user_id=user_id,
            threat_indicator=threat_indicator,
            threat_level=threat_level,
            threat_category=threat_category,
            threat_score=threat_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "insider_threat.threat_recorded",
            record_id=record.id,
            user_id=user_id,
            threat_indicator=threat_indicator.value,
            threat_level=threat_level.value,
        )
        return record

    def get_threat(self, record_id: str) -> ThreatRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_threats(
        self,
        indicator: ThreatIndicator | None = None,
        level: ThreatLevel | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ThreatRecord]:
        results = list(self._records)
        if indicator is not None:
            results = [r for r in results if r.threat_indicator == indicator]
        if level is not None:
            results = [r for r in results if r.threat_level == level]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_signal(
        self,
        user_id: str,
        threat_indicator: ThreatIndicator = ThreatIndicator.UNUSUAL_ACCESS,
        value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ThreatSignal:
        signal = ThreatSignal(
            user_id=user_id,
            threat_indicator=threat_indicator,
            value=value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._signals.append(signal)
        if len(self._signals) > self._max_records:
            self._signals = self._signals[-self._max_records :]
        logger.info(
            "insider_threat.signal_added",
            user_id=user_id,
            threat_indicator=threat_indicator.value,
            value=value,
        )
        return signal

    # -- domain operations --------------------------------------------------

    def analyze_threat_patterns(self) -> dict[str, Any]:
        """Group by indicator; return count and avg threat score per indicator."""
        indicator_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.threat_indicator.value
            indicator_data.setdefault(key, []).append(r.threat_score)
        result: dict[str, Any] = {}
        for indicator, scores in indicator_data.items():
            result[indicator] = {
                "count": len(scores),
                "avg_threat_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_risk_users(self) -> list[dict[str, Any]]:
        """Return records where level == CRITICAL or HIGH."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.threat_level in (
                ThreatLevel.CRITICAL,
                ThreatLevel.HIGH,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "user_id": r.user_id,
                        "threat_indicator": r.threat_indicator.value,
                        "threat_level": r.threat_level.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_threat_score(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg score."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.threat_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(scores),
                    "avg_threat_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_threat_score"], reverse=True)
        return results

    def detect_threat_escalation(self) -> dict[str, Any]:
        """Split-half on value; delta threshold 5.0."""
        if len(self._signals) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [s.value for s in self._signals]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> InsiderThreatReport:
        by_indicator: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_indicator[r.threat_indicator.value] = (
                by_indicator.get(r.threat_indicator.value, 0) + 1
            )
            by_level[r.threat_level.value] = by_level.get(r.threat_level.value, 0) + 1
            by_category[r.threat_category.value] = by_category.get(r.threat_category.value, 0) + 1
        high_risk_count = sum(
            1 for r in self._records if r.threat_level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH)
        )
        scores = [r.threat_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        rankings = self.rank_by_threat_score()
        top_risky = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        high_risk_rate = (
            round(high_risk_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        if high_risk_rate > (100.0 - self._min_threat_confidence_pct):
            recs.append(
                f"High risk rate {high_risk_rate}% exceeds threshold"
                f" ({100.0 - self._min_threat_confidence_pct}%)"
            )
        if high_risk_count > 0:
            recs.append(f"{high_risk_count} high-risk user(s) detected — review threats")
        if not recs:
            recs.append("Insider threat posture is acceptable")
        return InsiderThreatReport(
            total_records=len(self._records),
            total_signals=len(self._signals),
            high_risk_users=high_risk_count,
            avg_threat_score=avg_score,
            by_indicator=by_indicator,
            by_level=by_level,
            by_category=by_category,
            top_risky=top_risky,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._signals.clear()
        logger.info("insider_threat.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        indicator_dist: dict[str, int] = {}
        for r in self._records:
            key = r.threat_indicator.value
            indicator_dist[key] = indicator_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_signals": len(self._signals),
            "min_threat_confidence_pct": self._min_threat_confidence_pct,
            "indicator_distribution": indicator_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_users": len({r.user_id for r in self._records}),
        }
