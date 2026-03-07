"""Usage-based billing calculations.

Provides invoice previews, cost breakdowns, monthly forecasts,
and usage analytics based on metered event data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from shieldops.billing.usage_models import (
    BillingTier,
)
from shieldops.billing.usage_tracker import UsageTracker

logger = structlog.get_logger()

# ------------------------------------------------------------------
# Tier definitions
# ------------------------------------------------------------------

TIER_DEFINITIONS: dict[str, BillingTier] = {
    "starter": BillingTier(
        tier_name="Starter",
        included_executions=500,
        overage_price_per_unit=0.50,
        features=[
            "10 agents",
            "500 included executions/month",
            "Email support",
            "Standard dashboards",
        ],
    ),
    "professional": BillingTier(
        tier_name="Professional",
        included_executions=5_000,
        overage_price_per_unit=0.30,
        features=[
            "50 agents",
            "5,000 included executions/month",
            "Priority support",
            "Advanced analytics",
            "Custom playbooks",
            "Slack & PagerDuty integration",
        ],
    ),
    "enterprise": BillingTier(
        tier_name="Enterprise",
        included_executions=-1,  # unlimited
        overage_price_per_unit=0.0,
        features=[
            "Unlimited agents",
            "Unlimited executions",
            "Dedicated support",
            "Custom SLAs",
            "On-prem deployment",
            "SOC 2 compliance",
        ],
    ),
}


class UsageBillingEngine:
    """Calculates invoices, cost breakdowns, and forecasts from usage data."""

    def __init__(
        self,
        tracker: UsageTracker,
        org_plans: dict[str, str] | None = None,
    ) -> None:
        """Initialise the billing engine.

        Args:
            tracker: The ``UsageTracker`` instance to read events from.
            org_plans: Optional mapping of org_id to tier key
                       (e.g. ``{"org-1": "starter"}``).
        """
        self._tracker = tracker
        self._org_plans: dict[str, str] = org_plans or {}

    def set_org_plan(self, org_id: str, plan: str) -> None:
        """Register or update an org's billing tier."""
        self._org_plans[org_id] = plan

    def _tier_for_org(self, org_id: str) -> BillingTier:
        """Resolve the billing tier for an org."""
        plan_key = self._org_plans.get(org_id, "starter")
        return TIER_DEFINITIONS.get(plan_key, TIER_DEFINITIONS["starter"])

    # ------------------------------------------------------------------
    # Invoice preview
    # ------------------------------------------------------------------

    async def calculate_invoice_preview(
        self,
        org_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        """Calculate what the org would be billed for a given period.

        Args:
            org_id: Organisation identifier.
            period_start: Billing period start (inclusive).
            period_end: Billing period end (exclusive).

        Returns:
            Dict with ``included``, ``overage``, ``overage_cost``,
            ``total_events``, and ``tier`` information.
        """
        summary = await self._tracker.get_usage_summary(
            org_id,
            period_start,
            period_end,
        )
        tier = self._tier_for_org(org_id)

        if tier.included_executions < 0:
            # Unlimited plan
            return {
                "org_id": org_id,
                "tier": tier.tier_name,
                "total_events": summary.total_events,
                "included_executions": "unlimited",
                "overage_events": 0,
                "overage_cost": 0.0,
                "total_cost": 0.0,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            }

        overage = max(0, summary.total_events - tier.included_executions)
        overage_cost = round(overage * tier.overage_price_per_unit, 2)

        return {
            "org_id": org_id,
            "tier": tier.tier_name,
            "total_events": summary.total_events,
            "included_executions": tier.included_executions,
            "overage_events": overage,
            "overage_cost": overage_cost,
            "total_cost": overage_cost,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }

    # ------------------------------------------------------------------
    # Cost breakdown by event type
    # ------------------------------------------------------------------

    async def get_cost_breakdown(
        self,
        org_id: str,
    ) -> dict[str, Any]:
        """Break down current-period cost by event type.

        Allocates overage cost proportionally to each event type's
        share of total usage.

        Returns:
            Dict with per-type counts, proportional costs, and totals.
        """
        summary = await self._tracker.get_current_period_usage(org_id)
        tier = self._tier_for_org(org_id)

        breakdown: list[dict[str, Any]] = []
        overage = self._calc_overage(summary.total_events, tier)
        overage_cost = round(overage * tier.overage_price_per_unit, 2)

        for event_type, count in summary.events_by_type.items():
            proportion = count / summary.total_events if summary.total_events else 0
            type_cost = round(overage_cost * proportion, 2)
            breakdown.append(
                {
                    "event_type": event_type.value,
                    "count": count,
                    "proportion": round(proportion, 4),
                    "estimated_cost": type_cost,
                }
            )

        breakdown.sort(key=lambda x: x["count"], reverse=True)

        return {
            "org_id": org_id,
            "tier": tier.tier_name,
            "total_events": summary.total_events,
            "overage_events": overage,
            "total_overage_cost": overage_cost,
            "breakdown": breakdown,
        }

    # ------------------------------------------------------------------
    # Monthly forecast
    # ------------------------------------------------------------------

    async def forecast_monthly_cost(
        self,
        org_id: str,
    ) -> dict[str, Any]:
        """Project the current month's total cost based on usage trend.

        Uses a simple linear extrapolation: events so far this month
        divided by days elapsed, multiplied by days in the month.

        Returns:
            Dict with ``projected_events``, ``projected_overage_cost``,
            and current pace information.
        """
        now = datetime.now(UTC)
        month_start = now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        # End of month
        if now.month == 12:
            month_end = month_start.replace(year=now.year + 1, month=1)
        else:
            month_end = month_start.replace(month=now.month + 1)

        summary = await self._tracker.get_usage_summary(
            org_id,
            month_start,
            now,
        )
        tier = self._tier_for_org(org_id)

        days_elapsed = max((now - month_start).total_seconds() / 86400, 1)
        days_in_month = (month_end - month_start).days
        daily_rate = summary.total_events / days_elapsed
        projected_events = int(daily_rate * days_in_month)

        projected_overage = self._calc_overage(projected_events, tier)
        projected_cost = round(
            projected_overage * tier.overage_price_per_unit,
            2,
        )

        return {
            "org_id": org_id,
            "tier": tier.tier_name,
            "current_events": summary.total_events,
            "days_elapsed": round(days_elapsed, 1),
            "days_in_month": days_in_month,
            "daily_rate": round(daily_rate, 1),
            "projected_events": projected_events,
            "included_executions": (
                "unlimited" if tier.included_executions < 0 else tier.included_executions
            ),
            "projected_overage": projected_overage,
            "projected_overage_cost": projected_cost,
        }

    # ------------------------------------------------------------------
    # Usage analytics
    # ------------------------------------------------------------------

    async def get_usage_analytics(
        self,
        org_id: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """Return usage analytics: daily trends, peak hours, top features.

        Args:
            org_id: Organisation identifier.
            days: Number of days to analyse (default 30).

        Returns:
            Dict with ``daily_usage``, ``peak_hours``, and
            ``most_used_features``.
        """
        now = datetime.now(UTC)
        start = now - timedelta(days=days)
        summary = await self._tracker.get_usage_summary(
            org_id,
            start,
            now,
        )

        # Build daily buckets from history
        daily: dict[str, int] = {}
        hourly: dict[int, int] = {h: 0 for h in range(24)}

        # Access the tracker's history directly (read-only snapshot)
        async with self._tracker._lock:
            events = list(self._tracker._history.get(org_id, []))

        for ev in events:
            if start <= ev.timestamp < now:
                day_key = ev.timestamp.strftime("%Y-%m-%d")
                daily[day_key] = daily.get(day_key, 0) + ev.quantity
                hourly[ev.timestamp.hour] += ev.quantity

        daily_usage = [{"date": k, "events": v} for k, v in sorted(daily.items())]

        peak_hours = sorted(
            [{"hour": h, "events": c} for h, c in hourly.items()],
            key=lambda x: x["events"],
            reverse=True,
        )[:5]

        most_used = sorted(
            [{"feature": t.value, "count": c} for t, c in summary.events_by_type.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

        return {
            "org_id": org_id,
            "period_days": days,
            "total_events": summary.total_events,
            "daily_usage": daily_usage,
            "peak_hours": peak_hours,
            "most_used_features": most_used,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_overage(total_events: int, tier: BillingTier) -> int:
        """Calculate overage events beyond the tier's included amount."""
        if tier.included_executions < 0:
            return 0
        return max(0, total_events - tier.included_executions)
