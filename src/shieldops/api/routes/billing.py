"""Billing API endpoints for Stripe SaaS subscription management.

Provides plan listing, subscription management, checkout sessions,
usage tracking, and Stripe webhook processing.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shieldops.api.auth.dependencies import (
    get_current_user,
    require_role,
)
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.integrations.billing.stripe_billing import (
    PLANS,
    StripeClient,
    get_plan,
)

logger = structlog.get_logger()

router = APIRouter()

# ------------------------------------------------------------------
# Module-level singleton — wired from app.py lifespan
# ------------------------------------------------------------------

_stripe_client: StripeClient | None = None

# In-memory subscription store (replaced by DB in production)
_org_subscriptions: dict[str, dict[str, Any]] = {}
_org_usage: dict[str, dict[str, int]] = {}
_payment_history: dict[str, list[dict[str, Any]]] = {}

# Enforcement service -- wired from app.py when billing enforcement
# is active.  When set, the /billing/usage endpoint returns live
# agent counts and API quota from the enforcement layer.
_enforcement_service: Any = None


def set_stripe_client(client: StripeClient) -> None:
    """Override the Stripe client (used during app startup)."""
    global _stripe_client
    _stripe_client = client


def set_enforcement_service(service: Any) -> None:
    """Inject the PlanEnforcementService (called from app.py)."""
    global _enforcement_service
    _enforcement_service = service


def _get_client() -> StripeClient:
    if _stripe_client is None:
        raise HTTPException(
            status_code=503,
            detail="Stripe billing not configured",
        )
    return _stripe_client


def _get_org_id(user: UserResponse) -> str:
    """Derive org_id from user. Falls back to user id."""
    return getattr(user, "org_id", None) or user.id


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    """Request body to create a Stripe Checkout session."""

    plan: str


class CancelRequest(BaseModel):
    """Request body to cancel a subscription."""

    reason: str = ""


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("/billing/plans")
async def list_plans(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all available subscription plans."""
    plans_out = []
    for key, plan in PLANS.items():
        plans_out.append(
            {
                "key": key,
                "name": plan["name"],
                "agent_limit": plan["agent_limit"],
                "api_calls_limit": plan["api_calls_limit"],
                "features": plan.get("features", []),
                "has_price": plan["price_id"] is not None,
            }
        )
    return {"plans": plans_out}


@router.get("/billing/subscription")
async def get_subscription(
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the current organisation's subscription details."""
    org_id = _get_org_id(user)
    sub = _org_subscriptions.get(org_id)

    if sub and sub.get("stripe_subscription_id"):
        try:
            client = _get_client()
            details = await client.get_subscription(
                sub["stripe_subscription_id"],
            )
            return {**sub, **details}
        except Exception as exc:
            logger.warning(
                "stripe_subscription_fetch_failed",
                org_id=org_id,
                error=str(exc),
            )

    # Default to free plan
    plan_def = PLANS["free"]
    return {
        "org_id": org_id,
        "plan": "free",
        "plan_name": plan_def["name"],
        "agent_limit": plan_def["agent_limit"],
        "api_calls_limit": plan_def["api_calls_limit"],
        "status": "active",
        "stripe_subscription_id": None,
        "current_period_end": None,
        "cancel_at_period_end": False,
    }


@router.post("/billing/checkout")
async def create_checkout(
    body: CheckoutRequest,
    request: Request,
    user: UserResponse = Depends(
        require_role(UserRole.ADMIN),
    ),
) -> dict[str, Any]:
    """Create a Stripe Checkout session and return the URL."""
    plan_def = get_plan(body.plan)
    if plan_def is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown plan: {body.plan}",
        )
    if plan_def["price_id"] is None:
        raise HTTPException(
            status_code=400,
            detail="Cannot checkout for the free plan",
        )

    from shieldops.config import settings

    client = _get_client()
    org_id = _get_org_id(user)

    result = await client.create_checkout_session(
        org_id=org_id,
        plan=body.plan,
        success_url=settings.stripe_success_url,
        cancel_url=settings.stripe_cancel_url,
    )
    return result


@router.post("/billing/cancel")
async def cancel_subscription(
    body: CancelRequest,
    user: UserResponse = Depends(
        require_role(UserRole.ADMIN),
    ),
) -> dict[str, Any]:
    """Cancel the current subscription at the end of the period."""
    org_id = _get_org_id(user)
    sub = _org_subscriptions.get(org_id)

    if not sub or not sub.get("stripe_subscription_id"):
        raise HTTPException(
            status_code=400,
            detail="No active subscription to cancel",
        )

    client = _get_client()
    result = await client.cancel_subscription(
        sub["stripe_subscription_id"],
    )

    logger.info(
        "billing_subscription_cancel_requested",
        org_id=org_id,
        reason=body.reason,
    )
    return result


