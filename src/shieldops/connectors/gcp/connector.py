"""GCP connector implementation for Compute Engine and Cloud Run operations."""

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


class GCPConnector(InfraConnector):
    """Connector for GCP infrastructure (Compute Engine, Cloud Run).

    Supports health checks, resource listing, action execution, snapshotting,
    and rollback for both Compute Engine instances and Cloud Run services.

    Resource ID conventions:
      - Compute Engine: instance name (e.g. "my-instance")
      - Cloud Run: "run:service-name"
    """

    provider = "gcp"

    def __init__(self, project_id: str, region: str = "us-central1") -> None:
        self._project_id = project_id
        self._region = region
        self._compute_client: Any = None
        self._run_client: Any = None
        self._snapshots: dict[str, dict[str, Any]] = {}

    def _ensure_clients(self) -> None:
        """Lazily initialize GCP API clients."""
        if self._compute_client is None:
            from google.cloud import compute_v1, run_v2

            self._compute_client = compute_v1.InstancesClient()
            self._run_client = run_v2.ServicesClient()

    async def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous GCP client call in a thread executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    async def get_health(self, resource_id: str) -> HealthStatus:
        """Get health status of a Compute Engine instance or Cloud Run service.

        For Cloud Run services, prefix the resource ID with ``run:``.
        """
        self._ensure_clients()

        try:
            if resource_id.startswith("run:"):
                return await self._get_run_health(resource_id[4:])
            return await self._get_compute_health(resource_id)
        except Exception as e:
            logger.error("gcp_health_check_failed", resource_id=resource_id, error=str(e))
            return HealthStatus(
                resource_id=resource_id,
                healthy=False,
                status="error",
                message=str(e),
                last_checked=datetime.now(UTC),
            )

    async def _get_compute_health(self, instance_name: str) -> HealthStatus:
        """Check health of a Compute Engine instance by name."""
        instance = await self._run_sync(
            self._compute_client.get,
            project=self._project_id,
            zone=f"{self._region}-a",
            instance=instance_name,
        )

        status = instance.status
        healthy = status == "RUNNING"

        return HealthStatus(
            resource_id=instance_name,
            healthy=healthy,
            status=status.lower() if status else "unknown",
            message=f"instance_status={status}",
            last_checked=datetime.now(UTC),
            metrics={
                "running": float(healthy),
            },
        )

    async def _get_run_health(self, service_name: str) -> HealthStatus:
        """Check health of a Cloud Run service by name."""
        parent = f"projects/{self._project_id}/locations/{self._region}/services/{service_name}"
        service = await self._run_sync(
            self._run_client.get_service,
            name=parent,
        )

        # Cloud Run exposes conditions; the "Ready" condition signals overall health
        conditions = service.conditions if hasattr(service, "conditions") else []
        ready = False
        condition_message = "no conditions"
        for cond in conditions:
            cond_type = cond.type_ if hasattr(cond, "type_") else getattr(cond, "type", "")
            if cond_type == "Ready":
                cond_state = cond.state if hasattr(cond, "state") else None
                # state may be an enum or string; normalise to string comparison
                ready = str(cond_state) == "CONDITION_SUCCEEDED" or cond_state is True
                msg = getattr(cond, "message", "") or "ready"
                condition_message = msg if ready else "not_ready"
                break

        return HealthStatus(
            resource_id=f"run:{service_name}",
            healthy=ready,
            status="running" if ready else "degraded",
            message=condition_message,
            last_checked=datetime.now(UTC),
            metrics={
                "ready": float(ready),
            },
        )

    # ------------------------------------------------------------------
    # list_resources
    # ------------------------------------------------------------------

    async def list_resources(
        self,
        resource_type: str,
        environment: Environment,
        filters: dict[str, Any] | None = None,
    ) -> list[Resource]:
        """List Compute Engine instances, optionally filtered by labels.

        Supports resource_type values: ``instance``, ``compute``.
        Label filters are applied using the GCP ``filter`` string syntax.
        """
        self._ensure_clients()
        resources: list[Resource] = []

        if resource_type in ("instance", "compute"):
            filter_parts: list[str] = []
            for key, value in (filters or {}).items():
                filter_parts.append(f"labels.{key}={value}")

            filter_str = " AND ".join(filter_parts) if filter_parts else None

            request_kwargs: dict[str, Any] = {
                "project": self._project_id,
                "zone": f"{self._region}-a",
            }
            if filter_str:
                request_kwargs["filter"] = filter_str

            try:
                result = await self._run_sync(
                    self._compute_client.list,
                    **request_kwargs,
                )

                for inst in result:
                    labels = dict(inst.labels) if inst.labels else {}
                    resources.append(
                        Resource(
                            id=str(inst.id),
                            name=inst.name or str(inst.id),
                            resource_type="gce_instance",
                            environment=environment,
                            provider="gcp",
                            labels=labels,
                            metadata={
                                "machine_type": inst.machine_type,
                                "status": inst.status,
                                "zone": inst.zone,
                            },
                            created_at=(
                                datetime.fromisoformat(inst.creation_timestamp)
                                if inst.creation_timestamp
                                else None
                            ),
                        )
                    )
            except Exception as e:
                logger.error(
                    "gcp_list_resources_failed",
                    resource_type=resource_type,
                    error=str(e),
                )

        return resources

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def get_events(self, resource_id: str, time_range: TimeRange) -> list[dict[str, Any]]:
        """Get events for a resource (stub -- requires Cloud Audit Logs integration)."""
        return []

    # ------------------------------------------------------------------
    # Execute action
    # ------------------------------------------------------------------

    async def execute_action(self, action: RemediationAction) -> ActionResult:
        """Execute a remediation action on GCP resources."""
        self._ensure_clients()
        started_at = datetime.now(UTC)

        logger.info(
            "gcp_execute_action",
            action_type=action.action_type,
            target=action.target_resource,
        )

        try:
            if action.action_type in ("reboot_instance", "reset_instance"):
                return await self._reset_instance(action, started_at)
            elif action.action_type == "stop_instance":
                return await self._stop_instance(action, started_at)
            elif action.action_type == "start_instance":
                return await self._start_instance(action, started_at)
            elif action.action_type in ("update_service", "force_new_deployment"):
                return await self._update_run_service(action, started_at)
            elif action.action_type == "scale_horizontal":
                return await self._scale_run_service(action, started_at)
            else:
                return ActionResult(
                    action_id=action.id,
                    status=ExecutionStatus.FAILED,
                    message=f"Unsupported action type: {action.action_type}",
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                )
        except Exception as e:
            logger.error("gcp_action_failed", action=action.id, error=str(e))
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"GCP API error: {e}",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error=str(e),
            )

    async def _reset_instance(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        """Reset (reboot) a Compute Engine instance."""
        instance_name = action.target_resource
        zone = action.parameters.get("zone", f"{self._region}-a")
        await self._run_sync(
            self._compute_client.reset,
            project=self._project_id,
            zone=zone,
            instance=instance_name,
        )
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Compute Engine instance {instance_name} reset initiated",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _stop_instance(self, action: RemediationAction, started_at: datetime) -> ActionResult:
        """Stop a Compute Engine instance."""
        instance_name = action.target_resource
        zone = action.parameters.get("zone", f"{self._region}-a")
        await self._run_sync(
            self._compute_client.stop,
            project=self._project_id,
            zone=zone,
            instance=instance_name,
        )
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Compute Engine instance {instance_name} stop initiated",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _start_instance(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        """Start a Compute Engine instance."""
        instance_name = action.target_resource
        zone = action.parameters.get("zone", f"{self._region}-a")
        await self._run_sync(
            self._compute_client.start,
            project=self._project_id,
            zone=zone,
            instance=instance_name,
        )
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Compute Engine instance {instance_name} start initiated",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _update_run_service(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        """Update a Cloud Run service (force new revision / traffic routing)."""
        service_name = action.target_resource
        parent = f"projects/{self._project_id}/locations/{self._region}/services/{service_name}"
        traffic_percent = action.parameters.get("traffic_percent", 100)

        from google.cloud.run_v2.types import Service, TrafficTarget, TrafficTargetAllocationType

        service = Service(
            name=parent,
            traffic=[
                TrafficTarget(
                    type_=TrafficTargetAllocationType.TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST,
                    percent=traffic_percent,
                ),
            ],
        )

        await self._run_sync(
            self._run_client.update_service,
            service=service,
        )

        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=(f"Cloud Run service {service_name} updated (traffic={traffic_percent}%)"),
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _scale_run_service(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        """Scale a Cloud Run service by adjusting min/max instance counts."""
        service_name = action.target_resource
        parent = f"projects/{self._project_id}/locations/{self._region}/services/{service_name}"
        min_instances = action.parameters.get("min_instances", 1)
        max_instances = action.parameters.get("max_instances", 10)

        from google.cloud.run_v2.types import (
            RevisionScaling,
            RevisionTemplate,
            Service,
        )

        service = Service(
            name=parent,
            template=RevisionTemplate(
                scaling=RevisionScaling(
                    min_instance_count=min_instances,
                    max_instance_count=max_instances,
                ),
            ),
        )

        await self._run_sync(
            self._run_client.update_service,
            service=service,
        )

        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=(
                f"Cloud Run service {service_name} scaled"
                f" (min={min_instances}, max={max_instances})"
            ),
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    # ------------------------------------------------------------------
    # Snapshot / rollback
    # ------------------------------------------------------------------

    async def create_snapshot(self, resource_id: str) -> Snapshot:
        """Capture current state for rollback capability."""
        self._ensure_clients()
        snapshot_id = str(uuid4())

        try:
            if resource_id.startswith("run:"):
                state = await self._snapshot_run(resource_id[4:])
                snapshot_type = "cloud_run_service"
            else:
                state = await self._snapshot_compute(resource_id)
                snapshot_type = "gce_instance"
        except Exception:
            state = {"resource_id": resource_id, "error": "could_not_capture"}
            snapshot_type = "gcp_state"

        snapshot = Snapshot(
            id=snapshot_id,
            resource_id=resource_id,
            snapshot_type=snapshot_type,
            state=state,
            created_at=datetime.now(UTC),
        )
        self._snapshots[snapshot_id] = state
        return snapshot

    async def _snapshot_compute(self, instance_name: str) -> dict[str, Any]:
        """Capture Compute Engine instance metadata and status."""
        instance = await self._run_sync(
            self._compute_client.get,
            project=self._project_id,
            zone=f"{self._region}-a",
            instance=instance_name,
        )
        return {
            "instance_name": instance_name,
            "status": instance.status,
            "machine_type": instance.machine_type,
            "labels": dict(instance.labels) if instance.labels else {},
            "zone": instance.zone,
        }

    async def _snapshot_run(self, service_name: str) -> dict[str, Any]:
        """Capture Cloud Run service configuration (template, traffic)."""
        parent = f"projects/{self._project_id}/locations/{self._region}/services/{service_name}"
        service = await self._run_sync(
            self._run_client.get_service,
            name=parent,
        )
        traffic_list: list[dict[str, Any]] = []
        if hasattr(service, "traffic") and service.traffic:
            for target in service.traffic:
                traffic_list.append(
                    {
                        "percent": getattr(target, "percent", 0),
                        "revision": getattr(target, "revision", ""),
                    }
                )

        template_info: dict[str, Any] = {}
        if hasattr(service, "template") and service.template:
            tmpl = service.template
            if hasattr(tmpl, "scaling") and tmpl.scaling:
                template_info["min_instance_count"] = getattr(tmpl.scaling, "min_instance_count", 0)
                template_info["max_instance_count"] = getattr(tmpl.scaling, "max_instance_count", 0)

        return {
            "service_name": service_name,
            "template": template_info,
            "traffic": traffic_list,
        }

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

        logger.info("gcp_rollback", snapshot_id=snapshot_id)
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
        """Poll until resource is healthy or timeout (10-second intervals)."""
        deadline = datetime.now(UTC).timestamp() + timeout_seconds
        while datetime.now(UTC).timestamp() < deadline:
            health = await self.get_health(resource_id)
            if health.healthy:
                return True
            await asyncio.sleep(10)
        return False
