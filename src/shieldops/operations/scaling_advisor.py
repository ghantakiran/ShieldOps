"""Predictive Scaling Advisor — predict and advise on infrastructure scaling decisions."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScalingAction(StrEnum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    NO_ACTION = "no_action"


class ScalingTrigger(StrEnum):
    CPU_THRESHOLD = "cpu_threshold"
    MEMORY_THRESHOLD = "memory_threshold"
    REQUEST_RATE = "request_rate"
    QUEUE_DEPTH = "queue_depth"
    SCHEDULED = "scheduled"


class ScalingConfidence(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class ScalingRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    service_name: str = ""
    action: ScalingAction = ScalingAction.NO_ACTION
    trigger: ScalingTrigger = ScalingTrigger.CPU_THRESHOLD
    confidence: ScalingConfidence = ScalingConfidence.MODERATE
    confidence_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ScalingRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    service_name: str = ""
    action: ScalingAction = ScalingAction.NO_ACTION
    trigger: ScalingTrigger = ScalingTrigger.CPU_THRESHOLD
    savings_potential: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ScalingAdvisorReport(BaseModel):
    total_records: int = 0
    total_recommendations: int = 0
    avg_confidence_pct: float = 0.0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_trigger: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PredictiveScalingAdvisor:
    """Predict and advise on infrastructure scaling decisions."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[ScalingRecord] = []
        self._recommendations: list[ScalingRecommendation] = []
        logger.info(
            "scaling_advisor.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_scaling(
        self,
        service_name: str,
        action: ScalingAction = ScalingAction.NO_ACTION,
        trigger: ScalingTrigger = ScalingTrigger.CPU_THRESHOLD,
        confidence: ScalingConfidence = ScalingConfidence.MODERATE,
        confidence_pct: float = 0.0,
        details: str = "",
    ) -> ScalingRecord:
        record = ScalingRecord(
            service_name=service_name,
            action=action,
            trigger=trigger,
            confidence=confidence,
            confidence_pct=confidence_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "scaling_advisor.recorded",
            record_id=record.id,
            service_name=service_name,
            confidence_pct=confidence_pct,
        )
        return record

    def get_scaling(self, record_id: str) -> ScalingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scalings(
        self,
        service_name: str | None = None,
        action: ScalingAction | None = None,
        limit: int = 50,
    ) -> list[ScalingRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if action is not None:
            results = [r for r in results if r.action == action]
        return results[-limit:]

    def add_recommendation(
        self,
        service_name: str,
        action: ScalingAction = ScalingAction.NO_ACTION,
        trigger: ScalingTrigger = ScalingTrigger.CPU_THRESHOLD,
        savings_potential: float = 0.0,
        description: str = "",
    ) -> ScalingRecommendation:
        recommendation = ScalingRecommendation(
            service_name=service_name,
            action=action,
            trigger=trigger,
            savings_potential=savings_potential,
            description=description,
        )
        self._recommendations.append(recommendation)
        if len(self._recommendations) > self._max_records:
            self._recommendations = self._recommendations[-self._max_records :]
        logger.info(
            "scaling_advisor.recommendation_added",
            service_name=service_name,
            savings_potential=savings_potential,
        )
        return recommendation

    # -- domain operations -----------------------------------------------

    def analyze_scaling_patterns(self, service_name: str) -> dict[str, Any]:
        """Analyze scaling patterns for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_confidence = round(sum(r.confidence_pct for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total": len(records),
            "avg_confidence_pct": avg_confidence,
            "meets_threshold": avg_confidence >= self._min_confidence_pct,
        }

    def identify_over_provisioned(self) -> list[dict[str, Any]]:
        """Find services with repeated scale-down or scale-in actions."""
        downsizing = {ScalingAction.SCALE_DOWN, ScalingAction.SCALE_IN}
        service_counts: dict[str, int] = {}
        for r in self._records:
            if r.action in downsizing:
                service_counts[r.service_name] = service_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, count in service_counts.items():
            if count > 1:
                results.append({"service_name": name, "scale_down_count": count})
        results.sort(key=lambda x: x["scale_down_count"], reverse=True)
        return results

    def rank_by_savings_potential(self) -> list[dict[str, Any]]:
        """Rank services by total savings potential from recommendations descending."""
        service_savings: dict[str, list[float]] = {}
        for rec in self._recommendations:
            service_savings.setdefault(rec.service_name, []).append(rec.savings_potential)
        results: list[dict[str, Any]] = []
        for name, savings in service_savings.items():
            total = round(sum(savings), 2)
            results.append({"service_name": name, "total_savings_potential": total})
        results.sort(key=lambda x: x["total_savings_potential"], reverse=True)
        return results

    def detect_scaling_anomalies(self) -> list[dict[str, Any]]:
        """Detect scaling anomalies for services with sufficient data."""
        service_records: dict[str, list[ScalingRecord]] = {}
        for r in self._records:
            service_records.setdefault(r.service_name, []).append(r)
        results: list[dict[str, Any]] = []
        for name, records in service_records.items():
            if len(records) > 3:
                pcts = [r.confidence_pct for r in records]
                pattern = "increasing" if pcts[-1] > pcts[0] else "decreasing"
                results.append(
                    {
                        "service_name": name,
                        "record_count": len(records),
                        "confidence_pattern": pattern,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ScalingAdvisorReport:
        by_action: dict[str, int] = {}
        by_trigger: dict[str, int] = {}
        for r in self._records:
            by_action[r.action.value] = by_action.get(r.action.value, 0) + 1
            by_trigger[r.trigger.value] = by_trigger.get(r.trigger.value, 0) + 1
        avg_confidence = (
            round(
                sum(r.confidence_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        low_conf = {
            ScalingConfidence.LOW,
            ScalingConfidence.SPECULATIVE,
            ScalingConfidence.INSUFFICIENT_DATA,
        }
        low_confidence_count = sum(1 for r in self._records if r.confidence in low_conf)
        recs: list[str] = []
        if low_confidence_count > 0:
            recs.append(f"{low_confidence_count} scaling decision(s) with low confidence")
        below_threshold = sum(
            1 for r in self._records if r.confidence_pct < self._min_confidence_pct
        )
        if below_threshold > 0:
            recs.append(f"{below_threshold} record(s) below minimum confidence threshold")
        if not recs:
            recs.append("Scaling confidence within acceptable limits")
        return ScalingAdvisorReport(
            total_records=len(self._records),
            total_recommendations=len(self._recommendations),
            avg_confidence_pct=avg_confidence,
            by_action=by_action,
            by_trigger=by_trigger,
            low_confidence_count=low_confidence_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._recommendations.clear()
        logger.info("scaling_advisor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        action_dist: dict[str, int] = {}
        for r in self._records:
            key = r.action.value
            action_dist[key] = action_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_recommendations": len(self._recommendations),
            "min_confidence_pct": self._min_confidence_pct,
            "action_distribution": action_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
