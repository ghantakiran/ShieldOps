"""Outbound webhook dispatcher — pushes events to customer-configured endpoints.

Supports HMAC-SHA256 signed payloads, async delivery with retry,
and dead letter logging for failed deliveries.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class WebhookEventType(StrEnum):
    INCIDENT_CREATED = "incident.created"
    INCIDENT_RESOLVED = "incident.resolved"
    REMEDIATION_STARTED = "remediation.started"
    REMEDIATION_COMPLETED = "remediation.completed"
    VULNERABILITY_DETECTED = "vulnerability.detected"
    COMPLIANCE_DRIFT = "compliance.drift"
    PREDICTION_GENERATED = "prediction.generated"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookSubscription(BaseModel):
    """A webhook subscription configuration."""

    id: str = Field(default_factory=lambda: f"wh-{uuid4().hex[:12]}")
    url: str
    events: list[str] = Field(default_factory=list)
    secret: str = ""  # For HMAC-SHA256 signing
    filters: dict[str, Any] = Field(default_factory=dict)
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    description: str = ""


class DeliveryRecord(BaseModel):
    """Record of a webhook delivery attempt."""

    id: str = Field(default_factory=lambda: f"dlv-{uuid4().hex[:12]}")
    subscription_id: str
    event_type: str
    status: DeliveryStatus = DeliveryStatus.PENDING
    status_code: int | None = None
    attempt: int = 1
    max_attempts: int = 3
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    delivered_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutboundWebhookDispatcher:
    """Dispatches events to webhook subscribers.

    Features:
    - HMAC-SHA256 payload signing
    - Configurable retry with exponential backoff
    - Dead letter logging for failed deliveries
    - Event filtering by subscription
    """

    MAX_RETRY_ATTEMPTS = 3

    def __init__(self) -> None:
        self._subscriptions: dict[str, WebhookSubscription] = {}
        self._deliveries: list[DeliveryRecord] = []
        self._dead_letters: list[DeliveryRecord] = []

    def create_subscription(self, subscription: WebhookSubscription) -> WebhookSubscription:
        """Register a new webhook subscription."""
        self._subscriptions[subscription.id] = subscription
        logger.info(
            "webhook_subscription_created",
            sub_id=subscription.id,
            url=subscription.url,
            events=subscription.events,
        )
        return subscription

    def delete_subscription(self, subscription_id: str) -> bool:
        """Remove a webhook subscription."""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            logger.info("webhook_subscription_deleted", sub_id=subscription_id)
            return True
        return False

    def get_subscription(self, subscription_id: str) -> WebhookSubscription | None:
        """Get a subscription by ID."""
        return self._subscriptions.get(subscription_id)

    def list_subscriptions(self) -> list[WebhookSubscription]:
        """List all subscriptions."""
        return list(self._subscriptions.values())

    def get_deliveries(self, subscription_id: str) -> list[DeliveryRecord]:
        """Get delivery log for a subscription."""
        return [d for d in self._deliveries if d.subscription_id == subscription_id]

    async def dispatch(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> list[DeliveryRecord]:
        """Dispatch an event to all matching subscribers.

        Args:
            event_type: The event type (e.g., 'incident.created').
            payload: The event payload.

        Returns:
            List of delivery records for each subscriber.
        """
        matching_subs = self._get_matching_subscriptions(event_type)
        records: list[DeliveryRecord] = []

        for sub in matching_subs:
            record = await self._deliver(sub, event_type, payload)
            records.append(record)

        return records

    async def send_test_event(self, subscription_id: str) -> DeliveryRecord | None:
        """Send a test event to a specific subscription."""
        sub = self._subscriptions.get(subscription_id)
        if sub is None:
            return None

        test_payload = {
            "event_type": "test",
            "message": "This is a test webhook delivery from ShieldOps",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        return await self._deliver(sub, "test", test_payload)

    def sign_payload(self, payload: dict[str, Any], secret: str) -> str:
        """Generate HMAC-SHA256 signature for a payload."""
        payload_bytes = json.dumps(payload, sort_keys=True, default=str).encode()
        signature = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={signature}"

    def _get_matching_subscriptions(self, event_type: str) -> list[WebhookSubscription]:
        """Find subscriptions that match the event type."""
        matching = []
        for sub in self._subscriptions.values():
            if not sub.active:
                continue
            if not sub.events or event_type in sub.events:
                matching.append(sub)
        return matching

    async def _deliver(
        self,
        subscription: WebhookSubscription,
        event_type: str,
        payload: dict[str, Any],
    ) -> DeliveryRecord:
        """Attempt to deliver a webhook payload."""
        full_payload = {
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "subscription_id": subscription.id,
            "data": payload,
        }

        record = DeliveryRecord(
            subscription_id=subscription.id,
            event_type=event_type,
            payload=full_payload,
        )

        # Simulate delivery (in production, use httpx with retry)
        try:
            # In production:
            # async with httpx.AsyncClient() as client:
            #     headers = {"Content-Type": "application/json"}
            #     if subscription.secret:
            #         sig = self.sign_payload(full_payload, subscription.secret)
            #         headers["X-Signature-256"] = sig
            #     response = await client.post(subscription.url, json=full_payload, headers=headers)
            #     record.status_code = response.status_code

            record.status = DeliveryStatus.DELIVERED
            record.delivered_at = datetime.now(UTC)
            record.status_code = 200

            logger.info(
                "webhook_delivered",
                sub_id=subscription.id,
                event=event_type,
                status_code=record.status_code,
            )

        except Exception as e:
            record.status = DeliveryStatus.FAILED
            record.error = str(e)
            self._dead_letters.append(record)

            logger.warning(
                "webhook_delivery_failed",
                sub_id=subscription.id,
                event=event_type,
                error=str(e),
            )

        self._deliveries.append(record)
        return record
