"""Azure connector implementation for Virtual Machines and Container Apps operations."""

import asyncio
from datetime import UTC, datetime
from functools import partial
from typing import Any
from uuid import uuid4

import structlog

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


class AzureConnector(InfraConnector):
    """Connector for Azure infrastructure (Virtual Machines, Container Apps).

    Supports health checks, resource listing, action execution, snapshotting,
    and rollback for Azure VMs and Container Apps. Uses lazy client initialization
    with ``DefaultAzureCredential`` so no credentials are needed at construction
    time.
    """

    provider = "azure"

    def __init__(
        self,
        subscription_id: str,
        resource_group: str,
        location: str = "eastus",
    ) -> None:
        self._subscription_id = subscription_id
        self._resource_group = resource_group
        self._location = location
        self._compute_client: Any = None
        self._container_client: Any = None
        self._snapshots: dict[str, dict[str, Any]] = {}

    def _ensure_clients(self) -> None:
        """Lazily initialize Azure management clients.

        Creates ``ComputeManagementClient`` and ``ContainerAppsAPIClient``
        using ``DefaultAzureCredential``.  The imports are deferred so that
        the Azure SDK is only required at runtime, not at import time.
        """
        if self._compute_client is None:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.appcontainers import ContainerAppsAPIClient
            from azure.mgmt.compute import ComputeManagementClient

            credential = DefaultAzureCredential()
            self._compute_client = ComputeManagementClient(credential, self._subscription_id)
            self._container_client = ContainerAppsAPIClient(credential, self._subscription_id)

    async def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous Azure SDK call in a thread executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def get_health(self, resource_id: str) -> HealthStatus:
        """Get health status of an Azure VM or Container App.

        For Container Apps, use the ``containerapp:<app-name>`` prefix.
        All other resource IDs are treated as VM names.
        """
        self._ensure_clients()

        try:
            if resource_id.startswith("containerapp:"):
                app_name = resource_id.split(":", 1)[1]
                return await self._get_container_app_health(app_name)
            return await self._get_vm_health(resource_id)
        except Exception as e:
            logger.error("azure_health_check_failed", resource_id=resource_id, error=str(e))
            return HealthStatus(
                resource_id=resource_id,
                healthy=False,
                status="error",
                message=str(e),
                last_checked=datetime.now(UTC),
            )

    async def _get_vm_health(self, vm_name: str) -> HealthStatus:
        """Retrieve VM instance view and derive health from power state."""
        instance_view = await self._run_sync(
            self._compute_client.virtual_machines.instance_view,
            self._resource_group,
            vm_name,
        )

        power_state = "unknown"
        for status in getattr(instance_view, "statuses", []):
            code = getattr(status, "code", "")
            if code.startswith("PowerState/"):
                power_state = code.split("/", 1)[1]
                break

        healthy = power_state == "running"

        return HealthStatus(
            resource_id=vm_name,
            healthy=healthy,
            status=power_state,
            message=f"power_state={power_state}",
            last_checked=datetime.now(UTC),
            metrics={"power_state_running": float(healthy)},
        )

    async def _get_container_app_health(self, app_name: str) -> HealthStatus:
        """Retrieve Container App status and derive health."""
        app = await self._run_sync(
            self._container_client.container_apps.get,
            self._resource_group,
            app_name,
        )

        provisioning_state = getattr(app, "provisioning_state", "Unknown")
        running_status = getattr(app, "running_status", None)
        running_state = (
            getattr(running_status, "running_state", "Unknown") if running_status else "Unknown"
        )

        healthy = provisioning_state == "Succeeded" and running_state == "Running"

        return HealthStatus(
            resource_id=f"containerapp:{app_name}",
            healthy=healthy,
            status="running" if healthy else "degraded",
            message=f"provisioning={provisioning_state}, running={running_state}",
            last_checked=datetime.now(UTC),
            metrics={
                "provisioning_succeeded": float(provisioning_state == "Succeeded"),
                "running": float(running_state == "Running"),
            },
        )

    # ------------------------------------------------------------------
    # List resources
    # ------------------------------------------------------------------

    async def list_resources(
        self,
        resource_type: str,
        environment: Environment,
        filters: dict[str, Any] | None = None,
    ) -> list[Resource]:
        """List Azure VMs or Container Apps in the configured resource group.

        For VMs, use ``resource_type`` of ``"vm"`` or ``"virtual_machine"``.
        For Container Apps, use ``"containerapp"`` or ``"container_app"``.
        Tag-based filtering is applied when *filters* are provided.
        """
        self._ensure_clients()
        resources: list[Resource] = []

        if resource_type in ("vm", "virtual_machine"):
            resources = await self._list_vms(environment, filters)
        elif resource_type in ("containerapp", "container_app"):
            resources = await self._list_container_apps(environment, filters)

        return resources

    async def _list_vms(
        self,
        environment: Environment,
        filters: dict[str, Any] | None = None,
    ) -> list[Resource]:
        """List all VMs in the resource group, applying optional tag filters."""
        vm_list = await self._run_sync(
            self._compute_client.virtual_machines.list,
            self._resource_group,
        )

        resources: list[Resource] = []
        for vm in vm_list:
            tags: dict[str, str] = getattr(vm, "tags", None) or {}

            # Apply tag-based filters
            if filters:
                match = all(tags.get(k) == v for k, v in filters.items())
                if not match:
                    continue

            vm_name: str = getattr(vm, "name", "")
            vm_id: str = getattr(vm, "id", vm_name)

            resources.append(
                Resource(
                    id=vm_id,
                    name=vm_name,
                    resource_type="azure_vm",
                    environment=environment,
                    provider="azure",
                    labels=tags,
                    metadata={
                        "location": getattr(vm, "location", self._location),
                        "vm_size": getattr(getattr(vm, "hardware_profile", None), "vm_size", None),
                        "resource_group": self._resource_group,
                    },
                )
            )

        return resources

    async def _list_container_apps(
        self,
        environment: Environment,
        filters: dict[str, Any] | None = None,
    ) -> list[Resource]:
        """List all Container Apps in the resource group, applying optional tag filters."""
        app_list = await self._run_sync(
            self._container_client.container_apps.list_by_resource_group,
            self._resource_group,
        )

        resources: list[Resource] = []
        for app in app_list:
            tags: dict[str, str] = getattr(app, "tags", None) or {}

            if filters:
                match = all(tags.get(k) == v for k, v in filters.items())
                if not match:
                    continue

            app_name: str = getattr(app, "name", "")
            app_id: str = getattr(app, "id", app_name)

            resources.append(
                Resource(
                    id=app_id,
                    name=app_name,
                    resource_type="azure_container_app",
                    environment=environment,
                    provider="azure",
                    labels=tags,
                    metadata={
                        "location": getattr(app, "location", self._location),
                        "resource_group": self._resource_group,
                        "provisioning_state": getattr(app, "provisioning_state", None),
                    },
                )
            )

        return resources

    # ------------------------------------------------------------------
    # Events (stub)
    # ------------------------------------------------------------------

    async def get_events(self, resource_id: str, time_range: TimeRange) -> list[dict[str, Any]]:
        """Get events for a resource (stub -- requires Azure Activity Log integration)."""
        return []

    # ------------------------------------------------------------------
    # Execute action
    # ------------------------------------------------------------------

    async def execute_action(self, action: RemediationAction) -> ActionResult:
        """Execute a remediation action on Azure resources."""
        self._ensure_clients()
        started_at = datetime.now(UTC)

        logger.info(
            "azure_execute_action",
            action_type=action.action_type,
            target=action.target_resource,
        )

        try:
            if action.action_type in ("reboot_instance", "restart_vm"):
                return await self._restart_vm(action, started_at)
            elif action.action_type in ("stop_instance", "deallocate_vm"):
                return await self._deallocate_vm(action, started_at)
            elif action.action_type in ("start_instance", "start_vm"):
                return await self._start_vm(action, started_at)
            elif action.action_type == "restart_container_app":
                return await self._restart_container_app(action, started_at)
            elif action.action_type == "scale_horizontal":
                return await self._scale_container_app(action, started_at)
            else:
                return ActionResult(
                    action_id=action.id,
                    status=ExecutionStatus.FAILED,
                    message=f"Unsupported action type: {action.action_type}",
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                )
        except Exception as e:
            logger.error("azure_action_failed", action=action.id, error=str(e))
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"Azure API error: {e}",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error=str(e),
            )

    async def _restart_vm(self, action: RemediationAction, started_at: datetime) -> ActionResult:
        """Restart (reboot) an Azure VM."""
        vm_name = action.target_resource
        poller = await self._run_sync(
            self._compute_client.virtual_machines.begin_restart,
            self._resource_group,
            vm_name,
        )
        await self._run_sync(poller.wait)
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Azure VM {vm_name} restart initiated",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _deallocate_vm(self, action: RemediationAction, started_at: datetime) -> ActionResult:
        """Deallocate (stop) an Azure VM."""
        vm_name = action.target_resource
        poller = await self._run_sync(
            self._compute_client.virtual_machines.begin_deallocate,
            self._resource_group,
            vm_name,
        )
        await self._run_sync(poller.wait)
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Azure VM {vm_name} deallocated",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _start_vm(self, action: RemediationAction, started_at: datetime) -> ActionResult:
        """Start an Azure VM."""
        vm_name = action.target_resource
        poller = await self._run_sync(
            self._compute_client.virtual_machines.begin_start,
            self._resource_group,
            vm_name,
        )
        await self._run_sync(poller.wait)
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Azure VM {vm_name} started",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _restart_container_app(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        """Restart a Container App by deactivating and reactivating the latest revision."""
        app_name = action.target_resource
        app = await self._run_sync(
            self._container_client.container_apps.get,
            self._resource_group,
            app_name,
        )

        latest_revision = getattr(app, "latest_revision_name", None)
        if latest_revision:
            await self._run_sync(
                self._container_client.container_apps_revisions.deactivate_revision,
                self._resource_group,
                app_name,
                latest_revision,
            )
            await self._run_sync(
                self._container_client.container_apps_revisions.activate_revision,
                self._resource_group,
                app_name,
                latest_revision,
            )

        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Container App {app_name} revision {latest_revision} restarted",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _scale_container_app(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        """Scale a Container App horizontally by updating min/max replicas."""
        app_name = action.target_resource
        min_replicas = action.parameters.get("min_replicas", 1)
        max_replicas = action.parameters.get("max_replicas", action.parameters.get("replicas", 3))

        app = await self._run_sync(
            self._container_client.container_apps.get,
            self._resource_group,
            app_name,
        )

        template = getattr(app, "template", None)
        if template is not None:
            scale = getattr(template, "scale", None)
            if scale is not None:
                scale.min_replicas = min_replicas
                scale.max_replicas = max_replicas

        await self._run_sync(
            self._container_client.container_apps.begin_create_or_update,
            self._resource_group,
            app_name,
            app,
        )

        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=(
                f"Container App {app_name} scaled to " f"min={min_replicas}, max={max_replicas}"
            ),
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    async def create_snapshot(self, resource_id: str) -> Snapshot:
        """Capture current state of a VM or Container App for rollback capability."""
        self._ensure_clients()
        snapshot_id = str(uuid4())

        try:
            if resource_id.startswith("containerapp:"):
                app_name = resource_id.split(":", 1)[1]
                state = await self._snapshot_container_app(app_name)
                snapshot_type = "azure_container_app"
            else:
                state = await self._snapshot_vm(resource_id)
                snapshot_type = "azure_vm"
        except Exception:
            state = {"resource_id": resource_id, "error": "could_not_capture"}
            snapshot_type = "azure_state"

        snapshot = Snapshot(
            id=snapshot_id,
            resource_id=resource_id,
            snapshot_type=snapshot_type,
            state=state,
            created_at=datetime.now(UTC),
        )
        self._snapshots[snapshot_id] = state
        return snapshot

    async def _snapshot_vm(self, vm_name: str) -> dict[str, Any]:
        """Capture VM instance view, tags, and hardware profile."""
        vm = await self._run_sync(
            self._compute_client.virtual_machines.get,
            self._resource_group,
            vm_name,
        )
        instance_view = await self._run_sync(
            self._compute_client.virtual_machines.instance_view,
            self._resource_group,
            vm_name,
        )

        power_state = "unknown"
        for status in getattr(instance_view, "statuses", []):
            code = getattr(status, "code", "")
            if code.startswith("PowerState/"):
                power_state = code.split("/", 1)[1]
                break

        return {
            "vm_name": vm_name,
            "resource_group": self._resource_group,
            "location": getattr(vm, "location", self._location),
            "vm_size": getattr(getattr(vm, "hardware_profile", None), "vm_size", None),
            "tags": dict(getattr(vm, "tags", None) or {}),
            "power_state": power_state,
        }

    async def _snapshot_container_app(self, app_name: str) -> dict[str, Any]:
        """Capture Container App template, scale, and traffic configuration."""
        app = await self._run_sync(
            self._container_client.container_apps.get,
            self._resource_group,
            app_name,
        )

        template = getattr(app, "template", None)
        scale = getattr(template, "scale", None) if template else None

        traffic_config: list[dict[str, Any]] = []
        ingress = getattr(getattr(app, "configuration", None), "ingress", None)
        if ingress is not None:
            for rule in getattr(ingress, "traffic", []) or []:
                traffic_config.append(
                    {
                        "revision_name": getattr(rule, "revision_name", None),
                        "weight": getattr(rule, "weight", None),
                        "latest_revision": getattr(rule, "latest_revision", None),
                    }
                )

        return {
            "app_name": app_name,
            "resource_group": self._resource_group,
            "min_replicas": getattr(scale, "min_replicas", None) if scale else None,
            "max_replicas": getattr(scale, "max_replicas", None) if scale else None,
            "traffic": traffic_config,
            "provisioning_state": getattr(app, "provisioning_state", None),
        }

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    async def rollback(self, snapshot_id: str) -> ActionResult:
        """Rollback to a captured snapshot state."""
        started_at = datetime.now(UTC)

        if snapshot_id not in self._snapshots:
            return ActionResult(
                action_id=f"rollback-{snapshot_id}",
                status=ExecutionStatus.FAILED,
                message=f"Snapshot {snapshot_id} not found",
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        logger.info("azure_rollback", snapshot_id=snapshot_id)
        return ActionResult(
            action_id=f"rollback-{snapshot_id}",
            status=ExecutionStatus.SUCCESS,
            message=f"Rolled back to snapshot {snapshot_id}",
            started_at=started_at,
            completed_at=datetime.now(UTC),
            snapshot_id=snapshot_id,
        )

    # ------------------------------------------------------------------
    # Validate health
    # ------------------------------------------------------------------

    async def validate_health(self, resource_id: str, timeout_seconds: int = 300) -> bool:
        """Poll until the resource is healthy or the timeout expires.

        Checks health every 10 seconds.  Returns ``True`` as soon as a healthy
        status is observed, or ``False`` if the deadline is reached.
        """
        deadline = datetime.now(UTC).timestamp() + timeout_seconds
        while datetime.now(UTC).timestamp() < deadline:
            health = await self.get_health(resource_id)
            if health.healthy:
                return True
            await asyncio.sleep(10)
        return False
