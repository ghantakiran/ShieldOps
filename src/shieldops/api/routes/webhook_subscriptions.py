"""API routes for outbound webhook subscriptions."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shieldops.integrations.outbound.webhook_dispatcher import (
    OutboundWebhookDispatcher,
    WebhookSubscription,
)

router = APIRouter()

_dispatcher: OutboundWebhookDispatcher | None = None


def set_dispatcher(dispatcher: OutboundWebhookDispatcher) -> None:
    global _dispatcher
    _dispatcher = dispatcher


def _get_dispatcher() -> OutboundWebhookDispatcher:
    if _dispatcher is None:
        raise HTTPException(status_code=503, detail="Webhook dispatcher not initialized")
    return _dispatcher


class CreateSubscriptionRequest(BaseModel):
    url: str
    events: list[str] = Field(default_factory=list)
    secret: str = ""
    description: str = ""


@router.post("/webhooks/subscriptions")
async def create_subscription(body: CreateSubscriptionRequest) -> dict[str, Any]:
    dispatcher = _get_dispatcher()
    sub = WebhookSubscription(
        url=body.url,
        events=body.events,
        secret=body.secret,
        description=body.description,
    )
    created = dispatcher.create_subscription(sub)
    return created.model_dump()


@router.get("/webhooks/subscriptions")
async def list_subscriptions() -> dict[str, Any]:
    dispatcher = _get_dispatcher()
    subs = dispatcher.list_subscriptions()
    return {"subscriptions": [s.model_dump() for s in subs], "count": len(subs)}


@router.delete("/webhooks/subscriptions/{sub_id}")
async def delete_subscription(sub_id: str) -> dict[str, Any]:
    dispatcher = _get_dispatcher()
    deleted = dispatcher.delete_subscription(sub_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"deleted": True, "subscription_id": sub_id}


@router.get("/webhooks/subscriptions/{sub_id}/deliveries")
async def get_deliveries(sub_id: str) -> dict[str, Any]:
    dispatcher = _get_dispatcher()
    deliveries = dispatcher.get_deliveries(sub_id)
    return {"deliveries": [d.model_dump() for d in deliveries], "count": len(deliveries)}


@router.post("/webhooks/subscriptions/{sub_id}/test")
async def test_webhook(sub_id: str) -> dict[str, Any]:
    dispatcher = _get_dispatcher()
    record = await dispatcher.send_test_event(sub_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return record.model_dump()
