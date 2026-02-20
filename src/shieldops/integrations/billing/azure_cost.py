"""Azure Cost Management billing source.

Queries the Azure Cost Management Query API to retrieve cost data
grouped by service and broken down by day.  The
azure-mgmt-costmanagement client is lazily initialised and sync SDK
calls run in a thread executor so the caller's event loop is never
blocked.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any

import structlog

from shieldops.integrations.billing.base import BillingData

logger = structlog.get_logger()

_PERIOD_RE = re.compile(r"^(\d+)d$")


def _parse_period_days(period: str) -> int:
    """Extract the number of days from a period string like '30d'.

    Falls back to 30 if the format is unrecognised.
    """
    match = _PERIOD_RE.match(period)
    return int(match.group(1)) if match else 30


class AzureCostManagementSource:
    """Query Azure Cost Management for billing data.

    Requires:
    - ``azure-mgmt-costmanagement`` and ``azure-identity`` packages
    - Service principal or managed identity with
      Cost Management Reader role
    """

    provider: str = "azure"

    def __init__(
        self,
        subscription_id: str,
        resource_group: str | None = None,
    ) -> None:
        self._subscription_id = subscription_id
        self._resource_group = resource_group
        self._client: Any = None

    # ------------------------------------------------------------------
    # Client management
    # ------------------------------------------------------------------

    def _ensure_client(self) -> Any:
        """Lazily initialise the Azure Cost Management client."""
        if self._client is None:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.costmanagement import (
                CostManagementClient,
            )

            credential = DefaultAzureCredential()
            self._client = CostManagementClient(credential)
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query(
        self,
        environment: str = "production",
        period: str = "30d",
    ) -> BillingData:
        """Query Azure Cost Management for the given period.

        Args:
            environment: Target environment label (stored in
                the ``by_environment`` breakdown).
            period: Lookback window expressed as ``<N>d``
                (e.g. ``7d``, ``30d``, ``90d``).

        Returns:
            A :class:`BillingData` instance with service and daily
            breakdowns.  On error an empty ``BillingData`` with
            the exception message in ``metadata["error"]`` is
            returned.
        """
        days = _parse_period_days(period)
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days)

        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None,
                partial(
                    self._query_costs,
                    start_date.isoformat(),
                    end_date.isoformat(),
                    environment,
                ),
            )
            logger.info(
                "azure_billing_queried",
                total_cost=result.total_cost,
                services=len(result.by_service),
                days=days,
            )
            return result
        except Exception as exc:
            logger.error(
                "azure_billing_query_failed",
                error=str(exc),
            )
            return BillingData(
                total_cost=0.0,
                currency="USD",
                period_start=start_date.isoformat(),
                period_end=end_date.isoformat(),
                metadata={"error": str(exc)},
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _query_costs(
        self,
        start_date: str,
        end_date: str,
        environment: str,
    ) -> BillingData:
        """Execute the Cost Management query synchronously.

        Called inside a thread executor from :meth:`query`.
        """
        client = self._ensure_client()
        scope = f"/subscriptions/{self._subscription_id}"

        query_body = self._build_query_body(start_date, end_date)
        result = client.query.usage(
            scope=scope,
            parameters=query_body,
        )

        by_service, daily_costs, total_cost, currency = self._parse_rows(result)

        return BillingData(
            total_cost=round(total_cost, 2),
            currency=currency,
            period_start=start_date,
            period_end=end_date,
            by_service=[
                {"service": s, "cost": round(c, 2)}
                for s, c in sorted(
                    by_service.items(),
                    key=lambda x: -x[1],
                )
            ],
            by_environment=[
                {
                    "environment": environment,
                    "cost": round(total_cost, 2),
                },
            ],
            daily_breakdown=[
                {"date": d, "cost": round(c, 2)} for d, c in sorted(daily_costs.items())
            ],
            metadata={
                "provider": "azure",
                "subscription_id": self._subscription_id,
            },
        )

    @staticmethod
    def _build_query_body(
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """Build the Cost Management query request body."""
        return {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {
                "from": f"{start_date}T00:00:00Z",
                "to": f"{end_date}T23:59:59Z",
            },
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "totalCost": {
                        "name": "Cost",
                        "function": "Sum",
                    },
                },
                "grouping": [
                    {
                        "type": "Dimension",
                        "name": "ServiceName",
                    },
                ],
            },
        }

    @staticmethod
    def _parse_rows(
        result: Any,
    ) -> tuple[dict[str, float], dict[str, float], float, str]:
        """Parse Cost Management query result rows.

        Returns ``(by_service, daily_costs, total_cost, currency)``.
        """
        by_service: dict[str, float] = {}
        daily_costs: dict[str, float] = {}
        total_cost = 0.0
        currency = "USD"

        if not getattr(result, "rows", None):
            return by_service, daily_costs, total_cost, currency

        for row in result.rows:
            cost = float(row[0]) if row[0] else 0.0
            date_val = str(row[1]) if len(row) > 1 else ""
            service = str(row[2]) if len(row) > 2 else "Unknown"
            cur = str(row[3]) if len(row) > 3 else "USD"

            total_cost += cost
            currency = cur
            by_service[service] = by_service.get(service, 0.0) + cost

            if date_val:
                date_key = date_val[:10]
                daily_costs[date_key] = daily_costs.get(date_key, 0.0) + cost

        return by_service, daily_costs, total_cost, currency
