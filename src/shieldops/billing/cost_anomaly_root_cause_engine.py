"""Cost Anomaly Root Cause Engine
correlate anomalies with events, decompose
contributors, assess recurrence risk."""

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
    STEP_CHANGE = "step_change"
    SEASONAL = "seasonal"


class EventCorrelation(StrEnum):
    DEPLOYMENT = "deployment"
    SCALING = "scaling"
    CONFIG_CHANGE = "config_change"
    TRAFFIC = "traffic"


class RecurrenceRisk(StrEnum):
    LIKELY = "likely"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"
    ONE_TIME = "one_time"


# --- Models ---


class CostAnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_id: str = ""
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    event_correlation: EventCorrelation = EventCorrelation.DEPLOYMENT
    recurrence_risk: RecurrenceRisk = RecurrenceRisk.POSSIBLE
    anomaly_amount: float = 0.0
    baseline_amount: float = 0.0
    service_name: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostAnomalyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_id: str = ""
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    deviation_pct: float = 0.0
    root_cause: str = ""
    recurrence_risk: RecurrenceRisk = RecurrenceRisk.POSSIBLE
    contributors: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostAnomalyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_anomaly_amount: float = 0.0
    by_anomaly_type: dict[str, int] = Field(default_factory=dict)
    by_event_correlation: dict[str, int] = Field(default_factory=dict)
    by_recurrence_risk: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostAnomalyRootCauseEngine:
    """Correlate anomalies with events, decompose
    contributors, assess recurrence risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CostAnomalyRecord] = []
        self._analyses: dict[str, CostAnomalyAnalysis] = {}
        logger.info(
            "cost_anomaly_root_cause.init",
            max_records=max_records,
        )

    def add_record(
        self,
        anomaly_id: str = "",
        anomaly_type: AnomalyType = AnomalyType.SPIKE,
        event_correlation: EventCorrelation = (EventCorrelation.DEPLOYMENT),
        recurrence_risk: RecurrenceRisk = (RecurrenceRisk.POSSIBLE),
        anomaly_amount: float = 0.0,
        baseline_amount: float = 0.0,
        service_name: str = "",
        description: str = "",
    ) -> CostAnomalyRecord:
        record = CostAnomalyRecord(
            anomaly_id=anomaly_id,
            anomaly_type=anomaly_type,
            event_correlation=event_correlation,
            recurrence_risk=recurrence_risk,
            anomaly_amount=anomaly_amount,
            baseline_amount=baseline_amount,
            service_name=service_name,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_anomaly.record_added",
            record_id=record.id,
            anomaly_id=anomaly_id,
        )
        return record

    def process(self, key: str) -> CostAnomalyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        dev = 0.0
        if rec.baseline_amount > 0:
            dev = round(
                (rec.anomaly_amount - rec.baseline_amount) / rec.baseline_amount * 100,
                2,
            )
        contribs = sum(1 for r in self._records if r.anomaly_id == rec.anomaly_id)
        analysis = CostAnomalyAnalysis(
            anomaly_id=rec.anomaly_id,
            anomaly_type=rec.anomaly_type,
            deviation_pct=dev,
            root_cause=rec.event_correlation.value,
            recurrence_risk=rec.recurrence_risk,
            contributors=contribs,
            description=(f"Anomaly {rec.anomaly_id} dev {dev}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CostAnomalyReport:
        by_at: dict[str, int] = {}
        by_ec: dict[str, int] = {}
        by_rr: dict[str, int] = {}
        total_amt = 0.0
        for r in self._records:
            k = r.anomaly_type.value
            by_at[k] = by_at.get(k, 0) + 1
            k2 = r.event_correlation.value
            by_ec[k2] = by_ec.get(k2, 0) + 1
            k3 = r.recurrence_risk.value
            by_rr[k3] = by_rr.get(k3, 0) + 1
            total_amt += r.anomaly_amount
        recs: list[str] = []
        likely = [r for r in self._records if r.recurrence_risk == RecurrenceRisk.LIKELY]
        if likely:
            recs.append(f"{len(likely)} anomalies likely to recur")
        if not recs:
            recs.append("No recurring anomalies")
        return CostAnomalyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_anomaly_amount=round(total_amt, 2),
            by_anomaly_type=by_at,
            by_event_correlation=by_ec,
            by_recurrence_risk=by_rr,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        at_dist: dict[str, int] = {}
        for r in self._records:
            k = r.anomaly_type.value
            at_dist[k] = at_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "anomaly_type_distribution": at_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("cost_anomaly_root_cause.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def correlate_anomaly_with_events(
        self,
    ) -> list[dict[str, Any]]:
        """Correlate anomalies with events."""
        event_map: dict[str, list[float]] = {}
        for r in self._records:
            k = r.event_correlation.value
            event_map.setdefault(k, []).append(r.anomaly_amount)
        results: list[dict[str, Any]] = []
        for evt, amounts in event_map.items():
            total = round(sum(amounts), 2)
            results.append(
                {
                    "event_type": evt,
                    "anomaly_count": len(amounts),
                    "total_amount": total,
                    "avg_amount": round(total / len(amounts), 2),
                }
            )
        results.sort(
            key=lambda x: x["total_amount"],
            reverse=True,
        )
        return results

    def decompose_anomaly_contributors(
        self,
    ) -> list[dict[str, Any]]:
        """Decompose anomaly by contributors."""
        svc_map: dict[str, list[float]] = {}
        for r in self._records:
            svc_map.setdefault(r.service_name, []).append(r.anomaly_amount)
        results: list[dict[str, Any]] = []
        for svc, amounts in svc_map.items():
            total = round(sum(amounts), 2)
            results.append(
                {
                    "service_name": svc,
                    "contribution_count": len(amounts),
                    "total_amount": total,
                }
            )
        results.sort(
            key=lambda x: x["total_amount"],
            reverse=True,
        )
        return results

    def assess_anomaly_recurrence_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Assess recurrence risk per anomaly."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.anomaly_id not in seen:
                seen.add(r.anomaly_id)
                count = sum(1 for x in self._records if x.anomaly_id == r.anomaly_id)
                results.append(
                    {
                        "anomaly_id": r.anomaly_id,
                        "type": (r.anomaly_type.value),
                        "recurrence_risk": (r.recurrence_risk.value),
                        "occurrences": count,
                        "total_amount": round(r.anomaly_amount, 2),
                    }
                )
        results.sort(
            key=lambda x: x["occurrences"],
            reverse=True,
        )
        return results
