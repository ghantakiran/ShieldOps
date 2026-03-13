"""Notification Channel Effectiveness
rank channels by response rate, detect degradation,
recommend channel optimization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChannelType(StrEnum):
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    SMS = "sms"
    EMAIL = "email"


class EffectivenessRating(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class DeliveryStatus(StrEnum):
    DELIVERED = "delivered"
    DELAYED = "delayed"
    FAILED = "failed"
    UNKNOWN = "unknown"


# --- Models ---


class NotificationChannelRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_type: ChannelType = ChannelType.SLACK
    effectiveness: EffectivenessRating = EffectivenessRating.GOOD
    delivery_status: DeliveryStatus = DeliveryStatus.DELIVERED
    response_time_ms: float = 0.0
    acknowledged: bool = False
    recipient_id: str = ""
    incident_id: str = ""
    created_at: float = Field(default_factory=time.time)


class NotificationChannelAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_type: ChannelType = ChannelType.SLACK
    effectiveness: EffectivenessRating = EffectivenessRating.GOOD
    avg_response_time_ms: float = 0.0
    delivery_rate: float = 0.0
    acknowledgment_rate: float = 0.0
    notification_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class NotificationChannelReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_response_time: float = 0.0
    by_channel_type: dict[str, int] = Field(default_factory=dict)
    by_effectiveness: dict[str, int] = Field(default_factory=dict)
    by_delivery_status: dict[str, int] = Field(default_factory=dict)
    degraded_channels: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class NotificationChannelEffectiveness:
    """Rank channels by response rate, detect
    degradation, recommend optimization."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[NotificationChannelRecord] = []
        self._analyses: dict[str, NotificationChannelAnalysis] = {}
        logger.info(
            "notification_channel_effectiveness.init",
            max_records=max_records,
        )

    def add_record(
        self,
        channel_type: ChannelType = ChannelType.SLACK,
        effectiveness: EffectivenessRating = (EffectivenessRating.GOOD),
        delivery_status: DeliveryStatus = (DeliveryStatus.DELIVERED),
        response_time_ms: float = 0.0,
        acknowledged: bool = False,
        recipient_id: str = "",
        incident_id: str = "",
    ) -> NotificationChannelRecord:
        record = NotificationChannelRecord(
            channel_type=channel_type,
            effectiveness=effectiveness,
            delivery_status=delivery_status,
            response_time_ms=response_time_ms,
            acknowledged=acknowledged,
            recipient_id=recipient_id,
            incident_id=incident_id,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "notification_channel.record_added",
            record_id=record.id,
            channel_type=channel_type.value,
        )
        return record

    def process(self, key: str) -> NotificationChannelAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.channel_type == rec.channel_type]
        count = len(related)
        del_rate = (
            sum(1 for r in related if r.delivery_status == DeliveryStatus.DELIVERED) / count
            if count
            else 0.0
        )
        ack_rate = sum(1 for r in related if r.acknowledged) / count if count else 0.0
        avg_rt = sum(r.response_time_ms for r in related) / count if count else 0.0
        analysis = NotificationChannelAnalysis(
            channel_type=rec.channel_type,
            effectiveness=rec.effectiveness,
            avg_response_time_ms=round(avg_rt, 2),
            delivery_rate=round(del_rate, 2),
            acknowledgment_rate=round(ack_rate, 2),
            notification_count=count,
            description=(f"Channel {rec.channel_type.value} ack rate {ack_rate:.2f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> NotificationChannelReport:
        by_ct: dict[str, int] = {}
        by_ef: dict[str, int] = {}
        by_ds: dict[str, int] = {}
        rts: list[float] = []
        for r in self._records:
            k = r.channel_type.value
            by_ct[k] = by_ct.get(k, 0) + 1
            k2 = r.effectiveness.value
            by_ef[k2] = by_ef.get(k2, 0) + 1
            k3 = r.delivery_status.value
            by_ds[k3] = by_ds.get(k3, 0) + 1
            rts.append(r.response_time_ms)
        avg_rt = round(sum(rts) / len(rts), 2) if rts else 0.0
        degraded = list(
            {
                r.channel_type.value
                for r in self._records
                if r.effectiveness
                in (
                    EffectivenessRating.FAIR,
                    EffectivenessRating.POOR,
                )
            }
        )[:10]
        recs: list[str] = []
        if degraded:
            recs.append(f"{len(degraded)} degraded channels")
        if not recs:
            recs.append("All channels performing well")
        return NotificationChannelReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_response_time=avg_rt,
            by_channel_type=by_ct,
            by_effectiveness=by_ef,
            by_delivery_status=by_ds,
            degraded_channels=degraded,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ct_dist: dict[str, int] = {}
        for r in self._records:
            k = r.channel_type.value
            ct_dist[k] = ct_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "channel_type_distribution": ct_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("notification_channel_eff.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def rank_channels_by_response_rate(
        self,
    ) -> list[dict[str, Any]]:
        """Rank channels by response rate."""
        ch_data: dict[str, list[float]] = {}
        ch_ack: dict[str, list[bool]] = {}
        for r in self._records:
            c = r.channel_type.value
            ch_data.setdefault(c, []).append(r.response_time_ms)
            ch_ack.setdefault(c, []).append(r.acknowledged)
        results: list[dict[str, Any]] = []
        for ch, times in ch_data.items():
            acks = ch_ack[ch]
            ack_rate = sum(1 for a in acks if a) / len(acks) if acks else 0.0
            avg_rt = sum(times) / len(times) if times else 0.0
            results.append(
                {
                    "channel": ch,
                    "ack_rate": round(ack_rate, 2),
                    "avg_response_ms": round(avg_rt, 2),
                    "notification_count": len(times),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["ack_rate"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results

    def detect_channel_degradation(
        self,
    ) -> list[dict[str, Any]]:
        """Detect channel degradation."""
        ch_status: dict[str, dict[str, int]] = {}
        for r in self._records:
            c = r.channel_type.value
            if c not in ch_status:
                ch_status[c] = {}
            s = r.delivery_status.value
            ch_status[c][s] = ch_status[c].get(s, 0) + 1
        results: list[dict[str, Any]] = []
        for ch, statuses in ch_status.items():
            total = sum(statuses.values())
            failed = statuses.get("failed", 0) + statuses.get("delayed", 0)
            fail_rate = failed / total if total else 0.0
            results.append(
                {
                    "channel": ch,
                    "total_notifications": total,
                    "failure_rate": round(fail_rate, 2),
                    "statuses": statuses,
                    "degraded": fail_rate > 0.1,
                }
            )
        results.sort(
            key=lambda x: x["failure_rate"],
            reverse=True,
        )
        return results

    def recommend_channel_optimization(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend channel optimization."""
        ch_ack: dict[str, list[bool]] = {}
        ch_rt: dict[str, list[float]] = {}
        for r in self._records:
            c = r.channel_type.value
            ch_ack.setdefault(c, []).append(r.acknowledged)
            ch_rt.setdefault(c, []).append(r.response_time_ms)
        results: list[dict[str, Any]] = []
        for ch in ch_ack:
            acks = ch_ack[ch]
            rate = sum(1 for a in acks if a) / len(acks) if acks else 0.0
            times = ch_rt[ch]
            avg_rt = sum(times) / len(times) if times else 0.0
            rec = "maintain"
            if rate < 0.5:
                rec = "replace"
            elif rate < 0.7:
                rec = "improve"
            results.append(
                {
                    "channel": ch,
                    "ack_rate": round(rate, 2),
                    "avg_response_ms": round(avg_rt, 2),
                    "recommendation": rec,
                }
            )
        results.sort(
            key=lambda x: x["ack_rate"],
            reverse=True,
        )
        return results
