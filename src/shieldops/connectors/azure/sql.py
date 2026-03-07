"""Azure SQL connector using REST APIs via httpx.

All operations hit the Azure Resource Manager REST API directly rather
than relying on the ``azure-mgmt-sql`` SDK.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from shieldops.connectors.azure.auth import AzureAuthProvider
from shieldops.connectors.azure.models import AzureMetric, AzureSQLServer

logger = structlog.get_logger()

_ARM_BASE = "https://management.azure.com"
_SQL_API_VERSION = "2021-11-01"
_MONITOR_API_VERSION = "2023-10-01"


class AzureSQLClient:
    """Interact with Azure SQL servers via the ARM REST API.

    Parameters
    ----------
    auth:
        An ``AzureAuthProvider`` instance for obtaining Bearer tokens.
    """

    def __init__(self, auth: AzureAuthProvider) -> None:
        self._auth = auth
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = await self._auth.get_auth_headers()
        client = await self._get_client()
        resp = await client.request(
            method,
            url,
            headers=headers,
            json=json,
            params=params,
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    # ------------------------------------------------------------------
    # SQL Server operations
    # ------------------------------------------------------------------

    def _sql_base_url(self, resource_group: str) -> str:
        sub = self._auth.subscription_id
        return (
            f"{_ARM_BASE}/subscriptions/{sub}"
            f"/resourceGroups/{resource_group}"
            "/providers/Microsoft.Sql/servers"
        )

    async def list_servers(
        self,
        resource_group: str,
    ) -> list[AzureSQLServer]:
        """List all SQL logical servers in a resource group."""
        url = self._sql_base_url(resource_group)
        data = await self._request(
            "GET",
            url,
            params={"api-version": _SQL_API_VERSION},
        )
        items: list[dict[str, Any]] = data.get("value", [])
        logger.info(
            "azure_sql_list_servers",
            resource_group=resource_group,
            count=len(items),
        )
        return [self._parse_server(item, resource_group) for item in items]

    async def get_server(
        self,
        resource_group: str,
        server_name: str,
    ) -> AzureSQLServer:
        """Get detailed information about a single SQL server."""
        url = f"{self._sql_base_url(resource_group)}/{server_name}"
        data = await self._request(
            "GET",
            url,
            params={"api-version": _SQL_API_VERSION},
        )
        logger.info(
            "azure_sql_get_server",
            resource_group=resource_group,
            server=server_name,
        )
        return self._parse_server(data, resource_group)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    async def get_metrics(
        self,
        resource_group: str,
        server_name: str,
        metric_name: str,
        minutes: int = 30,
    ) -> AzureMetric:
        """Retrieve Azure Monitor metrics for a SQL server.

        Parameters
        ----------
        resource_group:
            Resource group containing the SQL server.
        server_name:
            Name of the SQL logical server.
        metric_name:
            Metric name (e.g. ``cpu_percent``, ``dtu_used``).
        minutes:
            Look-back window in minutes.  Defaults to 30.
        """
        sub = self._auth.subscription_id
        resource_id = (
            f"/subscriptions/{sub}"
            f"/resourceGroups/{resource_group}"
            f"/providers/Microsoft.Sql/servers/{server_name}"
        )
        url = f"{_ARM_BASE}{resource_id}/providers/Microsoft.Insights/metrics"

        now = datetime.now(tz=UTC)
        start = datetime.fromtimestamp(
            now.timestamp() - minutes * 60,
            tz=UTC,
        )
        timespan = f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{now.strftime('%Y-%m-%dT%H:%M:%SZ')}"

        data = await self._request(
            "GET",
            url,
            params={
                "api-version": _MONITOR_API_VERSION,
                "metricnames": metric_name,
                "timespan": timespan,
                "interval": "PT1M",
            },
        )

        timestamps: list[datetime] = []
        values: list[float] = []
        unit = ""

        metric_values: list[dict[str, Any]] = data.get("value", [])
        if metric_values:
            metric_entry: dict[str, Any] = metric_values[0]
            unit = metric_entry.get("unit", "")
            timeseries: list[dict[str, Any]] = metric_entry.get(
                "timeseries",
                [],
            )
            if timeseries:
                ts_data: list[dict[str, Any]] = timeseries[0].get(
                    "data",
                    [],
                )
                for point in ts_data:
                    ts_str = point.get("timeStamp", "")
                    val = point.get("average") or point.get("total", 0.0)
                    if ts_str:
                        try:
                            timestamps.append(
                                datetime.fromisoformat(ts_str),
                            )
                            values.append(float(val))
                        except (ValueError, TypeError):
                            pass

        logger.info(
            "azure_sql_get_metrics",
            resource_group=resource_group,
            server=server_name,
            metric=metric_name,
            points=len(values),
        )
        return AzureMetric(
            name=metric_name,
            unit=unit,
            timestamps=timestamps,
            values=values,
            resource_id=resource_id,
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_server(
        data: dict[str, Any],
        resource_group: str,
    ) -> AzureSQLServer:
        """Convert raw ARM JSON to an ``AzureSQLServer`` model."""
        properties: dict[str, Any] = data.get("properties", {})
        fqdn = properties.get(
            "fullyQualifiedDomainName",
            "",
        )
        return AzureSQLServer(
            name=data.get("name", ""),
            resource_group=resource_group,
            location=data.get("location", ""),
            version=properties.get("version", ""),
            state=properties.get("state", ""),
            fqdn=fqdn,
            admin_login=properties.get("administratorLogin", ""),
        )
