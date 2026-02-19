"""AWS Cost Explorer billing source.

Queries the AWS Cost Explorer GetCostAndUsage API to retrieve billing
data grouped by service and broken down by day.  The boto3 client is
lazily initialised and all synchronous SDK calls are dispatched to a
thread executor so the caller's event loop is never blocked.
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


class AWSCostExplorerSource:
    """Query AWS Cost Explorer for billing data.

    Uses ``GetCostAndUsage`` with ``UnblendedCost`` metrics, grouping by
    SERVICE for the service breakdown and using DAILY granularity for
    the day-by-day view.

    Note: The Cost Explorer API endpoint is global and always lives in
    ``us-east-1`` regardless of the workload region, so the client is
    pinned to that region.
    """

    provider: str = "aws"

    def __init__(self, region: str = "us-east-1") -> None:
        self._region = region
        self._client: Any = None

    def _ensure_client(self) -> Any:
        """Lazily initialise the boto3 Cost Explorer client."""
        if self._client is None:
            import boto3

            # Cost Explorer API is only available in us-east-1.
            self._client = boto3.client("ce", region_name="us-east-1")
        return self._client

    async def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous boto3 call in a thread executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query(
        self,
        environment: str = "production",
        period: str = "30d",
    ) -> BillingData:
        """Query AWS Cost Explorer for the given period.

        Args:
            environment: Target environment label (stored in metadata).
            period: Lookback window expressed as ``<N>d`` (e.g. ``7d``,
                ``30d``, ``90d``).

        Returns:
            A :class:`BillingData` instance with service and daily
            breakdowns.  On error an empty ``BillingData`` with the
            exception message in ``metadata["error"]`` is returned.
        """
        try:
            client = self._ensure_client()
            end_date = datetime.now(UTC).date()
            days = _parse_period_days(period)
            start_date = end_date - timedelta(days=days)

            time_period = {
                "Start": start_date.isoformat(),
                "End": end_date.isoformat(),
            }

            by_service, total_cost, currency = await self._fetch_service_costs(client, time_period)
            daily_breakdown = await self._fetch_daily_breakdown(client, time_period)

            logger.info(
                "aws_billing_queried",
                total_cost=round(total_cost, 2),
                services=len(by_service),
                days=days,
            )

            return BillingData(
                total_cost=round(total_cost, 2),
                currency=currency,
                period_start=start_date.isoformat(),
                period_end=end_date.isoformat(),
                by_service=by_service,
                daily_breakdown=daily_breakdown,
                metadata={
                    "provider": "aws",
                    "region": self._region,
                    "environment": environment,
                },
            )

        except Exception as exc:
            logger.error("aws_billing_error", error=str(exc))
            return BillingData(
                total_cost=0.0,
                metadata={"error": str(exc), "provider": "aws"},
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_service_costs(
        self,
        client: Any,
        time_period: dict[str, str],
    ) -> tuple[list[dict[str, Any]], float, str]:
        """Fetch costs grouped by AWS service.

        Returns ``(by_service_list, total_cost, currency)``.
        """
        response = await self._run_sync(
            client.get_cost_and_usage,
            TimePeriod=time_period,
            Granularity="MONTHLY",
            Metrics=["UnblendedCost", "UsageQuantity"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        by_service: list[dict[str, Any]] = []
        total_cost = 0.0
        currency = "USD"

        for result_group in response.get("ResultsByTime", []):
            for group in result_group.get("Groups", []):
                service_name = group["Keys"][0]
                cost_val = float(group["Metrics"]["UnblendedCost"]["Amount"])
                currency = group["Metrics"]["UnblendedCost"].get("Unit", "USD")
                total_cost += cost_val
                by_service.append(
                    {
                        "service": service_name,
                        "cost": round(cost_val, 2),
                        "currency": currency,
                    }
                )

        by_service.sort(key=lambda x: x["cost"], reverse=True)
        return by_service, total_cost, currency

    async def _fetch_daily_breakdown(
        self,
        client: Any,
        time_period: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Fetch day-by-day total cost breakdown."""
        response = await self._run_sync(
            client.get_cost_and_usage,
            TimePeriod=time_period,
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )

        daily_breakdown: list[dict[str, Any]] = []
        for result in response.get("ResultsByTime", []):
            day_cost = float(result["Total"]["UnblendedCost"]["Amount"])
            daily_breakdown.append(
                {
                    "date": result["TimePeriod"]["Start"],
                    "cost": round(day_cost, 2),
                }
            )

        return daily_breakdown
