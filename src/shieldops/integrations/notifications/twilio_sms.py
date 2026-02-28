"""Twilio SMS Gateway — SMS alerting with delivery tracking and opt-out management."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SMSPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DeliveryStatus(StrEnum):
    DELIVERED = "delivered"
    PENDING = "pending"
    FAILED = "failed"
    BOUNCED = "bounced"
    OPTED_OUT = "opted_out"


class MessageType(StrEnum):
    ALERT = "alert"
    ACKNOWLEDGMENT = "acknowledgment"
    ESCALATION = "escalation"
    NOTIFICATION = "notification"
    TWO_WAY = "two_way"


# --- Models ---


class SMSRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recipient_number: str = ""
    priority: SMSPriority = SMSPriority.MEDIUM
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    message_type: MessageType = MessageType.ALERT
    character_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DeliveryReceipt(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    receipt_id: str = ""
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    message_type: MessageType = MessageType.ALERT
    latency_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


class TwilioSMSReport(BaseModel):
    total_messages: int = 0
    total_receipts: int = 0
    delivery_rate_pct: float = 0.0
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    failed_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TwilioSMSGateway:
    """SMS alerting with delivery tracking and opt-out management."""

    def __init__(
        self,
        max_records: int = 200000,
        max_retries: int = 3,
    ) -> None:
        self._max_records = max_records
        self._max_retries = max_retries
        self._records: list[SMSRecord] = []
        self._receipts: list[DeliveryReceipt] = []
        logger.info(
            "twilio_sms.initialized",
            max_records=max_records,
            max_retries=max_retries,
        )

    # -- record / get / list ---------------------------------------------

    def record_message(
        self,
        recipient_number: str,
        priority: SMSPriority = SMSPriority.MEDIUM,
        delivery_status: DeliveryStatus = DeliveryStatus.PENDING,
        message_type: MessageType = MessageType.ALERT,
        character_count: int = 0,
        details: str = "",
    ) -> SMSRecord:
        record = SMSRecord(
            recipient_number=recipient_number,
            priority=priority,
            delivery_status=delivery_status,
            message_type=message_type,
            character_count=character_count,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "twilio_sms.message_recorded",
            record_id=record.id,
            recipient_number=recipient_number,
            priority=priority.value,
            delivery_status=delivery_status.value,
        )
        return record

    def get_message(self, record_id: str) -> SMSRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_messages(
        self,
        recipient_number: str | None = None,
        priority: SMSPriority | None = None,
        limit: int = 50,
    ) -> list[SMSRecord]:
        results = list(self._records)
        if recipient_number is not None:
            results = [r for r in results if r.recipient_number == recipient_number]
        if priority is not None:
            results = [r for r in results if r.priority == priority]
        return results[-limit:]

    def add_receipt(
        self,
        receipt_id: str,
        delivery_status: DeliveryStatus = DeliveryStatus.PENDING,
        message_type: MessageType = MessageType.ALERT,
        latency_ms: float = 0.0,
    ) -> DeliveryReceipt:
        receipt = DeliveryReceipt(
            receipt_id=receipt_id,
            delivery_status=delivery_status,
            message_type=message_type,
            latency_ms=latency_ms,
        )
        self._receipts.append(receipt)
        if len(self._receipts) > self._max_records:
            self._receipts = self._receipts[-self._max_records :]
        logger.info(
            "twilio_sms.receipt_added",
            receipt_id=receipt_id,
            delivery_status=delivery_status.value,
            message_type=message_type.value,
        )
        return receipt

    # -- domain operations -----------------------------------------------

    def analyze_delivery_performance(self, recipient_number: str) -> dict[str, Any]:
        """Analyze delivery performance for a specific recipient."""
        records = [r for r in self._records if r.recipient_number == recipient_number]
        if not records:
            return {"recipient_number": recipient_number, "status": "no_data"}
        delivered = sum(1 for r in records if r.delivery_status == DeliveryStatus.DELIVERED)
        delivery_rate = round(delivered / len(records) * 100, 2)
        avg_chars = round(sum(r.character_count for r in records) / len(records), 2)
        return {
            "recipient_number": recipient_number,
            "total_messages": len(records),
            "delivered_count": delivered,
            "delivery_rate_pct": delivery_rate,
            "avg_character_count": avg_chars,
            "meets_threshold": delivery_rate >= (100.0 - self._max_retries * 10),
        }

    def identify_failed_deliveries(self) -> list[dict[str, Any]]:
        """Find recipients with repeated delivery failures."""
        failure_counts: dict[str, int] = {}
        for r in self._records:
            if r.delivery_status in (
                DeliveryStatus.FAILED,
                DeliveryStatus.BOUNCED,
                DeliveryStatus.OPTED_OUT,
            ):
                failure_counts[r.recipient_number] = failure_counts.get(r.recipient_number, 0) + 1
        results: list[dict[str, Any]] = []
        for recipient, count in failure_counts.items():
            if count > 1:
                results.append(
                    {
                        "recipient_number": recipient,
                        "failure_count": count,
                    }
                )
        results.sort(key=lambda x: x["failure_count"], reverse=True)
        return results

    def rank_by_message_volume(self) -> list[dict[str, Any]]:
        """Rank recipients by message volume descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.recipient_number] = freq.get(r.recipient_number, 0) + 1
        results: list[dict[str, Any]] = []
        for recipient, count in freq.items():
            results.append(
                {
                    "recipient_number": recipient,
                    "message_count": count,
                }
            )
        results.sort(key=lambda x: x["message_count"], reverse=True)
        return results

    def detect_opt_out_patterns(self) -> list[dict[str, Any]]:
        """Detect recipients with opt-out patterns (>3 non-delivered)."""
        non_delivered: dict[str, int] = {}
        for r in self._records:
            if r.delivery_status != DeliveryStatus.DELIVERED:
                non_delivered[r.recipient_number] = non_delivered.get(r.recipient_number, 0) + 1
        results: list[dict[str, Any]] = []
        for recipient, count in non_delivered.items():
            if count > 3:
                results.append(
                    {
                        "recipient_number": recipient,
                        "non_delivered_count": count,
                        "opt_out_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_delivered_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> TwilioSMSReport:
        by_priority: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_priority[r.priority.value] = by_priority.get(r.priority.value, 0) + 1
            by_status[r.delivery_status.value] = by_status.get(r.delivery_status.value, 0) + 1
        delivered_count = sum(
            1 for r in self._records if r.delivery_status == DeliveryStatus.DELIVERED
        )
        delivery_rate = (
            round(delivered_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        failed_deliveries = sum(1 for d in self.identify_failed_deliveries())
        recs: list[str] = []
        if delivery_rate < 95.0:
            recs.append(f"Delivery rate {delivery_rate}% is below 95.0% threshold")
        if failed_deliveries > 0:
            recs.append(f"{failed_deliveries} recipient(s) with repeated failures")
        opt_outs = len(self.detect_opt_out_patterns())
        if opt_outs > 0:
            recs.append(f"{opt_outs} recipient(s) detected with opt-out patterns")
        if not recs:
            recs.append("SMS delivery performance meets targets")
        return TwilioSMSReport(
            total_messages=len(self._records),
            total_receipts=len(self._receipts),
            delivery_rate_pct=delivery_rate,
            by_priority=by_priority,
            by_status=by_status,
            failed_count=failed_deliveries,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._receipts.clear()
        logger.info("twilio_sms.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        priority_dist: dict[str, int] = {}
        for r in self._records:
            key = r.priority.value
            priority_dist[key] = priority_dist.get(key, 0) + 1
        return {
            "total_messages": len(self._records),
            "total_receipts": len(self._receipts),
            "max_retries": self._max_retries,
            "priority_distribution": priority_dist,
            "unique_recipients": len({r.recipient_number for r in self._records}),
        }
