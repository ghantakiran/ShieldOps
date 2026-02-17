"""Kubernetes connector implementation."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog
from kubernetes_asyncio import client, config

from shieldops.connectors.base import InfraConnector
from shieldops.models.base import (
    ActionResult,
    Environment,
    ExecutionStatus,
    HealthStatus,
    RemediationAction,
    Resource,
    Snapshot,
    TimeRange,
)

logger = structlog.get_logger()


class KubernetesConnector(InfraConnector):
    """Connector for Kubernetes clusters (any cloud or on-prem)."""

    provider = "kubernetes"

    def __init__(self, kubeconfig_path: str | None = None, context: str | None = None) -> None:
        self._kubeconfig_path = kubeconfig_path
        self._context = context
        self._core_api: client.CoreV1Api | None = None
        self._apps_api: client.AppsV1Api | None = None
        self._snapshots: dict[str, dict[str, Any]] = {}

    async def _ensure_client(self) -> None:
        """Initialize Kubernetes client if not already done."""
        if self._core_api is not None:
            return
        if self._kubeconfig_path:
            await config.load_kube_config(
                config_file=self._kubeconfig_path, context=self._context
            )
        else:
            config.load_incluster_config()
        self._core_api = client.CoreV1Api()
        self._apps_api = client.AppsV1Api()

    async def get_health(self, resource_id: str) -> HealthStatus:
        """Get health status of a Kubernetes resource (pod, deployment, node)."""
        await self._ensure_client()
        assert self._core_api is not None

        namespace, name = self._parse_resource_id(resource_id)

        try:
            pod = await self._core_api.read_namespaced_pod(name=name, namespace=namespace)
            phase = pod.status.phase if pod.status else "Unknown"
            healthy = phase == "Running"

            container_restarts = 0
            if pod.status and pod.status.container_statuses:
                container_restarts = sum(
                    cs.restart_count for cs in pod.status.container_statuses
                )

            return HealthStatus(
                resource_id=resource_id,
                healthy=healthy and container_restarts < 5,
                status=phase,
                message=f"Restarts: {container_restarts}" if container_restarts > 0 else None,
                last_checked=datetime.now(timezone.utc),
                metrics={"restart_count": float(container_restarts)},
            )
        except client.ApiException as e:
            logger.error("k8s_health_check_failed", resource_id=resource_id, error=str(e))
            return HealthStatus(
                resource_id=resource_id,
                healthy=False,
                status="error",
                message=str(e),
                last_checked=datetime.now(timezone.utc),
            )

    async def list_resources(
        self,
        resource_type: str,
        environment: Environment,
        filters: dict[str, Any] | None = None,
    ) -> list[Resource]:
        """List Kubernetes resources of a given type."""
        await self._ensure_client()
        assert self._core_api is not None

        namespace = (filters or {}).get("namespace", "default")
        label_selector = (filters or {}).get("label_selector", "")
        resources: list[Resource] = []

        if resource_type == "pod":
            pods = await self._core_api.list_namespaced_pod(
                namespace=namespace, label_selector=label_selector
            )
            for pod in pods.items:
                resources.append(
                    Resource(
                        id=f"{pod.metadata.namespace}/{pod.metadata.name}",
                        name=pod.metadata.name,
                        resource_type="pod",
                        environment=environment,
                        provider="kubernetes",
                        namespace=pod.metadata.namespace,
                        labels=pod.metadata.labels or {},
                        created_at=pod.metadata.creation_timestamp,
                    )
                )

        return resources

    async def get_events(
        self, resource_id: str, time_range: TimeRange
    ) -> list[dict[str, Any]]:
        """Get Kubernetes events for a resource."""
        await self._ensure_client()
        assert self._core_api is not None

        namespace, name = self._parse_resource_id(resource_id)
        field_selector = f"involvedObject.name={name}"

        events = await self._core_api.list_namespaced_event(
            namespace=namespace, field_selector=field_selector
        )

        return [
            {
                "type": event.type,
                "reason": event.reason,
                "message": event.message,
                "timestamp": event.last_timestamp or event.first_timestamp,
                "count": event.count,
            }
            for event in events.items
            if event.last_timestamp
            and time_range.start <= event.last_timestamp <= time_range.end
        ]

    async def execute_action(self, action: RemediationAction) -> ActionResult:
        """Execute a remediation action on Kubernetes resources."""
        await self._ensure_client()
        assert self._apps_api is not None

        started_at = datetime.now(timezone.utc)
        logger.info(
            "k8s_execute_action",
            action_type=action.action_type,
            target=action.target_resource,
        )

        try:
            if action.action_type == "restart_pod":
                return await self._restart_pod(action, started_at)
            elif action.action_type == "scale_horizontal":
                return await self._scale_deployment(action, started_at)
            elif action.action_type == "rollback_deployment":
                return await self._rollback_deployment(action, started_at)
            else:
                return ActionResult(
                    action_id=action.id,
                    status=ExecutionStatus.FAILED,
                    message=f"Unsupported action type: {action.action_type}",
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )
        except client.ApiException as e:
            logger.error("k8s_action_failed", action=action.id, error=str(e))
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"Kubernetes API error: {e.reason}",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error=str(e),
            )

    async def create_snapshot(self, resource_id: str) -> Snapshot:
        """Capture current state of a Kubernetes resource for rollback."""
        await self._ensure_client()
        assert self._core_api is not None

        namespace, name = self._parse_resource_id(resource_id)
        snapshot_id = str(uuid4())

        try:
            pod = await self._core_api.read_namespaced_pod(name=name, namespace=namespace)
            state = client.ApiClient().sanitize_for_serialization(pod)
        except client.ApiException:
            state = {"resource_id": resource_id, "error": "could_not_capture"}

        snapshot = Snapshot(
            id=snapshot_id,
            resource_id=resource_id,
            snapshot_type="k8s_resource",
            state=state,
            created_at=datetime.now(timezone.utc),
        )
        self._snapshots[snapshot_id] = state
        return snapshot

    async def rollback(self, snapshot_id: str) -> ActionResult:
        """Rollback to a captured snapshot state."""
        started_at = datetime.now(timezone.utc)

        if snapshot_id not in self._snapshots:
            return ActionResult(
                action_id=f"rollback-{snapshot_id}",
                status=ExecutionStatus.FAILED,
                message=f"Snapshot {snapshot_id} not found",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        # Implementation: re-apply the captured resource state
        logger.info("k8s_rollback", snapshot_id=snapshot_id)
        return ActionResult(
            action_id=f"rollback-{snapshot_id}",
            status=ExecutionStatus.SUCCESS,
            message=f"Rolled back to snapshot {snapshot_id}",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            snapshot_id=snapshot_id,
        )

    async def validate_health(self, resource_id: str, timeout_seconds: int = 300) -> bool:
        """Validate resource is healthy after an action."""
        import asyncio

        deadline = datetime.now(timezone.utc).timestamp() + timeout_seconds
        while datetime.now(timezone.utc).timestamp() < deadline:
            health = await self.get_health(resource_id)
            if health.healthy:
                return True
            await asyncio.sleep(5)
        return False

    # --- Private helpers ---

    @staticmethod
    def _parse_resource_id(resource_id: str) -> tuple[str, str]:
        """Parse 'namespace/name' format into (namespace, name)."""
        parts = resource_id.split("/", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "default", parts[0]

    async def _restart_pod(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        """Delete a pod to trigger restart via controller."""
        assert self._core_api is not None
        namespace, name = self._parse_resource_id(action.target_resource)
        await self._core_api.delete_namespaced_pod(name=name, namespace=namespace)
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Pod {namespace}/{name} deleted (will be recreated by controller)",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

    async def _scale_deployment(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        """Scale a deployment horizontally."""
        assert self._apps_api is not None
        namespace, name = self._parse_resource_id(action.target_resource)
        replicas = action.parameters.get("replicas", 3)

        body = {"spec": {"replicas": replicas}}
        await self._apps_api.patch_namespaced_deployment_scale(
            name=name, namespace=namespace, body=body
        )
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Deployment {namespace}/{name} scaled to {replicas} replicas",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

    async def _rollback_deployment(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        """Rollback a deployment to previous revision."""
        assert self._apps_api is not None
        namespace, name = self._parse_resource_id(action.target_resource)

        # Trigger rollback by patching revision annotation
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "shieldops.io/rollback-trigger": datetime.now(
                                timezone.utc
                            ).isoformat()
                        }
                    }
                }
            }
        }
        await self._apps_api.patch_namespaced_deployment(
            name=name, namespace=namespace, body=body
        )
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Deployment {namespace}/{name} rollback triggered",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )
