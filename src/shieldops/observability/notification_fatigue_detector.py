"""Notification Fatigue Detector
detect fatigue patterns, calculate fatigue risk scores,
recommend load redistribution."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FatigueLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NotificationType(StrEnum):
    PAGE = "page"
    ALERT = "alert"
    WARNING = "warning"
    INFO = "info"


class DetectionMethod(StrEnum):
    VOLUME_BASED = "volume_based"
    LATENCY_BASED = "latency_based"
    ENGAGEMENT_BASED = "engagement_based"
    COMPOSITE = "composite"


# --- Models ---


class NotificationFatigueRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recipient_id: str = ""
    notification_type: NotificationType = NotificationType.ALERT
    fatigue_level: FatigueLevel = FatigueLevel.LOW
    detection_method: DetectionMethod = DetectionMethod.VOLUME_BASED
    volume: int = 0
    response_time_ms: float = 0.0
    acknowledged: bool = False
    source: str = ""
    created_at: float = Field(default_factory=time.time)


class NotificationFatigueAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recipient_id: str = ""
    fatigue_level: FatigueLevel = FatigueLevel.LOW
    fatigue_score: float = 0.0
    avg_response_time_ms: float = 0.0
    acknowledgment_rate: float = 0.0
    notification_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class NotificationFatigueReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_fatigue_score: float = 0.0
    by_fatigue_level: dict[str, int] = Field(default_factory=dict)
    by_notification_type: dict[str, int] = Field(default_factory=dict)
    by_detection_method: dict[str, int] = Field(default_factory=dict)
    high_fatigue_recipients: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class NotificationFatigueDetector:
    """Detect fatigue patterns, calculate fatigue risk
    scores, recommend load redistribution."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[NotificationFatigueRecord] = []
        self._analyses: dict[str, NotificationFatigueAnalysis] = {}
        logger.info(
            "notification_fatigue_detector.init",
            max_records=max_records,
        )

    def add_record(
        self,
        recipient_id: str = "",
        notification_type: NotificationType = (NotificationType.ALERT),
        fatigue_level: FatigueLevel = FatigueLevel.LOW,
        detection_method: DetectionMethod = (DetectionMethod.VOLUME_BASED),
        volume: int = 0,
        response_time_ms: float = 0.0,
        acknowledged: bool = False,
        source: str = "",
    ) -> NotificationFatigueRecord:
        record = NotificationFatigueRecord(
            recipient_id=recipient_id,
            notification_type=notification_type,
            fatigue_level=fatigue_level,
            detection_method=detection_method,
            volume=volume,
            response_time_ms=response_time_ms,
            acknowledged=acknowledged,
            source=source,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "notification_fatigue.record_added",
            record_id=record.id,
            recipient_id=recipient_id,
        )
        return record

    def process(self, key: str) -> NotificationFatigueAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.recipient_id == rec.recipient_id]
        count = len(related)
        ack_rate = sum(1 for r in related if r.acknowledged) / count if count else 0.0
        avg_rt = sum(r.response_time_ms for r in related) / count if count else 0.0
        score = min(
            100.0,
            (1.0 - ack_rate) * 50 + min(avg_rt / 100.0, 50.0),
        )
        analysis = NotificationFatigueAnalysis(
            recipient_id=rec.recipient_id,
            fatigue_level=rec.fatigue_level,
            fatigue_score=round(score, 2),
            avg_response_time_ms=round(avg_rt, 2),
            acknowledgment_rate=round(ack_rate, 2),
            notification_count=count,
            description=(f"Recipient {rec.recipient_id} fatigue score {score:.2f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> NotificationFatigueReport:
        by_fl: dict[str, int] = {}
        by_nt: dict[str, int] = {}
        by_dm: dict[str, int] = {}
        volumes: list[int] = []
        for r in self._records:
            k = r.fatigue_level.value
            by_fl[k] = by_fl.get(k, 0) + 1
            k2 = r.notification_type.value
            by_nt[k2] = by_nt.get(k2, 0) + 1
            k3 = r.detection_method.value
            by_dm[k3] = by_dm.get(k3, 0) + 1
            volumes.append(r.volume)
        avg_score = round(sum(volumes) / len(volumes), 2) if volumes else 0.0
        high = list(
            {
                r.recipient_id
                for r in self._records
                if r.fatigue_level in (FatigueLevel.CRITICAL, FatigueLevel.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} high-fatigue recipients")
        if not recs:
            recs.append("No significant fatigue detected")
        return NotificationFatigueReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_fatigue_score=avg_score,
            by_fatigue_level=by_fl,
            by_notification_type=by_nt,
            by_detection_method=by_dm,
            high_fatigue_recipients=high,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        fl_dist: dict[str, int] = {}
        for r in self._records:
            k = r.fatigue_level.value
            fl_dist[k] = fl_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "fatigue_level_distribution": fl_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("notification_fatigue_detector.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def detect_fatigue_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Detect fatigue patterns per recipient."""
        recipient_data: dict[str, list[float]] = {}
        recipient_ack: dict[str, list[bool]] = {}
        for r in self._records:
            recipient_data.setdefault(r.recipient_id, []).append(r.response_time_ms)
            recipient_ack.setdefault(r.recipient_id, []).append(r.acknowledged)
        results: list[dict[str, Any]] = []
        for rid, times in recipient_data.items():
            acks = recipient_ack[rid]
            ack_rate = sum(1 for a in acks if a) / len(acks) if acks else 0.0
            avg_rt = sum(times) / len(times) if times else 0.0
            results.append(
                {
                    "recipient_id": rid,
                    "notification_count": len(times),
                    "avg_response_time_ms": round(avg_rt, 2),
                    "acknowledgment_rate": round(ack_rate, 2),
                    "fatigue_detected": ack_rate < 0.5,
                }
            )
        results.sort(
            key=lambda x: x["acknowledgment_rate"],
        )
        return results

    def calculate_fatigue_risk_score(
        self,
    ) -> list[dict[str, Any]]:
        """Calculate fatigue risk score per recipient."""
        recipient_vols: dict[str, list[int]] = {}
        recipient_ack: dict[str, list[bool]] = {}
        for r in self._records:
            recipient_vols.setdefault(r.recipient_id, []).append(r.volume)
            recipient_ack.setdefault(r.recipient_id, []).append(r.acknowledged)
        results: list[dict[str, Any]] = []
        for rid, vols in recipient_vols.items():
            acks = recipient_ack[rid]
            ack_rate = sum(1 for a in acks if a) / len(acks) if acks else 0.0
            avg_vol = sum(vols) / len(vols) if vols else 0.0
            score = min(
                100.0,
                (1.0 - ack_rate) * 60 + min(avg_vol / 10.0, 40.0),
            )
            results.append(
                {
                    "recipient_id": rid,
                    "fatigue_risk_score": round(score, 2),
                    "avg_volume": round(avg_vol, 2),
                    "acknowledgment_rate": round(ack_rate, 2),
                }
            )
        results.sort(
            key=lambda x: x["fatigue_risk_score"],
            reverse=True,
        )
        return results

    def recommend_load_redistribution(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend load redistribution."""
        recipient_vols: dict[str, int] = {}
        for r in self._records:
            recipient_vols[r.recipient_id] = recipient_vols.get(r.recipient_id, 0) + r.volume
        if not recipient_vols:
            return []
        avg_load = sum(recipient_vols.values()) / len(recipient_vols)
        results: list[dict[str, Any]] = []
        for rid, total_vol in recipient_vols.items():
            overload = total_vol - avg_load
            results.append(
                {
                    "recipient_id": rid,
                    "total_volume": total_vol,
                    "avg_load": round(avg_load, 2),
                    "overload_amount": round(overload, 2),
                    "needs_redistribution": overload > avg_load * 0.5,
                }
            )
        results.sort(
            key=lambda x: x["overload_amount"],
            reverse=True,
        )
        return results
