"""GCP Compute Engine connector using REST APIs via httpx.

All operations hit the Compute Engine v1 REST API directly rather than
relying on the ``google-cloud-compute`` SDK.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog

from shieldops.connectors.gcp.auth import GCPAuthProvider
from shieldops.connectors.gcp.models import GCPInstance

logger = structlog.get_logger()

_COMPUTE_BASE = "https://compute.googleapis.com/compute/v1/projects"


class GCPComputeConnector:
    """Interact with Compute Engine instances via the REST API.

    Parameters
    ----------
    project_id:
        GCP project ID.
    credentials_path:
        Optional path to a service account JSON key file.
        When *None*, Application Default Credentials are used.
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
    ) -> dict[str, Any]:
        headers = await self._auth.get_auth_headers()
        client = await self._get_client()
        resp = await client.request(method, url, headers=headers, json=json)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    # ------------------------------------------------------------------
    # Instance operations
    # ------------------------------------------------------------------

    async def list_instances(
        self,
        zone: str | None = None,
    ) -> list[GCPInstance]:
        """List VM instances, optionally scoped to a single zone.

        When *zone* is ``None`` the aggregated list endpoint is used,
        returning instances across all zones.
        """
        if zone:
            url = f"{_COMPUTE_BASE}/{self._project_id}/zones/{zone}/instances"
            data = await self._request("GET", url)
            items = data.get("items", [])
        else:
            url = f"{_COMPUTE_BASE}/{self._project_id}/aggregated/instances"
            data = await self._request("GET", url)
            items = []
            for scoped in data.get("items", {}).values():
                items.extend(scoped.get("instances", []))

        logger.info(
            "gcp_compute_list_instances",
            zone=zone,
            count=len(items),
        )
        return [self._parse_instance(i) for i in items]

    async def get_instance(self, zone: str, instance_name: str) -> GCPInstance:
        """Get detailed information about a single VM instance."""
        url = f"{_COMPUTE_BASE}/{self._project_id}/zones/{zone}/instances/{instance_name}"
        data = await self._request("GET", url)
        logger.info(
            "gcp_compute_get_instance",
            zone=zone,
            instance=instance_name,
        )
        return self._parse_instance(data)

    async def start_instance(self, zone: str, instance_name: str) -> dict[str, Any]:
        """Start a stopped VM instance."""
        url = f"{_COMPUTE_BASE}/{self._project_id}/zones/{zone}/instances/{instance_name}/start"
        result = await self._request("POST", url)
        logger.info(
            "gcp_compute_start_instance",
            zone=zone,
            instance=instance_name,
            operation=result.get("name"),
        )
        return result

    async def stop_instance(self, zone: str, instance_name: str) -> dict[str, Any]:
        """Stop a running VM instance."""
        url = f"{_COMPUTE_BASE}/{self._project_id}/zones/{zone}/instances/{instance_name}/stop"
        result = await self._request("POST", url)
        logger.info(
            "gcp_compute_stop_instance",
            zone=zone,
            instance=instance_name,
            operation=result.get("name"),
        )
        return result

    async def restart_instance(self, zone: str, instance_name: str) -> dict[str, Any]:
        """Restart a VM by stopping then starting it.

        Uses the ``reset`` action which is equivalent to a hard reboot
        without needing to wait for the stop to complete first.
        """
        url = f"{_COMPUTE_BASE}/{self._project_id}/zones/{zone}/instances/{instance_name}/reset"
        result = await self._request("POST", url)
        logger.info(
            "gcp_compute_restart_instance",
            zone=zone,
            instance=instance_name,
            operation=result.get("name"),
        )
        return result

    async def get_serial_console_output(self, zone: str, instance_name: str) -> str:
        """Retrieve serial console output for debugging boot issues."""
        url = (
            f"{_COMPUTE_BASE}/{self._project_id}/zones/{zone}/instances/{instance_name}/serialPort"
        )
        data = await self._request("GET", url)
        output: str = data.get("contents", "")
        logger.info(
            "gcp_compute_serial_output",
            zone=zone,
            instance=instance_name,
            length=len(output),
        )
        return output

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
    def _parse_instance(data: dict[str, Any]) -> GCPInstance:
        """Convert raw Compute Engine JSON to a ``GCPInstance`` model."""
        # Extract IPs from network interfaces
        internal_ip: str | None = None
        external_ip: str | None = None
        interfaces = data.get("networkInterfaces", [])
        if interfaces:
            internal_ip = interfaces[0].get("networkIP")
            access_configs = interfaces[0].get("accessConfigs", [])
            if access_configs:
                external_ip = access_configs[0].get("natIP")

        created_at: datetime | None = None
        raw_ts = data.get("creationTimestamp")
        if raw_ts:
            try:
                created_at = datetime.fromisoformat(raw_ts)
            except (ValueError, TypeError):
                created_at = None

        # machine_type is a full URL — extract just the type name
        machine_type_raw = data.get("machineType", "")
        machine_type = machine_type_raw.rsplit("/", 1)[-1]

        # zone is a full URL — extract zone name
        zone_raw = data.get("zone", "")
        zone = zone_raw.rsplit("/", 1)[-1]

        return GCPInstance(
            instance_id=str(data.get("id", "")),
            name=data.get("name", ""),
            zone=zone,
            machine_type=machine_type,
            status=data.get("status", "UNKNOWN"),
            internal_ip=internal_ip,
            external_ip=external_ip,
            labels=data.get("labels", {}),
            created_at=created_at,
            network_tags=data.get("tags", {}).get("items", []),
        )
