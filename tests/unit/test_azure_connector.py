"""Comprehensive tests for the Azure infrastructure connector.

Tests cover:
- VM health checks (running, deallocated, API error)
- Container App health checks (running, degraded, API error)
- list_resources for VMs and Container Apps (with/without tag filters, empty, unsupported type)
- execute_action: restart_vm, reboot_instance, deallocate_vm, stop_instance,
  start_vm, start_instance, restart_container_app, scale_horizontal, unsupported action
- create_snapshot for VM and Container App (success + error fallback)
- rollback (found + not found)
- validate_health polling (immediate success, timeout, polls-until-healthy)
- get_events (stub returns empty)
- Connector initialization and import re-exports
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.connectors.azure.connector import AzureConnector
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
def connector() -> AzureConnector:
    """Create an AzureConnector with mocked Azure SDK clients.

    Replaces _ensure_clients to avoid the lazy Azure SDK import, and injects
    MagicMock clients that individual tests configure via return_value /
    side_effect.
    """
    conn = AzureConnector(
        subscription_id="sub-123",
        resource_group="rg-shieldops",
        location="eastus",
    )
    conn._compute_client = MagicMock()
    conn._container_client = MagicMock()
    # Prevent _ensure_clients from replacing our mocks
    conn._ensure_clients = MagicMock()  # type: ignore[method-assign]
    return conn


def _make_action(
    action_type: str,
    target: str = "test-vm-01",
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
    now = datetime.now(UTC)
    return TimeRange(start=now - timedelta(hours=1), end=now)


def _make_vm_instance_view(power_state: str = "running") -> MagicMock:
    """Create a mock Azure VM instance view with the given power state."""
    status = MagicMock()
    status.code = f"PowerState/{power_state}"
    view = MagicMock()
    view.statuses = [status]
    return view


def _make_container_app(
    provisioning_state: str = "Succeeded",
    running_state: str = "Running",
    name: str = "my-app",
    app_id: str = "/subscriptions/sub-123/resourceGroups/rg/providers/app/my-app",
    tags: dict[str, str] | None = None,
    location: str = "eastus",
    min_replicas: int = 1,
    max_replicas: int = 3,
    latest_revision_name: str = "my-app--rev1",
) -> MagicMock:
    """Create a mock Azure Container App object."""
    app = MagicMock()
    app.name = name
    app.id = app_id
    app.provisioning_state = provisioning_state
    app.location = location
    app.tags = tags or {}
    app.latest_revision_name = latest_revision_name

    running_status = MagicMock()
    running_status.running_state = running_state
    app.running_status = running_status

    scale = MagicMock()
    scale.min_replicas = min_replicas
    scale.max_replicas = max_replicas

    template = MagicMock()
    template.scale = scale
    app.template = template

    ingress = MagicMock()
    traffic_rule = MagicMock()
    traffic_rule.revision_name = latest_revision_name
    traffic_rule.weight = 100
    traffic_rule.latest_revision = True
    ingress.traffic = [traffic_rule]

    configuration = MagicMock()
    configuration.ingress = ingress
    app.configuration = configuration

    return app


def _make_vm(
    name: str = "test-vm-01",
    vm_id: str = "/subscriptions/sub-123/resourceGroups/rg/providers/vm/test-vm-01",
    vm_size: str = "Standard_D2s_v3",
    location: str = "eastus",
    tags: dict[str, str] | None = None,
) -> MagicMock:
    """Create a mock Azure VM object."""
    vm = MagicMock()
    vm.name = name
    vm.id = vm_id
    vm.location = location
    vm.tags = tags or {}
    hardware = MagicMock()
    hardware.vm_size = vm_size
    vm.hardware_profile = hardware
    return vm


# ============================================================================
# VM Health Checks
# ============================================================================


class TestVMGetHealth:
    @pytest.mark.asyncio
    async def test_get_health_vm_running(self, connector: AzureConnector) -> None:
        """Healthy VM with PowerState/running."""
        connector._compute_client.virtual_machines.instance_view.return_value = (
            _make_vm_instance_view("running")
        )

        health = await connector.get_health("test-vm-01")

        assert health.healthy is True
        assert health.status == "running"
        assert health.resource_id == "test-vm-01"
        assert health.metrics["power_state_running"] == 1.0
        assert "power_state=running" in (health.message or "")
        connector._compute_client.virtual_machines.instance_view.assert_called_once_with(
            "rg-shieldops",
            "test-vm-01",
        )

    @pytest.mark.asyncio
    async def test_get_health_vm_stopped(self, connector: AzureConnector) -> None:
        """Deallocated VM is reported as unhealthy."""
        connector._compute_client.virtual_machines.instance_view.return_value = (
            _make_vm_instance_view("deallocated")
        )

        health = await connector.get_health("test-vm-02")

        assert health.healthy is False
        assert health.status == "deallocated"
        assert health.metrics["power_state_running"] == 0.0

    @pytest.mark.asyncio
    async def test_get_health_vm_unknown_power_state(self, connector: AzureConnector) -> None:
        """VM with no PowerState status code defaults to 'unknown'."""
        view = MagicMock()
        # A status that is not PowerState
        status = MagicMock()
        status.code = "ProvisioningState/succeeded"
        view.statuses = [status]
        connector._compute_client.virtual_machines.instance_view.return_value = view

        health = await connector.get_health("test-vm-03")

        assert health.healthy is False
        assert health.status == "unknown"

    @pytest.mark.asyncio
    async def test_get_health_error(self, connector: AzureConnector) -> None:
        """API error returns unhealthy status."""
        connector._compute_client.virtual_machines.instance_view.side_effect = Exception(
            "AuthorizationFailed"
        )

        health = await connector.get_health("test-vm-01")

        assert health.healthy is False
        assert health.status == "error"
        assert "AuthorizationFailed" in (health.message or "")

    @pytest.mark.asyncio
    async def test_get_health_has_last_checked(self, connector: AzureConnector) -> None:
        connector._compute_client.virtual_machines.instance_view.return_value = (
            _make_vm_instance_view("running")
        )

        health = await connector.get_health("test-vm-01")

        assert health.last_checked is not None
        delta = datetime.now(UTC) - health.last_checked
        assert delta.total_seconds() < 5


# ============================================================================
# Container App Health Checks
# ============================================================================


class TestContainerAppGetHealth:
    @pytest.mark.asyncio
    async def test_get_health_container_app_running(self, connector: AzureConnector) -> None:
        """Healthy Container App with Succeeded provisioning and Running state."""
        app = _make_container_app(
            provisioning_state="Succeeded",
            running_state="Running",
        )
        connector._container_client.container_apps.get.return_value = app

        health = await connector.get_health("containerapp:my-app")

        assert health.healthy is True
        assert health.status == "running"
        assert health.resource_id == "containerapp:my-app"
        assert health.metrics["provisioning_succeeded"] == 1.0
        assert health.metrics["running"] == 1.0
        connector._container_client.container_apps.get.assert_called_once_with(
            "rg-shieldops",
            "my-app",
        )

    @pytest.mark.asyncio
    async def test_get_health_container_app_degraded(self, connector: AzureConnector) -> None:
        """Container App with failed provisioning is unhealthy."""
        app = _make_container_app(
            provisioning_state="Failed",
            running_state="Stopped",
        )
        connector._container_client.container_apps.get.return_value = app

        health = await connector.get_health("containerapp:my-app")

        assert health.healthy is False
        assert health.status == "degraded"
        assert health.metrics["provisioning_succeeded"] == 0.0

    @pytest.mark.asyncio
    async def test_get_health_container_app_no_running_status(
        self, connector: AzureConnector
    ) -> None:
        """Container App with no running_status attribute is unhealthy."""
        app = MagicMock()
        app.provisioning_state = "Succeeded"
        app.running_status = None
        connector._container_client.container_apps.get.return_value = app

        health = await connector.get_health("containerapp:my-app")

        assert health.healthy is False
        assert health.metrics["running"] == 0.0

    @pytest.mark.asyncio
    async def test_get_health_container_app_error(self, connector: AzureConnector) -> None:
        """API error for Container App returns unhealthy."""
        connector._container_client.container_apps.get.side_effect = Exception("ResourceNotFound")

        health = await connector.get_health("containerapp:missing-app")

        assert health.healthy is False
        assert health.status == "error"
        assert "ResourceNotFound" in (health.message or "")


# ============================================================================
# list_resources
# ============================================================================


class TestListResources:
    @pytest.mark.asyncio
    async def test_list_resources_vms(self, connector: AzureConnector) -> None:
        """List VMs returns Resource objects with azure provider."""
        vm1 = _make_vm(name="web-01", tags={"Environment": "staging", "team": "platform"})
        vm2 = _make_vm(name="web-02", tags={"Environment": "staging", "team": "platform"})
        connector._compute_client.virtual_machines.list.return_value = [vm1, vm2]

        resources = await connector.list_resources("vm", Environment.STAGING)

        assert len(resources) == 2
        assert resources[0].name == "web-01"
        assert resources[0].provider == "azure"
        assert resources[0].resource_type == "azure_vm"
        assert resources[0].environment == Environment.STAGING
        assert resources[0].labels["team"] == "platform"
        connector._compute_client.virtual_machines.list.assert_called_once_with("rg-shieldops")

    @pytest.mark.asyncio
    async def test_list_resources_vms_with_tag_filter(self, connector: AzureConnector) -> None:
        """Tag filters narrow down the VM list."""
        vm_match = _make_vm(name="web-01", tags={"team": "platform"})
        vm_no_match = _make_vm(name="db-01", tags={"team": "data"})
        connector._compute_client.virtual_machines.list.return_value = [vm_match, vm_no_match]

        resources = await connector.list_resources(
            "virtual_machine", Environment.STAGING, filters={"team": "platform"}
        )

        assert len(resources) == 1
        assert resources[0].name == "web-01"

    @pytest.mark.asyncio
    async def test_list_resources_container_apps(self, connector: AzureConnector) -> None:
        """List Container Apps returns Resource objects."""
        app = _make_container_app(name="api-app", tags={"service": "api"})
        connector._container_client.container_apps.list_by_resource_group.return_value = [app]

        resources = await connector.list_resources("containerapp", Environment.PRODUCTION)

        assert len(resources) == 1
        assert resources[0].name == "api-app"
        assert resources[0].resource_type == "azure_container_app"
        assert resources[0].provider == "azure"
        connector._container_client.container_apps.list_by_resource_group.assert_called_once_with(
            "rg-shieldops"
        )

    @pytest.mark.asyncio
    async def test_list_resources_container_apps_with_filter(
        self, connector: AzureConnector
    ) -> None:
        """Tag filters narrow down the Container App list."""
        app_match = _make_container_app(name="api", tags={"tier": "frontend"})
        app_no_match = _make_container_app(name="worker", tags={"tier": "backend"})
        connector._container_client.container_apps.list_by_resource_group.return_value = [
            app_match,
            app_no_match,
        ]

        resources = await connector.list_resources(
            "container_app", Environment.STAGING, filters={"tier": "frontend"}
        )

        assert len(resources) == 1
        assert resources[0].name == "api"

    @pytest.mark.asyncio
    async def test_list_resources_empty(self, connector: AzureConnector) -> None:
        """No resources found returns empty list."""
        connector._compute_client.virtual_machines.list.return_value = []

        resources = await connector.list_resources("vm", Environment.PRODUCTION)

        assert resources == []

    @pytest.mark.asyncio
    async def test_list_resources_unsupported_type(self, connector: AzureConnector) -> None:
        """Unsupported resource type returns empty list."""
        resources = await connector.list_resources("function_app", Environment.PRODUCTION)

        assert resources == []

    @pytest.mark.asyncio
    async def test_list_resources_vm_null_tags(self, connector: AzureConnector) -> None:
        """VMs with None tags should not raise."""
        vm = _make_vm(name="no-tags")
        vm.tags = None
        connector._compute_client.virtual_machines.list.return_value = [vm]

        resources = await connector.list_resources("vm", Environment.DEVELOPMENT)

        assert len(resources) == 1
        assert resources[0].labels == {}


# ============================================================================
# execute_action
# ============================================================================


class TestExecuteAction:
    @pytest.mark.asyncio
    async def test_execute_action_restart_vm(self, connector: AzureConnector) -> None:
        """restart_vm action calls begin_restart and waits."""
        poller = MagicMock()
        poller.wait.return_value = None
        connector._compute_client.virtual_machines.begin_restart.return_value = poller
        action = _make_action("restart_vm", target="test-vm-01")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert "restart" in result.message.lower()
        connector._compute_client.virtual_machines.begin_restart.assert_called_once_with(
            "rg-shieldops",
            "test-vm-01",
        )

    @pytest.mark.asyncio
    async def test_execute_action_reboot_instance(self, connector: AzureConnector) -> None:
        """reboot_instance also maps to VM restart."""
        poller = MagicMock()
        poller.wait.return_value = None
        connector._compute_client.virtual_machines.begin_restart.return_value = poller
        action = _make_action("reboot_instance", target="test-vm-01")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        connector._compute_client.virtual_machines.begin_restart.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_action_deallocate_vm(self, connector: AzureConnector) -> None:
        """deallocate_vm calls begin_deallocate."""
        poller = MagicMock()
        poller.wait.return_value = None
        connector._compute_client.virtual_machines.begin_deallocate.return_value = poller
        action = _make_action("deallocate_vm", target="test-vm-01")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert "deallocated" in result.message.lower()
        connector._compute_client.virtual_machines.begin_deallocate.assert_called_once_with(
            "rg-shieldops",
            "test-vm-01",
        )

    @pytest.mark.asyncio
    async def test_execute_action_stop_instance(self, connector: AzureConnector) -> None:
        """stop_instance also maps to VM deallocate."""
        poller = MagicMock()
        poller.wait.return_value = None
        connector._compute_client.virtual_machines.begin_deallocate.return_value = poller
        action = _make_action("stop_instance", target="test-vm-01")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_action_start_vm(self, connector: AzureConnector) -> None:
        """start_vm calls begin_start."""
        poller = MagicMock()
        poller.wait.return_value = None
        connector._compute_client.virtual_machines.begin_start.return_value = poller
        action = _make_action("start_vm", target="test-vm-01")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert "started" in result.message.lower()

    @pytest.mark.asyncio
    async def test_execute_action_start_instance(self, connector: AzureConnector) -> None:
        """start_instance also maps to VM start."""
        poller = MagicMock()
        poller.wait.return_value = None
        connector._compute_client.virtual_machines.begin_start.return_value = poller
        action = _make_action("start_instance", target="test-vm-01")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_action_restart_container_app(self, connector: AzureConnector) -> None:
        """restart_container_app deactivates then reactivates the latest revision."""
        app = _make_container_app(latest_revision_name="my-app--rev1")
        connector._container_client.container_apps.get.return_value = app
        connector._container_client.container_apps_revisions.deactivate_revision.return_value = None
        connector._container_client.container_apps_revisions.activate_revision.return_value = None
        action = _make_action("restart_container_app", target="my-app")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert "my-app" in result.message
        assert "rev1" in result.message
        connector._container_client.container_apps_revisions.deactivate_revision.assert_called_once_with(
            "rg-shieldops",
            "my-app",
            "my-app--rev1",
        )
        connector._container_client.container_apps_revisions.activate_revision.assert_called_once_with(
            "rg-shieldops",
            "my-app",
            "my-app--rev1",
        )

    @pytest.mark.asyncio
    async def test_execute_action_scale_container_app(self, connector: AzureConnector) -> None:
        """scale_horizontal updates min/max replicas on the Container App."""
        app = _make_container_app(min_replicas=1, max_replicas=3)
        connector._container_client.container_apps.get.return_value = app
        connector._container_client.container_apps.begin_create_or_update.return_value = None
        action = _make_action(
            "scale_horizontal",
            target="my-app",
            parameters={"min_replicas": 2, "max_replicas": 10},
        )

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert "min=2" in result.message
        assert "max=10" in result.message
        # Verify the app template was updated
        assert app.template.scale.min_replicas == 2
        assert app.template.scale.max_replicas == 10
        connector._container_client.container_apps.begin_create_or_update.assert_called_once_with(
            "rg-shieldops",
            "my-app",
            app,
        )

    @pytest.mark.asyncio
    async def test_execute_action_scale_uses_replicas_param(
        self, connector: AzureConnector
    ) -> None:
        """When max_replicas is not given, falls back to 'replicas' param."""
        app = _make_container_app(min_replicas=1, max_replicas=3)
        connector._container_client.container_apps.get.return_value = app
        connector._container_client.container_apps.begin_create_or_update.return_value = None
        action = _make_action(
            "scale_horizontal",
            target="my-app",
            parameters={"replicas": 5},
        )

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert app.template.scale.max_replicas == 5

    @pytest.mark.asyncio
    async def test_execute_action_unsupported(self, connector: AzureConnector) -> None:
        """Unsupported action type returns FAILED status."""
        action = _make_action("delete_vm", target="test-vm-01")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.FAILED
        assert "Unsupported action type" in result.message
        assert "delete_vm" in result.message

    @pytest.mark.asyncio
    async def test_execute_action_api_error(self, connector: AzureConnector) -> None:
        """Azure API error is caught and returned as FAILED."""
        connector._compute_client.virtual_machines.begin_restart.side_effect = Exception(
            "UnauthorizedAccess"
        )
        action = _make_action("restart_vm", target="test-vm-01")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.FAILED
        assert result.error is not None
        assert "UnauthorizedAccess" in result.error

    @pytest.mark.asyncio
    async def test_execute_action_has_timestamps(self, connector: AzureConnector) -> None:
        poller = MagicMock()
        poller.wait.return_value = None
        connector._compute_client.virtual_machines.begin_restart.return_value = poller
        action = _make_action("restart_vm")

        result = await connector.execute_action(action)

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at

    @pytest.mark.asyncio
    async def test_execute_action_id_propagated(self, connector: AzureConnector) -> None:
        poller = MagicMock()
        poller.wait.return_value = None
        connector._compute_client.virtual_machines.begin_restart.return_value = poller
        action = _make_action("restart_vm")

        result = await connector.execute_action(action)

        assert result.action_id == "action-001"


# ============================================================================
# create_snapshot
# ============================================================================


class TestCreateSnapshot:
    @pytest.mark.asyncio
    async def test_create_snapshot_vm(self, connector: AzureConnector) -> None:
        """VM snapshot captures instance view, tags, and hardware profile."""
        vm = _make_vm(
            name="test-vm-01",
            vm_size="Standard_D2s_v3",
            tags={"Name": "web-01"},
        )
        connector._compute_client.virtual_machines.get.return_value = vm
        connector._compute_client.virtual_machines.instance_view.return_value = (
            _make_vm_instance_view("running")
        )

        snapshot = await connector.create_snapshot("test-vm-01")

        assert snapshot.resource_id == "test-vm-01"
        assert snapshot.snapshot_type == "azure_vm"
        assert snapshot.id in connector._snapshots
        assert snapshot.created_at is not None
        assert snapshot.state["vm_name"] == "test-vm-01"
        assert snapshot.state["vm_size"] == "Standard_D2s_v3"
        assert snapshot.state["power_state"] == "running"
        assert snapshot.state["tags"]["Name"] == "web-01"

    @pytest.mark.asyncio
    async def test_create_snapshot_container_app(self, connector: AzureConnector) -> None:
        """Container App snapshot captures template, scale, and traffic config."""
        app = _make_container_app(
            name="api-app",
            min_replicas=2,
            max_replicas=10,
            provisioning_state="Succeeded",
        )
        connector._container_client.container_apps.get.return_value = app

        snapshot = await connector.create_snapshot("containerapp:api-app")

        assert snapshot.resource_id == "containerapp:api-app"
        assert snapshot.snapshot_type == "azure_container_app"
        assert snapshot.id in connector._snapshots
        assert snapshot.state["app_name"] == "api-app"
        assert snapshot.state["min_replicas"] == 2
        assert snapshot.state["max_replicas"] == 10
        assert snapshot.state["provisioning_state"] == "Succeeded"
        assert len(snapshot.state["traffic"]) == 1
        assert snapshot.state["traffic"][0]["weight"] == 100

    @pytest.mark.asyncio
    async def test_create_snapshot_vm_api_error(self, connector: AzureConnector) -> None:
        """API error during VM snapshot returns fallback state."""
        connector._compute_client.virtual_machines.get.side_effect = Exception("AccessDenied")

        snapshot = await connector.create_snapshot("test-vm-01")

        assert snapshot.state.get("error") == "could_not_capture"
        assert snapshot.snapshot_type == "azure_state"
        assert snapshot.id in connector._snapshots

    @pytest.mark.asyncio
    async def test_create_snapshot_container_app_api_error(self, connector: AzureConnector) -> None:
        """API error during Container App snapshot returns fallback state."""
        connector._container_client.container_apps.get.side_effect = Exception("ResourceNotFound")

        snapshot = await connector.create_snapshot("containerapp:missing-app")

        assert snapshot.state.get("error") == "could_not_capture"
        assert snapshot.id in connector._snapshots


# ============================================================================
# rollback
# ============================================================================


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_success(self, connector: AzureConnector) -> None:
        """Rollback with existing snapshot returns SUCCESS."""
        connector._snapshots["snap-001"] = {"vm_name": "test-vm-01", "power_state": "running"}

        result = await connector.rollback("snap-001")

        assert result.status == ExecutionStatus.SUCCESS
        assert result.snapshot_id == "snap-001"
        assert "snap-001" in result.message

    @pytest.mark.asyncio
    async def test_rollback_not_found(self, connector: AzureConnector) -> None:
        """Rollback with missing snapshot returns FAILED."""
        result = await connector.rollback("snap-nonexistent")

        assert result.status == ExecutionStatus.FAILED
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_rollback_has_timestamps(self, connector: AzureConnector) -> None:
        connector._snapshots["snap-002"] = {"vm_name": "test-vm-01"}

        result = await connector.rollback("snap-002")

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at

    @pytest.mark.asyncio
    async def test_rollback_action_id_format(self, connector: AzureConnector) -> None:
        connector._snapshots["snap-003"] = {}

        result = await connector.rollback("snap-003")

        assert result.action_id == "rollback-snap-003"


# ============================================================================
# validate_health
# ============================================================================


class TestValidateHealth:
    @pytest.mark.asyncio
    async def test_validate_health_success(self, connector: AzureConnector) -> None:
        """Returns True when the resource is immediately healthy."""
        connector._compute_client.virtual_machines.instance_view.return_value = (
            _make_vm_instance_view("running")
        )

        result = await connector.validate_health("test-vm-01", timeout_seconds=5)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_health_timeout(self, connector: AzureConnector) -> None:
        """Returns False when the resource never becomes healthy within the timeout."""
        connector._compute_client.virtual_machines.instance_view.return_value = (
            _make_vm_instance_view("deallocated")
        )

        with patch("shieldops.connectors.azure.connector.asyncio.sleep", new_callable=AsyncMock):
            result = await connector.validate_health("test-vm-01", timeout_seconds=0)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_health_polls_until_healthy(self, connector: AzureConnector) -> None:
        """validate_health retries and eventually succeeds."""
        unhealthy_view = _make_vm_instance_view("starting")
        healthy_view = _make_vm_instance_view("running")

        connector._compute_client.virtual_machines.instance_view.side_effect = [
            unhealthy_view,
            unhealthy_view,
            healthy_view,
        ]

        with patch("shieldops.connectors.azure.connector.asyncio.sleep", new_callable=AsyncMock):
            result = await connector.validate_health("test-vm-01", timeout_seconds=120)

        assert result is True
        assert connector._compute_client.virtual_machines.instance_view.call_count == 3

    @pytest.mark.asyncio
    async def test_validate_health_container_app(self, connector: AzureConnector) -> None:
        """validate_health works for Container Apps too."""
        app = _make_container_app(provisioning_state="Succeeded", running_state="Running")
        connector._container_client.container_apps.get.return_value = app

        result = await connector.validate_health("containerapp:my-app", timeout_seconds=5)

        assert result is True


# ============================================================================
# get_events
# ============================================================================


def _make_activity_log_event(
    event_data_id: str = "evt-001",
    correlation_id: str = "corr-001",
    timestamp: datetime | None = None,
    level_value: str = "Warning",
    operation_name: str = "Microsoft.Compute/virtualMachines/restart/action",
    status_value: str = "Succeeded",
    caller: str = "user@example.com",
    category: str = "Administrative",
    description: str = "VM restarted",
    resource_type: str = "Microsoft.Compute/virtualMachines",
) -> MagicMock:
    """Create a mock Azure Activity Log event entry."""
    ev = MagicMock()
    ev.event_data_id = event_data_id
    ev.correlation_id = correlation_id
    ev.event_timestamp = timestamp or datetime.now(UTC)
    ev.level = MagicMock()
    ev.level.value = level_value
    ev.operation_name = MagicMock()
    ev.operation_name.localized_value = operation_name
    ev.status = MagicMock()
    ev.status.localized_value = status_value
    ev.caller = caller
    ev.category = MagicMock()
    ev.category.localized_value = category
    ev.description = description
    ev.resource_type = MagicMock()
    ev.resource_type.localized_value = resource_type
    return ev


class TestAzureConnectorGetEvents:
    """Tests for the real Azure Activity Log get_events implementation.

    Because ``azure-mgmt-monitor`` is not installed in the test environment,
    we inject mock modules into ``sys.modules`` so the deferred ``import``
    statements inside ``get_events`` resolve successfully.
    """

    @staticmethod
    def _inject_azure_mocks(
        monitor_client_instance: MagicMock,
    ) -> tuple[dict[str, Any], MagicMock]:
        """Create fake azure.* sys.modules entries that return *monitor_client_instance*.

        Returns (modules_dict, MonitorManagementClientClass) so callers can
        inspect the class mock after the test.
        """
        monitor_cls = MagicMock(return_value=monitor_client_instance)
        mock_monitor_mod = MagicMock()
        mock_monitor_mod.MonitorManagementClient = monitor_cls

        mock_identity_mod = MagicMock()
        mock_identity_mod.DefaultAzureCredential = MagicMock(return_value=MagicMock())

        modules: dict[str, Any] = {
            "azure": MagicMock(),
            "azure.mgmt": MagicMock(),
            "azure.mgmt.monitor": mock_monitor_mod,
            "azure.identity": mock_identity_mod,
        }
        return modules, monitor_cls

    @staticmethod
    def _make_loop_mock() -> tuple[MagicMock, MagicMock]:
        """Return (loop_instance, get_running_loop_mock) for executor tests."""
        loop_instance = MagicMock()

        async def fake_executor(executor, fn):
            return fn()

        loop_instance.run_in_executor = fake_executor
        get_loop = MagicMock(return_value=loop_instance)
        return loop_instance, get_loop

    @pytest.mark.asyncio
    async def test_get_events_virtual_machine(
        self, connector: AzureConnector, time_range: TimeRange
    ) -> None:
        """VM resource ID generates a virtualMachines resource URI filter."""
        mock_monitor = MagicMock()
        mock_monitor.activity_logs.list.return_value = []
        modules, _ = self._inject_azure_mocks(mock_monitor)
        _, get_loop = self._make_loop_mock()

        with (
            patch.dict("sys.modules", modules),
            patch(
                "shieldops.connectors.azure.connector.asyncio.get_running_loop",
                get_loop,
            ),
        ):
            await connector.get_events("test-vm-01", time_range)

        call_args = mock_monitor.activity_logs.list.call_args
        odata_filter = call_args.kwargs.get("filter", call_args.args[0] if call_args.args else "")
        assert "virtualMachines/test-vm-01" in odata_filter
        assert "Microsoft.Compute" in odata_filter

    @pytest.mark.asyncio
    async def test_get_events_container_app(
        self, connector: AzureConnector, time_range: TimeRange
    ) -> None:
        """containerapp: prefix generates a Container Apps resource URI."""
        mock_monitor = MagicMock()
        mock_monitor.activity_logs.list.return_value = []
        modules, _ = self._inject_azure_mocks(mock_monitor)
        _, get_loop = self._make_loop_mock()

        with (
            patch.dict("sys.modules", modules),
            patch(
                "shieldops.connectors.azure.connector.asyncio.get_running_loop",
                get_loop,
            ),
        ):
            await connector.get_events("containerapp:my-api", time_range)

        call_args = mock_monitor.activity_logs.list.call_args
        odata_filter = call_args.kwargs.get("filter", call_args.args[0] if call_args.args else "")
        assert "containerApps/my-api" in odata_filter
        assert "Microsoft.App" in odata_filter

    @pytest.mark.asyncio
    async def test_get_events_parses_entries(
        self, connector: AzureConnector, time_range: TimeRange
    ) -> None:
        """Activity log entries are parsed into structured event dicts."""
        ts = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        mock_event = _make_activity_log_event(
            event_data_id="evt-abc",
            timestamp=ts,
            level_value="Warning",
            operation_name="Restart VM",
            status_value="Succeeded",
            caller="admin@corp.com",
            category="Administrative",
            description="VM restarted by automation",
            resource_type="Microsoft.Compute/virtualMachines",
        )

        mock_monitor = MagicMock()
        mock_monitor.activity_logs.list.return_value = [mock_event]
        modules, _ = self._inject_azure_mocks(mock_monitor)
        _, get_loop = self._make_loop_mock()

        with (
            patch.dict("sys.modules", modules),
            patch(
                "shieldops.connectors.azure.connector.asyncio.get_running_loop",
                get_loop,
            ),
        ):
            events = await connector.get_events("test-vm-01", time_range)

        assert len(events) == 1
        ev = events[0]
        assert ev["event_id"] == "evt-abc"
        assert ev["timestamp"] == ts.isoformat()
        assert ev["severity"] == "Warning"
        assert ev["event_type"] == "Restart VM"
        assert ev["resource_id"] == "test-vm-01"
        assert ev["status"] == "Succeeded"
        assert ev["actor"] == "admin@corp.com"
        assert ev["source"] == "azure_activity_log"
        assert ev["details"]["category"] == "Administrative"
        assert ev["details"]["description"] == "VM restarted by automation"
        assert ev["details"]["resource_type"] == "Microsoft.Compute/virtualMachines"

    @pytest.mark.asyncio
    async def test_get_events_empty_result(
        self, connector: AzureConnector, time_range: TimeRange
    ) -> None:
        """No activity log entries returns an empty list."""
        mock_monitor = MagicMock()
        mock_monitor.activity_logs.list.return_value = []
        modules, _ = self._inject_azure_mocks(mock_monitor)
        _, get_loop = self._make_loop_mock()

        with (
            patch.dict("sys.modules", modules),
            patch(
                "shieldops.connectors.azure.connector.asyncio.get_running_loop",
                get_loop,
            ),
        ):
            events = await connector.get_events("test-vm-01", time_range)

        assert events == []

    @pytest.mark.asyncio
    async def test_get_events_error_handling(
        self, connector: AzureConnector, time_range: TimeRange
    ) -> None:
        """Azure API exception returns empty list without raising."""
        # Make MonitorManagementClient constructor raise
        mock_monitor_mod = MagicMock()
        mock_monitor_mod.MonitorManagementClient = MagicMock(
            side_effect=Exception("AuthorizationFailed")
        )
        mock_identity_mod = MagicMock()
        mock_identity_mod.DefaultAzureCredential = MagicMock(return_value=MagicMock())
        modules: dict[str, Any] = {
            "azure": MagicMock(),
            "azure.mgmt": MagicMock(),
            "azure.mgmt.monitor": mock_monitor_mod,
            "azure.identity": mock_identity_mod,
        }

        with patch.dict("sys.modules", modules):
            events = await connector.get_events("test-vm-01", time_range)

        assert events == []

    @pytest.mark.asyncio
    async def test_get_events_no_monitor_library(
        self, connector: AzureConnector, time_range: TimeRange
    ) -> None:
        """Missing azure-mgmt-monitor package returns empty list."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "azure.mgmt.monitor":
                raise ImportError("No module named 'azure.mgmt.monitor'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            events = await connector.get_events("test-vm-01", time_range)

        assert events == []

    @pytest.mark.asyncio
    async def test_get_events_null_fields(
        self, connector: AzureConnector, time_range: TimeRange
    ) -> None:
        """Events with None fields are handled gracefully."""
        ev = MagicMock()
        ev.event_data_id = None
        ev.correlation_id = None
        ev.event_timestamp = None
        ev.level = None
        ev.operation_name = None
        ev.status = None
        ev.caller = None
        ev.category = None
        ev.description = None
        ev.resource_type = None

        mock_monitor = MagicMock()
        mock_monitor.activity_logs.list.return_value = [ev]
        modules, _ = self._inject_azure_mocks(mock_monitor)
        _, get_loop = self._make_loop_mock()

        with (
            patch.dict("sys.modules", modules),
            patch(
                "shieldops.connectors.azure.connector.asyncio.get_running_loop",
                get_loop,
            ),
        ):
            events = await connector.get_events("test-vm-01", time_range)

        assert len(events) == 1
        parsed = events[0]
        assert parsed["event_id"] == ""
        assert parsed["timestamp"] == ""
        assert parsed["severity"] == "Informational"
        assert parsed["event_type"] == ""
        assert parsed["status"] == ""
        assert parsed["actor"] == ""
        assert parsed["details"]["category"] == ""
        assert parsed["details"]["description"] == ""
        assert parsed["details"]["resource_type"] == ""


# ============================================================================
# Initialization / provider attribute
# ============================================================================


class TestConnectorInit:
    def test_provider_is_azure(self) -> None:
        connector = AzureConnector(
            subscription_id="sub-123",
            resource_group="rg-test",
        )
        assert connector.provider == "azure"

    def test_snapshots_dict_initialized_empty(self) -> None:
        connector = AzureConnector(
            subscription_id="sub-123",
            resource_group="rg-test",
        )
        assert connector._snapshots == {}

    def test_default_location(self) -> None:
        connector = AzureConnector(
            subscription_id="sub-123",
            resource_group="rg-test",
        )
        assert connector._location == "eastus"

    def test_custom_location(self) -> None:
        connector = AzureConnector(
            subscription_id="sub-123",
            resource_group="rg-test",
            location="westeurope",
        )
        assert connector._location == "westeurope"

    def test_subscription_and_resource_group_stored(self) -> None:
        connector = AzureConnector(
            subscription_id="sub-456",
            resource_group="rg-prod",
        )
        assert connector._subscription_id == "sub-456"
        assert connector._resource_group == "rg-prod"

    def test_clients_initially_none(self) -> None:
        connector = AzureConnector(
            subscription_id="sub-123",
            resource_group="rg-test",
        )
        assert connector._compute_client is None
        assert connector._container_client is None


# ============================================================================
# Import re-export
# ============================================================================


class TestImports:
    def test_azure_connector_importable_from_package(self) -> None:
        from shieldops.connectors.azure import AzureConnector as Imported

        assert Imported is AzureConnector
        assert Imported.provider == "azure"
