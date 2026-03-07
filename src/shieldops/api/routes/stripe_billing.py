"""Production Stripe billing API routes.

Provides checkout, portal, subscription management, and webhook
processing backed by the :class:`StripeService` with DB persistence.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.billing.stripe_service import (
    PLAN_TIERS,
    StripeService,
)

logger = structlog.get_logger()

router = APIRouter()

# ------------------------------------------------------------------
# Module-level singleton — wired from app.py lifespan
# ------------------------------------------------------------------

_stripe_service: StripeService | None = None


def set_stripe_service(service: StripeService) -> None:
    """Inject the StripeService instance (called during app startup)."""
    global _stripe_service
    _stripe_service = service


def _get_service() -> StripeService:
    if _stripe_service is None:
        raise HTTPException(
            status_code=503,
            detail="Stripe billing service not configured",
        )
    return _stripe_service


def _get_org_id(user: UserResponse) -> str:
    """Derive org_id from user.  Falls back to user id."""
    return getattr(user, "org_id", None) or user.id


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    """Request body to create a Stripe Checkout session."""

    plan: str  # starter, professional, enterprise
    success_url: str | None = None
    cancel_url: str | None = None


class PortalRequest(BaseModel):
    """Request body to create a Stripe Customer Portal session."""

    return_url: str | None = None


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
    """List all available subscription plans with pricing."""
    plans_out = []
    for key, plan in PLAN_TIERS.items():
        plans_out.append(
            {
                "key": key,
                "name": plan["name"],
                "monthly_price": plan["monthly_price"],
                "agent_limit": plan["agent_limit"],
                "api_calls_limit": plan["api_calls_limit"],
                "features": plan["features"],
            }
        )
    return {"plans": plans_out}


@router.post("/billing/checkout")
async def create_checkout(
    body: CheckoutRequest,
    request: Request,
    user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Create a Stripe Checkout session and return the URL.

    The caller must be an admin.  If the organisation does not yet
    have a Stripe customer, one is created automatically.
    """
    service = _get_service()
    org_id = _get_org_id(user)

    if body.plan not in PLAN_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown plan: {body.plan}. Choose from: {list(PLAN_TIERS.keys())}",
        )

    # Resolve price ID from settings
    price_id = service._price_ids.get(body.plan)
    if not price_id:
        raise HTTPException(
            status_code=400,
            detail=f"No Stripe price configured for plan: {body.plan}",
        )

    # Ensure org has a Stripe customer
    customer = await service.create_customer(
        org_id=org_id,
        email=user.email,
        name=user.name,
    )

    from shieldops.config import settings

    success_url = body.success_url or settings.stripe_success_url
    cancel_url = body.cancel_url or settings.stripe_cancel_url

    result = await service.create_checkout_session(
        customer_id=customer.stripe_customer_id,
        price_id=price_id,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    logger.info(
        "billing_checkout_created",
        org_id=org_id,
        plan=body.plan,
    )
    return {"session_id": result.session_id, "url": result.url}


@router.post("/billing/portal")
async def create_portal(
    body: PortalRequest,
    user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Create a Stripe Customer Portal session.

    Allows the customer to manage payment methods, view invoices,
    and change or cancel their subscription.
    """
    service = _get_service()
    org_id = _get_org_id(user)

    # Look up Stripe customer ID for this org
    customer = await service.create_customer(
        org_id=org_id,
        email=user.email,
        name=user.name,
    )

    from shieldops.config import settings

    return_url = body.return_url or settings.stripe_success_url

    result = await service.create_portal_session(
        customer_id=customer.stripe_customer_id,
        return_url=return_url,
    )

    logger.info("billing_portal_created", org_id=org_id)
    return {"url": result.url}


@router.get("/billing/subscription")
async def get_subscription(
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the current organisation's subscription details."""
    service = _get_service()
    org_id = _get_org_id(user)

    sub = await service.get_subscription_for_org(org_id)
    if sub is None:
        return {
            "org_id": org_id,
            "plan": "free",
            "plan_name": "Free",
            "status": "none",
            "stripe_subscription_id": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
        }

    return sub.model_dump(mode="json")


@router.post("/billing/cancel")
async def cancel_subscription(
    body: CancelRequest,
    user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Cancel the current subscription at the end of the billing period."""
    service = _get_service()
    org_id = _get_org_id(user)

    sub = await service.get_subscription_for_org(org_id)
    if sub is None:
        raise HTTPException(
            status_code=400,
            detail="No active subscription to cancel",
        )

    result = await service.cancel_subscription(sub.stripe_subscription_id)

    logger.info(
        "billing_subscription_cancel_requested",
        org_id=org_id,
        reason=body.reason,
    )
    return result.model_dump(mode="json")


# ------------------------------------------------------------------
# Stripe webhook — NO JWT auth, verified by Stripe signature
# ------------------------------------------------------------------


@router.post("/billing/webhook")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Handle incoming Stripe webhook events.

    This endpoint does **not** require JWT authentication.
    Verification is performed via the ``Stripe-Signature`` header
    against the configured webhook secret.
    """
    service = _get_service()
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        result = await service.handle_webhook(payload, sig_header)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook signature",
        ) from None

    return {
        "status": "ok",
        "event_type": result.event_type,
        "handled": str(result.handled),
    }
