"""Azure Kubernetes Service (AKS) connector using REST APIs via httpx.

All operations hit the Azure Resource Manager REST API directly rather
than relying on the ``azure-mgmt-containerservice`` SDK.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from shieldops.connectors.azure.auth import AzureAuthProvider
from shieldops.connectors.azure.models import AKSCluster, AKSNodePool

logger = structlog.get_logger()

_ARM_BASE = "https://management.azure.com"
_API_VERSION = "2023-11-01"


class AKSClient:
    """Interact with AKS managed clusters via the ARM REST API.

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
    # Cluster operations
    # ------------------------------------------------------------------

    def _cluster_base_url(self, resource_group: str) -> str:
        sub = self._auth.subscription_id
        return (
            f"{_ARM_BASE}/subscriptions/{sub}"
            f"/resourceGroups/{resource_group}"
            "/providers/Microsoft.ContainerService/managedClusters"
        )

    async def list_clusters(
        self,
        resource_group: str,
    ) -> list[AKSCluster]:
        """List all AKS clusters in a resource group."""
        url = self._cluster_base_url(resource_group)
        data = await self._request("GET", url)
        items: list[dict[str, Any]] = data.get("value", [])
        logger.info(
            "azure_aks_list_clusters",
            resource_group=resource_group,
            count=len(items),
        )
        return [self._parse_cluster(item, resource_group) for item in items]

    async def get_cluster(
        self,
        resource_group: str,
        cluster_name: str,
    ) -> AKSCluster:
        """Get detailed information about a single AKS cluster."""
        url = f"{self._cluster_base_url(resource_group)}/{cluster_name}"
        data = await self._request("GET", url)
        logger.info(
            "azure_aks_get_cluster",
            resource_group=resource_group,
            cluster=cluster_name,
        )
        return self._parse_cluster(data, resource_group)

    # ------------------------------------------------------------------
    # Node pool operations
    # ------------------------------------------------------------------

    def _pool_base_url(
        self,
        resource_group: str,
        cluster_name: str,
    ) -> str:
        return f"{self._cluster_base_url(resource_group)}/{cluster_name}/agentPools"

    async def get_node_pools(
        self,
        resource_group: str,
        cluster_name: str,
    ) -> list[AKSNodePool]:
        """List all node pools in an AKS cluster."""
        url = self._pool_base_url(resource_group, cluster_name)
        data = await self._request("GET", url)
        items: list[dict[str, Any]] = data.get("value", [])
        logger.info(
            "azure_aks_get_node_pools",
            resource_group=resource_group,
            cluster=cluster_name,
            count=len(items),
        )
        return [self._parse_node_pool(item) for item in items]

    async def scale_node_pool(
        self,
        resource_group: str,
        cluster_name: str,
        pool_name: str,
        count: int,
    ) -> dict[str, Any]:
        """Scale a node pool to the specified node count."""
        url = f"{self._pool_base_url(resource_group, cluster_name)}/{pool_name}"
        # Fetch current config then patch the count
        current = await self._request("GET", url)
        properties: dict[str, Any] = current.get("properties", {})
        properties["count"] = count
        body: dict[str, Any] = {"properties": properties}

        result = await self._request("PUT", url, json=body)
        logger.info(
            "azure_aks_scale_node_pool",
            resource_group=resource_group,
            cluster=cluster_name,
            pool=pool_name,
            target_count=count,
        )
        return result

    async def get_cluster_credentials(
        self,
        resource_group: str,
        cluster_name: str,
    ) -> dict[str, str]:
        """Retrieve admin kubeconfig for an AKS cluster.

        Returns a dict with ``kubeconfig`` as base64-encoded YAML.
        """
        url = f"{self._cluster_base_url(resource_group)}/{cluster_name}/listClusterAdminCredential"
        data = await self._request("POST", url)
        kubeconfigs: list[dict[str, Any]] = data.get("kubeconfigs", [])
        if kubeconfigs:
            return {"kubeconfig": kubeconfigs[0].get("value", "")}
        logger.warning(
            "azure_aks_no_credentials",
            resource_group=resource_group,
            cluster=cluster_name,
        )
        return {"kubeconfig": ""}

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
    def _parse_cluster(
        data: dict[str, Any],
        resource_group: str,
    ) -> AKSCluster:
        """Convert raw ARM JSON to an ``AKSCluster`` model."""
        properties: dict[str, Any] = data.get("properties", {})
        pools_raw: list[dict[str, Any]] = properties.get(
            "agentPoolProfiles",
            [],
        )
        node_pools = [AKSClient._parse_node_pool_profile(p) for p in pools_raw]
        total_nodes = sum(p.node_count for p in node_pools)

        return AKSCluster(
            name=data.get("name", ""),
            resource_group=resource_group,
            location=data.get("location", ""),
            kubernetes_version=properties.get("kubernetesVersion", ""),
            node_count=total_nodes,
            status=properties.get("provisioningState", ""),
            fqdn=properties.get("fqdn", ""),
            node_pools=node_pools,
        )

    @staticmethod
    def _parse_node_pool_profile(
        data: dict[str, Any],
    ) -> AKSNodePool:
        """Parse an inline agentPoolProfile from the cluster payload."""
        return AKSNodePool(
            name=data.get("name", ""),
            vm_size=data.get("vmSize", ""),
            node_count=data.get("count", 0),
            min_count=data.get("minCount", 0),
            max_count=data.get("maxCount", 0),
            mode=data.get("mode", ""),
            os_type=data.get("osType", ""),
        )

    @staticmethod
    def _parse_node_pool(data: dict[str, Any]) -> AKSNodePool:
        """Parse a standalone agentPool resource."""
        properties: dict[str, Any] = data.get("properties", {})
        return AKSNodePool(
            name=data.get("name", ""),
            vm_size=properties.get("vmSize", ""),
            node_count=properties.get("count", 0),
            min_count=properties.get("minCount", 0),
            max_count=properties.get("maxCount", 0),
            mode=properties.get("mode", ""),
            os_type=properties.get("osType", ""),
        )
