"""Traffic Pattern Intelligence.

Detect traffic anomalies, classify seasonality patterns,
and predict traffic shifts across services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PatternType(StrEnum):
    SEASONAL = "seasonal"
    EVENT_DRIVEN = "event_driven"
    ORGANIC = "organic"
    ANOMALOUS = "anomalous"


class TrafficTrend(StrEnum):
    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"


class AnomalySeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class TrafficPatternRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    endpoint: str = ""
    pattern_type: PatternType = PatternType.ORGANIC
    traffic_trend: TrafficTrend = TrafficTrend.STABLE
    anomaly_severity: AnomalySeverity = AnomalySeverity.LOW
    request_rate: float = 0.0
    baseline_rate: float = 0.0
    deviation_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class TrafficPatternAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    pattern_type: PatternType = PatternType.ORGANIC
    is_anomalous: bool = False
    deviation_pct: float = 0.0
    sample_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TrafficPatternReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_deviation: float = 0.0
    by_pattern_type: dict[str, int] = Field(default_factory=dict)
    by_traffic_trend: dict[str, int] = Field(default_factory=dict)
    by_anomaly_severity: dict[str, int] = Field(default_factory=dict)
    anomalous_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TrafficPatternIntelligence:
    """Detect traffic anomalies, classify seasonality,
    and predict traffic shifts."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TrafficPatternRecord] = []
        self._analyses: dict[str, TrafficPatternAnalysis] = {}
        logger.info(
            "traffic_pattern_intelligence.init",
            max_records=max_records,
        )

    def record_item(
        self,
        service: str = "",
        endpoint: str = "",
        pattern_type: PatternType = PatternType.ORGANIC,
        traffic_trend: TrafficTrend = (TrafficTrend.STABLE),
        anomaly_severity: AnomalySeverity = (AnomalySeverity.LOW),
        request_rate: float = 0.0,
        baseline_rate: float = 0.0,
        deviation_pct: float = 0.0,
    ) -> TrafficPatternRecord:
        record = TrafficPatternRecord(
            service=service,
            endpoint=endpoint,
            pattern_type=pattern_type,
            traffic_trend=traffic_trend,
            anomaly_severity=anomaly_severity,
            request_rate=request_rate,
            baseline_rate=baseline_rate,
            deviation_pct=deviation_pct,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "traffic_pattern.record_added",
            record_id=record.id,
            service=service,
        )
        return record

    def process(self, key: str) -> TrafficPatternAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        samples = sum(1 for r in self._records if r.service == rec.service)
        is_anom = rec.pattern_type == PatternType.ANOMALOUS
        analysis = TrafficPatternAnalysis(
            service=rec.service,
            pattern_type=rec.pattern_type,
            is_anomalous=is_anom,
            deviation_pct=round(rec.deviation_pct, 2),
            sample_count=samples,
            description=(f"Service {rec.service} deviation {rec.deviation_pct}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TrafficPatternReport:
        by_pt: dict[str, int] = {}
        by_tt: dict[str, int] = {}
        by_as: dict[str, int] = {}
        devs: list[float] = []
        for r in self._records:
            k = r.pattern_type.value
            by_pt[k] = by_pt.get(k, 0) + 1
            k2 = r.traffic_trend.value
            by_tt[k2] = by_tt.get(k2, 0) + 1
            k3 = r.anomaly_severity.value
            by_as[k3] = by_as.get(k3, 0) + 1
            devs.append(r.deviation_pct)
        avg = round(sum(devs) / len(devs), 2) if devs else 0.0
        anomalous = list(
            {r.service for r in self._records if r.pattern_type == PatternType.ANOMALOUS}
        )[:10]
        recs: list[str] = []
        if anomalous:
            recs.append(f"{len(anomalous)} anomalous services")
        if not recs:
            recs.append("Traffic patterns normal")
        return TrafficPatternReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_deviation=avg,
            by_pattern_type=by_pt,
            by_traffic_trend=by_tt,
            by_anomaly_severity=by_as,
            anomalous_services=anomalous,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.pattern_type.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "pattern_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("traffic_pattern_intelligence.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def detect_traffic_anomalies(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with anomalous traffic."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.pattern_type == PatternType.ANOMALOUS and r.service not in seen:
                seen.add(r.service)
                results.append(
                    {
                        "service": r.service,
                        "endpoint": r.endpoint,
                        "severity": (r.anomaly_severity.value),
                        "deviation_pct": r.deviation_pct,
                        "request_rate": r.request_rate,
                    }
                )
        results.sort(
            key=lambda x: x["deviation_pct"],
            reverse=True,
        )
        return results

    def classify_traffic_seasonality(
        self,
    ) -> list[dict[str, Any]]:
        """Classify traffic patterns by type."""
        svc_patterns: dict[str, dict[str, int]] = {}
        for r in self._records:
            svc_patterns.setdefault(r.service, {})
            pt = r.pattern_type.value
            svc_patterns[r.service][pt] = svc_patterns[r.service].get(pt, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, patterns in svc_patterns.items():
            dominant = max(
                patterns,
                key=patterns.get,  # type: ignore[arg-type]
            )
            results.append(
                {
                    "service": svc,
                    "dominant_pattern": dominant,
                    "pattern_counts": patterns,
                }
            )
        return results

    def predict_traffic_shift(
        self,
    ) -> list[dict[str, Any]]:
        """Predict traffic shifts by trend."""
        svc_rates: dict[str, list[float]] = {}
        svc_trends: dict[str, str] = {}
        for r in self._records:
            svc_rates.setdefault(r.service, []).append(r.request_rate)
            svc_trends[r.service] = r.traffic_trend.value
        results: list[dict[str, Any]] = []
        for svc, rates in svc_rates.items():
            avg = round(sum(rates) / len(rates), 2)
            results.append(
                {
                    "service": svc,
                    "trend": svc_trends[svc],
                    "avg_rate": avg,
                    "sample_count": len(rates),
                }
            )
        results.sort(
            key=lambda x: x["avg_rate"],
            reverse=True,
        )
        return results
