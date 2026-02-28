"""Predictive Alert Engine — generate alerts before issues occur using trend analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PredictionType(StrEnum):
    ANOMALY_PROJECTION = "anomaly_projection"
    TREND_BREACH = "trend_breach"
    CAUSAL_INFERENCE = "causal_inference"
    PATTERN_MATCH = "pattern_match"
    SEASONAL = "seasonal"


class AlertConfidence(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"


class PreventionOutcome(StrEnum):
    PREVENTED = "prevented"
    MITIGATED = "mitigated"
    FALSE_POSITIVE = "false_positive"
    MISSED = "missed"
    INCONCLUSIVE = "inconclusive"


# --- Models ---


class PredictiveAlertRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    prediction_type: PredictionType = PredictionType.TREND_BREACH
    alert_confidence: AlertConfidence = AlertConfidence.MODERATE
    prevention_outcome: PreventionOutcome = PreventionOutcome.PREVENTED
    lead_time_minutes: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class SignalTrend(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trend_label: str = ""
    prediction_type: PredictionType = PredictionType.TREND_BREACH
    alert_confidence: AlertConfidence = AlertConfidence.HIGH
    slope_value: float = 0.0
    created_at: float = Field(default_factory=time.time)


class PredictiveAlertReport(BaseModel):
    total_alerts: int = 0
    total_trends: int = 0
    prevention_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    false_positive_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PredictiveAlertEngine:
    """Generate predictive alerts before issues occur using trend analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[PredictiveAlertRecord] = []
        self._trends: list[SignalTrend] = []
        logger.info(
            "predictive_alert.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_alert(
        self,
        service_name: str,
        prediction_type: PredictionType = PredictionType.TREND_BREACH,
        alert_confidence: AlertConfidence = AlertConfidence.MODERATE,
        prevention_outcome: PreventionOutcome = PreventionOutcome.PREVENTED,
        lead_time_minutes: float = 0.0,
        details: str = "",
    ) -> PredictiveAlertRecord:
        record = PredictiveAlertRecord(
            service_name=service_name,
            prediction_type=prediction_type,
            alert_confidence=alert_confidence,
            prevention_outcome=prevention_outcome,
            lead_time_minutes=lead_time_minutes,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "predictive_alert.recorded",
            record_id=record.id,
            service_name=service_name,
            prediction_type=prediction_type.value,
        )
        return record

    def get_alert(self, record_id: str) -> PredictiveAlertRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_alerts(
        self,
        service_name: str | None = None,
        prediction_type: PredictionType | None = None,
        limit: int = 50,
    ) -> list[PredictiveAlertRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if prediction_type is not None:
            results = [r for r in results if r.prediction_type == prediction_type]
        return results[-limit:]

    def add_trend(
        self,
        trend_label: str,
        prediction_type: PredictionType = PredictionType.TREND_BREACH,
        alert_confidence: AlertConfidence = AlertConfidence.HIGH,
        slope_value: float = 0.0,
    ) -> SignalTrend:
        trend = SignalTrend(
            trend_label=trend_label,
            prediction_type=prediction_type,
            alert_confidence=alert_confidence,
            slope_value=slope_value,
        )
        self._trends.append(trend)
        if len(self._trends) > self._max_records:
            self._trends = self._trends[-self._max_records :]
        logger.info(
            "predictive_alert.trend_added",
            trend_label=trend_label,
            prediction_type=prediction_type.value,
        )
        return trend

    # -- domain operations -----------------------------------------------

    def analyze_prediction_accuracy(self, service_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        prevented = sum(1 for r in records if r.prevention_outcome == PreventionOutcome.PREVENTED)
        prevention_rate = round(prevented / len(records) * 100, 2)
        avg_lead = round(sum(r.lead_time_minutes for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total_alerts": len(records),
            "prevented_count": prevented,
            "prevention_rate_pct": prevention_rate,
            "avg_lead_time_minutes": avg_lead,
            "meets_threshold": prevention_rate >= self._min_confidence_pct,
        }

    def identify_false_positives(self) -> list[dict[str, Any]]:
        by_service: dict[str, int] = {}
        for r in self._records:
            if r.prevention_outcome == PreventionOutcome.FALSE_POSITIVE:
                by_service[r.service_name] = by_service.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in by_service.items():
            if count > 1:
                results.append({"service_name": svc, "false_positive_count": count})
        results.sort(key=lambda x: x["false_positive_count"], reverse=True)
        return results

    def rank_by_lead_time(self) -> list[dict[str, Any]]:
        svc_times: dict[str, list[float]] = {}
        for r in self._records:
            svc_times.setdefault(r.service_name, []).append(r.lead_time_minutes)
        results: list[dict[str, Any]] = []
        for svc, times in svc_times.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_lead_time_minutes": round(sum(times) / len(times), 2),
                    "record_count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_lead_time_minutes"], reverse=True)
        return results

    def detect_prediction_drift(self) -> list[dict[str, Any]]:
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.prevention_outcome != PreventionOutcome.PREVENTED:
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "non_prevented_count": count,
                        "drifting": True,
                    }
                )
        results.sort(key=lambda x: x["non_prevented_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> PredictiveAlertReport:
        by_type: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_type[r.prediction_type.value] = by_type.get(r.prediction_type.value, 0) + 1
            by_confidence[r.alert_confidence.value] = (
                by_confidence.get(r.alert_confidence.value, 0) + 1
            )
        prevented = sum(
            1 for r in self._records if r.prevention_outcome == PreventionOutcome.PREVENTED
        )
        prevention_rate = round(prevented / len(self._records) * 100, 2) if self._records else 0.0
        false_positive_count = sum(
            1 for r in self._records if r.prevention_outcome == PreventionOutcome.FALSE_POSITIVE
        )
        recs: list[str] = []
        if false_positive_count > 0:
            recs.append(f"{false_positive_count} false positive(s) detected across alerts")
        if prevention_rate < self._min_confidence_pct and self._records:
            recs.append(
                f"Prevention rate {prevention_rate}% below threshold {self._min_confidence_pct}%"
            )
        if not recs:
            recs.append("Predictive alert engine meets targets")
        return PredictiveAlertReport(
            total_alerts=len(self._records),
            total_trends=len(self._trends),
            prevention_rate_pct=prevention_rate,
            by_type=by_type,
            by_confidence=by_confidence,
            false_positive_count=false_positive_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._trends.clear()
        logger.info("predictive_alert.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.prediction_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_trends": len(self._trends),
            "min_confidence_pct": self._min_confidence_pct,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
