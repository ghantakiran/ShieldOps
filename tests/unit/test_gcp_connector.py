"""Tests for the GCP infrastructure connector.

Tests cover:
- Compute Engine health checks (healthy, stopped, error)
- Cloud Run health checks (ready, not ready, error)
- list_resources for Compute Engine instances (with filters, empty)
- execute_action: reset, stop, start, update_service, scale_horizontal, unsupported
- create_snapshot for Compute Engine and Cloud Run
- rollback (found + not found)
- validate_health polling
- get_events (stub)
- Initialization and import re-exports
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.connectors.gcp.connector import GCPConnector
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
def connector() -> GCPConnector:
    """Create a GCPConnector with mocked GCP clients."""
    conn = GCPConnector(project_id="test-project", region="us-central1")
    conn._compute_client = MagicMock()
    conn._run_client = MagicMock()
    conn._ensure_clients = MagicMock()  # type: ignore[method-assign]
    return conn


def _make_action(
    action_type: str,
    target: str = "my-instance",
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


# ============================================================================
# Compute Engine Health Checks
# ============================================================================


class TestComputeGetHealth:
    @pytest.mark.asyncio
    async def test_healthy_running_instance(self, connector: GCPConnector) -> None:
        mock_instance = MagicMock()
        mock_instance.status = "RUNNING"
        connector._compute_client.get.return_value = mock_instance

        health = await connector.get_health("my-instance")

        assert health.healthy is True
        assert health.status == "running"
        assert health.resource_id == "my-instance"
        assert health.metrics["running"] == 1.0

    @pytest.mark.asyncio
    async def test_unhealthy_stopped_instance(self, connector: GCPConnector) -> None:
        mock_instance = MagicMock()
        mock_instance.status = "TERMINATED"
        connector._compute_client.get.return_value = mock_instance

        health = await connector.get_health("my-instance")

        assert health.healthy is False
        assert health.status == "terminated"

    @pytest.mark.asyncio
    async def test_api_error(self, connector: GCPConnector) -> None:
        connector._compute_client.get.side_effect = Exception("NotFound")

        health = await connector.get_health("missing-instance")

        assert health.healthy is False
        assert health.status == "error"
        assert "NotFound" in (health.message or "")

    @pytest.mark.asyncio
    async def test_health_has_last_checked(self, connector: GCPConnector) -> None:
        mock_instance = MagicMock()
        mock_instance.status = "RUNNING"
        connector._compute_client.get.return_value = mock_instance

        health = await connector.get_health("my-instance")

        assert health.last_checked is not None
        delta = datetime.now(UTC) - health.last_checked
        assert delta.total_seconds() < 5


# ============================================================================
# Cloud Run Health Checks
# ============================================================================


class TestCloudRunGetHealth:
    @pytest.mark.asyncio
    async def test_healthy_run_service(self, connector: GCPConnector) -> None:
        mock_condition = MagicMock()
        mock_condition.type_ = "Ready"
        mock_condition.state = "CONDITION_SUCCEEDED"
        mock_condition.message = "Service is ready"

        mock_service = MagicMock()
        mock_service.conditions = [mock_condition]
        connector._run_client.get_service.return_value = mock_service

        health = await connector.get_health("run:api-service")

        assert health.healthy is True
        assert health.resource_id == "run:api-service"
        assert health.status == "running"

    @pytest.mark.asyncio
    async def test_unhealthy_run_service(self, connector: GCPConnector) -> None:
        mock_condition = MagicMock()
        mock_condition.type_ = "Ready"
        mock_condition.state = "CONDITION_FAILED"
        mock_condition.message = "Revision failed"

        mock_service = MagicMock()
        mock_service.conditions = [mock_condition]
        connector._run_client.get_service.return_value = mock_service

        health = await connector.get_health("run:api-service")

        assert health.healthy is False
        assert health.status == "degraded"

    @pytest.mark.asyncio
    async def test_run_service_no_conditions(self, connector: GCPConnector) -> None:
        mock_service = MagicMock()
        mock_service.conditions = []
        connector._run_client.get_service.return_value = mock_service

        health = await connector.get_health("run:api-service")

        assert health.healthy is False

    @pytest.mark.asyncio
    async def test_run_api_error(self, connector: GCPConnector) -> None:
        connector._run_client.get_service.side_effect = Exception("PermissionDenied")

        health = await connector.get_health("run:api-service")

        assert health.healthy is False
        assert health.status == "error"


# ============================================================================
# list_resources
# ============================================================================


class TestListResources:
    @pytest.mark.asyncio
    async def test_list_compute_instances(self, connector: GCPConnector) -> None:
        mock_inst = MagicMock()
        mock_inst.id = 12345
        mock_inst.name = "web-01"
        mock_inst.machine_type = "e2-medium"
        mock_inst.status = "RUNNING"
        mock_inst.zone = "us-central1-a"
        mock_inst.labels = {"env": "staging"}
        mock_inst.creation_timestamp = "2024-06-01T00:00:00Z"

        connector._compute_client.list.return_value = [mock_inst]

        resources = await connector.list_resources("instance", Environment.STAGING)

        assert len(resources) == 1
        assert resources[0].name == "web-01"
        assert resources[0].provider == "gcp"
        assert resources[0].labels["env"] == "staging"

    @pytest.mark.asyncio
    async def test_list_with_label_filters(self, connector: GCPConnector) -> None:
        connector._compute_client.list.return_value = []

        await connector.list_resources(
            "compute", Environment.PRODUCTION, filters={"team": "platform"}
        )

        call_kwargs = connector._compute_client.list.call_args
        assert "filter" in call_kwargs.kwargs
        assert "labels.team=platform" in call_kwargs.kwargs["filter"]

    @pytest.mark.asyncio
    async def test_list_empty(self, connector: GCPConnector) -> None:
        connector._compute_client.list.return_value = []

        resources = await connector.list_resources("instance", Environment.PRODUCTION)

        assert resources == []

    @pytest.mark.asyncio
    async def test_list_unsupported_type(self, connector: GCPConnector) -> None:
        resources = await connector.list_resources("cloud_function", Environment.STAGING)

        assert resources == []

    @pytest.mark.asyncio
    async def test_list_api_error(self, connector: GCPConnector) -> None:
        connector._compute_client.list.side_effect = Exception("QuotaExceeded")

        resources = await connector.list_resources("instance", Environment.PRODUCTION)

        assert resources == []


# ============================================================================
# execute_action
# ============================================================================


class TestExecuteAction:
    @pytest.mark.asyncio
    async def test_reset_instance(self, connector: GCPConnector) -> None:
        connector._compute_client.reset.return_value = MagicMock()
        action = _make_action("reset_instance", target="my-instance")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert "reset" in result.message.lower()

    @pytest.mark.asyncio
    async def test_reboot_instance(self, connector: GCPConnector) -> None:
        connector._compute_client.reset.return_value = MagicMock()
        action = _make_action("reboot_instance", target="my-instance")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_stop_instance(self, connector: GCPConnector) -> None:
        connector._compute_client.stop.return_value = MagicMock()
        action = _make_action("stop_instance", target="my-instance")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert "stop" in result.message.lower()

    @pytest.mark.asyncio
    async def test_start_instance(self, connector: GCPConnector) -> None:
        connector._compute_client.start.return_value = MagicMock()
        action = _make_action("start_instance", target="my-instance")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert "start" in result.message.lower()

    @pytest.mark.asyncio
    async def test_scale_horizontal(self, connector: GCPConnector) -> None:
        connector._run_client.update_service.return_value = MagicMock()
        action = _make_action(
            "scale_horizontal",
            target="api-service",
            parameters={"min_instances": 2, "max_instances": 8},
        )

        # Mock the inline import of google.cloud.run_v2.types
        mock_types = MagicMock()
        with patch.dict("sys.modules", {"google.cloud.run_v2.types": mock_types}):
            result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert "scaled" in result.message.lower()

    @pytest.mark.asyncio
    async def test_unsupported_action(self, connector: GCPConnector) -> None:
        action = _make_action("delete_instance", target="my-instance")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.FAILED
        assert "Unsupported" in result.message

    @pytest.mark.asyncio
    async def test_action_api_error(self, connector: GCPConnector) -> None:
        connector._compute_client.reset.side_effect = Exception("PermissionDenied")
        action = _make_action("reset_instance")

        result = await connector.execute_action(action)

        assert result.status == ExecutionStatus.FAILED
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_action_timestamps(self, connector: GCPConnector) -> None:
        connector._compute_client.reset.return_value = MagicMock()
        action = _make_action("reset_instance")

        result = await connector.execute_action(action)

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at

    @pytest.mark.asyncio
    async def test_action_id_propagated(self, connector: GCPConnector) -> None:
        connector._compute_client.reset.return_value = MagicMock()
        action = _make_action("reset_instance")

        result = await connector.execute_action(action)

        assert result.action_id == "action-001"


# ============================================================================
# create_snapshot
# ============================================================================


class TestCreateSnapshot:
    @pytest.mark.asyncio
    async def test_compute_snapshot(self, connector: GCPConnector) -> None:
        mock_instance = MagicMock()
        mock_instance.status = "RUNNING"
        mock_instance.machine_type = "e2-medium"
        mock_instance.labels = {"env": "staging"}
        mock_instance.zone = "us-central1-a"
        connector._compute_client.get.return_value = mock_instance

        snapshot = await connector.create_snapshot("my-instance")

        assert snapshot.resource_id == "my-instance"
        assert snapshot.snapshot_type == "gce_instance"
        assert snapshot.id in connector._snapshots
        assert snapshot.state["status"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_run_snapshot(self, connector: GCPConnector) -> None:
        mock_service = MagicMock()
        mock_service.traffic = []
        mock_service.template = MagicMock()
        mock_service.template.scaling = MagicMock()
        mock_service.template.scaling.min_instance_count = 1
        mock_service.template.scaling.max_instance_count = 10
        connector._run_client.get_service.return_value = mock_service

        snapshot = await connector.create_snapshot("run:api-service")

        assert snapshot.resource_id == "run:api-service"
        assert snapshot.snapshot_type == "cloud_run_service"
        assert snapshot.id in connector._snapshots

    @pytest.mark.asyncio
    async def test_snapshot_on_error(self, connector: GCPConnector) -> None:
        connector._compute_client.get.side_effect = Exception("NotFound")

        snapshot = await connector.create_snapshot("missing-instance")

        assert snapshot.state.get("error") == "could_not_capture"
        assert snapshot.id in connector._snapshots


# ============================================================================
# rollback
# ============================================================================


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_existing(self, connector: GCPConnector) -> None:
        connector._snapshots["snap-001"] = {"instance_name": "my-instance"}

        result = await connector.rollback("snap-001")

        assert result.status == ExecutionStatus.SUCCESS
        assert result.snapshot_id == "snap-001"

    @pytest.mark.asyncio
    async def test_rollback_missing(self, connector: GCPConnector) -> None:
        result = await connector.rollback("snap-nonexistent")

        assert result.status == ExecutionStatus.FAILED
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_rollback_action_id_format(self, connector: GCPConnector) -> None:
        connector._snapshots["snap-002"] = {}

        result = await connector.rollback("snap-002")

        assert result.action_id == "rollback-snap-002"


# ============================================================================
# validate_health
# ============================================================================


class TestValidateHealth:
    @pytest.mark.asyncio
    async def test_immediately_healthy(self, connector: GCPConnector) -> None:
        mock_instance = MagicMock()
        mock_instance.status = "RUNNING"
        connector._compute_client.get.return_value = mock_instance

        result = await connector.validate_health("my-instance", timeout_seconds=5)

        assert result is True

    @pytest.mark.asyncio
    async def test_timeout(self, connector: GCPConnector) -> None:
        mock_instance = MagicMock()
        mock_instance.status = "TERMINATED"
        connector._compute_client.get.return_value = mock_instance

        with patch("shieldops.connectors.gcp.connector.asyncio.sleep", new_callable=AsyncMock):
            result = await connector.validate_health("my-instance", timeout_seconds=0)

        assert result is False


# ============================================================================
# get_events (Cloud Audit Logs)
# ============================================================================


def _make_log_entry(
    insert_id: str = "entry-1",
    timestamp: datetime | None = None,
    severity: str = "INFO",
    payload: dict[str, Any] | str | None = None,
) -> MagicMock:
    """Build a mock Cloud Logging entry."""
    entry = MagicMock()
    entry.insert_id = insert_id
    entry.timestamp = timestamp or datetime.now(UTC)
    entry.severity = severity
    entry.payload = (
        payload
        if payload is not None
        else {
            "methodName": "v1.compute.instances.stop",
            "authenticationInfo": {
                "principalEmail": "admin@example.com",
            },
            "resourceName": "projects/test-project/zones/us-central1-a/instances/web-01",
        }
    )
    return entry


def _patch_gcloud_logging(mock_client: MagicMock):  # type: ignore[type-arg]
    """Context manager that patches the lazy ``from google.cloud import logging``
    inside ``get_events`` so it resolves to a mock module whose ``Client``
    returns *mock_client*.

    The ``from google.cloud import logging`` statement requires:
    1. ``google`` in ``sys.modules``
    2. ``google.cloud`` in ``sys.modules`` with a ``logging`` attribute
    3. ``google.cloud.logging`` in ``sys.modules``
    """
    mock_logging_mod = MagicMock()
    mock_logging_mod.Client.return_value = mock_client

    mock_cloud = MagicMock()
    mock_cloud.logging = mock_logging_mod

    mock_google = MagicMock()
    mock_google.cloud = mock_cloud

    return patch.dict(
        "sys.modules",
        {
            "google": mock_google,
            "google.cloud": mock_cloud,
            "google.cloud.logging": mock_logging_mod,
        },
    )


class TestGCPConnectorGetEvents:
    """Tests for the real Cloud Audit Logs get_events implementation."""

    @pytest.mark.asyncio
    async def test_get_events_compute_instance(
        self, connector: GCPConnector, time_range: TimeRange
    ) -> None:
        """Verify the filter targets gce_instance for bare resource IDs."""
        mock_client = MagicMock()
        mock_client.list_entries.return_value = []

        with _patch_gcloud_logging(mock_client):
            events = await connector.get_events("web-01", time_range)

        assert events == []
        call_kwargs = mock_client.list_entries.call_args
        assert call_kwargs is not None
        filter_str = call_kwargs.kwargs.get("filter_", "")
        assert 'resource.type="gce_instance"' in filter_str
        assert 'resource.labels.instance_id="web-01"' in filter_str
        assert 'resource.labels.zone="us-central1-a"' in filter_str

    @pytest.mark.asyncio
    async def test_get_events_cloud_run(
        self, connector: GCPConnector, time_range: TimeRange
    ) -> None:
        """Verify the filter targets cloud_run_revision for run: prefix."""
        mock_client = MagicMock()
        mock_client.list_entries.return_value = []

        with _patch_gcloud_logging(mock_client):
            events = await connector.get_events("run:api-service", time_range)

        assert events == []
        call_kwargs = mock_client.list_entries.call_args
        assert call_kwargs is not None
        filter_str = call_kwargs.kwargs.get("filter_", "")
        assert 'resource.type="cloud_run_revision"' in filter_str
        assert 'resource.labels.service_name="api-service"' in filter_str
        assert 'resource.labels.location="us-central1"' in filter_str

    @pytest.mark.asyncio
    async def test_get_events_parses_entries(
        self, connector: GCPConnector, time_range: TimeRange
    ) -> None:
        """Verify log entries are correctly parsed into event dicts."""
        ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        entries = [
            _make_log_entry(
                insert_id="entry-abc",
                timestamp=ts,
                severity="NOTICE",
                payload={
                    "methodName": "v1.compute.instances.stop",
                    "authenticationInfo": {
                        "principalEmail": "ops@example.com",
                    },
                    "extra": "data",
                },
            ),
            _make_log_entry(
                insert_id="entry-def",
                timestamp=ts,
                severity="WARNING",
                payload="plain text log message",
            ),
        ]

        mock_client = MagicMock()
        mock_client.list_entries.return_value = entries

        with _patch_gcloud_logging(mock_client):
            events = await connector.get_events("web-01", time_range)

        assert len(events) == 2

        # First entry: dict payload
        e0 = events[0]
        assert e0["event_id"] == "entry-abc"
        assert e0["timestamp"] == ts.isoformat()
        assert e0["severity"] == "NOTICE"
        assert e0["event_type"] == "v1.compute.instances.stop"
        assert e0["resource_id"] == "web-01"
        assert e0["actor"] == "ops@example.com"
        assert e0["details"]["extra"] == "data"
        assert e0["source"] == "gcp_audit_log"

        # Second entry: string payload
        e1 = events[1]
        assert e1["event_type"] == "plain text log message"
        assert e1["actor"] == ""
        assert e1["details"] == {"message": "plain text log message"}

    @pytest.mark.asyncio
    async def test_get_events_empty_result(
        self, connector: GCPConnector, time_range: TimeRange
    ) -> None:
        """Verify empty list when no log entries are returned."""
        mock_client = MagicMock()
        mock_client.list_entries.return_value = []

        with _patch_gcloud_logging(mock_client):
            events = await connector.get_events("web-01", time_range)

        assert events == []

    @pytest.mark.asyncio
    async def test_get_events_error_handling(
        self, connector: GCPConnector, time_range: TimeRange
    ) -> None:
        """Verify API errors return [] and are logged."""
        mock_client = MagicMock()
        mock_client.list_entries.side_effect = Exception("403 Permission Denied")

        with _patch_gcloud_logging(mock_client):
            events = await connector.get_events("web-01", time_range)

        assert events == []

    @pytest.mark.asyncio
    async def test_get_events_no_logging_library(
        self, connector: GCPConnector, time_range: TimeRange
    ) -> None:
        """Verify ImportError returns [] gracefully."""
        # Setting a module to None in sys.modules causes ImportError
        with patch.dict(
            "sys.modules",
            {"google.cloud.logging": None},
        ):
            events = await connector.get_events("web-01", time_range)

        assert events == []


# ============================================================================
# Initialization
# ============================================================================


class TestInit:
    def test_provider_is_gcp(self) -> None:
        conn = GCPConnector(project_id="test", region="us-west1")
        assert conn.provider == "gcp"

    def test_snapshots_empty(self) -> None:
        conn = GCPConnector(project_id="test")
        assert conn._snapshots == {}

    def test_clients_initially_none(self) -> None:
        conn = GCPConnector(project_id="test")
        assert conn._compute_client is None
        assert conn._run_client is None

    def test_default_region(self) -> None:
        conn = GCPConnector(project_id="test")
        assert conn._region == "us-central1"

    def test_custom_region(self) -> None:
        conn = GCPConnector(project_id="test", region="europe-west1")
        assert conn._region == "europe-west1"

    def test_importable_from_package(self) -> None:
        from shieldops.connectors.gcp import GCPConnector as Imported

        assert Imported is GCPConnector
        assert Imported.provider == "gcp"