@router.get("/billing/usage")
async def get_usage(
    request: Request,
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current billing-period usage vs plan limits.

    When the ``PlanEnforcementService`` is available, returns live
    agent counts and API call totals.  Otherwise falls back to the
    in-memory subscription store.
    """
    org_id: str = getattr(request.state, "organization_id", None) or _get_org_id(user)

    # Prefer the enforcement service for accurate, DB-backed data
    if _enforcement_service is not None:
        summary = await _enforcement_service.get_usage_summary(org_id)
        agent_limit = summary["agent_limit"]
        api_limit = summary["api_calls_limit"]
        return {
            "org_id": org_id,
            "plan": summary["plan"],
            "plan_name": summary["plan_name"],
            "agent_count": summary["agent_count"],
            "agent_limit": agent_limit,
            "agent_limit_reached": summary["agent_limit_reached"],
            "api_calls_used": summary["api_calls_used"],
            "api_calls_limit": api_limit,
            "api_quota_exceeded": summary["api_quota_exceeded"],
            "upgrade_available": summary["upgrade_available"],
        }

    # Fallback: in-memory subscription store
    sub = _org_subscriptions.get(org_id, {})
    plan_key = sub.get("plan", "free")
    plan_def = PLANS.get(plan_key, PLANS["free"])
    usage = _org_usage.get(org_id, {"agents": 0, "api_calls": 0})

    agent_limit = plan_def["agent_limit"]
    api_limit = plan_def["api_calls_limit"]

    return {
        "org_id": org_id,
        "plan": plan_key,
        "agents_used": usage.get("agents", 0),
        "agents_limit": agent_limit,
        "agents_percent": (
            round(usage.get("agents", 0) / agent_limit * 100, 1) if agent_limit > 0 else 0.0
        ),
        "api_calls_used": usage.get("api_calls", 0),
        "api_calls_limit": api_limit,
        "api_calls_percent": (
            round(
                usage.get("api_calls", 0) / api_limit * 100,
                1,
            )
            if api_limit > 0
            else 0.0
        ),
    }


# ------------------------------------------------------------------
# Stripe webhook (NO auth — verified by Stripe signature)
# ------------------------------------------------------------------


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Handle incoming Stripe webhook events.

    This endpoint does **not** require JWT authentication.
    Instead it verifies the ``Stripe-Signature`` header against
    the configured webhook secret.
    """
    client = _get_client()
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        event = client.verify_webhook(payload, signature)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook signature",
        ) from None

    event_type: str = event["type"]
    data: dict[str, Any] = event["data"]
    obj: dict[str, Any] = data.get("object", {})

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(obj)
    elif event_type == "invoice.paid":
        _handle_invoice_paid(obj)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(obj)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(obj)
    else:
        logger.debug(
            "stripe_webhook_unhandled",
            event_type=event_type,
        )

    return {"status": "ok"}


# ------------------------------------------------------------------
# Webhook event handlers
# ------------------------------------------------------------------


def _handle_checkout_completed(obj: dict[str, Any]) -> None:
    """Activate subscription for the org after checkout."""
    org_id = obj.get("client_reference_id") or obj.get("metadata", {}).get("org_id", "")
    plan = obj.get("metadata", {}).get("plan", "pro")
    subscription_id = obj.get("subscription", "")

    plan_def = PLANS.get(plan, PLANS["pro"])
    _org_subscriptions[org_id] = {
        "org_id": org_id,
        "plan": plan,
        "plan_name": plan_def["name"],
        "agent_limit": plan_def["agent_limit"],
        "api_calls_limit": plan_def["api_calls_limit"],
        "stripe_subscription_id": subscription_id,
        "status": "active",
        "cancel_at_period_end": False,
    }
    logger.info(
        "billing_subscription_activated",
        org_id=org_id,
        plan=plan,
    )


def _handle_invoice_paid(obj: dict[str, Any]) -> None:
    """Record a successful payment."""
    sub_id = obj.get("subscription", "")
    amount = obj.get("amount_paid", 0)
    currency = obj.get("currency", "usd")

    # Find org by subscription id
    for org_id, sub in _org_subscriptions.items():
        if sub.get("stripe_subscription_id") == sub_id:
            history = _payment_history.setdefault(org_id, [])
            history.append(
                {
                    "invoice_id": obj.get("id", ""),
                    "amount": amount,
                    "currency": currency,
                    "status": "paid",
                }
            )
            logger.info(
                "billing_invoice_paid",
                org_id=org_id,
                amount=amount,
            )
            break


def _handle_subscription_updated(
    obj: dict[str, Any],
) -> None:
    """Update org subscription when Stripe sends changes."""
    sub_id = obj.get("id", "")
    plan = obj.get("metadata", {}).get("plan", "")
    status = obj.get("status", "active")

    for org_id, sub in _org_subscriptions.items():
        if sub.get("stripe_subscription_id") == sub_id:
            if plan and plan in PLANS:
                plan_def = PLANS[plan]
                sub["plan"] = plan
                sub["plan_name"] = plan_def["name"]
                sub["agent_limit"] = plan_def["agent_limit"]
                sub["api_calls_limit"] = plan_def["api_calls_limit"]
            sub["status"] = status
            sub["cancel_at_period_end"] = obj.get(
                "cancel_at_period_end",
                False,
            )
            logger.info(
                "billing_subscription_updated",
                org_id=org_id,
                plan=plan,
                status=status,
            )
            break


def _handle_subscription_deleted(
    obj: dict[str, Any],
) -> None:
    """Downgrade org to free plan when subscription is deleted."""
    sub_id = obj.get("id", "")

    for org_id, sub in _org_subscriptions.items():
        if sub.get("stripe_subscription_id") == sub_id:
            plan_def = PLANS["free"]
            _org_subscriptions[org_id] = {
                "org_id": org_id,
                "plan": "free",
                "plan_name": plan_def["name"],
                "agent_limit": plan_def["agent_limit"],
                "api_calls_limit": plan_def["api_calls_limit"],
                "stripe_subscription_id": None,
                "status": "active",
                "cancel_at_period_end": False,
            }
            logger.info(
                "billing_subscription_downgraded",
                org_id=org_id,
            )
            break
