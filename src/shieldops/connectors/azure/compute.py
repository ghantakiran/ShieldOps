"""Azure Compute connector using REST APIs via httpx.

All operations hit the Azure Resource Manager REST API directly rather
than relying on the ``azure-mgmt-compute`` SDK.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from shieldops.connectors.azure.auth import AzureAuthProvider
from shieldops.connectors.azure.models import AzureVM

logger = structlog.get_logger()

_ARM_BASE = "https://management.azure.com"
_API_VERSION = "2023-09-01"


class AzureComputeClient:
    """Interact with Azure Virtual Machines via the ARM REST API.

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
        merged_params = {"api-version": _API_VERSION}
        if params:
            merged_params.update(params)
        client = await self._get_client()
        resp = await client.request(
            method,
            url,
            headers=headers,
            json=json,
            params=merged_params,
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    # ------------------------------------------------------------------
    # VM operations
    # ------------------------------------------------------------------

    def _vm_base_url(self, resource_group: str) -> str:
        sub = self._auth.subscription_id
        return (
            f"{_ARM_BASE}/subscriptions/{sub}"
            f"/resourceGroups/{resource_group}"
            "/providers/Microsoft.Compute/virtualMachines"
        )

    async def list_vms(
        self,
        resource_group: str,
    ) -> list[AzureVM]:
        """List all VMs in a resource group."""
        url = self._vm_base_url(resource_group)
        data = await self._request("GET", url)
        items: list[dict[str, Any]] = data.get("value", [])
        logger.info(
            "azure_compute_list_vms",
            resource_group=resource_group,
            count=len(items),
        )
        return [self._parse_vm(item, resource_group) for item in items]

    async def get_vm(
        self,
        resource_group: str,
        vm_name: str,
    ) -> AzureVM:
        """Get detailed information about a single VM."""
        url = f"{self._vm_base_url(resource_group)}/{vm_name}"
        data = await self._request(
            "GET",
            url,
            params={"$expand": "instanceView"},
        )
        logger.info(
            "azure_compute_get_vm",
            resource_group=resource_group,
            vm=vm_name,
        )
        return self._parse_vm(data, resource_group)

    async def start_vm(
        self,
        resource_group: str,
        vm_name: str,
    ) -> dict[str, Any]:
        """Start a stopped/deallocated VM."""
        url = f"{self._vm_base_url(resource_group)}/{vm_name}/start"
        result = await self._request("POST", url)
        logger.info(
            "azure_compute_start_vm",
            resource_group=resource_group,
            vm=vm_name,
        )
        return result

    async def stop_vm(
        self,
        resource_group: str,
        vm_name: str,
    ) -> dict[str, Any]:
        """Stop (deallocate) a running VM."""
        url = f"{self._vm_base_url(resource_group)}/{vm_name}/deallocate"
        result = await self._request("POST", url)
        logger.info(
            "azure_compute_stop_vm",
            resource_group=resource_group,
            vm=vm_name,
        )
        return result

    async def restart_vm(
        self,
        resource_group: str,
        vm_name: str,
    ) -> dict[str, Any]:
        """Restart a running VM."""
        url = f"{self._vm_base_url(resource_group)}/{vm_name}/restart"
        result = await self._request("POST", url)
        logger.info(
            "azure_compute_restart_vm",
            resource_group=resource_group,
            vm=vm_name,
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
    def _parse_vm(
        data: dict[str, Any],
        resource_group: str,
    ) -> AzureVM:
        """Convert raw ARM JSON to an ``AzureVM`` model."""
        properties: dict[str, Any] = data.get("properties", {})
        hw_profile: dict[str, Any] = properties.get(
            "hardwareProfile",
            {},
        )
        os_profile: dict[str, Any] = properties.get("osProfile", {})
        storage_profile: dict[str, Any] = properties.get(
            "storageProfile",
            {},
        )

        # Determine power state from instanceView statuses
        status = "unknown"
        instance_view: dict[str, Any] = properties.get(
            "instanceView",
            {},
        )
        for s in instance_view.get("statuses", []):
            code: str = s.get("code", "")
            if code.startswith("PowerState/"):
                status = code.split("/", 1)[1]
                break

        # OS type from storage profile
        os_disk: dict[str, Any] = storage_profile.get("osDisk", {})
        os_type = os_disk.get("osType", os_profile.get("windowsConfiguration") and "Windows" or "")

        # Network IPs — best-effort extraction from network interfaces
        private_ip: str | None = None
        public_ip: str | None = None
        net_profile: dict[str, Any] = properties.get(
            "networkProfile",
            {},
        )
        nic_refs: list[dict[str, Any]] = net_profile.get(
            "networkInterfaces",
            [],
        )
        if nic_refs:
            # IPs are only available when instanceView is expanded or
            # from a separate NIC GET; store ref id for downstream use.
            pass

        return AzureVM(
            name=data.get("name", ""),
            resource_group=resource_group,
            location=data.get("location", ""),
            vm_size=hw_profile.get("vmSize", ""),
            status=status,
            os_type=os_type,
            private_ip=private_ip,
            public_ip=public_ip,
            tags=data.get("tags") or {},
        )
