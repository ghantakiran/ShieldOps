"""Stripe billing integration for SaaS subscription management.

Wraps the synchronous Stripe Python SDK in async helpers using
``loop.run_in_executor`` so the caller's event loop is never blocked.
The stripe package is lazily imported to keep it an optional dependency.
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import structlog

logger = structlog.get_logger()

# ------------------------------------------------------------------
# Plan definitions
# ------------------------------------------------------------------

PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "name": "Free",
        "agent_limit": 5,
        "api_calls_limit": 1_000,
        "price_id": None,
        "features": [
            "5 agents",
            "1,000 API calls/month",
            "Community support",
            "Basic dashboards",
        ],
    },
    "pro": {
        "name": "Pro",
        "agent_limit": 25,
        "api_calls_limit": 50_000,
        "price_id": "price_pro_monthly",
        "features": [
            "25 agents",
            "50,000 API calls/month",
            "Priority support",
            "Advanced analytics",
            "Custom playbooks",
            "Slack integration",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "agent_limit": -1,
        "api_calls_limit": -1,
        "price_id": "price_enterprise_monthly",
        "features": [
            "Unlimited agents",
            "Unlimited API calls",
            "Dedicated support",
            "SSO / OIDC",
            "Audit log export",
            "Custom SLAs",
            "On-prem deployment",
        ],
    },
}


def get_plan(plan_key: str) -> dict[str, Any] | None:
    """Return plan definition or ``None`` for unknown keys."""
    return PLANS.get(plan_key)


# ------------------------------------------------------------------
# Stripe client wrapper
# ------------------------------------------------------------------


class StripeClient:
    """Async wrapper around the synchronous Stripe Python SDK.

    All SDK calls are dispatched to a thread executor so they do not
    block the running event loop.
    """

    def __init__(
        self,
        api_key: str,
        webhook_secret: str,
    ) -> None:
        self._api_key = api_key
        self._webhook_secret = webhook_secret
        self._stripe: Any = None

    # -- lazy init -------------------------------------------------

    def _ensure_stripe(self) -> Any:
        """Lazily import and configure the stripe SDK."""
        if self._stripe is None:
            import stripe

            stripe.api_key = self._api_key
            self._stripe = stripe
        return self._stripe

    # -- public API ------------------------------------------------

    async def create_checkout_session(
        self,
        org_id: str,
        plan: str,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        """Create a Stripe Checkout session for subscription.

        Args:
            org_id: Organization identifier stored as client
                reference on the Checkout session.
            plan: Plan key (must exist in :data:`PLANS` and have
                a non-null ``price_id``).
            success_url: URL to redirect to after successful payment.
            cancel_url: URL to redirect to if the user cancels.

        Returns:
            Dict with ``session_id`` and ``url`` for the hosted
            checkout page.

        Raises:
            ValueError: If the plan key is unknown or has no price.
        """
        plan_def = get_plan(plan)
        if plan_def is None or plan_def["price_id"] is None:
            raise ValueError(f"Invalid or free plan '{plan}' — cannot create checkout session")

        stripe = self._ensure_stripe()
        loop = asyncio.get_running_loop()

        session = await loop.run_in_executor(
            None,
            partial(
                stripe.checkout.Session.create,
                mode="subscription",
                line_items=[
                    {"price": plan_def["price_id"], "quantity": 1},
                ],
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=org_id,
                metadata={"org_id": org_id, "plan": plan},
            ),
        )

        logger.info(
            "stripe_checkout_session_created",
            org_id=org_id,
            plan=plan,
            session_id=session.id,
        )
        return {"session_id": session.id, "url": session.url}

    async def get_subscription(
        self,
        subscription_id: str,
    ) -> dict[str, Any]:
        """Retrieve subscription details from Stripe.

        Returns:
            Dict with ``id``, ``status``, ``plan``,
            ``current_period_end``, and ``cancel_at_period_end``.
        """
        stripe = self._ensure_stripe()
        loop = asyncio.get_running_loop()

        sub = await loop.run_in_executor(
            None,
            partial(stripe.Subscription.retrieve, subscription_id),
        )

        return {
            "id": sub.id,
            "status": sub.status,
            "plan": sub.metadata.get("plan", "unknown"),
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }

    async def cancel_subscription(
        self,
        subscription_id: str,
    ) -> dict[str, Any]:
        """Cancel a subscription at the end of the current period.

        Returns:
            Dict with ``id``, ``status``, and
            ``cancel_at_period_end``.
        """
        stripe = self._ensure_stripe()
        loop = asyncio.get_running_loop()

        sub = await loop.run_in_executor(
            None,
            partial(
                stripe.Subscription.modify,
                subscription_id,
                cancel_at_period_end=True,
            ),
        )

        logger.info(
            "stripe_subscription_cancelled",
            subscription_id=subscription_id,
        )
        return {
            "id": sub.id,
            "status": sub.status,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }

    async def create_usage_record(
        self,
        subscription_item_id: str,
        quantity: int,
    ) -> dict[str, Any]:
        """Report metered usage for a subscription item.

        Returns:
            Dict with ``id`` and ``quantity``.
        """
        stripe = self._ensure_stripe()
        loop = asyncio.get_running_loop()

        record = await loop.run_in_executor(
            None,
            partial(
                stripe.SubscriptionItem.create_usage_record,
                subscription_item_id,
                quantity=quantity,
                action="increment",
            ),
        )

        logger.info(
            "stripe_usage_record_created",
            subscription_item_id=subscription_item_id,
            quantity=quantity,
        )
        return {"id": record.id, "quantity": record.quantity}

    def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> dict[str, Any]:
        """Verify and parse a Stripe webhook event.

        Args:
            payload: Raw request body bytes.
            signature: Value of the ``Stripe-Signature`` header.

        Returns:
            Parsed event dict with ``type`` and ``data``.

        Raises:
            ValueError: If signature verification fails.
        """
        stripe = self._ensure_stripe()
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self._webhook_secret,
            )
        except stripe.error.SignatureVerificationError as exc:
            logger.warning(
                "stripe_webhook_signature_invalid",
                error=str(exc),
            )
            raise ValueError("Invalid Stripe webhook signature") from exc

        return {
            "type": event["type"],
            "data": event["data"],
        }
