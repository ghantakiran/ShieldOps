"""Production Stripe billing service with DB-backed subscription management.

Provides customer creation, checkout sessions, billing portal access,
subscription lifecycle, and webhook processing — all persisted to PostgreSQL.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from functools import partial
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shieldops.db.models import OrganizationRecord, SubscriptionRecord

logger = structlog.get_logger()

# ------------------------------------------------------------------
# Plan definitions — maps plan key to Stripe price ID and metadata
# ------------------------------------------------------------------

PLAN_TIERS: dict[str, dict[str, Any]] = {
    "starter": {
        "name": "Starter",
        "monthly_price": 2_000,
        "agent_limit": 10,
        "api_calls_limit": 10_000,
        "features": [
            "10 agents",
            "10,000 API calls/month",
            "Email support",
            "Standard dashboards",
            "Basic playbooks",
        ],
    },
    "professional": {
        "name": "Professional",
        "monthly_price": 8_000,
        "agent_limit": 50,
        "api_calls_limit": 100_000,
        "features": [
            "50 agents",
            "100,000 API calls/month",
            "Priority support",
            "Advanced analytics",
            "Custom playbooks",
            "Slack & PagerDuty integration",
            "SSO / OIDC",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "monthly_price": 25_000,
        "agent_limit": -1,
        "api_calls_limit": -1,
        "features": [
            "Unlimited agents",
            "Unlimited API calls",
            "Dedicated support",
            "Audit log export",
            "Custom SLAs",
            "On-prem deployment",
            "SOC 2 compliance",
        ],
    },
}


# ------------------------------------------------------------------
# Pydantic response models
# ------------------------------------------------------------------


class CustomerResponse(BaseModel):
    """Response from Stripe customer creation."""

    stripe_customer_id: str
    email: str
    name: str


class CheckoutSessionResponse(BaseModel):
    """Response from creating a Checkout session."""

    session_id: str
    url: str


class PortalSessionResponse(BaseModel):
    """Response from creating a billing portal session."""

    url: str


class SubscriptionResponse(BaseModel):
    """Subscription details returned to the caller."""

    id: str
    org_id: str
    stripe_subscription_id: str
    plan: str
    plan_name: str
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class WebhookResult(BaseModel):
    """Result of processing a webhook event."""

    event_type: str
    handled: bool
    detail: str = ""


# ------------------------------------------------------------------
# Stripe service
# ------------------------------------------------------------------


class StripeService:
    """Production Stripe billing service with DB persistence.

    All Stripe SDK calls are dispatched to a thread executor so the
    running event loop is never blocked.  Subscription state is
    persisted to PostgreSQL via SQLAlchemy async sessions.
    """

    def __init__(
        self,
        secret_key: str,
        webhook_secret: str,
        price_ids: dict[str, str],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialise the service.

        Args:
            secret_key: Stripe secret API key (``sk_...``).
            webhook_secret: Stripe webhook signing secret (``whsec_...``).
            price_ids: Mapping of plan key to Stripe price ID,
                e.g. ``{"starter": "price_xxx", ...}``.
            session_factory: SQLAlchemy async session maker for DB access.
        """
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret
        self._price_ids = price_ids
        self._sf = session_factory
        self._stripe: Any = None

    # -- lazy import -----------------------------------------------

    def _ensure_stripe(self) -> Any:
        """Lazily import and configure the Stripe SDK."""
        if self._stripe is None:
            import stripe  # type: ignore[import-not-found]

            stripe.api_key = self._secret_key
            self._stripe = stripe
        return self._stripe

    # -- public API ------------------------------------------------

    async def create_customer(
        self,
        org_id: str,
        email: str,
        name: str,
    ) -> CustomerResponse:
        """Create a Stripe customer and persist the ID on the org.

        If the organisation already has a ``stripe_customer_id`` the
        existing customer is returned without hitting Stripe.
        """
        async with self._sf() as session:
            result = await session.execute(
                select(OrganizationRecord).where(OrganizationRecord.id == org_id)
            )
            org = result.scalar_one_or_none()
            if org is None:
                raise ValueError(f"Organization {org_id} not found")

            if org.stripe_customer_id:
                logger.info(
                    "stripe_customer_exists",
                    org_id=org_id,
                    stripe_customer_id=org.stripe_customer_id,
                )
                return CustomerResponse(
                    stripe_customer_id=org.stripe_customer_id,
                    email=email,
                    name=name,
                )

        stripe = self._ensure_stripe()
        loop = asyncio.get_running_loop()

        customer = await loop.run_in_executor(
            None,
            partial(
                stripe.Customer.create,
                email=email,
                name=name,
                metadata={"org_id": org_id},
            ),
        )

        # Persist customer ID on the organisation
        async with self._sf() as session:
            await session.execute(
                update(OrganizationRecord)
                .where(OrganizationRecord.id == org_id)
                .values(stripe_customer_id=customer.id)
            )
            await session.commit()

        logger.info(
            "stripe_customer_created",
            org_id=org_id,
            stripe_customer_id=customer.id,
        )
        return CustomerResponse(
            stripe_customer_id=customer.id,
            email=email,
            name=name,
        )

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSessionResponse:
        """Create a Stripe Checkout session for a subscription.

        Args:
            customer_id: Stripe customer ID (``cus_...``).
            price_id: Stripe price ID (``price_...``).
            success_url: Redirect URL after successful payment.
            cancel_url: Redirect URL if the user cancels.

        Returns:
            Session ID and hosted checkout URL.
        """
        # Resolve plan key from price ID for metadata
        plan_key = self._plan_key_for_price(price_id)

        stripe = self._ensure_stripe()
        loop = asyncio.get_running_loop()

        session = await loop.run_in_executor(
            None,
            partial(
                stripe.checkout.Session.create,
                customer=customer_id,
                mode="subscription",
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"plan": plan_key} if plan_key else {},
            ),
        )

        logger.info(
            "stripe_checkout_session_created",
            customer_id=customer_id,
            price_id=price_id,
            plan=plan_key,
            session_id=session.id,
        )
        return CheckoutSessionResponse(session_id=session.id, url=session.url)

    async def create_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> PortalSessionResponse:
        """Create a Stripe Customer Portal session.

        The portal lets customers manage payment methods, view invoices,
        and cancel or change their subscription.
        """
        stripe = self._ensure_stripe()
        loop = asyncio.get_running_loop()

        session = await loop.run_in_executor(
            None,
            partial(
                stripe.billing_portal.Session.create,
                customer=customer_id,
                return_url=return_url,
            ),
        )

        logger.info(
            "stripe_portal_session_created",
            customer_id=customer_id,
        )
        return PortalSessionResponse(url=session.url)

    async def get_subscription(
        self,
        subscription_id: str,
    ) -> SubscriptionResponse:
        """Retrieve subscription details from the database.

        Falls back to Stripe if the local record is missing.
        """
        async with self._sf() as session:
            result = await session.execute(
                select(SubscriptionRecord).where(
                    SubscriptionRecord.stripe_subscription_id == subscription_id
                )
            )
            record = result.scalar_one_or_none()

        if record is not None:
            plan_def = PLAN_TIERS.get(record.plan, {})
            return SubscriptionResponse(
                id=record.id,
                org_id=record.org_id,
                stripe_subscription_id=record.stripe_subscription_id,
                plan=record.plan,
                plan_name=plan_def.get("name", record.plan),
                status=record.status,
                current_period_start=record.current_period_start,
                current_period_end=record.current_period_end,
                cancel_at_period_end=record.cancel_at_period_end,
            )

        # Fallback: fetch from Stripe directly
        stripe = self._ensure_stripe()
        loop = asyncio.get_running_loop()
        sub = await loop.run_in_executor(
            None,
            partial(stripe.Subscription.retrieve, subscription_id),
        )

        plan_key = sub.metadata.get("plan", "starter")
        plan_def = PLAN_TIERS.get(plan_key, {})
        return SubscriptionResponse(
            id=sub.id,
            org_id=sub.metadata.get("org_id", ""),
            stripe_subscription_id=sub.id,
            plan=plan_key,
            plan_name=plan_def.get("name", plan_key),
            status=sub.status,
            current_period_start=(
                datetime.fromtimestamp(sub.current_period_start, tz=UTC)
                if sub.current_period_start
                else None
            ),
            current_period_end=(
                datetime.fromtimestamp(sub.current_period_end, tz=UTC)
                if sub.current_period_end
                else None
            ),
            cancel_at_period_end=sub.cancel_at_period_end,
        )

    async def cancel_subscription(
        self,
        subscription_id: str,
    ) -> SubscriptionResponse:
        """Cancel a subscription at the end of the current billing period."""
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

        # Update local record
        async with self._sf() as session:
            await session.execute(
                update(SubscriptionRecord)
                .where(SubscriptionRecord.stripe_subscription_id == subscription_id)
                .values(
                    cancel_at_period_end=True,
                    status=sub.status,
                    updated_at=datetime.now(UTC),
                )
            )
            await session.commit()

        logger.info(
            "stripe_subscription_cancelled",
            subscription_id=subscription_id,
        )

        plan_key = sub.metadata.get("plan", "starter")
        plan_def = PLAN_TIERS.get(plan_key, {})
        return SubscriptionResponse(
            id=sub.id,
            org_id=sub.metadata.get("org_id", ""),
            stripe_subscription_id=sub.id,
            plan=plan_key,
            plan_name=plan_def.get("name", plan_key),
            status=sub.status,
            current_period_start=(
                datetime.fromtimestamp(sub.current_period_start, tz=UTC)
                if sub.current_period_start
                else None
            ),
            current_period_end=(
                datetime.fromtimestamp(sub.current_period_end, tz=UTC)
                if sub.current_period_end
                else None
            ),
            cancel_at_period_end=sub.cancel_at_period_end,
        )

    async def handle_webhook(
        self,
        payload: bytes,
        sig_header: str,
    ) -> WebhookResult:
        """Verify and process a Stripe webhook event.

        Args:
            payload: Raw request body bytes.
            sig_header: Value of the ``Stripe-Signature`` header.

        Returns:
            Result indicating which event was processed.

        Raises:
            ValueError: If signature verification fails.
        """
        stripe = self._ensure_stripe()
        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                self._webhook_secret,
            )
        except stripe.error.SignatureVerificationError as exc:
            logger.warning(
                "stripe_webhook_signature_invalid",
                error=str(exc),
            )
            raise ValueError("Invalid Stripe webhook signature") from exc

        event_type: str = event["type"]
        obj: dict[str, Any] = event["data"]["object"]

        logger.info("stripe_webhook_received", event_type=event_type)

        if event_type == "checkout.session.completed":
            await self._handle_checkout_completed(obj)
            return WebhookResult(
                event_type=event_type,
                handled=True,
                detail="Subscription activated",
            )

        if event_type == "customer.subscription.updated":
            await self._handle_subscription_updated(obj)
            return WebhookResult(
                event_type=event_type,
                handled=True,
                detail="Subscription updated",
            )

        if event_type == "customer.subscription.deleted":
            await self._handle_subscription_deleted(obj)
            return WebhookResult(
                event_type=event_type,
                handled=True,
                detail="Subscription deleted",
            )

        if event_type == "invoice.payment_failed":
            await self._handle_payment_failed(obj)
            return WebhookResult(
                event_type=event_type,
                handled=True,
                detail="Payment failure recorded",
            )

        logger.debug("stripe_webhook_unhandled", event_type=event_type)
        return WebhookResult(
            event_type=event_type,
            handled=False,
            detail="Event type not handled",
        )

    # -- webhook handlers ------------------------------------------

    async def _handle_checkout_completed(self, obj: dict[str, Any]) -> None:
        """Activate a subscription after successful checkout."""
        customer_id: str = obj.get("customer", "")
        subscription_id: str = obj.get("subscription", "")
        plan_key: str = obj.get("metadata", {}).get("plan", "starter")

        if not subscription_id:
            logger.warning("stripe_checkout_no_subscription", obj_id=obj.get("id"))
            return

        # Fetch full subscription from Stripe for period data
        stripe = self._ensure_stripe()
        loop = asyncio.get_running_loop()
        sub = await loop.run_in_executor(
            None,
            partial(stripe.Subscription.retrieve, subscription_id),
        )

        # Resolve org_id from stripe_customer_id
        org_id = await self._org_id_for_customer(customer_id)
        if not org_id:
            org_id = obj.get("client_reference_id", "")

        async with self._sf() as session:
            record = SubscriptionRecord(
                org_id=org_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                plan=plan_key,
                status=sub.status,
                current_period_start=(
                    datetime.fromtimestamp(sub.current_period_start, tz=UTC)
                    if sub.current_period_start
                    else None
                ),
                current_period_end=(
                    datetime.fromtimestamp(sub.current_period_end, tz=UTC)
                    if sub.current_period_end
                    else None
                ),
                cancel_at_period_end=sub.cancel_at_period_end,
            )
            session.add(record)

            # Update the org plan
            if org_id:
                await session.execute(
                    update(OrganizationRecord)
                    .where(OrganizationRecord.id == org_id)
                    .values(plan=plan_key, stripe_customer_id=customer_id)
                )
            await session.commit()

        logger.info(
            "stripe_subscription_activated",
            org_id=org_id,
            plan=plan_key,
            subscription_id=subscription_id,
        )

    async def _handle_subscription_updated(self, obj: dict[str, Any]) -> None:
        """Update local subscription record when Stripe sends changes."""
        sub_id: str = obj.get("id", "")
        status: str = obj.get("status", "active")
        cancel_at_period_end: bool = obj.get("cancel_at_period_end", False)
        plan_key: str = obj.get("metadata", {}).get("plan", "")

        values: dict[str, Any] = {
            "status": status,
            "cancel_at_period_end": cancel_at_period_end,
            "updated_at": datetime.now(UTC),
        }
        if obj.get("current_period_start"):
            values["current_period_start"] = datetime.fromtimestamp(
                obj["current_period_start"], tz=UTC
            )
        if obj.get("current_period_end"):
            values["current_period_end"] = datetime.fromtimestamp(obj["current_period_end"], tz=UTC)
        if plan_key:
            values["plan"] = plan_key

        async with self._sf() as session:
            await session.execute(
                update(SubscriptionRecord)
                .where(SubscriptionRecord.stripe_subscription_id == sub_id)
                .values(**values)
            )

            # Also update org plan if changed
            if plan_key:
                result = await session.execute(
                    select(SubscriptionRecord.org_id).where(
                        SubscriptionRecord.stripe_subscription_id == sub_id
                    )
                )
                org_id = result.scalar_one_or_none()
                if org_id:
                    await session.execute(
                        update(OrganizationRecord)
                        .where(OrganizationRecord.id == org_id)
                        .values(plan=plan_key)
                    )

            await session.commit()

        logger.info(
            "stripe_subscription_updated",
            subscription_id=sub_id,
            status=status,
            plan=plan_key or "(unchanged)",
        )

    async def _handle_subscription_deleted(self, obj: dict[str, Any]) -> None:
        """Downgrade org to free when subscription is cancelled/deleted."""
        sub_id: str = obj.get("id", "")

        async with self._sf() as session:
            result = await session.execute(
                select(SubscriptionRecord.org_id).where(
                    SubscriptionRecord.stripe_subscription_id == sub_id
                )
            )
            org_id = result.scalar_one_or_none()

            await session.execute(
                update(SubscriptionRecord)
                .where(SubscriptionRecord.stripe_subscription_id == sub_id)
                .values(
                    status="canceled",
                    cancel_at_period_end=False,
                    updated_at=datetime.now(UTC),
                )
            )

            if org_id:
                await session.execute(
                    update(OrganizationRecord)
                    .where(OrganizationRecord.id == org_id)
                    .values(plan="free")
                )

            await session.commit()

        logger.info(
            "stripe_subscription_deleted",
            subscription_id=sub_id,
            org_id=org_id or "(unknown)",
        )

    async def _handle_payment_failed(self, obj: dict[str, Any]) -> None:
        """Mark subscription as past_due when payment fails."""
        sub_id: str = obj.get("subscription", "")
        if not sub_id:
            return

        async with self._sf() as session:
            await session.execute(
                update(SubscriptionRecord)
                .where(SubscriptionRecord.stripe_subscription_id == sub_id)
                .values(status="past_due", updated_at=datetime.now(UTC))
            )
            await session.commit()

        logger.warning(
            "stripe_payment_failed",
            subscription_id=sub_id,
            invoice_id=obj.get("id", ""),
        )

    # -- helpers ---------------------------------------------------

    async def _org_id_for_customer(self, customer_id: str) -> str | None:
        """Look up the org_id for a Stripe customer ID."""
        async with self._sf() as session:
            result = await session.execute(
                select(OrganizationRecord.id).where(
                    OrganizationRecord.stripe_customer_id == customer_id
                )
            )
            return result.scalar_one_or_none()

    def _plan_key_for_price(self, price_id: str) -> str:
        """Reverse-lookup plan key from a Stripe price ID."""
        for key, pid in self._price_ids.items():
            if pid == price_id:
                return key
        return ""

    async def get_subscription_for_org(
        self,
        org_id: str,
    ) -> SubscriptionResponse | None:
        """Get the active subscription for an org, if any."""
        async with self._sf() as session:
            result = await session.execute(
                select(SubscriptionRecord)
                .where(
                    SubscriptionRecord.org_id == org_id,
                    SubscriptionRecord.status.in_(["active", "past_due", "trialing"]),
                )
                .order_by(SubscriptionRecord.created_at.desc())
                .limit(1)
            )
            record = result.scalar_one_or_none()

        if record is None:
            return None

        plan_def = PLAN_TIERS.get(record.plan, {})
        return SubscriptionResponse(
            id=record.id,
            org_id=record.org_id,
            stripe_subscription_id=record.stripe_subscription_id,
            plan=record.plan,
            plan_name=plan_def.get("name", record.plan),
            status=record.status,
            current_period_start=record.current_period_start,
            current_period_end=record.current_period_end,
            cancel_at_period_end=record.cancel_at_period_end,
        )
