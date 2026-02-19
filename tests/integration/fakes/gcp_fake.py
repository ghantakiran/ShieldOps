"""Fake GCP connector for integration testing -- maintains in-memory state.

Simulates Compute Engine instances and Cloud Run services without requiring
real GCP API clients or credentials.  All state is held in plain dicts and
mutated synchronously, making tests deterministic and fast.
"""

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


class FakeGCPConnector(InfraConnector):
    """In-process fake for the GCP connector.

    Maintains dictionaries of Compute Engine instances and Cloud Run services
    so that integration tests can exercise the full connector interface
    (health, list, execute, snapshot, rollback) without cloud SDK dependencies.

    Resource ID conventions (matching the real ``GCPConnector``):
      - Compute Engine: bare instance name, e.g. ``"my-instance"``
      - Cloud Run:      ``"run:<service-name>"``
    """

    provider = "gcp"

    def __init__(
        self,
        project_id: str = "test-project",
        region: str = "us-central1",
    ) -> None:
        self._project_id = project_id
        self._region = region

        # Compute Engine instances: name -> state dict
        self._instances: dict[str, dict[str, Any]] = {}

        # Cloud Run services: name -> state dict
        self._services: dict[str, dict[str, Any]] = {}

        # Snapshots: snapshot_id -> deep-copied resource state
        self._snapshots: dict[str, dict[str, Any]] = {}

        # Ordered event log
        self._events: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Seed helpers (not part of InfraConnector interface)
    # ------------------------------------------------------------------

    def add_instance(
        self,
        name: str,
        status: str = "RUNNING",
        machine_type: str = "e2-medium",
        labels: dict[str, str] | None = None,
        zone: str | None = None,
    ) -> None:
        """Seed a Compute Engine instance into the fake state."""
        self._instances[name] = {
            "status": status,
            "machine_type": machine_type,
            "labels": labels or {},
            "zone": zone or f"{self._region}-a",
        }

    def add_service(
        self,
        name: str,
        status: str = "Ready",
        traffic: list[dict[str, Any]] | None = None,
        min_instances: int = 1,
        max_instances: int = 10,
    ) -> None:
        """Seed a Cloud Run service into the fake state."""
        self._services[name] = {
            "status": status,
            "traffic": traffic or [{"percent": 100, "revision": "latest"}],
            "min_instances": min_instances,
            "max_instances": max_instances,
        }

    # ------------------------------------------------------------------
    # InfraConnector interface
    # ------------------------------------------------------------------

    async def get_health(self, resource_id: str) -> HealthStatus:
        now = datetime.now(UTC)

        if resource_id.startswith("run:"):
            svc_name = resource_id[4:]
            svc = self._services.get(svc_name)
            if svc is None:
                return HealthStatus(
                    resource_id=resource_id,
                    healthy=False,
                    status="not_found",
                    message=f"Cloud Run service '{svc_name}' not found",
                    last_checked=now,
                )
            healthy = svc["status"] == "Ready"
            return HealthStatus(
                resource_id=resource_id,
                healthy=healthy,
                status="running" if healthy else "degraded",
                message=f"service_status={svc['status']}",
                last_checked=now,
                metrics={"ready": float(healthy)},
            )

        inst = self._instances.get(resource_id)
        if inst is None:
            return HealthStatus(
                resource_id=resource_id,
                healthy=False,
                status="not_found",
                message=f"Instance '{resource_id}' not found",
                last_checked=now,
            )
        healthy = inst["status"] == "RUNNING"
        return HealthStatus(
            resource_id=resource_id,
            healthy=healthy,
            status=inst["status"].lower(),
            message=f"instance_status={inst['status']}",
            last_checked=now,
            metrics={"running": float(healthy)},
        )

    async def list_resources(
        self,
        resource_type: str,
        environment: Environment,
        filters: dict[str, Any] | None = None,
    ) -> list[Resource]:
        if resource_type not in ("instance", "compute"):
            return []

        resources: list[Resource] = []
        for name, inst in self._instances.items():
            # Apply label-based filters
            if filters:
                match = all(inst["labels"].get(k) == v for k, v in filters.items())
                if not match:
                    continue

            resources.append(
                Resource(
                    id=f"{self._project_id}/{name}",
                    name=name,
                    resource_type="gce_instance",
                    environment=environment,
                    provider="gcp",
                    labels=inst["labels"],
                    metadata={
                        "machine_type": inst["machine_type"],
                        "status": inst["status"],
                        "zone": inst["zone"],
                    },
                )
            )
        return resources

    async def get_events(self, resource_id: str, time_range: TimeRange) -> list[dict[str, Any]]:
        return [
            ev
            for ev in self._events
            if ev["resource_id"] == resource_id
            and time_range.start <= ev["timestamp"] <= time_range.end
        ]

    async def execute_action(self, action: RemediationAction) -> ActionResult:
        started_at = datetime.now(UTC)

        # Record the event regardless of outcome
        self._events.append(
            {
                "timestamp": started_at,
                "resource_id": action.target_resource,
                "action": action.action_type,
            }
        )

        # --- Compute Engine actions ---
        if action.action_type in ("reboot_instance", "reset_instance"):
            inst = self._instances.get(action.target_resource)
            if inst is None:
                return self._failed(action.id, started_at, action.target_resource)
            inst["status"] = "RUNNING"
            return self._success(action.id, started_at, f"Instance {action.target_resource} reset")

        if action.action_type == "stop_instance":
            inst = self._instances.get(action.target_resource)
            if inst is None:
                return self._failed(action.id, started_at, action.target_resource)
            inst["status"] = "TERMINATED"
            return self._success(
                action.id, started_at, f"Instance {action.target_resource} stopped"
            )

        if action.action_type == "start_instance":
            inst = self._instances.get(action.target_resource)
            if inst is None:
                return self._failed(action.id, started_at, action.target_resource)
            inst["status"] = "RUNNING"
            return self._success(
                action.id, started_at, f"Instance {action.target_resource} started"
            )

        # --- Cloud Run actions ---
        if action.action_type in ("update_service", "force_new_deployment"):
            svc_name = action.target_resource
            svc = self._services.get(svc_name)
            if svc is None:
                return self._failed(action.id, started_at, svc_name)
            traffic_percent = action.parameters.get("traffic_percent", 100)
            svc["traffic"] = [{"percent": traffic_percent, "revision": "latest"}]
            return self._success(
                action.id, started_at, f"Service {svc_name} updated (traffic={traffic_percent}%)"
            )

        if action.action_type == "scale_horizontal":
            svc_name = action.target_resource
            svc = self._services.get(svc_name)
            if svc is None:
                return self._failed(action.id, started_at, svc_name)
            svc["min_instances"] = action.parameters.get("min_instances", svc["min_instances"])
            svc["max_instances"] = action.parameters.get("max_instances", svc["max_instances"])
            return self._success(
                action.id,
                started_at,
                f"Service {svc_name} scaled"
                f" (min={svc['min_instances']}, max={svc['max_instances']})",
            )

        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.FAILED,
            message=f"Unsupported action type: {action.action_type}",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def create_snapshot(self, resource_id: str) -> Snapshot:
        snapshot_id = str(uuid4())
        now = datetime.now(UTC)

        if resource_id.startswith("run:"):
            svc_name = resource_id[4:]
            svc = self._services.get(svc_name)
            state = copy.deepcopy(svc) if svc else {"error": "not_found"}
            state["resource_type"] = "cloud_run_service"
            state["resource_name"] = svc_name
        else:
            inst = self._instances.get(resource_id)
            state = copy.deepcopy(inst) if inst else {"error": "not_found"}
            state["resource_type"] = "gce_instance"
            state["resource_name"] = resource_id

        self._snapshots[snapshot_id] = state

        return Snapshot(
            id=snapshot_id,
            resource_id=resource_id,
            snapshot_type=state.get("resource_type", "gcp_state"),
            state=state,
            created_at=now,
        )

    async def rollback(self, snapshot_id: str) -> ActionResult:
        started_at = datetime.now(UTC)

        if snapshot_id not in self._snapshots:
            return ActionResult(
                action_id=f"rollback-{snapshot_id}",
                status=ExecutionStatus.FAILED,
                message=f"Snapshot {snapshot_id} not found",
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        snap = self._snapshots[snapshot_id]
        resource_name = snap["resource_name"]

        meta_keys = ("resource_type", "resource_name")
        if snap["resource_type"] == "cloud_run_service":
            restored = {k: v for k, v in snap.items() if k not in meta_keys}
            self._services[resource_name] = copy.deepcopy(restored)
        elif snap["resource_type"] == "gce_instance":
            restored = {k: v for k, v in snap.items() if k not in meta_keys}
            self._instances[resource_name] = copy.deepcopy(restored)

        return ActionResult(
            action_id=f"rollback-{snapshot_id}",
            status=ExecutionStatus.SUCCESS,
            message=f"Rolled back to snapshot {snapshot_id}",
            started_at=started_at,
            completed_at=datetime.now(UTC),
            snapshot_id=snapshot_id,
        )

    async def validate_health(self, resource_id: str, timeout_seconds: int = 300) -> bool:
        health = await self.get_health(resource_id)
        return health.healthy

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _success(action_id: str, started_at: datetime, message: str) -> ActionResult:
        return ActionResult(
            action_id=action_id,
            status=ExecutionStatus.SUCCESS,
            message=message,
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    @staticmethod
    def _failed(action_id: str, started_at: datetime, resource_id: str) -> ActionResult:
        return ActionResult(
            action_id=action_id,
            status=ExecutionStatus.FAILED,
            message=f"Resource '{resource_id}' not found",
            started_at=started_at,
            completed_at=datetime.now(UTC),
            error=f"Resource '{resource_id}' not found",
        )
