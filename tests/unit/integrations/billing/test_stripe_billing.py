"""Tests for the Stripe billing integration.

Tests cover:
- Plan configuration validation
- Checkout session creation (mock stripe)
- Subscription retrieval
- Subscription cancellation
- Usage record creation
- Webhook signature verification
- Webhook event handling (each event type)
- Invalid plan handling
- Error handling for stripe SDK failures
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from shieldops.integrations.billing.stripe_billing import (
    PLANS,
    StripeClient,
    get_plan,
)

# ============================================================
# Helpers
# ============================================================


def _make_stripe_client(
    api_key: str = "sk_test_fake",  # noqa: S107
    webhook_secret: str = "whsec_test_fake",  # noqa: S107
) -> StripeClient:
    """Create a StripeClient with test credentials."""
    return StripeClient(
        api_key=api_key,
        webhook_secret=webhook_secret,
    )


def _mock_stripe_module() -> MagicMock:
    """Build a mock stripe module with nested attributes."""
    mock = MagicMock()
    mock.error = MagicMock()
    mock.error.SignatureVerificationError = type(
        "SignatureVerificationError",
        (Exception,),
        {},
    )
    return mock


# ============================================================
# Plan configuration
# ============================================================


class TestPlanConfiguration:
    def test_free_plan_exists(self) -> None:
        plan = get_plan("free")
        assert plan is not None
        assert plan["name"] == "Free"
        assert plan["price_id"] is None

    def test_pro_plan_exists(self) -> None:
        plan = get_plan("pro")
        assert plan is not None
        assert plan["name"] == "Pro"
        assert plan["price_id"] == "price_pro_monthly"

    def test_enterprise_plan_exists(self) -> None:
        plan = get_plan("enterprise")
        assert plan is not None
        assert plan["name"] == "Enterprise"
        assert plan["agent_limit"] == -1
        assert plan["api_calls_limit"] == -1

    def test_unknown_plan_returns_none(self) -> None:
        assert get_plan("nonexistent") is None

    def test_all_plans_have_required_keys(self) -> None:
        required = {
            "name",
            "agent_limit",
            "api_calls_limit",
            "price_id",
            "features",
        }
        for key, plan in PLANS.items():
            missing = required - set(plan.keys())
            assert not missing, f"Plan '{key}' missing keys: {missing}"

    def test_free_plan_has_limits(self) -> None:
        plan = PLANS["free"]
        assert plan["agent_limit"] > 0
        assert plan["api_calls_limit"] > 0

    def test_enterprise_unlimited(self) -> None:
        plan = PLANS["enterprise"]
        assert plan["agent_limit"] == -1
        assert plan["api_calls_limit"] == -1


# ============================================================
# StripeClient — initialisation
# ============================================================


class TestClientInit:
    def test_stores_credentials(self) -> None:
        client = _make_stripe_client(
            api_key="sk_key",
            webhook_secret="whsec_sec",
        )
        assert client._api_key == "sk_key"
        assert client._webhook_secret == "whsec_sec"  # noqa: S105

    def test_stripe_initially_none(self) -> None:
        client = _make_stripe_client()
        assert client._stripe is None


# ============================================================
# Checkout session creation
# ============================================================


class TestCheckoutSession:
    @pytest.mark.asyncio
    async def test_create_checkout_session(self) -> None:
        client = _make_stripe_client()
        mock_stripe = _mock_stripe_module()

        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_123"
        mock_stripe.checkout.Session.create.return_value = mock_session

        client._stripe = mock_stripe

        result = await client.create_checkout_session(
            org_id="org_1",
            plan="pro",
            success_url="https://app.example.com/success",
            cancel_url="https://app.example.com/cancel",
        )

        assert result["session_id"] == "cs_test_123"
        assert "checkout.stripe.com" in result["url"]
        mock_stripe.checkout.Session.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_checkout_invalid_plan_raises(self) -> None:
        client = _make_stripe_client()
        client._stripe = _mock_stripe_module()

        with pytest.raises(ValueError, match="Invalid or free plan"):
            await client.create_checkout_session(
                org_id="org_1",
                plan="nonexistent",
                success_url="https://example.com/ok",
                cancel_url="https://example.com/cancel",
            )

    @pytest.mark.asyncio
    async def test_checkout_free_plan_raises(self) -> None:
        client = _make_stripe_client()
        client._stripe = _mock_stripe_module()

        with pytest.raises(ValueError, match="Invalid or free plan"):
            await client.create_checkout_session(
                org_id="org_1",
                plan="free",
                success_url="https://example.com/ok",
                cancel_url="https://example.com/cancel",
            )


# ============================================================
# Subscription retrieval
# ============================================================


class TestGetSubscription:
    @pytest.mark.asyncio
    async def test_get_subscription(self) -> None:
        client = _make_stripe_client()
        mock_stripe = _mock_stripe_module()

        mock_sub = MagicMock()
        mock_sub.id = "sub_123"
        mock_sub.status = "active"
        mock_sub.metadata = {"plan": "pro"}
        mock_sub.current_period_end = 1700000000
        mock_sub.cancel_at_period_end = False
        mock_stripe.Subscription.retrieve.return_value = mock_sub

        client._stripe = mock_stripe

        result = await client.get_subscription("sub_123")

        assert result["id"] == "sub_123"
        assert result["status"] == "active"
        assert result["plan"] == "pro"
        assert result["current_period_end"] == 1700000000
        assert result["cancel_at_period_end"] is False


# ============================================================
# Subscription cancellation
# ============================================================


class TestCancelSubscription:
    @pytest.mark.asyncio
    async def test_cancel_subscription(self) -> None:
        client = _make_stripe_client()
        mock_stripe = _mock_stripe_module()

        mock_sub = MagicMock()
        mock_sub.id = "sub_456"
        mock_sub.status = "active"
        mock_sub.cancel_at_period_end = True
        mock_stripe.Subscription.modify.return_value = mock_sub

        client._stripe = mock_stripe

        result = await client.cancel_subscription("sub_456")

        assert result["id"] == "sub_456"
        assert result["cancel_at_period_end"] is True
        mock_stripe.Subscription.modify.assert_called_once_with(
            "sub_456",
            cancel_at_period_end=True,
        )


# ============================================================
# Usage record
# ============================================================


class TestUsageRecord:
    @pytest.mark.asyncio
    async def test_create_usage_record(self) -> None:
        client = _make_stripe_client()
        mock_stripe = _mock_stripe_module()

        mock_record = MagicMock()
        mock_record.id = "mbur_abc"
        mock_record.quantity = 42
        mock_stripe.SubscriptionItem.create_usage_record.return_value = mock_record

        client._stripe = mock_stripe

        result = await client.create_usage_record(
            subscription_item_id="si_item_1",
            quantity=42,
        )

        assert result["id"] == "mbur_abc"
        assert result["quantity"] == 42


# ============================================================
# Webhook verification
# ============================================================


class TestWebhookVerification:
    def test_valid_webhook(self) -> None:
        client = _make_stripe_client()
        mock_stripe = _mock_stripe_module()

        mock_event: dict[str, Any] = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_123"}},
        }
        mock_stripe.Webhook.construct_event.return_value = mock_event

        client._stripe = mock_stripe

        result = client.verify_webhook(
            payload=b'{"id":"evt_1"}',
            signature="t=123,v1=abc",
        )

        assert result["type"] == "checkout.session.completed"
        assert result["data"]["object"]["id"] == "cs_123"

    def test_invalid_signature_raises(self) -> None:
        client = _make_stripe_client()
        mock_stripe = _mock_stripe_module()

        mock_stripe.Webhook.construct_event.side_effect = (
            mock_stripe.error.SignatureVerificationError(
                "bad sig",
            )
        )

        client._stripe = mock_stripe

        with pytest.raises(ValueError, match="Invalid Stripe"):
            client.verify_webhook(
                payload=b"bad",
                signature="invalid",
            )


# ============================================================
# Webhook event handlers (via billing routes)
# ============================================================


class TestWebhookHandlers:
    """Test the route-level webhook handler functions."""

    def test_checkout_completed_activates_sub(self) -> None:
        from shieldops.api.routes.billing import (
            _handle_checkout_completed,
            _org_subscriptions,
        )

        _org_subscriptions.clear()

        obj: dict[str, Any] = {
            "client_reference_id": "org_test",
            "metadata": {"plan": "pro"},
            "subscription": "sub_stripe_1",
        }
        _handle_checkout_completed(obj)

        assert "org_test" in _org_subscriptions
        sub = _org_subscriptions["org_test"]
        assert sub["plan"] == "pro"
        assert sub["stripe_subscription_id"] == "sub_stripe_1"
        assert sub["status"] == "active"

        _org_subscriptions.clear()

    def test_invoice_paid_records_payment(self) -> None:
        from shieldops.api.routes.billing import (
            _handle_invoice_paid,
            _org_subscriptions,
            _payment_history,
        )

        _org_subscriptions.clear()
        _payment_history.clear()

        _org_subscriptions["org_x"] = {
            "stripe_subscription_id": "sub_99",
        }

        obj: dict[str, Any] = {
            "id": "inv_abc",
            "subscription": "sub_99",
            "amount_paid": 4900,
            "currency": "usd",
        }
        _handle_invoice_paid(obj)

        assert len(_payment_history.get("org_x", [])) == 1
        assert _payment_history["org_x"][0]["amount"] == 4900

        _org_subscriptions.clear()
        _payment_history.clear()

    def test_subscription_updated_changes_plan(self) -> None:
        from shieldops.api.routes.billing import (
            _handle_subscription_updated,
            _org_subscriptions,
        )

        _org_subscriptions.clear()
        _org_subscriptions["org_y"] = {
            "stripe_subscription_id": "sub_upd",
            "plan": "pro",
            "plan_name": "Pro",
            "agent_limit": 25,
            "api_calls_limit": 50000,
            "status": "active",
            "cancel_at_period_end": False,
        }

        obj: dict[str, Any] = {
            "id": "sub_upd",
            "status": "active",
            "metadata": {"plan": "enterprise"},
            "cancel_at_period_end": False,
        }
        _handle_subscription_updated(obj)

        sub = _org_subscriptions["org_y"]
        assert sub["plan"] == "enterprise"
        assert sub["agent_limit"] == -1

        _org_subscriptions.clear()

    def test_subscription_deleted_downgrades(self) -> None:
        from shieldops.api.routes.billing import (
            _handle_subscription_deleted,
            _org_subscriptions,
        )

        _org_subscriptions.clear()
        _org_subscriptions["org_z"] = {
            "stripe_subscription_id": "sub_del",
            "plan": "pro",
        }

        obj: dict[str, Any] = {"id": "sub_del"}
        _handle_subscription_deleted(obj)

        sub = _org_subscriptions["org_z"]
        assert sub["plan"] == "free"
        assert sub["stripe_subscription_id"] is None

        _org_subscriptions.clear()


# ============================================================
# ensure_stripe lazy import
# ============================================================


class TestEnsureStripe:
    def test_idempotent(self) -> None:
        client = _make_stripe_client()
        mock_mod = _mock_stripe_module()
        client._stripe = mock_mod

        assert client._ensure_stripe() is mock_mod

    def test_sets_api_key(self) -> None:
        """Verify that _ensure_stripe sets stripe.api_key."""
        client = _make_stripe_client(api_key="sk_real_key")
        mock_mod = _mock_stripe_module()

        with patch.dict(
            "sys.modules",
            {"stripe": mock_mod},
        ):
            result = client._ensure_stripe()
            assert result is mock_mod
            assert mock_mod.api_key == "sk_real_key"
