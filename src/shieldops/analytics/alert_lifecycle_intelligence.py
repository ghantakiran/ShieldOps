"""Alert Lifecycle Intelligence
track alert aging, identify stale alert definitions,
generate retirement recommendations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LifecycleStage(StrEnum):
    ACTIVE = "active"
    AGING = "aging"
    STALE = "stale"
    RETIRED = "retired"


class AlertValue(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class RetirementReason(StrEnum):
    LOW_VALUE = "low_value"
    REDUNDANT = "redundant"
    OBSOLETE = "obsolete"
    REPLACED = "replaced"


# --- Models ---


class AlertLifecycleRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    lifecycle_stage: LifecycleStage = LifecycleStage.ACTIVE
    alert_value: AlertValue = AlertValue.MEDIUM
    retirement_reason: RetirementReason = RetirementReason.LOW_VALUE
    age_days: int = 0
    last_fired_days_ago: int = 0
    fire_count: int = 0
    action_rate: float = 0.0
    created_at: float = Field(default_factory=time.time)


class AlertLifecycleAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    lifecycle_stage: LifecycleStage = LifecycleStage.ACTIVE
    health_score: float = 0.0
    staleness_score: float = 0.0
    value_score: float = 0.0
    total_fires: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertLifecycleReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_age_days: float = 0.0
    by_lifecycle_stage: dict[str, int] = Field(default_factory=dict)
    by_alert_value: dict[str, int] = Field(default_factory=dict)
    by_retirement_reason: dict[str, int] = Field(default_factory=dict)
    stale_alerts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertLifecycleIntelligence:
    """Track alert aging, identify stale definitions,
    generate retirement recommendations."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AlertLifecycleRecord] = []
        self._analyses: dict[str, AlertLifecycleAnalysis] = {}
        logger.info(
            "alert_lifecycle_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        alert_name: str = "",
        lifecycle_stage: LifecycleStage = (LifecycleStage.ACTIVE),
        alert_value: AlertValue = AlertValue.MEDIUM,
        retirement_reason: RetirementReason = (RetirementReason.LOW_VALUE),
        age_days: int = 0,
        last_fired_days_ago: int = 0,
        fire_count: int = 0,
        action_rate: float = 0.0,
    ) -> AlertLifecycleRecord:
        record = AlertLifecycleRecord(
            alert_name=alert_name,
            lifecycle_stage=lifecycle_stage,
            alert_value=alert_value,
            retirement_reason=retirement_reason,
            age_days=age_days,
            last_fired_days_ago=last_fired_days_ago,
            fire_count=fire_count,
            action_rate=action_rate,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_lifecycle.record_added",
            record_id=record.id,
            alert_name=alert_name,
        )
        return record

    def process(self, key: str) -> AlertLifecycleAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        staleness = min(100.0, rec.last_fired_days_ago * 0.5)
        value = rec.action_rate * 100.0
        health = max(
            0.0,
            100.0 - staleness * 0.5 - (100.0 - value) * 0.3,
        )
        analysis = AlertLifecycleAnalysis(
            alert_name=rec.alert_name,
            lifecycle_stage=rec.lifecycle_stage,
            health_score=round(health, 2),
            staleness_score=round(staleness, 2),
            value_score=round(value, 2),
            total_fires=rec.fire_count,
            description=(f"Alert {rec.alert_name} health {health:.2f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> AlertLifecycleReport:
        by_ls: dict[str, int] = {}
        by_av: dict[str, int] = {}
        by_rr: dict[str, int] = {}
        ages: list[int] = []
        for r in self._records:
            k = r.lifecycle_stage.value
            by_ls[k] = by_ls.get(k, 0) + 1
            k2 = r.alert_value.value
            by_av[k2] = by_av.get(k2, 0) + 1
            k3 = r.retirement_reason.value
            by_rr[k3] = by_rr.get(k3, 0) + 1
            ages.append(r.age_days)
        avg = round(sum(ages) / len(ages), 2) if ages else 0.0
        stale = list(
            {
                r.alert_name
                for r in self._records
                if r.lifecycle_stage
                in (
                    LifecycleStage.STALE,
                    LifecycleStage.RETIRED,
                )
            }
        )[:10]
        recs: list[str] = []
        if stale:
            recs.append(f"{len(stale)} stale alerts found")
        if not recs:
            recs.append("Alert lifecycle within norms")
        return AlertLifecycleReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_age_days=avg,
            by_lifecycle_stage=by_ls,
            by_alert_value=by_av,
            by_retirement_reason=by_rr,
            stale_alerts=stale,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ls_dist: dict[str, int] = {}
        for r in self._records:
            k = r.lifecycle_stage.value
            ls_dist[k] = ls_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "lifecycle_stage_distribution": ls_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("alert_lifecycle_intelligence.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def track_alert_aging(
        self,
    ) -> list[dict[str, Any]]:
        """Track alert aging patterns."""
        alert_data: dict[str, list[int]] = {}
        alert_fires: dict[str, int] = {}
        for r in self._records:
            alert_data.setdefault(r.alert_name, []).append(r.age_days)
            alert_fires[r.alert_name] = alert_fires.get(r.alert_name, 0) + r.fire_count
        results: list[dict[str, Any]] = []
        for name, ages in alert_data.items():
            avg_age = sum(ages) / len(ages) if ages else 0.0
            results.append(
                {
                    "alert_name": name,
                    "avg_age_days": round(avg_age, 2),
                    "max_age_days": max(ages),
                    "total_fires": (alert_fires[name]),
                    "aging_status": "aged" if avg_age > 365 else "current",
                }
            )
        results.sort(
            key=lambda x: x["avg_age_days"],
            reverse=True,
        )
        return results

    def identify_stale_alert_definitions(
        self,
    ) -> list[dict[str, Any]]:
        """Identify stale alert definitions."""
        alert_staleness: dict[str, list[int]] = {}
        alert_rates: dict[str, list[float]] = {}
        for r in self._records:
            alert_staleness.setdefault(r.alert_name, []).append(r.last_fired_days_ago)
            alert_rates.setdefault(r.alert_name, []).append(r.action_rate)
        results: list[dict[str, Any]] = []
        for name, days in alert_staleness.items():
            avg_days = sum(days) / len(days) if days else 0.0
            rates = alert_rates[name]
            avg_rate = sum(rates) / len(rates) if rates else 0.0
            if avg_days > 90 or avg_rate < 0.1:
                results.append(
                    {
                        "alert_name": name,
                        "avg_last_fired_days": (round(avg_days, 2)),
                        "avg_action_rate": round(avg_rate, 2),
                        "is_stale": avg_days > 90,
                        "is_low_value": (avg_rate < 0.1),
                    }
                )
        results.sort(
            key=lambda x: x["avg_last_fired_days"],
            reverse=True,
        )
        return results

    def generate_retirement_recommendations(
        self,
    ) -> list[dict[str, Any]]:
        """Generate retirement recommendations."""
        alert_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.alert_name not in alert_data:
                alert_data[r.alert_name] = {
                    "ages": [],
                    "rates": [],
                    "fires": 0,
                    "last_fired": [],
                }
            alert_data[r.alert_name]["ages"].append(r.age_days)
            alert_data[r.alert_name]["rates"].append(r.action_rate)
            alert_data[r.alert_name]["fires"] += r.fire_count
            alert_data[r.alert_name]["last_fired"].append(r.last_fired_days_ago)
        results: list[dict[str, Any]] = []
        for name, data in alert_data.items():
            avg_rate = sum(data["rates"]) / len(data["rates"]) if data["rates"] else 0.0
            avg_last = (
                sum(data["last_fired"]) / len(data["last_fired"]) if data["last_fired"] else 0.0
            )
            if avg_rate < 0.2 or avg_last > 180:
                reason = (
                    "low_value" if avg_rate < 0.1 else "obsolete" if avg_last > 365 else "redundant"
                )
                results.append(
                    {
                        "alert_name": name,
                        "avg_action_rate": round(avg_rate, 2),
                        "avg_last_fired_days": (round(avg_last, 2)),
                        "total_fires": (data["fires"]),
                        "retirement_reason": (reason),
                        "recommendation": "retire",
                    }
                )
        results.sort(
            key=lambda x: x["avg_action_rate"],
        )
        return results
