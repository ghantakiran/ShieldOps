"""Threat Intelligence Tracker — track threat intelligence feeds and indicators."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatCategory(StrEnum):
    MALWARE = "malware"
    PHISHING = "phishing"
    EXPLOITATION = "exploitation"
    DATA_EXFILTRATION = "data_exfiltration"
    INSIDER_THREAT = "insider_threat"


class ThreatSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class IndicatorType(StrEnum):
    IP_ADDRESS = "ip_address"
    DOMAIN = "domain"
    FILE_HASH = "file_hash"
    URL = "url"
    EMAIL = "email"


# --- Models ---


class ThreatRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    indicator_id: str = ""
    threat_category: ThreatCategory = ThreatCategory.MALWARE
    threat_severity: ThreatSeverity = ThreatSeverity.INFORMATIONAL
    indicator_type: IndicatorType = IndicatorType.IP_ADDRESS
    confidence_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatIndicator(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    indicator_id: str = ""
    threat_category: ThreatCategory = ThreatCategory.MALWARE
    indicator_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatIntelligenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_indicators: int = 0
    critical_threats: int = 0
    avg_confidence_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_indicator_type: dict[str, int] = Field(default_factory=dict)
    top_threats: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatIntelligenceTracker:
    """Track threat intelligence feeds and indicators."""

    def __init__(
        self,
        max_records: int = 200000,
        min_threat_confidence_pct: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_threat_confidence_pct = min_threat_confidence_pct
        self._records: list[ThreatRecord] = []
        self._indicators: list[ThreatIndicator] = []
        logger.info(
            "threat_intelligence.initialized",
            max_records=max_records,
            min_threat_confidence_pct=min_threat_confidence_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_threat(
        self,
        indicator_id: str,
        threat_category: ThreatCategory = ThreatCategory.MALWARE,
        threat_severity: ThreatSeverity = ThreatSeverity.INFORMATIONAL,
        indicator_type: IndicatorType = IndicatorType.IP_ADDRESS,
        confidence_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ThreatRecord:
        record = ThreatRecord(
            indicator_id=indicator_id,
            threat_category=threat_category,
            threat_severity=threat_severity,
            indicator_type=indicator_type,
            confidence_pct=confidence_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_intelligence.threat_recorded",
            record_id=record.id,
            indicator_id=indicator_id,
            threat_category=threat_category.value,
            threat_severity=threat_severity.value,
        )
        return record

    def get_threat(self, record_id: str) -> ThreatRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_threats(
        self,
        category: ThreatCategory | None = None,
        severity: ThreatSeverity | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ThreatRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.threat_category == category]
        if severity is not None:
            results = [r for r in results if r.threat_severity == severity]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_indicator(
        self,
        indicator_id: str,
        threat_category: ThreatCategory = ThreatCategory.MALWARE,
        indicator_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ThreatIndicator:
        indicator = ThreatIndicator(
            indicator_id=indicator_id,
            threat_category=threat_category,
            indicator_score=indicator_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._indicators.append(indicator)
        if len(self._indicators) > self._max_records:
            self._indicators = self._indicators[-self._max_records :]
        logger.info(
            "threat_intelligence.indicator_added",
            indicator_id=indicator_id,
            threat_category=threat_category.value,
            indicator_score=indicator_score,
        )
        return indicator

    # -- domain operations --------------------------------------------------

    def analyze_threat_distribution(self) -> dict[str, Any]:
        """Group by threat_category; return count and avg confidence_pct per category."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.threat_category.value
            cat_data.setdefault(key, []).append(r.confidence_pct)
        result: dict[str, Any] = {}
        for category, pcts in cat_data.items():
            result[category] = {
                "count": len(pcts),
                "avg_confidence_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_critical_threats(self) -> list[dict[str, Any]]:
        """Return records where threat_severity is CRITICAL."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.threat_severity == ThreatSeverity.CRITICAL:
                results.append(
                    {
                        "record_id": r.id,
                        "indicator_id": r.indicator_id,
                        "threat_category": r.threat_category.value,
                        "confidence_pct": r.confidence_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_confidence(self) -> list[dict[str, Any]]:
        """Group by service, avg confidence_pct, sort descending."""
        svc_pcts: dict[str, list[float]] = {}
        for r in self._records:
            svc_pcts.setdefault(r.service, []).append(r.confidence_pct)
        results: list[dict[str, Any]] = []
        for service, pcts in svc_pcts.items():
            results.append(
                {
                    "service": service,
                    "avg_confidence_pct": round(sum(pcts) / len(pcts), 2),
                    "threat_count": len(pcts),
                }
            )
        results.sort(key=lambda x: x["avg_confidence_pct"], reverse=True)
        return results

    def detect_threat_trends(self) -> dict[str, Any]:
        """Split-half comparison on indicator_score; delta threshold 5.0."""
        if len(self._indicators) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [i.indicator_score for i in self._indicators]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> ThreatIntelligenceReport:
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_indicator_type: dict[str, int] = {}
        for r in self._records:
            by_category[r.threat_category.value] = by_category.get(r.threat_category.value, 0) + 1
            by_severity[r.threat_severity.value] = by_severity.get(r.threat_severity.value, 0) + 1
            by_indicator_type[r.indicator_type.value] = (
                by_indicator_type.get(r.indicator_type.value, 0) + 1
            )
        critical_threats = sum(
            1 for r in self._records if r.threat_severity == ThreatSeverity.CRITICAL
        )
        avg_confidence_pct = (
            round(
                sum(r.confidence_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        rankings = self.rank_by_confidence()
        top_threats = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if critical_threats > 0:
            recs.append(
                f"{critical_threats} critical threat(s) detected — review threat intelligence"
            )
        critical_pct = (
            round(critical_threats / len(self._records) * 100, 2) if self._records else 0.0
        )
        if critical_pct > self._min_threat_confidence_pct:
            recs.append(
                f"Critical threat rate {critical_pct}% exceeds "
                f"threshold ({self._min_threat_confidence_pct}%)"
            )
        if not recs:
            recs.append("Threat intelligence levels are healthy")
        return ThreatIntelligenceReport(
            total_records=len(self._records),
            total_indicators=len(self._indicators),
            critical_threats=critical_threats,
            avg_confidence_pct=avg_confidence_pct,
            by_category=by_category,
            by_severity=by_severity,
            by_indicator_type=by_indicator_type,
            top_threats=top_threats,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._indicators.clear()
        logger.info("threat_intelligence.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.threat_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_indicators": len(self._indicators),
            "min_threat_confidence_pct": self._min_threat_confidence_pct,
            "category_distribution": category_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
