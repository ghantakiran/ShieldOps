"""Communication Effectiveness Analyzer — measure incident communication effectiveness."""

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
    EMAIL = "email"
    PAGERDUTY = "pagerduty"
    SMS = "sms"
    STATUS_PAGE = "status_page"


class DeliveryStatus(StrEnum):
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    MISSED = "missed"
    DELAYED = "delayed"
    BOUNCED = "bounced"


class AudienceType(StrEnum):
    ENGINEERING = "engineering"
    MANAGEMENT = "management"
    CUSTOMER = "customer"
    EXECUTIVE = "executive"
    EXTERNAL = "external"


# --- Models ---


class CommDeliveryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    channel: ChannelType = ChannelType.SLACK
    audience: AudienceType = AudienceType.ENGINEERING
    status: DeliveryStatus = DeliveryStatus.DELIVERED
    delivery_time_seconds: float = 0.0
    ack_time_seconds: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CommChannelMetrics(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel: ChannelType = ChannelType.SLACK
    delivery_rate_pct: float = 0.0
    avg_ack_time_seconds: float = 0.0
    total_sent: int = 0
    total_missed: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CommEffectivenessReport(BaseModel):
    total_deliveries: int = 0
    total_channel_metrics: int = 0
    avg_delivery_rate_pct: float = 0.0
    by_channel: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    underperforming_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CommEffectivenessAnalyzer:
    """Measure incident communication effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        min_delivery_rate_pct: float = 95.0,
    ) -> None:
        self._max_records = max_records
        self._min_delivery_rate_pct = min_delivery_rate_pct
        self._records: list[CommDeliveryRecord] = []
        self._channel_metrics: list[CommChannelMetrics] = []
        logger.info(
            "comm_effectiveness.initialized",
            max_records=max_records,
            min_delivery_rate_pct=min_delivery_rate_pct,
        )

    # -- record / get / list -------------------------------------------------

    def record_delivery(
        self,
        incident_id: str,
        channel: ChannelType = ChannelType.SLACK,
        audience: AudienceType = AudienceType.ENGINEERING,
        status: DeliveryStatus = DeliveryStatus.DELIVERED,
        delivery_time_seconds: float = 0.0,
        ack_time_seconds: float = 0.0,
        details: str = "",
    ) -> CommDeliveryRecord:
        record = CommDeliveryRecord(
            incident_id=incident_id,
            channel=channel,
            audience=audience,
            status=status,
            delivery_time_seconds=delivery_time_seconds,
            ack_time_seconds=ack_time_seconds,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "comm_effectiveness.delivery_recorded",
            record_id=record.id,
            incident_id=incident_id,
            channel=channel.value,
        )
        return record

    def get_delivery(self, record_id: str) -> CommDeliveryRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_deliveries(
        self,
        incident_id: str | None = None,
        channel: ChannelType | None = None,
        limit: int = 50,
    ) -> list[CommDeliveryRecord]:
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if channel is not None:
            results = [r for r in results if r.channel == channel]
        return results[-limit:]

    def record_channel_metrics(
        self,
        channel: ChannelType = ChannelType.SLACK,
        delivery_rate_pct: float = 0.0,
        avg_ack_time_seconds: float = 0.0,
        total_sent: int = 0,
        total_missed: int = 0,
        details: str = "",
    ) -> CommChannelMetrics:
        metrics = CommChannelMetrics(
            channel=channel,
            delivery_rate_pct=delivery_rate_pct,
            avg_ack_time_seconds=avg_ack_time_seconds,
            total_sent=total_sent,
            total_missed=total_missed,
            details=details,
        )
        self._channel_metrics.append(metrics)
        if len(self._channel_metrics) > self._max_records:
            self._channel_metrics = self._channel_metrics[-self._max_records :]
        logger.info(
            "comm_effectiveness.channel_metrics_recorded",
            channel=channel.value,
            delivery_rate_pct=delivery_rate_pct,
        )
        return metrics

    # -- domain operations ---------------------------------------------------

    def analyze_channel_effectiveness(self, channel: ChannelType) -> dict[str, Any]:
        """Analyze effectiveness for a specific channel."""
        metrics = [m for m in self._channel_metrics if m.channel == channel]
        if not metrics:
            return {"channel": channel.value, "status": "no_data"}
        latest = metrics[-1]
        return {
            "channel": channel.value,
            "delivery_rate_pct": latest.delivery_rate_pct,
            "avg_ack_time_seconds": latest.avg_ack_time_seconds,
            "total_sent": latest.total_sent,
            "total_missed": latest.total_missed,
        }

    def identify_underperforming_channels(self) -> list[dict[str, Any]]:
        """Find channels with delivery rate below minimum threshold."""
        results: list[dict[str, Any]] = []
        for m in self._channel_metrics:
            if m.delivery_rate_pct < self._min_delivery_rate_pct:
                results.append(
                    {
                        "channel": m.channel.value,
                        "delivery_rate_pct": m.delivery_rate_pct,
                        "gap_pct": round(self._min_delivery_rate_pct - m.delivery_rate_pct, 2),
                        "total_missed": m.total_missed,
                    }
                )
        results.sort(key=lambda x: x["delivery_rate_pct"])
        return results

    def rank_channels_by_ack_time(self) -> list[dict[str, Any]]:
        """Rank channels by average acknowledgment time descending."""
        results: list[dict[str, Any]] = []
        for m in self._channel_metrics:
            results.append(
                {
                    "channel": m.channel.value,
                    "avg_ack_time_seconds": m.avg_ack_time_seconds,
                    "delivery_rate_pct": m.delivery_rate_pct,
                }
            )
        results.sort(key=lambda x: x["avg_ack_time_seconds"], reverse=True)
        return results

    def detect_communication_gaps(self) -> list[dict[str, Any]]:
        """Detect deliveries with MISSED or BOUNCED status."""
        results: list[dict[str, Any]] = []
        gap_statuses = {DeliveryStatus.MISSED, DeliveryStatus.BOUNCED}
        for r in self._records:
            if r.status in gap_statuses:
                results.append(
                    {
                        "incident_id": r.incident_id,
                        "channel": r.channel.value,
                        "audience": r.audience.value,
                        "status": r.status.value,
                    }
                )
        return results

    # -- report / stats ------------------------------------------------------

    def generate_report(self) -> CommEffectivenessReport:
        by_channel: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_channel[r.channel.value] = by_channel.get(r.channel.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        total_metrics = len(self._channel_metrics)
        avg_rate = (
            round(
                sum(m.delivery_rate_pct for m in self._channel_metrics) / total_metrics,
                2,
            )
            if total_metrics
            else 0.0
        )
        underperforming = sum(
            1 for m in self._channel_metrics if m.delivery_rate_pct < self._min_delivery_rate_pct
        )
        recs: list[str] = []
        if underperforming > 0:
            recs.append(
                f"{underperforming} channel(s) below {self._min_delivery_rate_pct}% delivery rate"
            )
        missed = sum(1 for r in self._records if r.status == DeliveryStatus.MISSED)
        if missed > 0:
            recs.append(f"{missed} missed delivery(ies) detected")
        if not recs:
            recs.append("Communication effectiveness meets targets")
        return CommEffectivenessReport(
            total_deliveries=len(self._records),
            total_channel_metrics=total_metrics,
            avg_delivery_rate_pct=avg_rate,
            by_channel=by_channel,
            by_status=by_status,
            underperforming_count=underperforming,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._channel_metrics.clear()
        logger.info("comm_effectiveness.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        channel_dist: dict[str, int] = {}
        for r in self._records:
            key = r.channel.value
            channel_dist[key] = channel_dist.get(key, 0) + 1
        return {
            "total_deliveries": len(self._records),
            "total_channel_metrics": len(self._channel_metrics),
            "min_delivery_rate_pct": self._min_delivery_rate_pct,
            "channel_distribution": channel_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
