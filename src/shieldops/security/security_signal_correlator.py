"""Security Signal Correlator — correlate signals across sources."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SignalSource(StrEnum):
    WAF = "waf"
    IDS_IPS = "ids_ips"
    SIEM = "siem"
    CLOUD_AUDIT = "cloud_audit"
    ENDPOINT_AGENT = "endpoint_agent"


class CorrelationPattern(StrEnum):
    LATERAL_MOVEMENT = "lateral_movement"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    RECONNAISSANCE = "reconnaissance"
    PERSISTENCE = "persistence"


class ThreatSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class SignalRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_name: str = ""
    signal_source: SignalSource = SignalSource.WAF
    correlation_pattern: CorrelationPattern = CorrelationPattern.LATERAL_MOVEMENT
    threat_severity: ThreatSeverity = ThreatSeverity.CRITICAL
    confidence_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SignalCorrelation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_name: str = ""
    signal_source: SignalSource = SignalSource.WAF
    correlation_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecuritySignalReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_correlations: int = 0
    low_confidence_count: int = 0
    avg_confidence_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_pattern: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_low_confidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecuritySignalCorrelator:
    """Correlate security signals across sources, detect threat patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        correlation_confidence_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._correlation_confidence_threshold = correlation_confidence_threshold
        self._records: list[SignalRecord] = []
        self._correlations: list[SignalCorrelation] = []
        logger.info(
            "security_signal_correlator.initialized",
            max_records=max_records,
            correlation_confidence_threshold=correlation_confidence_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_signal(
        self,
        signal_name: str,
        signal_source: SignalSource = SignalSource.WAF,
        correlation_pattern: CorrelationPattern = CorrelationPattern.LATERAL_MOVEMENT,
        threat_severity: ThreatSeverity = ThreatSeverity.CRITICAL,
        confidence_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SignalRecord:
        record = SignalRecord(
            signal_name=signal_name,
            signal_source=signal_source,
            correlation_pattern=correlation_pattern,
            threat_severity=threat_severity,
            confidence_score=confidence_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_signal_correlator.signal_recorded",
            record_id=record.id,
            signal_name=signal_name,
            signal_source=signal_source.value,
            correlation_pattern=correlation_pattern.value,
        )
        return record

    def get_signal(self, record_id: str) -> SignalRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_signals(
        self,
        signal_source: SignalSource | None = None,
        correlation_pattern: CorrelationPattern | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SignalRecord]:
        results = list(self._records)
        if signal_source is not None:
            results = [r for r in results if r.signal_source == signal_source]
        if correlation_pattern is not None:
            results = [r for r in results if r.correlation_pattern == correlation_pattern]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_correlation(
        self,
        signal_name: str,
        signal_source: SignalSource = SignalSource.WAF,
        correlation_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SignalCorrelation:
        correlation = SignalCorrelation(
            signal_name=signal_name,
            signal_source=signal_source,
            correlation_score=correlation_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._correlations.append(correlation)
        if len(self._correlations) > self._max_records:
            self._correlations = self._correlations[-self._max_records :]
        logger.info(
            "security_signal_correlator.correlation_added",
            signal_name=signal_name,
            signal_source=signal_source.value,
            correlation_score=correlation_score,
        )
        return correlation

    # -- domain operations --------------------------------------------------

    def analyze_signal_distribution(self) -> dict[str, Any]:
        """Group by signal_source; return count and avg confidence_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.signal_source.value
            src_data.setdefault(key, []).append(r.confidence_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_confidence_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_confidence_signals(self) -> list[dict[str, Any]]:
        """Return records where confidence_score < correlation_confidence_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.confidence_score < self._correlation_confidence_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "signal_name": r.signal_name,
                        "signal_source": r.signal_source.value,
                        "confidence_score": r.confidence_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["confidence_score"])

    def rank_by_confidence(self) -> list[dict[str, Any]]:
        """Group by service, avg confidence_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_confidence_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_confidence_score"])
        return results

    def detect_signal_trends(self) -> dict[str, Any]:
        """Split-half comparison on correlation_score; delta threshold 5.0."""
        if len(self._correlations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.correlation_score for c in self._correlations]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> SecuritySignalReport:
        by_source: dict[str, int] = {}
        by_pattern: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_source[r.signal_source.value] = by_source.get(r.signal_source.value, 0) + 1
            by_pattern[r.correlation_pattern.value] = (
                by_pattern.get(r.correlation_pattern.value, 0) + 1
            )
            by_severity[r.threat_severity.value] = by_severity.get(r.threat_severity.value, 0) + 1
        low_confidence_count = sum(
            1 for r in self._records if r.confidence_score < self._correlation_confidence_threshold
        )
        scores = [r.confidence_score for r in self._records]
        avg_confidence_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_confidence_signals()
        top_low_confidence = [o["signal_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_confidence_count > 0:
            recs.append(
                f"{low_confidence_count} signal(s) below confidence threshold "
                f"({self._correlation_confidence_threshold})"
            )
        if self._records and avg_confidence_score < self._correlation_confidence_threshold:
            recs.append(
                f"Avg confidence score {avg_confidence_score} below threshold "
                f"({self._correlation_confidence_threshold})"
            )
        if not recs:
            recs.append("Security signal correlation confidence is healthy")
        return SecuritySignalReport(
            total_records=len(self._records),
            total_correlations=len(self._correlations),
            low_confidence_count=low_confidence_count,
            avg_confidence_score=avg_confidence_score,
            by_source=by_source,
            by_pattern=by_pattern,
            by_severity=by_severity,
            top_low_confidence=top_low_confidence,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._correlations.clear()
        logger.info("security_signal_correlator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.signal_source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_correlations": len(self._correlations),
            "correlation_confidence_threshold": self._correlation_confidence_threshold,
            "source_distribution": source_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
