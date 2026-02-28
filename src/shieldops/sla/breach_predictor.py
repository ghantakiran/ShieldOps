"""SLA Breach Predictor — predict upcoming SLA breaches from trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BreachRisk(StrEnum):
    IMMINENT = "imminent"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class BreachCategory(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    DURABILITY = "durability"


class MitigationAction(StrEnum):
    SCALE_RESOURCES = "scale_resources"
    REROUTE_TRAFFIC = "reroute_traffic"
    ENABLE_CACHE = "enable_cache"
    ALERT_ONCALL = "alert_oncall"
    NO_ACTION = "no_action"


# --- Models ---


class BreachPrediction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    risk: BreachRisk = BreachRisk.LOW
    category: BreachCategory = BreachCategory.AVAILABILITY
    action: MitigationAction = MitigationAction.NO_ACTION
    confidence_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class BreachThreshold(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threshold_name: str = ""
    category: BreachCategory = BreachCategory.AVAILABILITY
    risk: BreachRisk = BreachRisk.MODERATE
    warning_hours: float = 24.0
    critical_hours: float = 4.0
    created_at: float = Field(default_factory=time.time)


class BreachPredictorReport(BaseModel):
    total_predictions: int = 0
    total_thresholds: int = 0
    high_risk_rate_pct: float = 0.0
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    imminent_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLABreachPredictor:
    """Predict upcoming SLA breaches from trends."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[BreachPrediction] = []
        self._thresholds: list[BreachThreshold] = []
        logger.info(
            "breach_predictor.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_prediction(
        self,
        service_name: str,
        risk: BreachRisk = BreachRisk.LOW,
        category: BreachCategory = BreachCategory.AVAILABILITY,
        action: MitigationAction = MitigationAction.NO_ACTION,
        confidence_pct: float = 0.0,
        details: str = "",
    ) -> BreachPrediction:
        record = BreachPrediction(
            service_name=service_name,
            risk=risk,
            category=category,
            action=action,
            confidence_pct=confidence_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "breach_predictor.prediction_recorded",
            record_id=record.id,
            service_name=service_name,
            risk=risk.value,
            category=category.value,
        )
        return record

    def get_prediction(self, record_id: str) -> BreachPrediction | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_predictions(
        self,
        service_name: str | None = None,
        risk: BreachRisk | None = None,
        limit: int = 50,
    ) -> list[BreachPrediction]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if risk is not None:
            results = [r for r in results if r.risk == risk]
        return results[-limit:]

    def add_threshold(
        self,
        threshold_name: str,
        category: BreachCategory = BreachCategory.AVAILABILITY,
        risk: BreachRisk = BreachRisk.MODERATE,
        warning_hours: float = 24.0,
        critical_hours: float = 4.0,
    ) -> BreachThreshold:
        threshold = BreachThreshold(
            threshold_name=threshold_name,
            category=category,
            risk=risk,
            warning_hours=warning_hours,
            critical_hours=critical_hours,
        )
        self._thresholds.append(threshold)
        if len(self._thresholds) > self._max_records:
            self._thresholds = self._thresholds[-self._max_records :]
        logger.info(
            "breach_predictor.threshold_added",
            threshold_name=threshold_name,
            category=category.value,
            risk=risk.value,
        )
        return threshold

    # -- domain operations -------------------------------------------

    def analyze_breach_risk(self, service_name: str) -> dict[str, Any]:
        """Analyze breach risk for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {
                "service_name": service_name,
                "status": "no_data",
            }
        high_risk = sum(1 for r in records if r.risk in (BreachRisk.IMMINENT, BreachRisk.HIGH))
        high_risk_rate = round(high_risk / len(records) * 100, 2)
        avg_confidence = round(
            sum(r.confidence_pct for r in records) / len(records),
            2,
        )
        return {
            "service_name": service_name,
            "prediction_count": len(records),
            "high_risk_count": high_risk,
            "high_risk_rate": high_risk_rate,
            "avg_confidence": avg_confidence,
            "meets_threshold": (avg_confidence >= self._min_confidence_pct),
        }

    def identify_imminent_breaches(
        self,
    ) -> list[dict[str, Any]]:
        """Find services with imminent breach risk."""
        counts: dict[str, int] = {}
        for r in self._records:
            if r.risk in (
                BreachRisk.IMMINENT,
                BreachRisk.HIGH,
            ):
                counts[r.service_name] = counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "imminent_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["imminent_count"],
            reverse=True,
        )
        return results

    def rank_by_confidence(
        self,
    ) -> list[dict[str, Any]]:
        """Rank services by avg confidence descending."""
        svc_vals: dict[str, list[float]] = {}
        for r in self._records:
            svc_vals.setdefault(r.service_name, []).append(r.confidence_pct)
        results: list[dict[str, Any]] = []
        for svc, vals in svc_vals.items():
            avg = round(sum(vals) / len(vals), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_confidence": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_confidence"],
            reverse=True,
        )
        return results

    def detect_breach_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with breach patterns (>3)."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.risk not in (
                BreachRisk.NEGLIGIBLE,
                BreachRisk.LOW,
            ):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "pattern_count": count,
                        "pattern_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["pattern_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> BreachPredictorReport:
        by_risk: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_risk[r.risk.value] = by_risk.get(r.risk.value, 0) + 1
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
        high_risk_count = sum(
            1 for r in self._records if r.risk in (BreachRisk.IMMINENT, BreachRisk.HIGH)
        )
        high_risk_rate = (
            round(
                high_risk_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        imminent = sum(1 for r in self._records if r.risk == BreachRisk.IMMINENT)
        imminent_svcs = len(self.identify_imminent_breaches())
        recs: list[str] = []
        if high_risk_rate > 0:
            recs.append(f"High risk rate {high_risk_rate}% across predictions")
        if imminent_svcs > 0:
            recs.append(f"{imminent_svcs} service(s) with imminent breaches")
        patterns = len(self.detect_breach_patterns())
        if patterns > 0:
            recs.append(f"{patterns} service(s) with breach patterns")
        if not recs:
            recs.append("SLA breach risk is healthy")
        return BreachPredictorReport(
            total_predictions=len(self._records),
            total_thresholds=len(self._thresholds),
            high_risk_rate_pct=high_risk_rate,
            by_risk=by_risk,
            by_category=by_category,
            imminent_count=imminent,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._thresholds.clear()
        logger.info("breach_predictor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        risk_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk.value
            risk_dist[key] = risk_dist.get(key, 0) + 1
        return {
            "total_predictions": len(self._records),
            "total_thresholds": len(self._thresholds),
            "min_confidence_pct": (self._min_confidence_pct),
            "risk_distribution": risk_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
