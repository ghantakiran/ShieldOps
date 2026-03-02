"""Realtime Cost Anomaly Detector — detect cost anomalies in real time."""

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
    SPIKE = "spike"
    DRIFT = "drift"
    SEASONAL = "seasonal"
    STRUCTURAL = "structural"
    UNKNOWN = "unknown"


class CostSource(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    SERVICES = "services"


class DetectionMethod(StrEnum):
    STATISTICAL = "statistical"
    ML_BASED = "ml_based"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"
    MANUAL = "manual"


# --- Models ---


class CostAnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_type: AnomalyType = AnomalyType.UNKNOWN
    cost_source: CostSource = CostSource.COMPUTE
    detection_method: DetectionMethod = DetectionMethod.STATISTICAL
    amount: float = 0.0
    baseline: float = 0.0
    deviation_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AnomalyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_type: AnomalyType = AnomalyType.UNKNOWN
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostAnomalyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    anomaly_count: int = 0
    avg_deviation_pct: float = 0.0
    by_anomaly_type: dict[str, int] = Field(default_factory=dict)
    by_cost_source: dict[str, int] = Field(default_factory=dict)
    by_detection_method: dict[str, int] = Field(default_factory=dict)
    top_anomalies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RealtimeCostAnomalyDetector:
    """Detect cost anomalies in real time across cloud services."""

    def __init__(
        self,
        max_records: int = 200000,
        deviation_threshold: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._deviation_threshold = deviation_threshold
        self._records: list[CostAnomalyRecord] = []
        self._analyses: list[AnomalyAnalysis] = []
        logger.info(
            "realtime_cost_anomaly_detector.initialized",
            max_records=max_records,
            deviation_threshold=deviation_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_anomaly(
        self,
        anomaly_type: AnomalyType = AnomalyType.UNKNOWN,
        cost_source: CostSource = CostSource.COMPUTE,
        detection_method: DetectionMethod = DetectionMethod.STATISTICAL,
        amount: float = 0.0,
        baseline: float = 0.0,
        deviation_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CostAnomalyRecord:
        record = CostAnomalyRecord(
            anomaly_type=anomaly_type,
            cost_source=cost_source,
            detection_method=detection_method,
            amount=amount,
            baseline=baseline,
            deviation_pct=deviation_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "realtime_cost_anomaly_detector.anomaly_recorded",
            record_id=record.id,
            anomaly_type=anomaly_type.value,
            deviation_pct=deviation_pct,
        )
        return record

    def get_anomaly(self, record_id: str) -> CostAnomalyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_anomalies(
        self,
        anomaly_type: AnomalyType | None = None,
        cost_source: CostSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CostAnomalyRecord]:
        results = list(self._records)
        if anomaly_type is not None:
            results = [r for r in results if r.anomaly_type == anomaly_type]
        if cost_source is not None:
            results = [r for r in results if r.cost_source == cost_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        anomaly_type: AnomalyType = AnomalyType.UNKNOWN,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AnomalyAnalysis:
        analysis = AnomalyAnalysis(
            anomaly_type=anomaly_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "realtime_cost_anomaly_detector.analysis_added",
            anomaly_type=anomaly_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_source_distribution(self) -> dict[str, Any]:
        """Group by cost_source; return count and avg deviation_pct."""
        source_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.cost_source.value
            source_data.setdefault(key, []).append(r.deviation_pct)
        result: dict[str, Any] = {}
        for source, devs in source_data.items():
            result[source] = {
                "count": len(devs),
                "avg_deviation_pct": round(sum(devs) / len(devs), 2),
            }
        return result

    def identify_high_deviation_anomalies(self) -> list[dict[str, Any]]:
        """Return records where deviation_pct >= deviation_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.deviation_pct >= self._deviation_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "anomaly_type": r.anomaly_type.value,
                        "cost_source": r.cost_source.value,
                        "deviation_pct": r.deviation_pct,
                        "amount": r.amount,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["deviation_pct"], reverse=True)

    def rank_by_impact(self) -> list[dict[str, Any]]:
        """Group by service, total amount, sort descending."""
        svc_amounts: dict[str, float] = {}
        for r in self._records:
            svc_amounts[r.service] = svc_amounts.get(r.service, 0.0) + r.amount
        results: list[dict[str, Any]] = [
            {"service": svc, "total_amount": round(amt, 2)} for svc, amt in svc_amounts.items()
        ]
        results.sort(key=lambda x: x["total_amount"], reverse=True)
        return results

    def detect_anomaly_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "worsening"
        else:
            trend = "improving"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> CostAnomalyReport:
        by_type: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_type[r.anomaly_type.value] = by_type.get(r.anomaly_type.value, 0) + 1
            by_source[r.cost_source.value] = by_source.get(r.cost_source.value, 0) + 1
            by_method[r.detection_method.value] = by_method.get(r.detection_method.value, 0) + 1
        anomaly_count = sum(
            1 for r in self._records if r.deviation_pct >= self._deviation_threshold
        )
        devs = [r.deviation_pct for r in self._records]
        avg_deviation_pct = round(sum(devs) / len(devs), 2) if devs else 0.0
        high_devs = self.identify_high_deviation_anomalies()
        top_anomalies = [o["record_id"] for o in high_devs[:5]]
        recs: list[str] = []
        if anomaly_count > 0:
            recs.append(
                f"{anomaly_count} anomaly(ies) exceed deviation threshold "
                f"({self._deviation_threshold}%)"
            )
        if avg_deviation_pct >= self._deviation_threshold:
            recs.append(
                f"Avg deviation {avg_deviation_pct}% is above threshold "
                f"({self._deviation_threshold}%)"
            )
        if not recs:
            recs.append("Cost anomaly detection is healthy")
        return CostAnomalyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            anomaly_count=anomaly_count,
            avg_deviation_pct=avg_deviation_pct,
            by_anomaly_type=by_type,
            by_cost_source=by_source,
            by_detection_method=by_method,
            top_anomalies=top_anomalies,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("realtime_cost_anomaly_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.anomaly_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "deviation_threshold": self._deviation_threshold,
            "anomaly_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
