"""End-to-end integration tests for Azure connector using FakeAzureConnector.

Tests cover VM lifecycle, Container App management, snapshot/rollback,
error handling, and event tracking -- all against deterministic in-memory state.
"""

from datetime import UTC, datetime, timedelta

import pytest

from shieldops.models.base import Environment, RemediationAction, RiskLevel, TimeRange
from tests.integration.fakes.azure_fake import FakeAzureConnector

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def connector() -> FakeAzureConnector:
    """Fresh FakeAzureConnector with no pre-seeded state."""
    return FakeAzureConnector()


@pytest.fixture
def connector_with_vms() -> FakeAzureConnector:
    """Connector pre-seeded with three VMs having different tags."""
    c = FakeAzureConnector()
    c.add_vm("web-server-1", tags={"env": "prod", "tier": "frontend"})
    c.add_vm("web-server-2", tags={"env": "prod", "tier": "backend"})
    c.add_vm("dev-box", tags={"env": "dev", "tier": "frontend"})
    return c


@pytest.fixture
def connector_with_app() -> FakeAzureConnector:
    """Connector pre-seeded with a single Container App."""
    c = FakeAzureConnector()
    c.add_container_app("my-api", min_replicas=2, max_replicas=5)
    return c


def _make_action(
    action_type: str,
    target: str,
    action_id: str = "act-test",
    parameters: dict | None = None,
) -> RemediationAction:
    """Helper to build a RemediationAction with sensible defaults."""
    return RemediationAction(
        id=action_id,
        action_type=action_type,
        target_resource=target,
        environment=Environment.STAGING,
        risk_level=RiskLevel.LOW,
        parameters=parameters or {},
        description=f"Test {action_type} on {target}",
    )


# =====================================================================
# VM Flow Tests
# =====================================================================


class TestAzureVMFlow:
    """Tests for Azure Virtual Machine lifecycle operations."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_vm_health_running(self, connector: FakeAzureConnector) -> None:
        """A running VM reports healthy=True."""
        connector.add_vm("vm-1")

        health = await connector.get_health("vm-1")

        assert health.healthy is True
        assert health.status == "running"
        assert health.resource_id == "vm-1"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_vm_restart_flow(self, connector: FakeAzureConnector) -> None:
        """Restarting a VM leaves it in running state."""
        connector.add_vm("vm-1")
        action = _make_action("restart_vm", "vm-1")

        result = await connector.execute_action(action)

        assert result.status.value == "success"
        health = await connector.get_health("vm-1")
        assert health.healthy is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_vm_deallocate_start_flow(self, connector: FakeAzureConnector) -> None:
        """Deallocating then starting a VM transitions through deallocated -> running."""
        connector.add_vm("vm-1")

        # Deallocate
        dealloc = _make_action("deallocate_vm", "vm-1", action_id="dealloc-1")
        result = await connector.execute_action(dealloc)
        assert result.status.value == "success"

        health = await connector.get_health("vm-1")
        assert health.healthy is False
        assert health.status == "deallocated"

        # Start
        start = _make_action("start_vm", "vm-1", action_id="start-1")
        result = await connector.execute_action(start)
        assert result.status.value == "success"

        health = await connector.get_health("vm-1")
        assert health.healthy is True
        assert health.status == "running"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_vm_snapshot_rollback(self, connector: FakeAzureConnector) -> None:
        """Snapshot captures VM state; rollback restores it after mutation."""
        connector.add_vm("vm-1")

        # Snapshot while running
        snapshot = await connector.create_snapshot("vm-1")
        assert snapshot.resource_id == "vm-1"
        assert snapshot.snapshot_type == "azure_vm"
        assert snapshot.state["power_state"] == "running"

        # Deallocate the VM
        dealloc = _make_action("deallocate_vm", "vm-1")
        await connector.execute_action(dealloc)
        health = await connector.get_health("vm-1")
        assert health.healthy is False

        # Rollback to snapshot
        rollback_result = await connector.rollback(snapshot.id)
        assert rollback_result.status.value == "success"

        # VM should be running again
        health = await connector.get_health("vm-1")
        assert health.healthy is True
        assert health.status == "running"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_vms_with_filters(self, connector_with_vms: FakeAzureConnector) -> None:
        """Tag filters return the correct subset of VMs."""
        # Filter by env=prod
        prod_vms = await connector_with_vms.list_resources(
            "vm", Environment.PRODUCTION, filters={"env": "prod"}
        )
        assert len(prod_vms) == 2
        names = {r.name for r in prod_vms}
        assert names == {"web-server-1", "web-server-2"}

        # Filter by tier=frontend
        frontend_vms = await connector_with_vms.list_resources(
            "vm", Environment.PRODUCTION, filters={"tier": "frontend"}
        )
        assert len(frontend_vms) == 2
        names = {r.name for r in frontend_vms}
        assert names == {"web-server-1", "dev-box"}

        # Filter by both env=prod AND tier=frontend
        prod_frontend = await connector_with_vms.list_resources(
            "vm", Environment.PRODUCTION, filters={"env": "prod", "tier": "frontend"}
        )
        assert len(prod_frontend) == 1
        assert prod_frontend[0].name == "web-server-1"


# =====================================================================
# Container App Flow Tests
# =====================================================================


class TestAzureContainerAppFlow:
    """Tests for Azure Container App lifecycle operations."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_container_app_health(self, connector_with_app: FakeAzureConnector) -> None:
        """A Running/Succeeded Container App reports healthy=True."""
        health = await connector_with_app.get_health("containerapp:my-api")

        assert health.healthy is True
        assert health.resource_id == "containerapp:my-api"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_container_app_scale(self, connector_with_app: FakeAzureConnector) -> None:
        """Scaling updates min/max replicas on the Container App."""
        action = _make_action(
            "scale_horizontal",
            "my-api",
            parameters={"min_replicas": 3, "max_replicas": 10},
        )

        result = await connector_with_app.execute_action(action)

        assert result.status.value == "success"
        app = connector_with_app._container_apps["my-api"]
        assert app["min_replicas"] == 3
        assert app["max_replicas"] == 10

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_container_app_restart(self, connector_with_app: FakeAzureConnector) -> None:
        """Restarting a Container App keeps it in Running state."""
        action = _make_action("restart_container_app", "my-api")

        result = await connector_with_app.execute_action(action)

        assert result.status.value == "success"
        health = await connector_with_app.get_health("containerapp:my-api")
        assert health.healthy is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_container_app_snapshot_rollback(
        self, connector_with_app: FakeAzureConnector
    ) -> None:
        """Snapshot captures Container App state; rollback restores after scaling."""
        # Snapshot at min=2, max=5
        snapshot = await connector_with_app.create_snapshot("containerapp:my-api")
        assert snapshot.state["min_replicas"] == 2
        assert snapshot.state["max_replicas"] == 5

        # Scale to different values
        action = _make_action(
            "scale_horizontal",
            "my-api",
            parameters={"min_replicas": 5, "max_replicas": 20},
        )
        await connector_with_app.execute_action(action)
        assert connector_with_app._container_apps["my-api"]["min_replicas"] == 5

        # Rollback
        rollback_result = await connector_with_app.rollback(snapshot.id)
        assert rollback_result.status.value == "success"

        # Verify original state restored
        app = connector_with_app._container_apps["my-api"]
        assert app["min_replicas"] == 2
        assert app["max_replicas"] == 5


