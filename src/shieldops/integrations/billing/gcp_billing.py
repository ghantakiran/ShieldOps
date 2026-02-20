"""GCP Cloud Billing source using BigQuery billing export.

Queries the BigQuery billing export table to retrieve cost data grouped
by service and broken down by day.  The google-cloud-bigquery client is
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


class GCPBillingSource:
    """Query GCP billing data via BigQuery billing export.

    Requires:
    - BigQuery billing export enabled in GCP project
    - ``google-cloud-bigquery`` package installed
    - ``GOOGLE_APPLICATION_CREDENTIALS`` or ADC configured
    """

    provider: str = "gcp"

    def __init__(
        self,
        project_id: str,
        dataset: str = "billing_export",
        table: str = "gcp_billing_export_v1",
    ) -> None:
        self._project_id = project_id
        self._dataset = dataset
        self._table = table
        self._client: Any = None

    # ------------------------------------------------------------------
    # Client management
    # ------------------------------------------------------------------

    def _ensure_client(self) -> Any:
        """Lazily initialise the BigQuery client."""
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(
                project=self._project_id,
            )
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query(
        self,
        environment: str = "production",
        period: str = "30d",
    ) -> BillingData:
        """Query GCP billing export for the given period.

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
                    self._query_billing,
                    start_date.isoformat(),
                    end_date.isoformat(),
                    environment,
                ),
            )
            logger.info(
                "gcp_billing_queried",
                total_cost=result.total_cost,
                services=len(result.by_service),
                days=days,
            )
            return result
        except Exception as exc:
            logger.error("gcp_billing_query_failed", error=str(exc))
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

    def _query_billing(
        self,
        start_date: str,
        end_date: str,
        environment: str,
    ) -> BillingData:
        """Execute BigQuery billing queries synchronously.

        Called inside a thread executor from :meth:`query`.
        """
        client = self._ensure_client()
        table_ref = f"{self._project_id}.{self._dataset}.{self._table}"

        by_service, total_cost, currency = self._fetch_service_costs(
            client, table_ref, start_date, end_date
        )
        daily_breakdown = self._fetch_daily_breakdown(
            client,
            table_ref,
            start_date,
            end_date,
        )

        return BillingData(
            total_cost=round(total_cost, 2),
            currency=currency,
            period_start=start_date,
            period_end=end_date,
            by_service=by_service,
            by_environment=[
                {
                    "environment": environment,
                    "cost": round(total_cost, 2),
                },
            ],
            daily_breakdown=daily_breakdown,
            metadata={
                "provider": "gcp",
                "project_id": self._project_id,
            },
        )

    @staticmethod
    def _fetch_service_costs(
        client: Any,
        table_ref: str,
        start_date: str,
        end_date: str,
    ) -> tuple[list[dict[str, Any]], float, str]:
        """Fetch costs grouped by GCP service.

        Returns ``(by_service_list, total_cost, currency)``.
        """
        # BigQuery does not support parameterised table refs;
        # inputs are internally generated ISO date strings.
        query = f"""
            SELECT
                service.description AS service_name,
                SUM(cost) AS total_cost,
                currency
            FROM `{table_ref}`
            WHERE usage_start_time >= '{start_date}'
              AND usage_start_time < '{end_date}'
            GROUP BY service_name, currency
            ORDER BY total_cost DESC
        """  # noqa: S608  # nosec B608
        rows = list(client.query(query).result())

        by_service: list[dict[str, Any]] = []
        total_cost = 0.0
        currency = "USD"

        for row in rows:
            cost = float(row.total_cost or 0)
            by_service.append(
                {
                    "service": row.service_name,
                    "cost": round(cost, 2),
                }
            )
            total_cost += cost
            currency = row.currency or "USD"

        return by_service, total_cost, currency

    @staticmethod
    def _fetch_daily_breakdown(
        client: Any,
        table_ref: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """Fetch day-by-day total cost breakdown."""
        query = f"""
            SELECT
                DATE(usage_start_time) AS usage_date,
                SUM(cost) AS daily_cost
            FROM `{table_ref}`
            WHERE usage_start_time >= '{start_date}'
              AND usage_start_time < '{end_date}'
            GROUP BY usage_date
            ORDER BY usage_date
        """  # noqa: S608  # nosec B608
        rows = list(client.query(query).result())

        return [
            {
                "date": str(row.usage_date),
                "cost": round(float(row.daily_cost or 0), 2),
            }
            for row in rows
        ]
