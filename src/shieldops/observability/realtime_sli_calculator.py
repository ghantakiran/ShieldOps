"""RealtimeSliCalculator — real-time SLI engine."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SliType(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"


class CalculationWindow(StrEnum):
    MINUTES_1 = "minutes_1"
    MINUTES_5 = "minutes_5"
    MINUTES_15 = "minutes_15"
    HOUR_1 = "hour_1"


class SliHealth(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# --- Models ---


class SliRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    sli_type: SliType = SliType.AVAILABILITY
    window: CalculationWindow = CalculationWindow.MINUTES_5
    health: SliHealth = SliHealth.HEALTHY
    score: float = 0.0
    value: float = 0.0
    target: float = 99.9
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SliAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    sli_type: SliType = SliType.AVAILABILITY
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SliReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    by_sli_type: dict[str, int] = Field(default_factory=dict)
    by_window: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RealtimeSliCalculator:
    """Realtime SLI Calculator.

    Calculates service level indicators in
    real-time across multiple time windows.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[SliRecord] = []
        self._analyses: list[SliAnalysis] = []
        logger.info(
            "realtime_sli_calculator.init",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        sli_type: SliType = SliType.AVAILABILITY,
        window: CalculationWindow = (CalculationWindow.MINUTES_5),
        health: SliHealth = SliHealth.HEALTHY,
        score: float = 0.0,
        value: float = 0.0,
        target: float = 99.9,
        service: str = "",
        team: str = "",
    ) -> SliRecord:
        record = SliRecord(
            name=name,
            sli_type=sli_type,
            window=window,
            health=health,
            score=score,
            value=value,
            target=target,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "realtime_sli_calculator.added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.name == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        scores = [r.score for r in matching]
        avg = round(sum(scores) / len(scores), 2)
        vals = [r.value for r in matching]
        avg_val = round(sum(vals) / len(vals), 4)
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "avg_value": avg_val,
        }

    def generate_report(self) -> SliReport:
        by_st: dict[str, int] = {}
        by_w: dict[str, int] = {}
        by_h: dict[str, int] = {}
        for r in self._records:
            v1 = r.sli_type.value
            by_st[v1] = by_st.get(v1, 0) + 1
            v2 = r.window.value
            by_w[v2] = by_w.get(v2, 0) + 1
            v3 = r.health.value
            by_h[v3] = by_h.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        critical = by_h.get("critical", 0)
        warning = by_h.get("warning", 0)
        if critical > 0:
            recs.append(f"{critical} SLI(s) in critical state")
        if warning > 0:
            recs.append(f"{warning} SLI(s) in warning state")
        if not recs:
            recs.append("All SLIs healthy")
        return SliReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            by_sli_type=by_st,
            by_window=by_w,
            by_health=by_h,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        st_dist: dict[str, int] = {}
        for r in self._records:
            k = r.sli_type.value
            st_dist[k] = st_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "sli_type_distribution": st_dist,
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("realtime_sli_calculator.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def compute_composite_sli(
        self,
        service: str = "",
    ) -> dict[str, Any]:
        """Compute composite SLI across types."""
        matching = list(self._records)
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return {"status": "no_data"}
        type_vals: dict[str, list[float]] = {}
        for r in matching:
            key = r.sli_type.value
            type_vals.setdefault(key, []).append(r.value)
        components: dict[str, float] = {}
        for st, vals in type_vals.items():
            components[st] = round(sum(vals) / len(vals), 4)
        composite = round(
            sum(components.values()) / len(components),
            4,
        )
        return {
            "service": service or "all",
            "composite_sli": composite,
            "components": components,
            "component_count": len(components),
        }

    def detect_sli_degradation(
        self,
    ) -> list[dict[str, Any]]:
        """Detect SLIs degrading below target."""
        degraded: list[dict[str, Any]] = []
        for r in self._records:
            if r.value < r.target:
                gap = round(r.target - r.value, 4)
                degraded.append(
                    {
                        "name": r.name,
                        "service": r.service,
                        "sli_type": r.sli_type.value,
                        "value": r.value,
                        "target": r.target,
                        "gap": gap,
                        "health": r.health.value,
                    }
                )
        degraded.sort(key=lambda x: x["gap"], reverse=True)
        return degraded

    def forecast_sli_breach(
        self,
    ) -> dict[str, Any]:
        """Forecast potential SLI breaches."""
        if len(self._records) < 2:
            return {"status": "insufficient_data"}
        svc_history: dict[str, list[SliRecord]] = {}
        for r in self._records:
            key = f"{r.service}:{r.sli_type.value}"
            svc_history.setdefault(key, []).append(r)
        at_risk: list[dict[str, Any]] = []
        for key, recs in svc_history.items():
            if len(recs) < 2:
                continue
            sorted_recs = sorted(recs, key=lambda x: x.created_at)
            mid = len(sorted_recs) // 2
            first = sorted_recs[:mid]
            second = sorted_recs[mid:]
            avg_first = sum(r.value for r in first) / len(first)
            avg_second = sum(r.value for r in second) / len(second)
            trend = round(avg_second - avg_first, 4)
            target = sorted_recs[-1].target
            if trend < 0 and avg_second < target * 1.05:
                at_risk.append(
                    {
                        "key": key,
                        "current_avg": round(avg_second, 4),
                        "target": target,
                        "trend": trend,
                        "risk": "high" if avg_second < target else "medium",
                    }
                )
        at_risk.sort(key=lambda x: x["trend"])
        return {
            "at_risk_count": len(at_risk),
            "at_risk": at_risk,
        }