# =====================================================================
# Error Handling Tests
# =====================================================================


class TestAzureErrorHandling:
    """Tests for graceful handling of missing resources and invalid operations."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_health_nonexistent_resource(self, connector: FakeAzureConnector) -> None:
        """Health check on a missing VM returns healthy=False with not_found status."""
        health = await connector.get_health("ghost-vm")

        assert health.healthy is False
        assert health.status == "not_found"
        assert health.resource_id == "ghost-vm"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_health_nonexistent_container_app(self, connector: FakeAzureConnector) -> None:
        """Health check on a missing Container App returns healthy=False."""
        health = await connector.get_health("containerapp:ghost-app")

        assert health.healthy is False
        assert health.status == "not_found"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_action_nonexistent_resource(self, connector: FakeAzureConnector) -> None:
        """Executing an action on a missing resource returns FAILED."""
        action = _make_action("restart_vm", "ghost-vm")

        result = await connector.execute_action(action)

        assert result.status.value == "failed"
        assert result.error is not None
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_rollback_nonexistent_snapshot(self, connector: FakeAzureConnector) -> None:
        """Rolling back a nonexistent snapshot returns FAILED."""
        result = await connector.rollback("ghost-snapshot-id")

        assert result.status.value == "failed"
        assert "not found" in result.message.lower()


# =====================================================================
# Event Tracking Tests
# =====================================================================


class TestAzureEventTracking:
    """Tests for action event logging and filtering."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_events_logged_on_action(self, connector: FakeAzureConnector) -> None:
        """Every executed action appends an event to the log."""
        connector.add_vm("vm-1")

        await connector.execute_action(_make_action("restart_vm", "vm-1", action_id="a1"))
        await connector.execute_action(_make_action("deallocate_vm", "vm-1", action_id="a2"))
        await connector.execute_action(_make_action("start_vm", "vm-1", action_id="a3"))

        time_range = TimeRange(
            start=datetime.now(UTC) - timedelta(minutes=5),
            end=datetime.now(UTC) + timedelta(minutes=5),
        )
        events = await connector.get_events("vm-1", time_range)

        assert len(events) == 3
        action_types = [e["action_type"] for e in events]
        assert action_types == ["restart_vm", "deallocate_vm", "start_vm"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_events_filtered_by_resource(self, connector: FakeAzureConnector) -> None:
        """Events are correctly filtered by resource_id."""
        connector.add_vm("vm-a")
        connector.add_vm("vm-b")

        await connector.execute_action(_make_action("restart_vm", "vm-a", action_id="a1"))
        await connector.execute_action(_make_action("restart_vm", "vm-b", action_id="a2"))
        await connector.execute_action(_make_action("deallocate_vm", "vm-a", action_id="a3"))

        time_range = TimeRange(
            start=datetime.now(UTC) - timedelta(minutes=5),
            end=datetime.now(UTC) + timedelta(minutes=5),
        )

        vm_a_events = await connector.get_events("vm-a", time_range)
        assert len(vm_a_events) == 2
        assert all(e["resource_id"] == "vm-a" for e in vm_a_events)

        vm_b_events = await connector.get_events("vm-b", time_range)
        assert len(vm_b_events) == 1
        assert vm_b_events[0]["resource_id"] == "vm-b"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_events_logged_even_on_failure(self, connector: FakeAzureConnector) -> None:
        """Events are recorded even when the action fails (resource not found)."""
        action = _make_action("restart_vm", "nonexistent")
        result = await connector.execute_action(action)

        assert result.status.value == "failed"

        time_range = TimeRange(
            start=datetime.now(UTC) - timedelta(minutes=5),
            end=datetime.now(UTC) + timedelta(minutes=5),
        )
        events = await connector.get_events("nonexistent", time_range)
        assert len(events) == 1
        assert events[0]["action_type"] == "restart_vm"
