"""Threat Intel Aggregator — aggregate/deduplicate/score IOCs from multiple feeds."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IOCType(StrEnum):
    IP_ADDRESS = "ip_address"
    DOMAIN = "domain"
    FILE_HASH = "file_hash"
    URL = "url"
    EMAIL = "email"


class FeedSource(StrEnum):
    STIX_TAXII = "stix_taxii"
    OSINT = "osint"
    COMMERCIAL = "commercial"
    INTERNAL = "internal"
    GOVERNMENT = "government"


class ThreatLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class IOCRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    indicator_value: str = ""
    ioc_type: IOCType = IOCType.IP_ADDRESS
    feed_source: FeedSource = FeedSource.STIX_TAXII
    threat_level: ThreatLevel = ThreatLevel.CRITICAL
    confidence_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class IOCCorrelation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    indicator_value: str = ""
    ioc_type: IOCType = IOCType.IP_ADDRESS
    correlation_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatIntelReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_correlations: int = 0
    low_confidence_count: int = 0
    avg_confidence_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_threat: dict[str, int] = Field(default_factory=dict)
    top_low_confidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatIntelAggregator:
    """Aggregate/deduplicate/score IOCs from multiple feeds (STIX/TAXII)."""

    def __init__(
        self,
        max_records: int = 200000,
        ioc_confidence_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._ioc_confidence_threshold = ioc_confidence_threshold
        self._records: list[IOCRecord] = []
        self._correlations: list[IOCCorrelation] = []
        logger.info(
            "threat_intel_aggregator.initialized",
            max_records=max_records,
            ioc_confidence_threshold=ioc_confidence_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_ioc(
        self,
        indicator_value: str,
        ioc_type: IOCType = IOCType.IP_ADDRESS,
        feed_source: FeedSource = FeedSource.STIX_TAXII,
        threat_level: ThreatLevel = ThreatLevel.CRITICAL,
        confidence_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> IOCRecord:
        record = IOCRecord(
            indicator_value=indicator_value,
            ioc_type=ioc_type,
            feed_source=feed_source,
            threat_level=threat_level,
            confidence_score=confidence_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_intel_aggregator.ioc_recorded",
            record_id=record.id,
            indicator_value=indicator_value,
            ioc_type=ioc_type.value,
            feed_source=feed_source.value,
        )
        return record

    def get_ioc(self, record_id: str) -> IOCRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_iocs(
        self,
        ioc_type: IOCType | None = None,
        feed_source: FeedSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[IOCRecord]:
        results = list(self._records)
        if ioc_type is not None:
            results = [r for r in results if r.ioc_type == ioc_type]
        if feed_source is not None:
            results = [r for r in results if r.feed_source == feed_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_correlation(
        self,
        indicator_value: str,
        ioc_type: IOCType = IOCType.IP_ADDRESS,
        correlation_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> IOCCorrelation:
        correlation = IOCCorrelation(
            indicator_value=indicator_value,
            ioc_type=ioc_type,
            correlation_score=correlation_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._correlations.append(correlation)
        if len(self._correlations) > self._max_records:
            self._correlations = self._correlations[-self._max_records :]
        logger.info(
            "threat_intel_aggregator.correlation_added",
            indicator_value=indicator_value,
            ioc_type=ioc_type.value,
            correlation_score=correlation_score,
        )
        return correlation

    # -- domain operations --------------------------------------------------

    def analyze_ioc_distribution(self) -> dict[str, Any]:
        """Group by ioc_type; return count and avg confidence_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.ioc_type.value
            type_data.setdefault(key, []).append(r.confidence_score)
        result: dict[str, Any] = {}
        for itype, scores in type_data.items():
            result[itype] = {
                "count": len(scores),
                "avg_confidence_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_confidence_iocs(self) -> list[dict[str, Any]]:
        """Return records where confidence_score < ioc_confidence_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.confidence_score < self._ioc_confidence_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "indicator_value": r.indicator_value,
                        "ioc_type": r.ioc_type.value,
                        "confidence_score": r.confidence_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["confidence_score"])

    def rank_by_confidence(self) -> list[dict[str, Any]]:
        """Group by service, avg confidence_score, sort ascending."""
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

    def detect_intel_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ThreatIntelReport:
        by_type: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_threat: dict[str, int] = {}
        for r in self._records:
            by_type[r.ioc_type.value] = by_type.get(r.ioc_type.value, 0) + 1
            by_source[r.feed_source.value] = by_source.get(r.feed_source.value, 0) + 1
            by_threat[r.threat_level.value] = by_threat.get(r.threat_level.value, 0) + 1
        low_confidence_count = sum(
            1 for r in self._records if r.confidence_score < self._ioc_confidence_threshold
        )
        scores = [r.confidence_score for r in self._records]
        avg_confidence_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_confidence_iocs()
        top_low_confidence = [o["indicator_value"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_confidence_count > 0:
            recs.append(
                f"{low_confidence_count} IOC(s) below confidence threshold "
                f"({self._ioc_confidence_threshold})"
            )
        if self._records and avg_confidence_score < self._ioc_confidence_threshold:
            recs.append(
                f"Avg confidence score {avg_confidence_score} below threshold "
                f"({self._ioc_confidence_threshold})"
            )
        if not recs:
            recs.append("Threat intelligence confidence is healthy")
        return ThreatIntelReport(
            total_records=len(self._records),
            total_correlations=len(self._correlations),
            low_confidence_count=low_confidence_count,
            avg_confidence_score=avg_confidence_score,
            by_type=by_type,
            by_source=by_source,
            by_threat=by_threat,
            top_low_confidence=top_low_confidence,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._correlations.clear()
        logger.info("threat_intel_aggregator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.ioc_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_correlations": len(self._correlations),
            "ioc_confidence_threshold": self._ioc_confidence_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
