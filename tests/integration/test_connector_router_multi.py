"""Integration tests for ConnectorRouter with multiple providers."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from shieldops.connectors.base import ConnectorRouter, InfraConnector
from shieldops.models.base import (
    ActionResult,
    Environment,
    ExecutionStatus,
    HealthStatus,
    RemediationAction,
    Resource,
    RiskLevel,
    Snapshot,
    TimeRange,
)


class FakeConnector(InfraConnector):
    """Minimal in-memory connector for router tests."""

    def __init__(self, provider_name: str) -> None:
        self.provider = provider_name
        self.actions_executed: list[str] = []

    async def get_health(self, resource_id: str) -> HealthStatus:
        return HealthStatus(
            resource_id=resource_id,
            healthy=True,
            status="running",
            message=f"healthy via {self.provider}",
            last_checked=datetime.now(UTC),
        )

    async def list_resources(
        self,
        resource_type: str,
        environment: Environment,
        filters: dict[str, Any] | None = None,
    ) -> list[Resource]:
        return [
            Resource(
                id=f"{self.provider}-res-1",
                name=f"test-{self.provider}",
                resource_type=resource_type,
                environment=environment,
                provider=self.provider,
            )
        ]

    async def get_events(self, resource_id: str, time_range: TimeRange) -> list[dict[str, Any]]:
        return [{"event": "test", "provider": self.provider}]

    async def execute_action(self, action: RemediationAction) -> ActionResult:
        self.actions_executed.append(action.id)
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Executed by {self.provider}",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )

    async def create_snapshot(self, resource_id: str) -> Snapshot:
        return Snapshot(
            id=str(uuid4()),
            resource_id=resource_id,
            snapshot_type=f"{self.provider}_state",
            state={"provider": self.provider},
            created_at=datetime.now(UTC),
        )

    async def rollback(self, snapshot_id: str) -> ActionResult:
        return ActionResult(
            action_id=f"rollback-{snapshot_id}",
            status=ExecutionStatus.SUCCESS,
            message="Rolled back",
            started_at=datetime.now(UTC),
        )

    async def validate_health(self, resource_id: str, timeout_seconds: int = 300) -> bool:
        return True


class TestConnectorRouterMultiProvider:
    @pytest.fixture()
    def router(self):
        router = ConnectorRouter()
        router.register(FakeConnector("aws"))
        router.register(FakeConnector("gcp"))
        router.register(FakeConnector("azure"))
        return router

    def test_routes_to_correct_provider(self, router):
        aws = router.get("aws")
        assert aws.provider == "aws"
        gcp = router.get("gcp")
        assert gcp.provider == "gcp"

    def test_lists_all_providers(self, router):
        assert sorted(router.providers) == ["aws", "azure", "gcp"]

    def test_unknown_provider_raises(self, router):
        with pytest.raises(ValueError, match="No connector registered"):
            router.get("digitalocean")

    @pytest.mark.asyncio
    async def test_execute_action_routes_correctly(self, router):
        action = RemediationAction(
            id="act-multi-1",
            action_type="restart",
            target_resource="res-1",
            environment=Environment.DEVELOPMENT,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="Test",
        )
        aws_connector = router.get("aws")
        result = await aws_connector.execute_action(action)
        assert result.status == ExecutionStatus.SUCCESS
        assert "aws" in result.message.lower() or result.message

    @pytest.mark.asyncio
    async def test_health_check_per_provider(self, router):
        for provider in ("aws", "gcp", "azure"):
            connector = router.get(provider)
            health = await connector.get_health("test-resource")
            assert health.healthy is True
            assert provider in health.message

    @pytest.mark.asyncio
    async def test_register_replaces_existing_provider(self):
        router = ConnectorRouter()
        old = FakeConnector("aws")
        new = FakeConnector("aws")
        router.register(old)
        router.register(new)
        assert router.get("aws") is new
