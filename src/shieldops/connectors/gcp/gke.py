"""GCP Google Kubernetes Engine connector using REST APIs via httpx.

All operations hit the GKE v1 REST API directly rather than relying on
the ``google-cloud-container`` SDK.
"""

from __future__ import annotations

import base64
import tempfile
from typing import Any

import httpx
import structlog

from shieldops.connectors.gcp.auth import GCPAuthProvider
from shieldops.connectors.gcp.models import GKECluster, GKENodePool

logger = structlog.get_logger()

_CONTAINER_BASE = "https://container.googleapis.com/v1/projects"


class GKEConnector:
    """Interact with GKE clusters and node pools via the REST API.

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
    ) -> dict[str, Any]:
        headers = await self._auth.get_auth_headers()
        client = await self._get_client()
        resp = await client.request(method, url, headers=headers, json=json)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    # ------------------------------------------------------------------
    # Cluster operations
    # ------------------------------------------------------------------

    async def list_clusters(
        self,
        location: str | None = None,
    ) -> list[GKECluster]:
        """List GKE clusters.

        When *location* is ``None``, uses ``-`` to list across all
        locations.
        """
        loc = location or "-"
        url = f"{_CONTAINER_BASE}/{self._project_id}/locations/{loc}/clusters"
        data = await self._request("GET", url)
        clusters = data.get("clusters", [])
        logger.info(
            "gke_list_clusters",
            location=loc,
            count=len(clusters),
        )
        return [self._parse_cluster(c) for c in clusters]

    async def get_cluster(self, location: str, cluster_name: str) -> GKECluster:
        """Get detailed information about a single GKE cluster."""
        url = f"{_CONTAINER_BASE}/{self._project_id}/locations/{location}/clusters/{cluster_name}"
        data = await self._request("GET", url)
        logger.info(
            "gke_get_cluster",
            location=location,
            cluster=cluster_name,
        )
        return self._parse_cluster(data)

    # ------------------------------------------------------------------
    # Node pool operations
    # ------------------------------------------------------------------

    async def get_node_pools(self, location: str, cluster_name: str) -> list[GKENodePool]:
        """List node pools for a given GKE cluster."""
        url = (
            f"{_CONTAINER_BASE}/{self._project_id}"
            f"/locations/{location}/clusters/{cluster_name}"
            "/nodePools"
        )
        data = await self._request("GET", url)
        pools = data.get("nodePools", [])
        logger.info(
            "gke_get_node_pools",
            location=location,
            cluster=cluster_name,
            count=len(pools),
        )
        return [self._parse_node_pool(p, cluster_name) for p in pools]

    async def resize_node_pool(
        self,
        location: str,
        cluster_name: str,
        pool_name: str,
        node_count: int,
    ) -> dict[str, Any]:
        """Resize a node pool to the specified node count."""
        url = (
            f"{_CONTAINER_BASE}/{self._project_id}"
            f"/locations/{location}/clusters/{cluster_name}"
            f"/nodePools/{pool_name}:setSize"
        )
        body = {"nodeCount": node_count}
        result = await self._request("POST", url, json=body)
        logger.info(
            "gke_resize_node_pool",
            location=location,
            cluster=cluster_name,
            pool=pool_name,
            node_count=node_count,
            operation=result.get("name"),
        )
        return result

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------

    async def get_cluster_credentials(self, location: str, cluster_name: str) -> dict[str, str]:
        """Retrieve cluster credentials for kubectl access.

        Returns a dict containing ``endpoint``, ``ca_cert_path``, and
        ``token`` that can be used to build a kubeconfig.
        """
        cluster = await self.get_cluster(location, cluster_name)
        token = await self._auth.get_access_token()

        # Fetch full cluster data for the CA certificate
        url = f"{_CONTAINER_BASE}/{self._project_id}/locations/{location}/clusters/{cluster_name}"
        data = await self._request("GET", url)
        ca_data = data.get("masterAuth", {}).get("clusterCaCertificate", "")

        # Write CA cert to a temp file so kubectl can reference it
        ca_path = ""
        if ca_data:
            ca_bytes = base64.b64decode(ca_data)
            with tempfile.NamedTemporaryFile(suffix=".pem", delete=False, prefix="gke-ca-") as tmp:
                tmp.write(ca_bytes)
                ca_path = tmp.name

        logger.info(
            "gke_get_credentials",
            location=location,
            cluster=cluster_name,
            endpoint=cluster.endpoint,
        )

        return {
            "endpoint": f"https://{cluster.endpoint}",
            "ca_cert_path": ca_path,
            "token": token,
        }

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
    def _parse_cluster(data: dict[str, Any]) -> GKECluster:
        """Convert raw GKE JSON to a ``GKECluster`` model."""
        # node_count is the sum across all node pools
        node_count = 0
        for pool in data.get("nodePools", []):
            node_count += pool.get("initialNodeCount", 0)

        return GKECluster(
            cluster_id=data.get("id", ""),
            name=data.get("name", ""),
            location=data.get("location", ""),
            status=data.get("status", "UNKNOWN"),
            node_count=node_count,
            master_version=data.get("currentMasterVersion", ""),
            node_version=data.get("currentNodeVersion", ""),
            endpoint=data.get("endpoint", ""),
            network=data.get("network", ""),
            subnetwork=data.get("subnetwork", ""),
        )

    @staticmethod
    def _parse_node_pool(data: dict[str, Any], cluster_name: str) -> GKENodePool:
        """Convert raw node-pool JSON to a ``GKENodePool`` model."""
        autoscaling = data.get("autoscaling", {})
        config = data.get("config", {})

        return GKENodePool(
            pool_id=data.get("instanceGroupUrls", [""])[0].rsplit("/", 1)[-1]
            if data.get("instanceGroupUrls")
            else data.get("name", ""),
            name=data.get("name", ""),
            cluster_name=cluster_name,
            machine_type=config.get("machineType", ""),
            node_count=data.get("initialNodeCount", 0),
            min_nodes=autoscaling.get("minNodeCount", 0),
            max_nodes=autoscaling.get("maxNodeCount", 0),
            status=data.get("status", "UNKNOWN"),
            autoscaling_enabled=autoscaling.get("enabled", False),
        )
