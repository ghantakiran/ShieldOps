"""Risk-Based Prioritizer
prioritize alert queues by risk score, compute
queue efficiency, detect priority inversions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PrioritizationMethod(StrEnum):
    RISK_SCORE = "risk_score"
    ASSET_VALUE = "asset_value"
    THREAT_SEVERITY = "threat_severity"
    COMPOSITE = "composite"


class QueuePosition(StrEnum):
    IMMEDIATE = "immediate"
    NEXT = "next"
    STANDARD = "standard"
    DEFERRED = "deferred"


class AnalystWorkload(StrEnum):
    OVERLOADED = "overloaded"
    BUSY = "busy"
    NORMAL = "normal"
    IDLE = "idle"


# --- Models ---


class PrioritizationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    method: PrioritizationMethod = PrioritizationMethod.RISK_SCORE
    position: QueuePosition = QueuePosition.STANDARD
    workload: AnalystWorkload = AnalystWorkload.NORMAL
    risk_score: float = 0.0
    asset_value: float = 0.0
    analyst_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PrioritizationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    computed_priority: float = 0.0
    position: QueuePosition = QueuePosition.STANDARD
    inversion_detected: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PrioritizationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_method: dict[str, int] = Field(default_factory=dict)
    by_position: dict[str, int] = Field(default_factory=dict)
    by_workload: dict[str, int] = Field(default_factory=dict)
    inversion_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskBasedPrioritizer:
    """Prioritize alerts by risk, compute queue
    efficiency, detect priority inversions."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[PrioritizationRecord] = []
        self._analyses: dict[str, PrioritizationAnalysis] = {}
        logger.info(
            "risk_based_prioritizer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        alert_id: str = "",
        method: PrioritizationMethod = (PrioritizationMethod.RISK_SCORE),
        position: QueuePosition = (QueuePosition.STANDARD),
        workload: AnalystWorkload = (AnalystWorkload.NORMAL),
        risk_score: float = 0.0,
        asset_value: float = 0.0,
        analyst_id: str = "",
        description: str = "",
    ) -> PrioritizationRecord:
        record = PrioritizationRecord(
            alert_id=alert_id,
            method=method,
            position=position,
            workload=workload,
            risk_score=risk_score,
            asset_value=asset_value,
            analyst_id=analyst_id,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_based_prioritizer.record_added",
            record_id=record.id,
            alert_id=alert_id,
        )
        return record

    def process(self, key: str) -> PrioritizationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        priority = round(
            rec.risk_score * 0.6 + rec.asset_value * 0.4,
            2,
        )
        pos_order = {
            "immediate": 0,
            "next": 1,
            "standard": 2,
            "deferred": 3,
        }
        expected_pos = (
            QueuePosition.IMMEDIATE
            if priority >= 80
            else QueuePosition.NEXT
            if priority >= 50
            else QueuePosition.STANDARD
            if priority >= 20
            else QueuePosition.DEFERRED
        )
        inversion = pos_order.get(rec.position.value, 2) > pos_order.get(expected_pos.value, 2)
        analysis = PrioritizationAnalysis(
            alert_id=rec.alert_id,
            computed_priority=priority,
            position=expected_pos,
            inversion_detected=inversion,
            description=(f"Alert {rec.alert_id} priority={priority}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> PrioritizationReport:
        by_m: dict[str, int] = {}
        by_p: dict[str, int] = {}
        by_w: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.method.value
            by_m[k] = by_m.get(k, 0) + 1
            k2 = r.position.value
            by_p[k2] = by_p.get(k2, 0) + 1
            k3 = r.workload.value
            by_w[k3] = by_w.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        inversions = sum(1 for a in self._analyses.values() if a.inversion_detected)
        recs: list[str] = []
        if inversions > 0:
            recs.append(f"{inversions} priority inversions")
        overloaded = by_w.get("overloaded", 0)
        if overloaded > 0:
            recs.append(f"{overloaded} overloaded analysts")
        if not recs:
            recs.append("Queue priorities are healthy")
        return PrioritizationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_method=by_m,
            by_position=by_p,
            by_workload=by_w,
            inversion_count=inversions,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        pos_dist: dict[str, int] = {}
        for r in self._records:
            k = r.position.value
            pos_dist[k] = pos_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "position_distribution": pos_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("risk_based_prioritizer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def prioritize_alert_queue(
        self,
    ) -> list[dict[str, Any]]:
        """Prioritize alerts by composite score."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            priority = round(
                r.risk_score * 0.6 + r.asset_value * 0.4,
                2,
            )
            results.append(
                {
                    "alert_id": r.alert_id,
                    "risk_score": r.risk_score,
                    "asset_value": r.asset_value,
                    "composite_priority": priority,
                    "position": r.position.value,
                }
            )
        results.sort(
            key=lambda x: x["composite_priority"],
            reverse=True,
        )
        return results

    def compute_queue_efficiency(
        self,
    ) -> dict[str, Any]:
        """Compute queue efficiency metrics."""
        if not self._records:
            return {
                "efficiency_pct": 0.0,
                "avg_wait_position": 0.0,
            }
        pos_vals = {
            "immediate": 1,
            "next": 2,
            "standard": 3,
            "deferred": 4,
        }
        positions = [pos_vals.get(r.position.value, 3) for r in self._records]
        avg_pos = round(sum(positions) / len(positions), 2)
        high_risk_immediate = sum(
            1
            for r in self._records
            if r.risk_score >= 80.0 and r.position == QueuePosition.IMMEDIATE
        )
        high_risk_total = sum(1 for r in self._records if r.risk_score >= 80.0)
        eff = (
            round(
                high_risk_immediate / high_risk_total * 100,
                2,
            )
            if high_risk_total > 0
            else 100.0
        )
        return {
            "efficiency_pct": eff,
            "avg_wait_position": avg_pos,
        }

    def detect_priority_inversions(
        self,
    ) -> list[dict[str, Any]]:
        """Find alerts with wrong queue position."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            priority = round(
                r.risk_score * 0.6 + r.asset_value * 0.4,
                2,
            )
            expected = (
                "immediate"
                if priority >= 80
                else "next"
                if priority >= 50
                else "standard"
                if priority >= 20
                else "deferred"
            )
            if r.position.value != expected:
                results.append(
                    {
                        "alert_id": r.alert_id,
                        "current_position": (r.position.value),
                        "expected_position": expected,
                        "composite_priority": priority,
                    }
                )
        return results
