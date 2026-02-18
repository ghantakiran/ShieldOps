"""Comprehensive tests for the AWS infrastructure connector.

Tests cover:
- EC2 health checks (healthy, unhealthy system/instance status, stopped, not found, API error)
- ECS health checks (healthy, degraded, zero desired, not found, API error)
- list_resources for EC2 instances (with tags, with state filter, empty, unsupported type)
- execute_action: restart_ec2, reboot_instance, force_new_deployment,
  update_desired_count, scale_horizontal, unsupported action, API error
- create_snapshot for EC2 and ECS (success + error fallback)
- rollback (found + not found)
- validate_health polling (immediate success, timeout, polls-until-healthy)
- get_events (stub returns empty)
- Connector initialization and import re-exports
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.connectors.aws.connector import AWSConnector
from shieldops.models.base import (
    Environment,
    ExecutionStatus,
    RemediationAction,
    RiskLevel,
    TimeRange,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def connector() -> AWSConnector:
    """Create an AWSConnector with mocked boto3 clients.

    Replaces _ensure_clients to avoid the lazy boto3 import, and injects
    MagicMock clients that individual tests configure via return_value /
    side_effect.
    """
    conn = AWSConnector(region="us-east-1")
    conn._ec2_client = MagicMock()
    conn._ecs_client = MagicMock()
    # Prevent _ensure_clients from replacing our mocks
    conn._ensure_clients = MagicMock()  # type: ignore[method-assign]
    return conn


def _make_action(
    action_type: str,
    target: str = "i-abc123",
    parameters: dict[str, Any] | None = None,
) -> RemediationAction:
    return RemediationAction(
        id="action-001",
        action_type=action_type,
        target_resource=target,
        environment=Environment.STAGING,
        risk_level=RiskLevel.MEDIUM,
        parameters=parameters or {},
        description=f"Test {action_type}",
    )


@pytest.fixture
def time_range() -> TimeRange:
    now = datetime.now(timezone.utc)
    return TimeRange(start=now - timedelta(hours=1), end=now)


# ============================================================================
# EC2 Health Checks
# ============================================================================


class TestEC2GetHealth:
    @pytest.mark.asyncio
    async def test_healthy_running_instance(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "running"},
                    "SystemStatus": {"Status": "ok"},
                    "InstanceStatus": {"Status": "ok"},
                }
            ]
        }

        health = await connector.get_health("i-abc123")

        assert health.healthy is True
        assert health.status == "running"
        assert health.resource_id == "i-abc123"
        assert health.metrics["system_status_ok"] == 1.0
        assert health.metrics["instance_status_ok"] == 1.0
        connector._ec2_client.describe_instance_status.assert_called_once_with(
            InstanceIds=["i-abc123"],
            IncludeAllInstances=True,
        )

    @pytest.mark.asyncio
    async def test_unhealthy_system_status_impaired(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "running"},
                    "SystemStatus": {"Status": "impaired"},
                    "InstanceStatus": {"Status": "ok"},
                }
            ]
        }

        health = await connector.get_health("i-abc123")

        assert health.healthy is False
        assert health.status == "running"
        assert health.metrics["system_status_ok"] == 0.0
        assert health.metrics["instance_status_ok"] == 1.0

    @pytest.mark.asyncio
    async def test_unhealthy_instance_status_impaired(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "running"},
                    "SystemStatus": {"Status": "ok"},
                    "InstanceStatus": {"Status": "impaired"},
                }
            ]
        }

        health = await connector.get_health("i-abc123")

        assert health.healthy is False
        assert health.metrics["instance_status_ok"] == 0.0

    @pytest.mark.asyncio
    async def test_unhealthy_stopped_instance(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "stopped"},
                    "SystemStatus": {"Status": "not-applicable"},
                    "InstanceStatus": {"Status": "not-applicable"},
                }
            ]
        }

        health = await connector.get_health("i-abc123")

        assert health.healthy is False
        assert health.status == "stopped"

    @pytest.mark.asyncio
    async def test_instance_not_found(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instance_status.return_value = {
            "InstanceStatuses": []
        }

        health = await connector.get_health("i-nonexistent")

        assert health.healthy is False
        assert health.status == "not_found"
        assert health.message is not None
        assert "not found" in health.message.lower() or "Instance" in health.message

    @pytest.mark.asyncio
    async def test_ec2_api_error(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instance_status.side_effect = Exception(
            "AccessDenied"
        )

        health = await connector.get_health("i-abc123")

        assert health.healthy is False
        assert health.status == "error"
        assert "AccessDenied" in (health.message or "")

    @pytest.mark.asyncio
    async def test_health_has_last_checked(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "running"},
                    "SystemStatus": {"Status": "ok"},
                    "InstanceStatus": {"Status": "ok"},
                }
            ]
        }

        health = await connector.get_health("i-abc123")

        assert health.last_checked is not None
        # Should be recent (within 5 seconds)
        delta = datetime.now(timezone.utc) - health.last_checked
        assert delta.total_seconds() < 5


# ============================================================================
# ECS Health Checks
# ============================================================================


class TestECSGetHealth:
    @pytest.mark.asyncio
    async def test_ecs_healthy_service(self, connector: AWSConnector) -> None:
        connector._ecs_client.describe_services.return_value = {
            "services": [
                {"runningCount": 3, "desiredCount": 3, "status": "ACTIVE"},
            ]
        }

        health = await connector.get_health("ecs:production/api-service")

        assert health.healthy is True
        assert health.metrics["running_count"] == 3.0
        assert health.metrics["desired_count"] == 3.0

    @pytest.mark.asyncio
    async def test_ecs_degraded_service(self, connector: AWSConnector) -> None:
        connector._ecs_client.describe_services.return_value = {
            "services": [
                {"runningCount": 1, "desiredCount": 3, "status": "ACTIVE"},
            ]
        }

        health = await connector.get_health("ecs:production/api-service")

        assert health.healthy is False
        assert "running=1" in (health.message or "")
        assert "desired=3" in (health.message or "")

    @pytest.mark.asyncio
    async def test_ecs_zero_desired_count(self, connector: AWSConnector) -> None:
        connector._ecs_client.describe_services.return_value = {
            "services": [
                {"runningCount": 0, "desiredCount": 0, "status": "ACTIVE"},
            ]
        }

        health = await connector.get_health("ecs:production/idle-service")

        assert health.healthy is False

    @pytest.mark.asyncio
    async def test_ecs_service_not_found(self, connector: AWSConnector) -> None:
        connector._ecs_client.describe_services.return_value = {"services": []}

        health = await connector.get_health("ecs:production/missing-svc")

        assert health.healthy is False
        assert health.status == "not_found"

    @pytest.mark.asyncio
    async def test_ecs_api_error(self, connector: AWSConnector) -> None:
        connector._ecs_client.describe_services.side_effect = Exception("ClusterNotFound")

        health = await connector.get_health("ecs:production/api-service")

        assert health.healthy is False
        assert health.status == "error"

    @pytest.mark.asyncio
    async def test_ecs_parses_cluster_and_service(self, connector: AWSConnector) -> None:
        """Verifies the ecs:cluster/service format is correctly split."""
        connector._ecs_client.describe_services.return_value = {
            "services": [{"runningCount": 2, "desiredCount": 2, "status": "ACTIVE"}]
        }

        await connector.get_health("ecs:my-cluster/my-service")

        connector._ecs_client.describe_services.assert_called_once_with(
            cluster="my-cluster",
            services=["my-service"],
        )


# ============================================================================
# list_resources
# ============================================================================


class TestListResources:
    @pytest.mark.asyncio
    async def test_list_ec2_instances(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-abc123",
                            "InstanceType": "t3.medium",
                            "State": {"Name": "running"},
                            "Tags": [
                                {"Key": "Name", "Value": "web-01"},
                                {"Key": "Environment", "Value": "staging"},
                            ],
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "LaunchTime": datetime(2025, 1, 1, tzinfo=timezone.utc),
                        }
                    ]
                }
            ]
        }

        resources = await connector.list_resources("ec2", Environment.STAGING)

        assert len(resources) == 1
        assert resources[0].id == "i-abc123"
        assert resources[0].name == "web-01"
        assert resources[0].provider == "aws"
        assert resources[0].labels["Name"] == "web-01"
        assert resources[0].metadata["instance_type"] == "t3.medium"

    @pytest.mark.asyncio
    async def test_list_instance_resource_type(self, connector: AWSConnector) -> None:
        """list_resources also accepts resource_type='instance'."""
        connector._ec2_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-xyz",
                            "InstanceType": "m5.large",
                            "State": {"Name": "running"},
                            "Tags": [],
                            "Placement": {},
                        }
                    ]
                }
            ]
        }

        resources = await connector.list_resources("instance", Environment.DEVELOPMENT)

        assert len(resources) == 1
        assert resources[0].id == "i-xyz"

    @pytest.mark.asyncio
    async def test_list_empty_reservations(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instances.return_value = {"Reservations": []}

        resources = await connector.list_resources("ec2", Environment.PRODUCTION)

        assert resources == []

    @pytest.mark.asyncio
    async def test_list_unsupported_type_returns_empty(self, connector: AWSConnector) -> None:
        resources = await connector.list_resources("lambda", Environment.PRODUCTION)

        assert resources == []

    @pytest.mark.asyncio
    async def test_list_with_state_filter(self, connector: AWSConnector) -> None:
        """When filters contain 'state', it maps to instance-state-name."""
        connector._ec2_client.describe_instances.return_value = {"Reservations": []}

        await connector.list_resources(
            "ec2", Environment.STAGING, filters={"state": "running"}
        )

        call_kwargs = connector._ec2_client.describe_instances.call_args
        filters_arg = call_kwargs.kwargs.get("Filters", call_kwargs[1].get("Filters", []))
        filter_names = [f["Name"] for f in filters_arg]
        assert "instance-state-name" in filter_names

    @pytest.mark.asyncio
    async def test_list_with_tag_filter(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instances.return_value = {"Reservations": []}

        await connector.list_resources(
            "ec2", Environment.STAGING, filters={"team": "platform"}
        )

        call_kwargs = connector._ec2_client.describe_instances.call_args
        filters_arg = call_kwargs.kwargs.get("Filters", call_kwargs[1].get("Filters", []))
        tag_filters = [f for f in filters_arg if f["Name"] == "tag:team"]
        assert len(tag_filters) == 1
        assert tag_filters[0]["Values"] == ["platform"]

    @pytest.mark.asyncio
    async def test_list_instances_without_name_tag(self, connector: AWSConnector) -> None:
        """When instance has no Name tag, falls back to InstanceId."""
        connector._ec2_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-noname",
                            "InstanceType": "t3.micro",
                            "State": {"Name": "running"},
                            "Tags": [],
                            "Placement": {},
                        }
                    ]
                }
            ]
        }

        resources = await connector.list_resources("ec2", Environment.DEVELOPMENT)

        assert resources[0].name == "i-noname"

    @pytest.mark.asyncio
    async def test_list_multiple_reservations(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-001",
                            "State": {"Name": "running"},
                            "Tags": [],
                            "Placement": {},
                        }
                    ]
                },
                {
                    "Instances": [
                        {
                            "InstanceId": "i-002",
                            "State": {"Name": "running"},
                            "Tags": [],
                            "Placement": {},
                        }
                    ]
                },
            ]
        }

        resources = await connector.list_resources("ec2", Environment.PRODUCTION)

        assert len(resources) == 2
        ids = {r.id for r in resources}
        assert ids == {"i-001", "i-002"}


# ============================================================================
# execute_action
# ============================================================================


class TestExecuteAction:
    @pytest.mark.asyncio
    async def test_reboot_instance(self, connector: AWSConnector) -> None:
        connector._ec2_client.reboot_instances.return_value = {}
        action = _make_action("reboot_instance", target="i-abc123")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert "reboot" in result.message.lower()
        connector._ec2_client.reboot_instances.assert_called_once_with(
            InstanceIds=["i-abc123"]
        )

    @pytest.mark.asyncio
    async def test_restart_ec2(self, connector: AWSConnector) -> None:
        connector._ec2_client.reboot_instances.return_value = {}
        action = _make_action("restart_ec2", target="i-abc123")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        connector._ec2_client.reboot_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_new_deployment(self, connector: AWSConnector) -> None:
        connector._ecs_client.update_service.return_value = {}
        action = _make_action(
            "force_new_deployment",
            target="api-service",
            parameters={"cluster": "production"},
        )

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert "force new deployment" in result.message.lower()
        connector._ecs_client.update_service.assert_called_once_with(
            cluster="production",
            service="api-service",
            forceNewDeployment=True,
        )

    @pytest.mark.asyncio
    async def test_update_desired_count(self, connector: AWSConnector) -> None:
        connector._ecs_client.update_service.return_value = {}
        action = _make_action(
            "update_desired_count",
            target="api-service",
            parameters={"cluster": "production", "desired_count": 5},
        )

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        connector._ecs_client.update_service.assert_called_once_with(
            cluster="production",
            service="api-service",
            desiredCount=5,
        )

    @pytest.mark.asyncio
    async def test_scale_horizontal(self, connector: AWSConnector) -> None:
        connector._ecs_client.update_service.return_value = {}
        action = _make_action(
            "scale_horizontal",
            target="worker-service",
            parameters={"cluster": "staging", "replicas": 8},
        )

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_unsupported_action_type(self, connector: AWSConnector) -> None:
        action = _make_action("delete_instance", target="i-abc123")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.FAILED
        assert "Unsupported action type" in result.message
        assert "delete_instance" in result.message

    @pytest.mark.asyncio
    async def test_action_api_error(self, connector: AWSConnector) -> None:
        connector._ec2_client.reboot_instances.side_effect = Exception("UnauthorizedAccess")
        action = _make_action("reboot_instance", target="i-abc123")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.FAILED
        assert result.error is not None
        assert "UnauthorizedAccess" in result.error

    @pytest.mark.asyncio
    async def test_action_has_timestamps(self, connector: AWSConnector) -> None:
        connector._ec2_client.reboot_instances.return_value = {}
        action = _make_action("reboot_instance")

        result = await connector.execute_action(action)

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at

    @pytest.mark.asyncio
    async def test_force_new_deployment_defaults_cluster(self, connector: AWSConnector) -> None:
        """When no cluster param is provided, defaults to 'default'."""
        connector._ecs_client.update_service.return_value = {}
        action = _make_action("force_new_deployment", target="svc")

        await connector.execute_action(action)

        call_kwargs = connector._ecs_client.update_service.call_args
        cluster = call_kwargs.kwargs.get("cluster", call_kwargs[1].get("cluster"))
        assert cluster == "default"

    @pytest.mark.asyncio
    async def test_action_id_propagated(self, connector: AWSConnector) -> None:
        connector._ec2_client.reboot_instances.return_value = {}
        action = _make_action("reboot_instance")

        result = await connector.execute_action(action)

        assert result.action_id == "action-001"


# ============================================================================
# create_snapshot
# ============================================================================


class TestCreateSnapshot:
    @pytest.mark.asyncio
    async def test_ec2_snapshot(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-abc123",
                            "InstanceType": "t3.medium",
                            "State": {"Name": "running"},
                            "Tags": [{"Key": "Name", "Value": "web-01"}],
                            "SecurityGroups": [{"GroupId": "sg-123"}],
                        }
                    ]
                }
            ]
        }

        snapshot = await connector.create_snapshot("i-abc123")

        assert snapshot.resource_id == "i-abc123"
        assert snapshot.snapshot_type == "ec2_instance"
        assert snapshot.id in connector._snapshots
        assert snapshot.created_at is not None

    @pytest.mark.asyncio
    async def test_ecs_snapshot(self, connector: AWSConnector) -> None:
        connector._ecs_client.describe_services.return_value = {
            "services": [
                {
                    "serviceName": "api-service",
                    "desiredCount": 3,
                    "runningCount": 3,
                    "taskDefinition": "arn:aws:ecs:us-east-1:123:task-def/api:5",
                    "status": "ACTIVE",
                }
            ]
        }

        snapshot = await connector.create_snapshot("ecs:production/api-service")

        assert snapshot.resource_id == "ecs:production/api-service"
        assert snapshot.snapshot_type == "ecs_service"
        assert snapshot.id in connector._snapshots
        assert snapshot.state["desired_count"] == 3

    @pytest.mark.asyncio
    async def test_ec2_snapshot_on_api_error(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instances.side_effect = Exception("AccessDenied")

        snapshot = await connector.create_snapshot("i-abc123")

        assert snapshot.state.get("error") == "could_not_capture"
        assert snapshot.id in connector._snapshots

    @pytest.mark.asyncio
    async def test_ecs_snapshot_no_services(self, connector: AWSConnector) -> None:
        connector._ecs_client.describe_services.return_value = {"services": []}

        snapshot = await connector.create_snapshot("ecs:production/missing")

        # Should still create a snapshot entry with resource_id
        assert snapshot.id in connector._snapshots

    @pytest.mark.asyncio
    async def test_ec2_snapshot_empty_reservations(self, connector: AWSConnector) -> None:
        connector._ec2_client.describe_instances.return_value = {
            "Reservations": [{"Instances": []}]
        }

        snapshot = await connector.create_snapshot("i-empty")

        # Should still succeed, possibly with just instance_id in state
        assert snapshot.id in connector._snapshots


# ============================================================================
# rollback
# ============================================================================


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_existing_snapshot(self, connector: AWSConnector) -> None:
        connector._snapshots["snap-001"] = {"resource_id": "i-abc123", "state": "captured"}

        result = await connector.rollback("snap-001")

        assert result.status == ExecutionStatus.SUCCESS
        assert result.snapshot_id == "snap-001"

    @pytest.mark.asyncio
    async def test_rollback_missing_snapshot(self, connector: AWSConnector) -> None:
        result = await connector.rollback("snap-nonexistent")

        assert result.status == ExecutionStatus.FAILED
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_rollback_has_timestamps(self, connector: AWSConnector) -> None:
        connector._snapshots["snap-002"] = {"resource_id": "i-abc123"}

        result = await connector.rollback("snap-002")

        assert result.started_at is not None
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_rollback_action_id_format(self, connector: AWSConnector) -> None:
        connector._snapshots["snap-003"] = {}

        result = await connector.rollback("snap-003")

        assert result.action_id == "rollback-snap-003"


# ============================================================================
# validate_health
# ============================================================================


class TestValidateHealth:
    @pytest.mark.asyncio
    async def test_returns_true_when_immediately_healthy(
        self, connector: AWSConnector
    ) -> None:
        connector._ec2_client.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "running"},
                    "SystemStatus": {"Status": "ok"},
                    "InstanceStatus": {"Status": "ok"},
                }
            ]
        }

        result = await connector.validate_health("i-abc123", timeout_seconds=5)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self, connector: AWSConnector) -> None:
        """With a zero timeout and a consistently unhealthy instance, returns False."""
        connector._ec2_client.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "stopped"},
                    "SystemStatus": {"Status": "not-applicable"},
                    "InstanceStatus": {"Status": "not-applicable"},
                }
            ]
        }

        with patch(
            "shieldops.connectors.aws.connector.asyncio.sleep", new_callable=AsyncMock
        ):
            result = await connector.validate_health("i-abc123", timeout_seconds=0)

        assert result is False

    @pytest.mark.asyncio
    async def test_polls_until_healthy(self, connector: AWSConnector) -> None:
        """validate_health retries and eventually succeeds."""
        unhealthy = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "pending"},
                    "SystemStatus": {"Status": "initializing"},
                    "InstanceStatus": {"Status": "initializing"},
                }
            ]
        }
        healthy = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "running"},
                    "SystemStatus": {"Status": "ok"},
                    "InstanceStatus": {"Status": "ok"},
                }
            ]
        }
        connector._ec2_client.describe_instance_status.side_effect = [
            unhealthy,
            unhealthy,
            healthy,
        ]

        with patch(
            "shieldops.connectors.aws.connector.asyncio.sleep", new_callable=AsyncMock
        ):
            result = await connector.validate_health("i-abc123", timeout_seconds=120)

        assert result is True
        assert connector._ec2_client.describe_instance_status.call_count == 3


# ============================================================================
# get_events
# ============================================================================


class TestGetEvents:
    @pytest.mark.asyncio
    async def test_returns_empty_list(
        self, connector: AWSConnector, time_range: TimeRange
    ) -> None:
        """get_events is currently a stub that returns an empty list."""
        events = await connector.get_events("i-abc123", time_range)

        assert events == []


# ============================================================================
# Initialization / provider attribute
# ============================================================================


class TestConnectorInit:
    def test_provider_is_aws(self) -> None:
        connector = AWSConnector(region="eu-west-1")
        assert connector.provider == "aws"

    def test_snapshots_dict_initialized_empty(self) -> None:
        connector = AWSConnector(region="us-west-2")
        assert connector._snapshots == {}

    def test_default_region(self) -> None:
        connector = AWSConnector()
        assert connector._region == "us-east-1"

    def test_custom_region(self) -> None:
        connector = AWSConnector(region="ap-southeast-1")
        assert connector._region == "ap-southeast-1"

    def test_clients_initially_none(self) -> None:
        connector = AWSConnector(region="us-east-1")
        assert connector._ec2_client is None
        assert connector._ecs_client is None


# ============================================================================
# Import re-export
# ============================================================================


class TestImports:
    def test_aws_connector_importable_from_package(self) -> None:
        from shieldops.connectors.aws import AWSConnector as Imported

        assert Imported is AWSConnector
        assert Imported.provider == "aws"
