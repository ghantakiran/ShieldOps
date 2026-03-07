"""GCP Cloud SQL connector using REST APIs via httpx.

All operations hit the Cloud SQL Admin v1 and Cloud Monitoring v3 REST
APIs directly rather than relying on the ``google-cloud-sqladmin`` SDK.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog

from shieldops.connectors.gcp.auth import GCPAuthProvider
from shieldops.connectors.gcp.models import CloudSQLInstance, GCPMetric

logger = structlog.get_logger()

_SQLADMIN_BASE = "https://sqladmin.googleapis.com/v1/projects"
_MONITORING_BASE = "https://monitoring.googleapis.com/v3/projects"


class CloudSQLConnector:
    """Interact with Cloud SQL instances via the REST API.

    Parameters
    ----------
    project_id:
        GCP project ID.
    credentials_path:
        Optional path to a service account JSON key file.
    """

    def __init__(
        self,
        project_id: str,
        credentials_path: str | None = None,
    ) -> None:
        self._project_id = project_id
        self._auth = GCPAuthProvider(credentials_path=credentials_path)
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
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = await self._auth.get_auth_headers()
        client = await self._get_client()
        resp = await client.request(method, url, headers=headers, json=json, params=params)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    # ------------------------------------------------------------------
    # Instance operations
    # ------------------------------------------------------------------

    async def list_instances(self) -> list[CloudSQLInstance]:
        """List all Cloud SQL instances in the project."""
        url = f"{_SQLADMIN_BASE}/{self._project_id}/instances"
        data = await self._request("GET", url)
        items = data.get("items", [])
        logger.info(
            "cloudsql_list_instances",
            count=len(items),
        )
        return [self._parse_instance(i) for i in items]

    async def get_instance(self, instance_name: str) -> CloudSQLInstance:
        """Get detailed information about a Cloud SQL instance."""
        url = f"{_SQLADMIN_BASE}/{self._project_id}/instances/{instance_name}"
        data = await self._request("GET", url)
        logger.info(
            "cloudsql_get_instance",
            instance=instance_name,
        )
        return self._parse_instance(data)

    async def restart_instance(self, instance_name: str) -> dict[str, Any]:
        """Restart a Cloud SQL instance."""
        url = f"{_SQLADMIN_BASE}/{self._project_id}/instances/{instance_name}/restart"
        result = await self._request("POST", url)
        logger.info(
            "cloudsql_restart_instance",
            instance=instance_name,
            operation=result.get("name"),
        )
        return result

    # ------------------------------------------------------------------
    # Metrics via Cloud Monitoring
    # ------------------------------------------------------------------

    async def get_metrics(
        self,
        instance_name: str,
        metric_type: str,
        *,
        minutes: int = 30,
    ) -> GCPMetric:
        """Query Cloud Monitoring for a Cloud SQL metric.

        Parameters
        ----------
        instance_name:
            Cloud SQL instance name.
        metric_type:
            Full metric type, e.g.
            ``cloudsql.googleapis.com/database/cpu/utilization``.
        minutes:
            Lookback window in minutes (default 30).
        """
        now = datetime.now(UTC)
        start = now - timedelta(minutes=minutes)

        url = f"{_MONITORING_BASE}/{self._project_id}/timeSeries"
        filter_str = (
            f'metric.type="{metric_type}" '
            f"AND resource.labels.database_id="
            f'"{self._project_id}:{instance_name}"'
        )
        params = {
            "filter": filter_str,
            "interval.startTime": start.isoformat() + "Z",
            "interval.endTime": now.isoformat() + "Z",
        }
        data = await self._request("GET", url, params=params)

        points: list[tuple[datetime, float]] = []
        resource_labels: dict[str, str] = {}
        for ts in data.get("timeSeries", []):
            resource_labels = ts.get("resource", {}).get("labels", {})
            for pt in ts.get("points", []):
                interval = pt.get("interval", {})
                ts_str = interval.get("endTime", interval.get("startTime", ""))
                value_obj = pt.get("value", {})
                # Cloud Monitoring may return int64, double, etc.
                value = value_obj.get("doubleValue") or value_obj.get("int64Value") or 0.0
                try:
                    timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    timestamp = now
                points.append((timestamp, float(value)))

        logger.info(
            "cloudsql_get_metrics",
            instance=instance_name,
            metric_type=metric_type,
            points_count=len(points),
        )

        return GCPMetric(
            metric_type=metric_type,
            resource_type="cloudsql_database",
            resource_labels=resource_labels,
            points=points,
        )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def check_health(self, instance_name: str) -> dict[str, object]:
        """Run a composite health check on a Cloud SQL instance.

        Returns a dict with keys: ``healthy``, ``status``,
        ``cpu_utilization``, ``storage_percent_used``, and
        ``details``.
        """
        instance = await self.get_instance(instance_name)
        details: dict[str, object] = {
            "status": instance.status,
            "storage_size_gb": instance.storage_size_gb,
            "storage_used_gb": instance.storage_used_gb,
            "ha_enabled": instance.ha_enabled,
            "backup_enabled": instance.backup_enabled,
        }

        # Storage utilization
        storage_pct = 0.0
        if instance.storage_size_gb > 0:
            storage_pct = instance.storage_used_gb / instance.storage_size_gb * 100

        # Attempt to fetch CPU utilization from monitoring
        cpu_utilization: float | None = None
        try:
            cpu_metric = await self.get_metrics(
                instance_name,
                "cloudsql.googleapis.com/database/cpu/utilization",
                minutes=5,
            )
            if cpu_metric.points:
                cpu_utilization = cpu_metric.points[0][1] * 100
        except Exception as exc:
            logger.warning(
                "cloudsql_health_cpu_fetch_failed",
                instance=instance_name,
                error=str(exc),
            )

        healthy = (
            instance.status == "RUNNABLE"
            and storage_pct < 90
            and (cpu_utilization is None or cpu_utilization < 95)
        )

        result: dict[str, object] = {
            "healthy": healthy,
            "status": instance.status,
            "cpu_utilization": cpu_utilization,
            "storage_percent_used": round(storage_pct, 2),
            "details": details,
        }

        logger.info(
            "cloudsql_check_health",
            instance=instance_name,
            healthy=healthy,
        )
        return result

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
    def _parse_instance(data: dict[str, Any]) -> CloudSQLInstance:
        """Convert raw SQL Admin JSON to a ``CloudSQLInstance``."""
        settings = data.get("settings", {})
        ip_addrs = [
            {
                "type": addr.get("type", ""),
                "ip": addr.get("ipAddress", ""),
            }
            for addr in data.get("ipAddresses", [])
        ]

        backup_cfg = settings.get("backupConfiguration", {})
        storage_gb = int(settings.get("dataDiskSizeGb", 0))

        # Actual usage comes from currentDiskSize (bytes string)
        raw_used = data.get("currentDiskSize")
        storage_used_gb = 0.0
        if raw_used:
            with contextlib.suppress(ValueError, TypeError):
                storage_used_gb = int(raw_used) / (1024**3)

        return CloudSQLInstance(
            instance_name=data.get("name", ""),
            database_version=data.get("databaseVersion", ""),
            tier=settings.get("tier", ""),
            status=data.get("state", "UNKNOWN"),
            region=data.get("region", ""),
            storage_size_gb=float(storage_gb),
            storage_used_gb=round(storage_used_gb, 2),
            ip_addresses=ip_addrs,
            backup_enabled=backup_cfg.get("enabled", False),
            ha_enabled=(settings.get("availabilityType", "") == "REGIONAL"),
        )
