"""Self-Tuning Alert Engine

Continuously optimizes alert rules by tracking signal
quality, recommending tuning actions, and measuring impact.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AlertSignalQuality(StrEnum):
    HIGH_SIGNAL = "high_signal"
    MODERATE_SIGNAL = "moderate_signal"
    LOW_SIGNAL = "low_signal"
    NOISE = "noise"
    UNKNOWN = "unknown"


class TuningAction(StrEnum):
    TIGHTEN_THRESHOLD = "tighten_threshold"
    LOOSEN_THRESHOLD = "loosen_threshold"
    CHANGE_ROUTING = "change_routing"
    ADD_CONTEXT = "add_context"
    SUPPRESS = "suppress"


class TuningOutcome(StrEnum):
    IMPROVED = "improved"
    NO_CHANGE = "no_change"
    DEGRADED = "degraded"
    PENDING = "pending"


# --- Models ---


class AlertTuningRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_rule_id: str = ""
    service: str = ""
    signal_quality: AlertSignalQuality = AlertSignalQuality.UNKNOWN
    action_taken_ratio: float = 0.0
    response_time_sec: float = 0.0
    acknowledged: bool = False
    tuning_action: TuningAction = TuningAction.ADD_CONTEXT
    tuning_outcome: TuningOutcome = TuningOutcome.PENDING
    false_positive_rate: float = 0.0
    created_at: float = Field(default_factory=time.time)


class AlertTuningAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_rule_id: str = ""
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertTuningReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_signal_to_noise: float = 0.0
    avg_false_positive_rate: float = 0.0
    by_quality: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SelfTuningAlertEngine:
    """Self-Tuning Alert Engine

    Optimizes alert rules by tracking signal quality,
    recommending tuning, and measuring impact.
    """

    def __init__(
        self,
        max_records: int = 200000,
        noise_threshold: float = 0.3,
    ) -> None:
        self._max_records = max_records
        self._noise_threshold = noise_threshold
        self._records: list[AlertTuningRecord] = []
        self._analyses: list[AlertTuningAnalysis] = []
        logger.info(
            "self_tuning_alert_engine.initialized",
            max_records=max_records,
            noise_threshold=noise_threshold,
        )

    def add_record(
        self,
        alert_rule_id: str,
        service: str,
        signal_quality: AlertSignalQuality = (AlertSignalQuality.UNKNOWN),
        action_taken_ratio: float = 0.0,
        response_time_sec: float = 0.0,
        acknowledged: bool = False,
        tuning_action: TuningAction = (TuningAction.ADD_CONTEXT),
        tuning_outcome: TuningOutcome = (TuningOutcome.PENDING),
        false_positive_rate: float = 0.0,
    ) -> AlertTuningRecord:
        record = AlertTuningRecord(
            alert_rule_id=alert_rule_id,
            service=service,
            signal_quality=signal_quality,
            action_taken_ratio=action_taken_ratio,
            response_time_sec=response_time_sec,
            acknowledged=acknowledged,
            tuning_action=tuning_action,
            tuning_outcome=tuning_outcome,
            false_positive_rate=false_positive_rate,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "self_tuning_alert_engine.record_added",
            record_id=record.id,
            alert_rule_id=alert_rule_id,
            service=service,
        )
        return record

    def compute_signal_to_noise(self, alert_rule_id: str = "") -> dict[str, Any]:
        matching = list(self._records)
        if alert_rule_id:
            matching = [r for r in matching if r.alert_rule_id == alert_rule_id]
        if not matching:
            return {
                "alert_rule_id": (alert_rule_id or "all"),
                "status": "no_data",
            }
        signal = sum(
            1
            for r in matching
            if r.signal_quality
            in (
                AlertSignalQuality.HIGH_SIGNAL,
                AlertSignalQuality.MODERATE_SIGNAL,
            )
        )
        noise = sum(
            1
            for r in matching
            if r.signal_quality
            in (
                AlertSignalQuality.LOW_SIGNAL,
                AlertSignalQuality.NOISE,
            )
        )
        ratio = round(signal / (signal + noise), 4) if (signal + noise) > 0 else 0.0
        return {
            "alert_rule_id": (alert_rule_id or "all"),
            "signal_count": signal,
            "noise_count": noise,
            "signal_to_noise_ratio": ratio,
        }

    def recommend_tuning(self, alert_rule_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.alert_rule_id == alert_rule_id]
        if not matching:
            return {
                "alert_rule_id": alert_rule_id,
                "status": "no_data",
            }
        fp_rates = [r.false_positive_rate for r in matching]
        avg_fp = round(sum(fp_rates) / len(fp_rates), 4)
        noise_count = sum(1 for r in matching if r.signal_quality == AlertSignalQuality.NOISE)
        noise_pct = round(noise_count / len(matching), 4)
        action = "no_change"
        if avg_fp > self._noise_threshold:
            action = "loosen_threshold"
        elif noise_pct > 0.5:
            action = "suppress"
        return {
            "alert_rule_id": alert_rule_id,
            "avg_fp_rate": avg_fp,
            "noise_pct": noise_pct,
            "recommended_action": action,
        }

    def evaluate_tuning_impact(self, alert_rule_id: str) -> dict[str, Any]:
        matching = [
            r
            for r in self._records
            if r.alert_rule_id == alert_rule_id and r.tuning_outcome != TuningOutcome.PENDING
        ]
        if not matching:
            return {
                "alert_rule_id": alert_rule_id,
                "status": "no_data",
            }
        improved = sum(1 for r in matching if r.tuning_outcome == TuningOutcome.IMPROVED)
        degraded = sum(1 for r in matching if r.tuning_outcome == TuningOutcome.DEGRADED)
        return {
            "alert_rule_id": alert_rule_id,
            "total_tunings": len(matching),
            "improved": improved,
            "degraded": degraded,
            "improvement_rate": round(improved / len(matching), 4),
        }

    def process(self, alert_rule_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.alert_rule_id == alert_rule_id]
        if not matching:
            return {
                "alert_rule_id": alert_rule_id,
                "status": "no_data",
            }
        fp_rates = [r.false_positive_rate for r in matching]
        avg_fp = round(sum(fp_rates) / len(fp_rates), 4)
        ack_rate = round(
            sum(1 for r in matching if r.acknowledged) / len(matching),
            4,
        )
        return {
            "alert_rule_id": alert_rule_id,
            "record_count": len(matching),
            "avg_fp_rate": avg_fp,
            "ack_rate": ack_rate,
        }

    def generate_report(self) -> AlertTuningReport:
        by_qual: dict[str, int] = {}
        by_act: dict[str, int] = {}
        by_out: dict[str, int] = {}
        for r in self._records:
            qv = r.signal_quality.value
            by_qual[qv] = by_qual.get(qv, 0) + 1
            av = r.tuning_action.value
            by_act[av] = by_act.get(av, 0) + 1
            ov = r.tuning_outcome.value
            by_out[ov] = by_out.get(ov, 0) + 1
        total = len(self._records)
        signal = by_qual.get("high_signal", 0) + by_qual.get("moderate_signal", 0)
        noise = by_qual.get("low_signal", 0) + by_qual.get("noise", 0)
        stn = round(signal / (signal + noise), 4) if (signal + noise) > 0 else 0.0
        fp_rates = [r.false_positive_rate for r in self._records]
        avg_fp = round(sum(fp_rates) / len(fp_rates), 4) if fp_rates else 0.0
        recs: list[str] = []
        if stn < 0.5:
            recs.append(f"Signal-to-noise {stn:.0%} — tune noisy alert rules")
        if avg_fp > self._noise_threshold:
            recs.append(f"Avg FP rate {avg_fp:.0%} — loosen thresholds")
        degraded = by_out.get("degraded", 0)
        if degraded > 0:
            recs.append(f"{degraded} tuning(s) degraded — review changes")
        if not recs:
            recs.append("Alert tuning health is nominal")
        return AlertTuningReport(
            total_records=total,
            total_analyses=len(self._analyses),
            avg_signal_to_noise=stn,
            avg_false_positive_rate=avg_fp,
            by_quality=by_qual,
            by_action=by_act,
            by_outcome=by_out,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        qual_dist: dict[str, int] = {}
        for r in self._records:
            k = r.signal_quality.value
            qual_dist[k] = qual_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "noise_threshold": (self._noise_threshold),
            "quality_distribution": qual_dist,
            "unique_rules": len({r.alert_rule_id for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("self_tuning_alert_engine.cleared")
        return {"status": "cleared"}
