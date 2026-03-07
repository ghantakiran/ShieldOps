"""Rollback manager for Kubernetes remediation actions.

Captures resource state before changes and restores it on failure or request.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from kubernetes_asyncio import client, config

from shieldops.remediation.models import ResourceSnapshot

logger = structlog.get_logger()


class RollbackManager:
    """Manages state snapshots and rollback operations for K8s resources.

    Takes a pre-action snapshot of the target resource, stores it in memory
    (and optionally persists), and can restore the resource to its previous
    state if the remediation action fails or needs to be undone.
    """

    def __init__(
        self,
        kubeconfig_path: str | None = None,
        context: str | None = None,
    ) -> None:
        self._kubeconfig_path = kubeconfig_path
        self._context = context
        self._core_api: client.CoreV1Api | None = None
        self._apps_api: client.AppsV1Api | None = None
        self._autoscaling_api: client.AutoscalingV1Api | None = None
        self._snapshots: dict[str, ResourceSnapshot] = {}

    async def _ensure_client(self) -> None:
        """Initialize Kubernetes client if not already done."""
        if self._core_api is not None:
            return
        if self._kubeconfig_path:
            await config.load_kube_config(
                config_file=self._kubeconfig_path,
                context=self._context,
            )
        else:
            config.load_incluster_config()
        self._core_api = client.CoreV1Api()
        self._apps_api = client.AppsV1Api()
        self._autoscaling_api = client.AutoscalingV1Api()

    async def create_snapshot(
        self,
        namespace: str,
        resource_type: str,
        resource_name: str,
    ) -> ResourceSnapshot:
        """Capture the current state of a Kubernetes resource.

        Args:
            namespace: Kubernetes namespace.
            resource_type: One of 'deployment', 'configmap', 'hpa', 'node', 'pod'.
            resource_name: Name of the resource.

        Returns:
            ResourceSnapshot containing the serialized resource state.
        """
        await self._ensure_client()

        logger.info(
            "snapshot_creating",
            resource_type=resource_type,
            resource_name=resource_name,
            namespace=namespace,
        )

        state = await self._read_resource_state(namespace, resource_type, resource_name)

        snapshot = ResourceSnapshot(
            resource_type=resource_type,
            resource_name=resource_name,
            namespace=namespace,
            state_json=state,
        )

        self._snapshots[snapshot.id] = snapshot

        logger.info(
            "snapshot_created",
            snapshot_id=snapshot.id,
            resource_type=resource_type,
            resource_name=resource_name,
        )

        return snapshot

    async def rollback_to_snapshot(self, snapshot: ResourceSnapshot) -> dict[str, Any]:
        """Restore a Kubernetes resource to its previously captured state.

        Args:
            snapshot: The ResourceSnapshot to restore.

        Returns:
            Dict with rollback status information.

        Raises:
            ValueError: If the snapshot state is empty or invalid.
        """
        await self._ensure_client()

        if not snapshot.state_json:
            raise ValueError(f"Snapshot {snapshot.id} has no state to restore")

        logger.info(
            "rollback_starting",
            snapshot_id=snapshot.id,
            resource_type=snapshot.resource_type,
            resource_name=snapshot.resource_name,
        )

        result = await self._apply_resource_state(
            namespace=snapshot.namespace,
            resource_type=snapshot.resource_type,
            resource_name=snapshot.resource_name,
            state=snapshot.state_json,
        )

        logger.info(
            "rollback_completed",
            snapshot_id=snapshot.id,
            resource_type=snapshot.resource_type,
            resource_name=snapshot.resource_name,
        )

        return result

    async def verify_health(
        self,
        namespace: str,
        deployment_name: str,
        timeout_seconds: int = 120,
    ) -> bool:
        """Wait for a deployment to reach a healthy state.

        Polls the deployment status until all replicas are available and updated,
        or until the timeout is reached.

        Args:
            namespace: Kubernetes namespace.
            deployment_name: Name of the deployment to check.
            timeout_seconds: Maximum wait time in seconds.

        Returns:
            True if the deployment is healthy within the timeout, False otherwise.
        """
        await self._ensure_client()
        assert self._apps_api is not None

        deadline = datetime.now(UTC).timestamp() + timeout_seconds
        poll_interval = 3.0

        logger.info(
            "health_check_starting",
            deployment=deployment_name,
            namespace=namespace,
            timeout=timeout_seconds,
        )

        while datetime.now(UTC).timestamp() < deadline:
            try:
                deploy = await self._apps_api.read_namespaced_deployment_status(
                    name=deployment_name,
                    namespace=namespace,
                )
                status = deploy.status
                spec_replicas = deploy.spec.replicas or 1

                if status and status.conditions:
                    for cond in status.conditions:
                        if cond.type == "Available" and cond.status == "True":
                            ready = status.ready_replicas or 0
                            updated = status.updated_replicas or 0
                            if ready >= spec_replicas and updated >= spec_replicas:
                                logger.info(
                                    "health_check_passed",
                                    deployment=deployment_name,
                                    ready=ready,
                                    desired=spec_replicas,
                                )
                                return True
            except client.ApiException as exc:
                logger.warning(
                    "health_check_api_error",
                    deployment=deployment_name,
                    error=str(exc),
                )

            await asyncio.sleep(poll_interval)

        logger.warning(
            "health_check_timeout",
            deployment=deployment_name,
            namespace=namespace,
            timeout=timeout_seconds,
        )
        return False

    def get_snapshot(self, snapshot_id: str) -> ResourceSnapshot | None:
        """Retrieve a stored snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _read_resource_state(
        self,
        namespace: str,
        resource_type: str,
        resource_name: str,
    ) -> dict[str, Any]:
        """Read and serialize the current state of a K8s resource."""
        assert self._core_api is not None
        assert self._apps_api is not None
        assert self._autoscaling_api is not None

        api_client = client.ApiClient()

        try:
            if resource_type == "deployment":
                obj = await self._apps_api.read_namespaced_deployment(
                    name=resource_name, namespace=namespace
                )
            elif resource_type == "configmap":
                obj = await self._core_api.read_namespaced_config_map(
                    name=resource_name, namespace=namespace
                )
            elif resource_type == "hpa":
                obj = await self._autoscaling_api.read_namespaced_horizontal_pod_autoscaler(
                    name=resource_name, namespace=namespace
                )
            elif resource_type == "node":
                obj = await self._core_api.read_node(name=resource_name)
            elif resource_type == "pod":
                obj = await self._core_api.read_namespaced_pod(
                    name=resource_name, namespace=namespace
                )
            else:
                logger.warning("snapshot_unsupported_type", resource_type=resource_type)
                return {"error": f"unsupported resource type: {resource_type}"}

            result: dict[str, Any] = api_client.sanitize_for_serialization(obj)
            return result

        except client.ApiException as exc:
            logger.error(
                "snapshot_read_failed",
                resource_type=resource_type,
                resource_name=resource_name,
                error=str(exc),
            )
            return {"error": f"failed to read resource: {exc.reason}"}

    async def _apply_resource_state(
        self,
        namespace: str,
        resource_type: str,
        resource_name: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply a previously captured state back to the cluster."""
        assert self._apps_api is not None
        assert self._core_api is not None
        assert self._autoscaling_api is not None

        try:
            if resource_type == "deployment":
                # Restore spec (replicas, template, strategy) — not metadata/status
                spec_patch = {"spec": state.get("spec", {})}
                await self._apps_api.patch_namespaced_deployment(
                    name=resource_name, namespace=namespace, body=spec_patch
                )
            elif resource_type == "configmap":
                data_patch = {"data": state.get("data", {})}
                await self._core_api.patch_namespaced_config_map(
                    name=resource_name, namespace=namespace, body=data_patch
                )
            elif resource_type == "hpa":
                spec_patch = {"spec": state.get("spec", {})}
                await self._autoscaling_api.patch_namespaced_horizontal_pod_autoscaler(
                    name=resource_name, namespace=namespace, body=spec_patch
                )
            elif resource_type == "node":
                spec_patch = {"spec": state.get("spec", {})}
                await self._core_api.patch_node(name=resource_name, body=spec_patch)
            else:
                return {
                    "status": "failed",
                    "reason": f"rollback not supported for resource type: {resource_type}",
                }

            return {
                "status": "restored",
                "resource_type": resource_type,
                "resource_name": resource_name,
                "namespace": namespace,
                "restored_at": datetime.now(UTC).isoformat(),
            }

        except client.ApiException as exc:
            logger.error(
                "rollback_apply_failed",
                resource_type=resource_type,
                resource_name=resource_name,
                error=str(exc),
            )
            return {
                "status": "failed",
                "reason": f"K8s API error: {exc.reason}",
                "resource_name": resource_name,
            }
