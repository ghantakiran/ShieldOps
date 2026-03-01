"""Threat Intelligence Correlator — correlate threat intel across sources and services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatSource(StrEnum):
    EXTERNAL_FEED = "external_feed"
    INTERNAL_DETECTION = "internal_detection"
    VENDOR_ADVISORY = "vendor_advisory"
    COMMUNITY = "community"
    GOVERNMENT = "government"


class ThreatSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class ThreatRelevance(StrEnum):
    DIRECT_MATCH = "direct_match"
    RELATED = "related"
    POTENTIAL = "potential"
    UNLIKELY = "unlikely"
    NOT_APPLICABLE = "not_applicable"


# --- Models ---


class ThreatRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_id: str = ""
    source: ThreatSource = ThreatSource.EXTERNAL_FEED
    severity: ThreatSeverity = ThreatSeverity.LOW
    relevance: ThreatRelevance = ThreatRelevance.POTENTIAL
    relevance_score: float = 0.0
    affected_service: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatCorrelation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_record_id: str = ""
    correlated_threat_id: str = ""
    correlation_score: float = 0.0
    correlation_type: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatCorrelatorReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_correlations: int = 0
    critical_threats: int = 0
    avg_relevance_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_relevance: dict[str, int] = Field(default_factory=dict)
    high_risk_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatIntelligenceCorrelator:
    """Correlate threat intelligence records across sources, severity, and services."""

    def __init__(
        self,
        max_records: int = 200000,
        min_relevance_score: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_relevance_score = min_relevance_score
        self._records: list[ThreatRecord] = []
        self._correlations: list[ThreatCorrelation] = []
        logger.info(
            "threat_correlator.initialized",
            max_records=max_records,
            min_relevance_score=min_relevance_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_threat(
        self,
        threat_id: str,
        source: ThreatSource = ThreatSource.EXTERNAL_FEED,
        severity: ThreatSeverity = ThreatSeverity.LOW,
        relevance: ThreatRelevance = ThreatRelevance.POTENTIAL,
        relevance_score: float = 0.0,
        affected_service: str = "",
        details: str = "",
    ) -> ThreatRecord:
        record = ThreatRecord(
            threat_id=threat_id,
            source=source,
            severity=severity,
            relevance=relevance,
            relevance_score=relevance_score,
            affected_service=affected_service,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_correlator.threat_recorded",
            record_id=record.id,
            threat_id=threat_id,
            source=source.value,
            severity=severity.value,
            relevance_score=relevance_score,
        )
        return record

    def get_threat(self, record_id: str) -> ThreatRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_threats(
        self,
        source: ThreatSource | None = None,
        severity: ThreatSeverity | None = None,
        relevance: ThreatRelevance | None = None,
        limit: int = 50,
    ) -> list[ThreatRecord]:
        results = list(self._records)
        if source is not None:
            results = [r for r in results if r.source == source]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        if relevance is not None:
            results = [r for r in results if r.relevance == relevance]
        return results[-limit:]

    def add_correlation(
        self,
        threat_record_id: str,
        correlated_threat_id: str = "",
        correlation_score: float = 0.0,
        correlation_type: str = "",
    ) -> ThreatCorrelation:
        correlation = ThreatCorrelation(
            threat_record_id=threat_record_id,
            correlated_threat_id=correlated_threat_id,
            correlation_score=correlation_score,
            correlation_type=correlation_type,
        )
        self._correlations.append(correlation)
        if len(self._correlations) > self._max_records:
            self._correlations = self._correlations[-self._max_records :]
        logger.info(
            "threat_correlator.correlation_added",
            correlation_id=correlation.id,
            threat_record_id=threat_record_id,
            correlated_threat_id=correlated_threat_id,
            correlation_score=correlation_score,
        )
        return correlation

    # -- domain operations -----------------------------------------------

    def analyze_threat_landscape(self) -> list[dict[str, Any]]:
        """Group by source, count per source and avg relevance_score."""
        source_map: dict[str, list[float]] = {}
        for r in self._records:
            source_map.setdefault(r.source.value, []).append(r.relevance_score)
        results: list[dict[str, Any]] = []
        for src, scores in source_map.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append({"source": src, "count": len(scores), "avg_relevance_score": avg})
        results.sort(key=lambda x: x["avg_relevance_score"], reverse=True)
        return results

    def identify_critical_threats(self) -> list[dict[str, Any]]:
        """Find threats with severity CRITICAL or HIGH."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.severity in (ThreatSeverity.CRITICAL, ThreatSeverity.HIGH):
                results.append(
                    {
                        "record_id": r.id,
                        "threat_id": r.threat_id,
                        "source": r.source.value,
                        "severity": r.severity.value,
                        "relevance_score": r.relevance_score,
                        "affected_service": r.affected_service,
                    }
                )
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results

    def rank_by_relevance(self) -> list[dict[str, Any]]:
        """Group by affected_service, avg relevance_score, sort descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.affected_service, []).append(r.relevance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {"affected_service": svc, "avg_relevance_score": avg, "threat_count": len(scores)}
            )
        results.sort(key=lambda x: x["avg_relevance_score"], reverse=True)
        return results

    def detect_threat_trends(self) -> list[dict[str, Any]]:
        """Split-half on relevance_score; flag sources with delta > 5.0."""
        if len(self._records) < 2:
            return []
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def avg_score(recs: list[ThreatRecord], src: str) -> float:
            subset = [r.relevance_score for r in recs if r.source.value == src]
            return sum(subset) / len(subset) if subset else 0.0

        sources = {r.source.value for r in self._records}
        results: list[dict[str, Any]] = []
        for src in sources:
            early = avg_score(first_half, src)
            late = avg_score(second_half, src)
            delta = round(late - early, 2)
            if abs(delta) > 5.0:
                results.append(
                    {
                        "source": src,
                        "early_avg": round(early, 2),
                        "late_avg": round(late, 2),
                        "delta": delta,
                        "trend": "escalating" if delta > 0 else "declining",
                    }
                )
        results.sort(key=lambda x: abs(x["delta"]), reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ThreatCorrelatorReport:
        by_source: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_relevance: dict[str, int] = {}
        for r in self._records:
            by_source[r.source.value] = by_source.get(r.source.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
            by_relevance[r.relevance.value] = by_relevance.get(r.relevance.value, 0) + 1
        avg_score = (
            round(sum(r.relevance_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        critical = sum(
            1 for r in self._records if r.severity in (ThreatSeverity.CRITICAL, ThreatSeverity.HIGH)
        )
        ranked = self.rank_by_relevance()
        high_risk = [
            item["affected_service"]
            for item in ranked
            if item["avg_relevance_score"] >= self._min_relevance_score and item["affected_service"]
        ]
        recs: list[str] = []
        if critical > 0:
            recs.append(f"{critical} critical/high severity threat(s) detected")
        below_min = sum(1 for r in self._records if r.relevance_score < self._min_relevance_score)
        if below_min > 0:
            recs.append(
                f"{below_min} threat(s) below minimum relevance score of "
                f"{self._min_relevance_score}"
            )
        if not recs:
            recs.append("No critical threats detected; threat landscape nominal")
        return ThreatCorrelatorReport(
            total_records=len(self._records),
            total_correlations=len(self._correlations),
            critical_threats=critical,
            avg_relevance_score=avg_score,
            by_source=by_source,
            by_severity=by_severity,
            by_relevance=by_relevance,
            high_risk_services=high_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._correlations.clear()
        logger.info("threat_correlator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        severity_dist: dict[str, int] = {}
        for r in self._records:
            key = r.severity.value
            severity_dist[key] = severity_dist.get(key, 0) + 1
        return {
            "total_threats": len(self._records),
            "total_correlations": len(self._correlations),
            "min_relevance_score": self._min_relevance_score,
            "severity_distribution": severity_dist,
            "unique_services": len({r.affected_service for r in self._records}),
        }
