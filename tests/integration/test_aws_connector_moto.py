"""Integration tests for the AWS connector using moto mock backend.

These tests exercise real connector methods against moto-emulated AWS
services (EC2, ECS, CloudTrail), providing higher fidelity than
MagicMock-based unit tests.
"""

import os
from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws

from shieldops.connectors.aws.connector import AWSConnector
from shieldops.models.base import Environment, RemediationAction, RiskLevel, TimeRange

REGION = "us-east-1"


@pytest.fixture(autouse=True)
def _aws_credentials():
    """Mocked AWS Credentials for moto (prevents real AWS calls)."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"  # noqa: S105
    os.environ["AWS_SECURITY_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_SESSION_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_DEFAULT_REGION"] = REGION
    yield
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SECURITY_TOKEN",
        "AWS_SESSION_TOKEN",
    ):
        os.environ.pop(key, None)


@pytest.fixture()
def mock_aws_env():
    """Context-managed moto mock for use in async tests."""
    with mock_aws():
        yield


def _fresh_connector() -> AWSConnector:
    """Create a connector with no cached clients."""
    connector = AWSConnector(region=REGION)
    connector._ec2_client = None
    connector._ecs_client = None
    connector._cloudtrail_client = None
    return connector


# ---------------------------------------------------------------------------
# EC2 Tests
# ---------------------------------------------------------------------------


class TestAWSConnectorEC2Health:
    @pytest.mark.asyncio
    async def test_get_health_running_instance(self, mock_aws_env):
        ec2 = boto3.client("ec2", region_name=REGION)
        resp = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t3.micro",
        )
        instance_id = resp["Instances"][0]["InstanceId"]
        connector = _fresh_connector()

        health = await connector.get_health(instance_id)
        assert health.resource_id == instance_id
        assert health.status in ("running", "pending")

    @pytest.mark.asyncio
    async def test_get_health_nonexistent_instance(self, mock_aws_env):
        connector = _fresh_connector()
        health = await connector.get_health("i-nonexistent999")
        assert health.healthy is False

    @pytest.mark.asyncio
    async def test_get_health_stopped_instance(self, mock_aws_env):
        ec2 = boto3.client("ec2", region_name=REGION)
        resp = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t3.micro",
        )
        instance_id = resp["Instances"][0]["InstanceId"]
        ec2.stop_instances(InstanceIds=[instance_id])
        connector = _fresh_connector()

        health = await connector.get_health(instance_id)
        assert health.resource_id == instance_id
        assert health.status in ("stopped", "stopping")


class TestAWSConnectorEC2ListResources:
    @pytest.mark.asyncio
    async def test_list_resources_returns_instances(self, mock_aws_env):
        ec2 = boto3.client("ec2", region_name=REGION)
        ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=2,
            MaxCount=2,
            InstanceType="t3.micro",
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name", "Value": "test-instance"},
                        {"Key": "env", "Value": "test"},
                    ],
                }
            ],
        )
        connector = _fresh_connector()

        resources = await connector.list_resources(
            resource_type="ec2",
            environment=Environment.DEVELOPMENT,
            filters={"env": "test"},
        )
        assert len(resources) == 2
        assert all(r.provider == "aws" for r in resources)
        assert all(r.resource_type == "ec2_instance" for r in resources)

    @pytest.mark.asyncio
    async def test_list_resources_with_tag_filtering(self, mock_aws_env):
        ec2 = boto3.client("ec2", region_name=REGION)
        ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t3.micro",
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [{"Key": "team", "Value": "platform"}],
                }
            ],
        )
        ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t3.micro",
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [{"Key": "team", "Value": "data"}],
                }
            ],
        )
        connector = _fresh_connector()

        resources = await connector.list_resources(
            resource_type="ec2",
            environment=Environment.DEVELOPMENT,
            filters={"team": "platform"},
        )
        assert len(resources) == 1


class TestAWSConnectorEC2Actions:
    @pytest.mark.asyncio
    async def test_execute_reboot_instance(self, mock_aws_env):
        ec2 = boto3.client("ec2", region_name=REGION)
        resp = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t3.micro",
        )
        instance_id = resp["Instances"][0]["InstanceId"]
        connector = _fresh_connector()

        action = RemediationAction(
            id="act-test-reboot",
            action_type="reboot_instance",
            target_resource=instance_id,
            environment=Environment.DEVELOPMENT,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="Reboot test instance",
        )

        result = await connector.execute_action(action)
        assert result.status.value == "success"
        assert instance_id in result.message

    @pytest.mark.asyncio
    async def test_execute_unsupported_action(self, mock_aws_env):
        connector = _fresh_connector()
        action = RemediationAction(
            id="act-test-bad",
            action_type="unsupported_action",
            target_resource="i-fake",
            environment=Environment.DEVELOPMENT,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="Bad action",
        )
        result = await connector.execute_action(action)
        assert result.status.value == "failed"
        assert "Unsupported" in result.message


# ---------------------------------------------------------------------------
# ECS Tests
# ---------------------------------------------------------------------------


class TestAWSConnectorECS:
    def _setup_ecs_cluster(self):
        """Create an ECS cluster, task def, and service inside the mock context."""
        ecs = boto3.client("ecs", region_name=REGION)
        ecs.create_cluster(clusterName="test-cluster")
        ecs.register_task_definition(
            family="test-task",
            containerDefinitions=[{"name": "app", "image": "nginx:latest", "memory": 512}],
        )
        ecs.create_service(
            cluster="test-cluster",
            serviceName="test-service",
            taskDefinition="test-task",
            desiredCount=2,
        )

    @pytest.mark.asyncio
    async def test_get_ecs_health(self, mock_aws_env):
        self._setup_ecs_cluster()
        connector = _fresh_connector()

        health = await connector.get_health("ecs:test-cluster/test-service")
        assert health.resource_id == "ecs:test-cluster/test-service"
        assert health.status in ("running", "degraded")

    @pytest.mark.asyncio
    async def test_force_new_deployment(self, mock_aws_env):
        self._setup_ecs_cluster()
        connector = _fresh_connector()

        action = RemediationAction(
            id="act-ecs-deploy",
            action_type="force_new_deployment",
            target_resource="test-service",
            environment=Environment.DEVELOPMENT,
            risk_level=RiskLevel.MEDIUM,
            parameters={"cluster": "test-cluster"},
            description="Force new deployment",
        )
        result = await connector.execute_action(action)
        assert result.status.value == "success"

    @pytest.mark.asyncio
    async def test_scale_ecs_service(self, mock_aws_env):
        self._setup_ecs_cluster()
        connector = _fresh_connector()

        action = RemediationAction(
            id="act-ecs-scale",
            action_type="update_desired_count",
            target_resource="test-service",
            environment=Environment.DEVELOPMENT,
            risk_level=RiskLevel.LOW,
            parameters={"cluster": "test-cluster", "desired_count": 5},
            description="Scale ECS service to 5",
        )
        result = await connector.execute_action(action)
        assert result.status.value == "success"
        assert "5" in result.message


# ---------------------------------------------------------------------------
# Snapshot & Rollback Tests
# ---------------------------------------------------------------------------


class TestAWSConnectorSnapshot:
    @pytest.mark.asyncio
    async def test_create_ec2_snapshot(self, mock_aws_env):
        ec2 = boto3.client("ec2", region_name=REGION)
        resp = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t3.micro",
        )
        instance_id = resp["Instances"][0]["InstanceId"]
        connector = _fresh_connector()

        snapshot = await connector.create_snapshot(instance_id)
        assert snapshot.resource_id == instance_id
        assert snapshot.snapshot_type == "ec2_instance"
        assert snapshot.id

    @pytest.mark.asyncio
    async def test_rollback_with_valid_snapshot(self, mock_aws_env):
        ec2 = boto3.client("ec2", region_name=REGION)
        resp = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t3.micro",
        )
        instance_id = resp["Instances"][0]["InstanceId"]
        connector = _fresh_connector()

        snapshot = await connector.create_snapshot(instance_id)
        result = await connector.rollback(snapshot.id)
        assert result.status.value == "success"

    @pytest.mark.asyncio
    async def test_rollback_unknown_snapshot(self, mock_aws_env):
        connector = _fresh_connector()
        result = await connector.rollback("nonexistent-snapshot-id")
        assert result.status.value == "failed"


# ---------------------------------------------------------------------------
# CloudTrail Events
# ---------------------------------------------------------------------------


class TestAWSConnectorCloudTrail:
    @pytest.mark.asyncio
    async def test_get_events_returns_list(self, mock_aws_env):
        connector = _fresh_connector()
        time_range = TimeRange(
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2025, 12, 31, tzinfo=UTC),
        )
        events = await connector.get_events("i-fake123", time_range)
        assert isinstance(events, list)
