"""Webhook replay engine.

Records webhook deliveries and enables replay of failed deliveries
with configurable retry logic.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class DeliveryStatus(enum.StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    REPLAYING = "replaying"


class ReplayStatus(enum.StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


# ── Models ───────────────────────────────────────────────────────────


class WebhookDelivery(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    subscription_id: str = ""
    url: str
    event_type: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    status: DeliveryStatus = DeliveryStatus.PENDING
    status_code: int = 0
    response_body: str = ""
    error: str = ""
    attempt_count: int = 0
    created_at: float = Field(default_factory=time.time)
    last_attempt_at: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReplayRequest(BaseModel):
    delivery_ids: list[str] = Field(default_factory=list)
    max_retries: int = 3


class ReplayResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: ReplayStatus = ReplayStatus.COMPLETED
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)
    started_at: float = Field(default_factory=time.time)
    completed_at: float | None = None


# ── Engine ───────────────────────────────────────────────────────────


class WebhookReplayEngine:
    """Record and replay webhook deliveries.

    Parameters
    ----------
    max_retries:
        Default maximum retries per delivery.
    max_deliveries:
        Maximum deliveries to store.
    """

    def __init__(
        self,
        max_retries: int = 3,
        max_deliveries: int = 50000,
    ) -> None:
        self._deliveries: dict[str, WebhookDelivery] = {}
        self._max_retries = max_retries
        self._max_deliveries = max_deliveries

    def record_delivery(
        self,
        url: str,
        event_type: str = "",
        payload: dict[str, Any] | None = None,
        subscription_id: str = "",
        status: DeliveryStatus = DeliveryStatus.PENDING,
        status_code: int = 0,
        response_body: str = "",
        error: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> WebhookDelivery:
        if len(self._deliveries) >= self._max_deliveries:
            self._cleanup_oldest()
        delivery = WebhookDelivery(
            url=url,
            event_type=event_type,
            payload=payload or {},
            subscription_id=subscription_id,
            status=status,
            status_code=status_code,
            response_body=response_body,
            error=error,
            attempt_count=1 if status != DeliveryStatus.PENDING else 0,
            last_attempt_at=time.time() if status != DeliveryStatus.PENDING else None,
            metadata=metadata or {},
        )
        self._deliveries[delivery.id] = delivery
        logger.info("webhook_delivery_recorded", delivery_id=delivery.id, status=status)
        return delivery

    def get_delivery(self, delivery_id: str) -> WebhookDelivery | None:
        return self._deliveries.get(delivery_id)

    def get_failed_deliveries(
        self,
        subscription_id: str | None = None,
        limit: int = 50,
    ) -> list[WebhookDelivery]:
        failed = [d for d in self._deliveries.values() if d.status == DeliveryStatus.FAILED]
        if subscription_id:
            failed = [d for d in failed if d.subscription_id == subscription_id]
        failed.sort(key=lambda d: d.created_at, reverse=True)
        return failed[:limit]

    def replay_delivery(
        self,
        delivery_id: str,
        simulate_success: bool = True,
    ) -> WebhookDelivery | None:
        delivery = self._deliveries.get(delivery_id)
        if delivery is None:
            return None
        if delivery.attempt_count >= self._max_retries:
            logger.warning(
                "webhook_replay_max_retries",
                delivery_id=delivery_id,
                attempts=delivery.attempt_count,
            )
            return delivery

        delivery.status = DeliveryStatus.REPLAYING
        delivery.attempt_count += 1
        delivery.last_attempt_at = time.time()

        # In production, this would make an actual HTTP call.
        # For now, simulate the result.
        if simulate_success:
            delivery.status = DeliveryStatus.SUCCESS
            delivery.status_code = 200
            delivery.error = ""
        else:
            delivery.status = DeliveryStatus.FAILED
            delivery.status_code = 500
            delivery.error = "Simulated failure"

        logger.info(
            "webhook_delivery_replayed",
            delivery_id=delivery_id,
            status=delivery.status,
        )
        return delivery

    def replay_batch(
        self,
        delivery_ids: list[str],
        simulate_success: bool = True,
    ) -> ReplayResult:
        result = ReplayResult(total=len(delivery_ids))
        for did in delivery_ids:
            delivery = self.replay_delivery(did, simulate_success=simulate_success)
            if delivery is None:
                result.failed += 1
                result.results.append({"delivery_id": did, "status": "not_found"})
            elif delivery.status == DeliveryStatus.SUCCESS:
                result.succeeded += 1
                result.results.append({"delivery_id": did, "status": "success"})
            else:
                result.failed += 1
                result.results.append({"delivery_id": did, "status": "failed"})

        result.completed_at = time.time()
        if result.failed == 0:
            result.status = ReplayStatus.COMPLETED
        elif result.succeeded > 0:
            result.status = ReplayStatus.PARTIAL
        else:
            result.status = ReplayStatus.FAILED
        return result

    def _cleanup_oldest(self) -> None:
        if not self._deliveries:
            return
        sorted_d = sorted(self._deliveries.values(), key=lambda d: d.created_at)
        to_remove = len(self._deliveries) - self._max_deliveries // 2
        for d in sorted_d[:to_remove]:
            del self._deliveries[d.id]

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for d in self._deliveries.values():
            by_status[d.status.value] = by_status.get(d.status.value, 0) + 1
        return {
            "total_deliveries": len(self._deliveries),
            "by_status": by_status,
        }
