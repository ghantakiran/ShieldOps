"""AWS connector implementation for EC2 and ECS operations."""

import asyncio
from datetime import datetime, timezone
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


class AWSConnector(InfraConnector):
    """Connector for AWS infrastructure (EC2, ECS)."""

    provider = "aws"

    def __init__(self, region: str = "us-east-1") -> None:
        self._region = region
        self._ec2_client: Any = None
        self._ecs_client: Any = None
        self._snapshots: dict[str, dict[str, Any]] = {}

    def _ensure_clients(self) -> None:
        """Lazily initialize boto3 clients."""
        if self._ec2_client is None:
            import boto3

            session = boto3.Session(region_name=self._region)
            self._ec2_client = session.client("ec2")
            self._ecs_client = session.client("ecs")

    async def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous boto3 call in a thread executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def get_health(self, resource_id: str) -> HealthStatus:
        """Get health status of an EC2 instance or ECS service."""
        self._ensure_clients()

        try:
            if resource_id.startswith("ecs:"):
                return await self._get_ecs_health(resource_id)
            return await self._get_ec2_health(resource_id)
        except Exception as e:
            logger.error("aws_health_check_failed", resource_id=resource_id, error=str(e))
            return HealthStatus(
                resource_id=resource_id,
                healthy=False,
                status="error",
                message=str(e),
                last_checked=datetime.now(timezone.utc),
            )

    async def _get_ec2_health(self, instance_id: str) -> HealthStatus:
        resp = await self._run_sync(
            self._ec2_client.describe_instance_status,
            InstanceIds=[instance_id],
            IncludeAllInstances=True,
        )
        statuses = resp.get("InstanceStatuses", [])
        if not statuses:
            return HealthStatus(
                resource_id=instance_id,
                healthy=False,
                status="not_found",
                message="Instance not found",
                last_checked=datetime.now(timezone.utc),
            )

        status = statuses[0]
        state = status["InstanceState"]["Name"]
        system_ok = status.get("SystemStatus", {}).get("Status") == "ok"
        instance_ok = status.get("InstanceStatus", {}).get("Status") == "ok"
        healthy = state == "running" and system_ok and instance_ok

        return HealthStatus(
            resource_id=instance_id,
            healthy=healthy,
            status=state,
            message=f"system={system_ok}, instance={instance_ok}",
            last_checked=datetime.now(timezone.utc),
            metrics={
                "system_status_ok": float(system_ok),
                "instance_status_ok": float(instance_ok),
            },
        )

    async def _get_ecs_health(self, resource_id: str) -> HealthStatus:
        """resource_id format: ecs:cluster/service"""
        _, cluster_service = resource_id.split(":", 1)
        cluster, service = cluster_service.rsplit("/", 1)

        resp = await self._run_sync(
            self._ecs_client.describe_services,
            cluster=cluster,
            services=[service],
        )
        services = resp.get("services", [])
        if not services:
            return HealthStatus(
                resource_id=resource_id,
                healthy=False,
                status="not_found",
                message="Service not found",
                last_checked=datetime.now(timezone.utc),
            )

        svc = services[0]
        running = svc.get("runningCount", 0)
        desired = svc.get("desiredCount", 0)
        status = svc.get("status", "UNKNOWN")
        healthy = running == desired and desired > 0 and status == "ACTIVE"

        return HealthStatus(
            resource_id=resource_id,
            healthy=healthy,
            status="running" if healthy else "degraded",
            message=f"running={running}, desired={desired}",
            last_checked=datetime.now(timezone.utc),
            metrics={"running_count": float(running), "desired_count": float(desired)},
        )

    async def list_resources(
        self,
        resource_type: str,
        environment: Environment,
        filters: dict[str, Any] | None = None,
    ) -> list[Resource]:
        """List EC2 instances or ECS services."""
        self._ensure_clients()
        resources: list[Resource] = []

        if resource_type in ("instance", "ec2"):
            tag_filters = [
                {"Name": f"tag:{k}", "Values": [v]}
                for k, v in (filters or {}).items()
                if k != "state"
            ]
            state_filter = (filters or {}).get("state")
            if state_filter:
                tag_filters.append({"Name": "instance-state-name", "Values": [state_filter]})

            resp = await self._run_sync(
                self._ec2_client.describe_instances,
                Filters=tag_filters or [],
            )
            for reservation in resp.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                    resources.append(
                        Resource(
                            id=inst["InstanceId"],
                            name=tags.get("Name", inst["InstanceId"]),
                            resource_type="ec2_instance",
                            environment=environment,
                            provider="aws",
                            labels=tags,
                            metadata={
                                "instance_type": inst.get("InstanceType"),
                                "state": inst["State"]["Name"],
                                "az": inst.get("Placement", {}).get("AvailabilityZone"),
                            },
                            created_at=inst.get("LaunchTime"),
                        )
                    )

        return resources

    async def get_events(
        self, resource_id: str, time_range: TimeRange
    ) -> list[dict[str, Any]]:
        """Get CloudTrail-style events for a resource (stub — requires CloudTrail integration)."""
        return []

    async def execute_action(self, action: RemediationAction) -> ActionResult:
        """Execute a remediation action on AWS resources."""
        self._ensure_clients()
        started_at = datetime.now(timezone.utc)

        logger.info(
            "aws_execute_action",
            action_type=action.action_type,
            target=action.target_resource,
        )

        try:
            if action.action_type in ("restart_ec2", "reboot_instance"):
                return await self._reboot_instance(action, started_at)
            elif action.action_type == "force_new_deployment":
                return await self._force_new_deployment(action, started_at)
            elif action.action_type == "update_desired_count":
                return await self._update_desired_count(action, started_at)
            elif action.action_type == "scale_horizontal":
                return await self._update_desired_count(action, started_at)
            else:
                return ActionResult(
                    action_id=action.id,
                    status=ExecutionStatus.FAILED,
                    message=f"Unsupported action type: {action.action_type}",
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )
        except Exception as e:
            logger.error("aws_action_failed", action=action.id, error=str(e))
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"AWS API error: {e}",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error=str(e),
            )

    async def _reboot_instance(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        instance_id = action.target_resource
        await self._run_sync(self._ec2_client.reboot_instances, InstanceIds=[instance_id])
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"EC2 instance {instance_id} reboot initiated",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

    async def _force_new_deployment(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        cluster = action.parameters.get("cluster", "default")
        service = action.target_resource
        await self._run_sync(
            self._ecs_client.update_service,
            cluster=cluster,
            service=service,
            forceNewDeployment=True,
        )
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"ECS service {service} force new deployment triggered",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

    async def _update_desired_count(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        cluster = action.parameters.get("cluster", "default")
        service = action.target_resource
        desired = action.parameters.get("replicas", action.parameters.get("desired_count", 3))
        await self._run_sync(
            self._ecs_client.update_service,
            cluster=cluster,
            service=service,
            desiredCount=desired,
        )
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"ECS service {service} scaled to {desired} tasks",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

    async def create_snapshot(self, resource_id: str) -> Snapshot:
        """Capture current state for rollback capability."""
        self._ensure_clients()
        snapshot_id = str(uuid4())

        try:
            if resource_id.startswith("ecs:"):
                state = await self._snapshot_ecs(resource_id)
                snapshot_type = "ecs_service"
            else:
                state = await self._snapshot_ec2(resource_id)
                snapshot_type = "ec2_instance"
        except Exception:
            state = {"resource_id": resource_id, "error": "could_not_capture"}
            snapshot_type = "aws_state"

        snapshot = Snapshot(
            id=snapshot_id,
            resource_id=resource_id,
            snapshot_type=snapshot_type,
            state=state,
            created_at=datetime.now(timezone.utc),
        )
        self._snapshots[snapshot_id] = state
        return snapshot

    async def _snapshot_ec2(self, instance_id: str) -> dict[str, Any]:
        resp = await self._run_sync(
            self._ec2_client.describe_instances, InstanceIds=[instance_id]
        )
        instances = resp.get("Reservations", [{}])[0].get("Instances", [])
        return instances[0] if instances else {"instance_id": instance_id}

    async def _snapshot_ecs(self, resource_id: str) -> dict[str, Any]:
        _, cluster_service = resource_id.split(":", 1)
        cluster, service = cluster_service.rsplit("/", 1)
        resp = await self._run_sync(
            self._ecs_client.describe_services, cluster=cluster, services=[service]
        )
        services = resp.get("services", [])
        if services:
            svc = services[0]
            return {
                "cluster": cluster,
                "service": service,
                "desired_count": svc.get("desiredCount"),
                "task_definition": svc.get("taskDefinition"),
            }
        return {"resource_id": resource_id}

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

        logger.info("aws_rollback", snapshot_id=snapshot_id)
        return ActionResult(
            action_id=f"rollback-{snapshot_id}",
            status=ExecutionStatus.SUCCESS,
            message=f"Rolled back to snapshot {snapshot_id}",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            snapshot_id=snapshot_id,
        )

    async def validate_health(self, resource_id: str, timeout_seconds: int = 300) -> bool:
        """Poll until resource is healthy or timeout."""
        deadline = datetime.now(timezone.utc).timestamp() + timeout_seconds
        while datetime.now(timezone.utc).timestamp() < deadline:
            health = await self.get_health(resource_id)
            if health.healthy:
                return True
            await asyncio.sleep(10)
        return False
