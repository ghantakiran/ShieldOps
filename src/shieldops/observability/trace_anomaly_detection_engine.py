"""Trace Anomaly Detection Engine —
detect anomalous traces in distributed systems,
classify anomaly patterns, rank anomalies by impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AnomalyType(StrEnum):
    LATENCY_SPIKE = "latency_spike"
    ERROR_BURST = "error_burst"
    TOPOLOGY_CHANGE = "topology_change"
    VOLUME_SHIFT = "volume_shift"


class DetectionMethod(StrEnum):
    STATISTICAL = "statistical"
    ML_BASED = "ml_based"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"


class AnomalySeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class TraceAnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    service_name: str = ""
    anomaly_type: AnomalyType = AnomalyType.LATENCY_SPIKE
    detection_method: DetectionMethod = DetectionMethod.STATISTICAL
    anomaly_severity: AnomalySeverity = AnomalySeverity.LOW
    anomaly_score: float = 0.0
    latency_ms: float = 0.0
    error_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceAnomalyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    service_name: str = ""
    anomaly_type: AnomalyType = AnomalyType.LATENCY_SPIKE
    impact_score: float = 0.0
    is_critical: bool = False
    root_service: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceAnomalyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_anomaly_score: float = 0.0
    by_anomaly_type: dict[str, int] = Field(default_factory=dict)
    by_detection_method: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TraceAnomalyDetectionEngine:
    """Detect anomalous traces in distributed systems,
    classify anomaly patterns, rank anomalies by impact."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TraceAnomalyRecord] = []
        self._analyses: dict[str, TraceAnomalyAnalysis] = {}
        logger.info("trace_anomaly_detection_engine.init", max_records=max_records)

    def add_record(
        self,
        trace_id: str = "",
        service_name: str = "",
        anomaly_type: AnomalyType = AnomalyType.LATENCY_SPIKE,
        detection_method: DetectionMethod = DetectionMethod.STATISTICAL,
        anomaly_severity: AnomalySeverity = AnomalySeverity.LOW,
        anomaly_score: float = 0.0,
        latency_ms: float = 0.0,
        error_rate: float = 0.0,
        description: str = "",
    ) -> TraceAnomalyRecord:
        record = TraceAnomalyRecord(
            trace_id=trace_id,
            service_name=service_name,
            anomaly_type=anomaly_type,
            detection_method=detection_method,
            anomaly_severity=anomaly_severity,
            anomaly_score=anomaly_score,
            latency_ms=latency_ms,
            error_rate=error_rate,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "trace_anomaly.record_added",
            record_id=record.id,
            trace_id=trace_id,
        )
        return record

    def process(self, key: str) -> TraceAnomalyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        sev_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        impact = round(
            sev_weights.get(rec.anomaly_severity.value, 1) * rec.anomaly_score,
            2,
        )
        analysis = TraceAnomalyAnalysis(
            trace_id=rec.trace_id,
            service_name=rec.service_name,
            anomaly_type=rec.anomaly_type,
            impact_score=impact,
            is_critical=rec.anomaly_severity == AnomalySeverity.CRITICAL,
            root_service=rec.service_name,
            description=f"Anomaly {rec.anomaly_type.value} on {rec.service_name}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TraceAnomalyReport:
        by_type: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            t = r.anomaly_type.value
            by_type[t] = by_type.get(t, 0) + 1
            m = r.detection_method.value
            by_method[m] = by_method.get(m, 0) + 1
            s = r.anomaly_severity.value
            by_sev[s] = by_sev.get(s, 0) + 1
            scores.append(r.anomaly_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        critical_svcs = list(
            {
                r.service_name
                for r in self._records
                if r.anomaly_severity in (AnomalySeverity.CRITICAL, AnomalySeverity.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if critical_svcs:
            recs.append(f"{len(critical_svcs)} services with critical anomalies")
        if not recs:
            recs.append("No critical trace anomalies detected")
        return TraceAnomalyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_anomaly_score=avg,
            by_anomaly_type=by_type,
            by_detection_method=by_method,
            by_severity=by_sev,
            critical_services=critical_svcs,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            k = r.anomaly_type.value
            type_dist[k] = type_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "anomaly_type_distribution": type_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("trace_anomaly_detection_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def detect_trace_anomalies(self) -> list[dict[str, Any]]:
        """Detect trace anomalies grouped by service."""
        service_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            service_data.setdefault(r.service_name, []).append(
                {
                    "anomaly_type": r.anomaly_type.value,
                    "score": r.anomaly_score,
                    "severity": r.anomaly_severity.value,
                }
            )
        results: list[dict[str, Any]] = []
        for svc, items in service_data.items():
            avg_score = sum(i["score"] for i in items) / len(items)
            results.append(
                {
                    "service_name": svc,
                    "anomaly_count": len(items),
                    "avg_anomaly_score": round(avg_score, 2),
                    "anomaly_types": list({i["anomaly_type"] for i in items}),
                }
            )
        results.sort(key=lambda x: x["avg_anomaly_score"], reverse=True)
        return results

    def classify_anomaly_patterns(self) -> list[dict[str, Any]]:
        """Classify detected anomalies into patterns."""
        pattern_counts: dict[str, dict[str, Any]] = {}
        for r in self._records:
            key = f"{r.anomaly_type.value}:{r.detection_method.value}"
            if key not in pattern_counts:
                pattern_counts[key] = {
                    "anomaly_type": r.anomaly_type.value,
                    "detection_method": r.detection_method.value,
                    "count": 0,
                    "total_score": 0.0,
                }
            pattern_counts[key]["count"] += 1
            pattern_counts[key]["total_score"] += r.anomaly_score
        results: list[dict[str, Any]] = []
        for pat_data in pattern_counts.values():
            cnt = pat_data["count"]
            results.append(
                {
                    "pattern": f"{pat_data['anomaly_type']}:{pat_data['detection_method']}",
                    "anomaly_type": pat_data["anomaly_type"],
                    "detection_method": pat_data["detection_method"],
                    "count": cnt,
                    "avg_score": round(pat_data["total_score"] / cnt, 2),
                }
            )
        results.sort(key=lambda x: x["count"], reverse=True)
        return results

    def rank_anomalies_by_impact(self) -> list[dict[str, Any]]:
        """Rank individual anomaly records by impact score."""
        sev_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        results: list[dict[str, Any]] = []
        for r in self._records:
            w = sev_weights.get(r.anomaly_severity.value, 1)
            impact = round(w * r.anomaly_score, 2)
            results.append(
                {
                    "trace_id": r.trace_id,
                    "service_name": r.service_name,
                    "anomaly_type": r.anomaly_type.value,
                    "severity": r.anomaly_severity.value,
                    "impact_score": impact,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["impact_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
