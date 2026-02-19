"""Fake Azure connector for integration testing -- maintains in-memory state."""

import copy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

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


class FakeAzureConnector(InfraConnector):
    """In-memory Azure connector for deterministic integration tests.

    Simulates Azure Virtual Machines and Container Apps without requiring
    real Azure credentials or SDK clients.  All state mutations are stored
    in plain dicts so tests can seed data, execute actions, and assert on
    the resulting state with zero network I/O.
    """

    provider = "azure"

    def __init__(
        self,
        subscription_id: str = "test-sub",
        resource_group: str = "test-rg",
        location: str = "eastus",
    ) -> None:
        self._subscription_id = subscription_id
        self._resource_group = resource_group
        self._location = location

        # Resource state stores
        self._vms: dict[str, dict[str, Any]] = {}
        self._container_apps: dict[str, dict[str, Any]] = {}

        # Snapshot store: snapshot_id -> deep-copied state
        self._snapshots: dict[str, dict[str, Any]] = {}

        # Event log
        self._events: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Seed helpers
    # ------------------------------------------------------------------

    def add_vm(
        self,
        name: str,
        power_state: str = "running",
        size: str = "Standard_B2s",
        tags: dict[str, str] | None = None,
    ) -> None:
        """Seed a Virtual Machine into the fake state."""
        self._vms[name] = {
            "power_state": power_state,
            "size": size,
            "tags": tags or {},
        }

    def add_container_app(
        self,
        name: str,
        status: str = "Running",
        provisioning_state: str = "Succeeded",
        min_replicas: int = 1,
        max_replicas: int = 3,
    ) -> None:
        """Seed a Container App into the fake state."""
        self._container_apps[name] = {
            "status": status,
            "provisioning_state": provisioning_state,
            "min_replicas": min_replicas,
            "max_replicas": max_replicas,
            "revision": "rev-1",
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def get_health(self, resource_id: str) -> HealthStatus:
        """Return health status for a VM or Container App."""
        if resource_id.startswith("containerapp:"):
            app_name = resource_id.split(":", 1)[1]
            app = self._container_apps.get(app_name)
            if app is None:
                return HealthStatus(
                    resource_id=resource_id,
                    healthy=False,
                    status="not_found",
                    message=f"Container App '{app_name}' not found",
                    last_checked=datetime.now(UTC),
                )
            healthy = app["status"] == "Running" and app["provisioning_state"] == "Succeeded"
            return HealthStatus(
                resource_id=resource_id,
                healthy=healthy,
                status="running" if healthy else "degraded",
                message=f"provisioning={app['provisioning_state']}, running={app['status']}",
                last_checked=datetime.now(UTC),
            )

        vm = self._vms.get(resource_id)
        if vm is None:
            return HealthStatus(
                resource_id=resource_id,
                healthy=False,
                status="not_found",
                message=f"VM '{resource_id}' not found",
                last_checked=datetime.now(UTC),
            )
        healthy = vm["power_state"] == "running"
        return HealthStatus(
            resource_id=resource_id,
            healthy=healthy,
            status=vm["power_state"],
            message=f"power_state={vm['power_state']}",
            last_checked=datetime.now(UTC),
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
        """List VMs or Container Apps, with optional tag-based filtering."""
        resources: list[Resource] = []

        if resource_type in ("vm", "virtual_machine"):
            for name, vm in self._vms.items():
                if filters and not all(vm["tags"].get(k) == v for k, v in filters.items()):
                    continue
                resources.append(
                    Resource(
                        id=name,
                        name=name,
                        resource_type="azure_vm",
                        environment=environment,
                        provider="azure",
                        labels=vm["tags"],
                        metadata={
                            "location": self._location,
                            "vm_size": vm["size"],
                            "resource_group": self._resource_group,
                        },
                    )
                )
        elif resource_type in ("containerapp", "container_app"):
            for name, app in self._container_apps.items():
                # Container Apps don't have tags in our fake, but support
                # filtering by metadata fields if needed.
                resources.append(
                    Resource(
                        id=name,
                        name=name,
                        resource_type="azure_container_app",
                        environment=environment,
                        provider="azure",
                        metadata={
                            "location": self._location,
                            "resource_group": self._resource_group,
                            "provisioning_state": app["provisioning_state"],
                        },
                    )
                )

        return resources

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def get_events(self, resource_id: str, time_range: TimeRange) -> list[dict[str, Any]]:
        """Return events filtered by resource_id."""
        return [e for e in self._events if e["resource_id"] == resource_id]

    # ------------------------------------------------------------------
    # Execute action
    # ------------------------------------------------------------------

    async def execute_action(self, action: RemediationAction) -> ActionResult:
        """Execute a remediation action, mutating in-memory state."""
        started_at = datetime.now(UTC)

        # Record event regardless of outcome
        self._events.append(
            {
                "resource_id": action.target_resource,
                "action_type": action.action_type,
                "timestamp": started_at.isoformat(),
                "parameters": action.parameters,
            }
        )

        # --- VM actions ---
        if action.action_type in ("reboot_instance", "restart_vm"):
            vm = self._vms.get(action.target_resource)
            if vm is None:
                return self._failed_result(action.id, "VM not found", started_at)
            vm["power_state"] = "running"
            return self._success_result(
                action.id, f"VM {action.target_resource} restarted", started_at
            )

        if action.action_type in ("stop_instance", "deallocate_vm"):
            vm = self._vms.get(action.target_resource)
            if vm is None:
                return self._failed_result(action.id, "VM not found", started_at)
            vm["power_state"] = "deallocated"
            return self._success_result(
                action.id, f"VM {action.target_resource} deallocated", started_at
            )

        if action.action_type in ("start_instance", "start_vm"):
            vm = self._vms.get(action.target_resource)
            if vm is None:
                return self._failed_result(action.id, "VM not found", started_at)
            vm["power_state"] = "running"
            return self._success_result(
                action.id, f"VM {action.target_resource} started", started_at
            )

        # --- Container App actions ---
        if action.action_type == "restart_container_app":
            app_name = action.target_resource
            app = self._container_apps.get(app_name)
            if app is None:
                return self._failed_result(action.id, "Container App not found", started_at)
            # No-op state change; app stays Running
            return self._success_result(
                action.id, f"Container App {app_name} restarted", started_at
            )

        if action.action_type == "scale_horizontal":
            app_name = action.target_resource
            app = self._container_apps.get(app_name)
            if app is None:
                return self._failed_result(action.id, "Container App not found", started_at)
            app["min_replicas"] = action.parameters.get("min_replicas", app["min_replicas"])
            app["max_replicas"] = action.parameters.get("max_replicas", app["max_replicas"])
            return self._success_result(
                action.id,
                f"Container App {app_name} scaled to "
                f"min={app['min_replicas']}, max={app['max_replicas']}",
                started_at,
            )

        return self._failed_result(
            action.id, f"Unsupported action type: {action.action_type}", started_at
        )

    # ------------------------------------------------------------------
    # Snapshot / rollback
    # ------------------------------------------------------------------

    async def create_snapshot(self, resource_id: str) -> Snapshot:
        """Deep-copy current resource state and store for rollback."""
        snapshot_id = str(uuid4())

        if resource_id.startswith("containerapp:"):
            app_name = resource_id.split(":", 1)[1]
            app = self._container_apps.get(app_name)
            state = copy.deepcopy(app) if app else {"error": "not_found"}
            snapshot_type = "azure_container_app"
        else:
            vm = self._vms.get(resource_id)
            state = copy.deepcopy(vm) if vm else {"error": "not_found"}
            snapshot_type = "azure_vm"

        snapshot = Snapshot(
            id=snapshot_id,
            resource_id=resource_id,
            snapshot_type=snapshot_type,
            state=state,
            created_at=datetime.now(UTC),
        )
        self._snapshots[snapshot_id] = {
            "resource_id": resource_id,
            "state": state,
        }
        return snapshot

    async def rollback(self, snapshot_id: str) -> ActionResult:
        """Restore resource state from a previously captured snapshot."""
        started_at = datetime.now(UTC)

        if snapshot_id not in self._snapshots:
            return self._failed_result(
                f"rollback-{snapshot_id}", f"Snapshot {snapshot_id} not found", started_at
            )

        snap = self._snapshots[snapshot_id]
        resource_id: str = snap["resource_id"]
        state = copy.deepcopy(snap["state"])

        if resource_id.startswith("containerapp:"):
            app_name = resource_id.split(":", 1)[1]
            self._container_apps[app_name] = state
        else:
            self._vms[resource_id] = state

        return ActionResult(
            action_id=f"rollback-{snapshot_id}",
            status=ExecutionStatus.SUCCESS,
            message=f"Rolled back {resource_id} to snapshot {snapshot_id}",
            started_at=started_at,
            completed_at=datetime.now(UTC),
            snapshot_id=snapshot_id,
        )

    # ------------------------------------------------------------------
    # Validate health
    # ------------------------------------------------------------------

    async def validate_health(self, resource_id: str, timeout_seconds: int = 300) -> bool:
        """Check current health (no polling needed for fake)."""
        health = await self.get_health(resource_id)
        return health.healthy

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _success_result(action_id: str, message: str, started_at: datetime) -> ActionResult:
        return ActionResult(
            action_id=action_id,
            status=ExecutionStatus.SUCCESS,
            message=message,
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    @staticmethod
    def _failed_result(action_id: str, message: str, started_at: datetime) -> ActionResult:
        return ActionResult(
            action_id=action_id,
            status=ExecutionStatus.FAILED,
            message=message,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            error=message,
        )
