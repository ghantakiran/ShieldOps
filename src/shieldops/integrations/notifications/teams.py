"""Microsoft Teams Notifier — adaptive card notifications with channel routing."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CardType(StrEnum):
    ALERT = "alert"
    INCIDENT = "incident"
    DEPLOYMENT = "deployment"
    COMPLIANCE = "compliance"
    SUMMARY = "summary"


class ChannelPriority(StrEnum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    INFORMATIONAL = "informational"


class DeliveryOutcome(StrEnum):
    DELIVERED = "delivered"
    FAILED = "failed"
    THROTTLED = "throttled"
    CHANNEL_NOT_FOUND = "channel_not_found"
    RETRY_PENDING = "retry_pending"


# --- Models ---


class TeamsMessageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_name: str = ""
    card_type: CardType = CardType.ALERT
    channel_priority: ChannelPriority = ChannelPriority.NORMAL
    delivery_outcome: DeliveryOutcome = DeliveryOutcome.DELIVERED
    message_size_bytes: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AdaptiveCardEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    card_label: str = ""
    card_type: CardType = CardType.ALERT
    delivery_outcome: DeliveryOutcome = DeliveryOutcome.DELIVERED
    render_time_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


class TeamsNotifierReport(BaseModel):
    total_messages: int = 0
    total_cards: int = 0
    delivery_rate_pct: float = 0.0
    by_card_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    throttle_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MicrosoftTeamsNotifier:
    """Adaptive card notifications with channel routing."""

    def __init__(
        self,
        max_records: int = 200000,
        max_retries: int = 3,
    ) -> None:
        self._max_records = max_records
        self._max_retries = max_retries
        self._records: list[TeamsMessageRecord] = []
        self._cards: list[AdaptiveCardEntry] = []
        logger.info(
            "teams_notifier.initialized",
            max_records=max_records,
            max_retries=max_retries,
        )

    # -- record / get / list ---------------------------------------------

    def record_message(
        self,
        channel_name: str,
        card_type: CardType = CardType.ALERT,
        channel_priority: ChannelPriority = ChannelPriority.NORMAL,
        delivery_outcome: DeliveryOutcome = DeliveryOutcome.DELIVERED,
        message_size_bytes: int = 0,
        details: str = "",
    ) -> TeamsMessageRecord:
        record = TeamsMessageRecord(
            channel_name=channel_name,
            card_type=card_type,
            channel_priority=channel_priority,
            delivery_outcome=delivery_outcome,
            message_size_bytes=message_size_bytes,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "teams_notifier.message_recorded",
            record_id=record.id,
            channel_name=channel_name,
            card_type=card_type.value,
            delivery_outcome=delivery_outcome.value,
        )
        return record

    def get_message(self, record_id: str) -> TeamsMessageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_messages(
        self,
        channel_name: str | None = None,
        card_type: CardType | None = None,
        limit: int = 50,
    ) -> list[TeamsMessageRecord]:
        results = list(self._records)
        if channel_name is not None:
            results = [r for r in results if r.channel_name == channel_name]
        if card_type is not None:
            results = [r for r in results if r.card_type == card_type]
        return results[-limit:]

    def add_card(
        self,
        card_label: str,
        card_type: CardType = CardType.ALERT,
        delivery_outcome: DeliveryOutcome = DeliveryOutcome.DELIVERED,
        render_time_ms: float = 0.0,
    ) -> AdaptiveCardEntry:
        card = AdaptiveCardEntry(
            card_label=card_label,
            card_type=card_type,
            delivery_outcome=delivery_outcome,
            render_time_ms=render_time_ms,
        )
        self._cards.append(card)
        if len(self._cards) > self._max_records:
            self._cards = self._cards[-self._max_records :]
        logger.info(
            "teams_notifier.card_added",
            card_label=card_label,
            card_type=card_type.value,
            delivery_outcome=delivery_outcome.value,
        )
        return card

    # -- domain operations -----------------------------------------------

    def analyze_channel_delivery(self, channel_name: str) -> dict[str, Any]:
        """Analyze delivery performance for a specific channel."""
        records = [r for r in self._records if r.channel_name == channel_name]
        if not records:
            return {"channel_name": channel_name, "status": "no_data"}
        delivered = sum(1 for r in records if r.delivery_outcome == DeliveryOutcome.DELIVERED)
        delivery_rate = round(delivered / len(records) * 100, 2)
        avg_size = round(sum(r.message_size_bytes for r in records) / len(records), 2)
        return {
            "channel_name": channel_name,
            "total_messages": len(records),
            "delivered_count": delivered,
            "delivery_rate_pct": delivery_rate,
            "avg_message_size_bytes": avg_size,
            "meets_threshold": delivery_rate >= (100.0 - self._max_retries * 10),
        }

    def identify_failed_notifications(self) -> list[dict[str, Any]]:
        """Find channels with repeated notification failures."""
        failure_counts: dict[str, int] = {}
        for r in self._records:
            if r.delivery_outcome in (
                DeliveryOutcome.FAILED,
                DeliveryOutcome.CHANNEL_NOT_FOUND,
                DeliveryOutcome.RETRY_PENDING,
            ):
                failure_counts[r.channel_name] = failure_counts.get(r.channel_name, 0) + 1
        results: list[dict[str, Any]] = []
        for channel, count in failure_counts.items():
            if count > 1:
                results.append(
                    {
                        "channel_name": channel,
                        "failure_count": count,
                    }
                )
        results.sort(key=lambda x: x["failure_count"], reverse=True)
        return results

    def rank_by_channel_volume(self) -> list[dict[str, Any]]:
        """Rank channels by message volume descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.channel_name] = freq.get(r.channel_name, 0) + 1
        results: list[dict[str, Any]] = []
        for channel, count in freq.items():
            results.append(
                {
                    "channel_name": channel,
                    "message_count": count,
                }
            )
        results.sort(key=lambda x: x["message_count"], reverse=True)
        return results

    def detect_throttling_patterns(self) -> list[dict[str, Any]]:
        """Detect channels with throttling patterns (>3 non-delivered)."""
        non_delivered: dict[str, int] = {}
        for r in self._records:
            if r.delivery_outcome != DeliveryOutcome.DELIVERED:
                non_delivered[r.channel_name] = non_delivered.get(r.channel_name, 0) + 1
        results: list[dict[str, Any]] = []
        for channel, count in non_delivered.items():
            if count > 3:
                results.append(
                    {
                        "channel_name": channel,
                        "non_delivered_count": count,
                        "throttling_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_delivered_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> TeamsNotifierReport:
        by_card_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_card_type[r.card_type.value] = by_card_type.get(r.card_type.value, 0) + 1
            by_outcome[r.delivery_outcome.value] = by_outcome.get(r.delivery_outcome.value, 0) + 1
        delivered_count = sum(
            1 for r in self._records if r.delivery_outcome == DeliveryOutcome.DELIVERED
        )
        delivery_rate = (
            round(delivered_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        failed_notifications = sum(1 for d in self.identify_failed_notifications())
        recs: list[str] = []
        if delivery_rate < 95.0:
            recs.append(f"Delivery rate {delivery_rate}% is below 95.0% threshold")
        if failed_notifications > 0:
            recs.append(f"{failed_notifications} channel(s) with repeated failures")
        throttles = len(self.detect_throttling_patterns())
        if throttles > 0:
            recs.append(f"{throttles} channel(s) detected with throttling patterns")
        if not recs:
            recs.append("Teams notification delivery meets targets")
        return TeamsNotifierReport(
            total_messages=len(self._records),
            total_cards=len(self._cards),
            delivery_rate_pct=delivery_rate,
            by_card_type=by_card_type,
            by_outcome=by_outcome,
            throttle_count=throttles,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._cards.clear()
        logger.info("teams_notifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        card_type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.card_type.value
            card_type_dist[key] = card_type_dist.get(key, 0) + 1
        return {
            "total_messages": len(self._records),
            "total_cards": len(self._cards),
            "max_retries": self._max_retries,
            "card_type_distribution": card_type_dist,
            "unique_channels": len({r.channel_name for r in self._records}),
        }
