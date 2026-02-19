"""End-to-end integration tests for GCP connector using FakeGCPConnector.

Tests cover Compute Engine instance lifecycle, Cloud Run service operations,
error handling for missing resources, and event audit trail tracking.
"""

from datetime import UTC, datetime, timedelta

import pytest

from shieldops.models.base import (
    Environment,
    ExecutionStatus,
    RemediationAction,
    RiskLevel,
    TimeRange,
)
from tests.integration.fakes.gcp_fake import FakeGCPConnector

# ── Helpers ──────────────────────────────────────────────────────────


def _make_action(
    action_type: str,
    target: str,
    action_id: str = "test-001",
    parameters: dict | None = None,
) -> RemediationAction:
    """Build a RemediationAction with sensible test defaults."""
    return RemediationAction(
        id=action_id,
        action_type=action_type,
        target_resource=target,
        environment=Environment.DEVELOPMENT,
        risk_level=RiskLevel.LOW,
        description=f"Test {action_type} on {target}",
        parameters=parameters or {},
    )


# ── Compute Engine ───────────────────────────────────────────────────


@pytest.mark.integration
class TestGCPComputeEngineFlow:
    """Compute Engine instance lifecycle through the connector interface."""

    async def test_instance_health_running(self):
        """A seeded RUNNING instance reports healthy=True."""
        conn = FakeGCPConnector()
        conn.add_instance("web-1")

        health = await conn.get_health("web-1")

        assert health.healthy is True
        assert health.status == "running"
        assert health.resource_id == "web-1"

    async def test_instance_restart_flow(self):
        """Rebooting a RUNNING instance leaves it in RUNNING state."""
        conn = FakeGCPConnector()
        conn.add_instance("web-1")

        result = await conn.execute_action(_make_action("reboot_instance", "web-1"))

        assert result.status == ExecutionStatus.SUCCESS
        health = await conn.get_health("web-1")
        assert health.healthy is True

    async def test_instance_stop_start_flow(self):
        """Stopping an instance transitions to TERMINATED; starting brings it back."""
        conn = FakeGCPConnector()
        conn.add_instance("worker-1")

        # Stop
        stop_result = await conn.execute_action(_make_action("stop_instance", "worker-1"))
        assert stop_result.status == ExecutionStatus.SUCCESS
        health = await conn.get_health("worker-1")
        assert health.healthy is False
        assert health.status == "terminated"

        # Start
        start_result = await conn.execute_action(_make_action("start_instance", "worker-1"))
        assert start_result.status == ExecutionStatus.SUCCESS
        health = await conn.get_health("worker-1")
        assert health.healthy is True
        assert health.status == "running"

    async def test_instance_snapshot_rollback(self):
        """Snapshot captures state; rollback restores it after mutation."""
        conn = FakeGCPConnector()
        conn.add_instance("db-1", status="RUNNING", machine_type="n2-standard-4")

        # Snapshot while running
        snapshot = await conn.create_snapshot("db-1")
        assert snapshot.resource_id == "db-1"
        assert snapshot.state["status"] == "RUNNING"

        # Mutate: stop the instance
        await conn.execute_action(_make_action("stop_instance", "db-1"))
        health = await conn.get_health("db-1")
        assert health.healthy is False

        # Rollback restores to RUNNING
        rollback_result = await conn.rollback(snapshot.id)
        assert rollback_result.status == ExecutionStatus.SUCCESS
        health = await conn.get_health("db-1")
        assert health.healthy is True
        assert health.status == "running"

    async def test_list_instances_with_filters(self):
        """Label filters return only matching instances."""
        conn = FakeGCPConnector()
        conn.add_instance("web-1", labels={"app": "web", "team": "platform"})
        conn.add_instance("web-2", labels={"app": "web", "team": "payments"})
        conn.add_instance("worker-1", labels={"app": "worker", "team": "platform"})

        # Filter to app=web only
        results = await conn.list_resources(
            "instance", Environment.DEVELOPMENT, filters={"app": "web"}
        )
        names = {r.name for r in results}
        assert names == {"web-1", "web-2"}

        # Filter to team=platform only
        results = await conn.list_resources(
            "instance", Environment.DEVELOPMENT, filters={"team": "platform"}
        )
        names = {r.name for r in results}
        assert names == {"web-1", "worker-1"}

        # Combined filter
        results = await conn.list_resources(
            "instance",
            Environment.DEVELOPMENT,
            filters={"app": "web", "team": "platform"},
        )
        assert len(results) == 1
        assert results[0].name == "web-1"


# ── Cloud Run ────────────────────────────────────────────────────────


@pytest.mark.integration
class TestGCPCloudRunFlow:
    """Cloud Run service operations through the connector interface."""

    async def test_service_health_ready(self):
        """A seeded Ready service reports healthy=True via run: prefix."""
        conn = FakeGCPConnector()
        conn.add_service("api-svc")

        health = await conn.get_health("run:api-svc")

        assert health.healthy is True
        assert health.resource_id == "run:api-svc"
        assert health.status == "running"

    async def test_service_scale(self):
        """scale_horizontal updates min/max instance counts."""
        conn = FakeGCPConnector()
        conn.add_service("api-svc", min_instances=1, max_instances=10)

        action = _make_action(
            "scale_horizontal",
            "api-svc",
            parameters={"min_instances": 3, "max_instances": 20},
        )
        result = await conn.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert conn._services["api-svc"]["min_instances"] == 3
        assert conn._services["api-svc"]["max_instances"] == 20

    async def test_service_update_traffic(self):
        """update_service modifies the traffic split on a Cloud Run service."""
        conn = FakeGCPConnector()
        conn.add_service("api-svc")

        action = _make_action(
            "update_service",
            "api-svc",
            parameters={"traffic_percent": 50},
        )
        result = await conn.execute_action(action)

        assert result.status == ExecutionStatus.SUCCESS
        assert conn._services["api-svc"]["traffic"][0]["percent"] == 50

    async def test_service_snapshot_rollback(self):
        """Snapshot and rollback restores Cloud Run service to original config."""
        conn = FakeGCPConnector()
        conn.add_service("api-svc", min_instances=2, max_instances=8)

        # Snapshot original state
        snapshot = await conn.create_snapshot("run:api-svc")
        assert snapshot.state["min_instances"] == 2
        assert snapshot.state["max_instances"] == 8

        # Mutate: scale up
        await conn.execute_action(
            _make_action(
                "scale_horizontal",
                "api-svc",
                parameters={"min_instances": 5, "max_instances": 50},
            )
        )
        assert conn._services["api-svc"]["min_instances"] == 5

        # Rollback restores to original
        rollback_result = await conn.rollback(snapshot.id)
        assert rollback_result.status == ExecutionStatus.SUCCESS
        assert conn._services["api-svc"]["min_instances"] == 2
        assert conn._services["api-svc"]["max_instances"] == 8


# ── Error Handling ───────────────────────────────────────────────────


@pytest.mark.integration
class TestGCPErrorHandling:
    """Connector gracefully reports failures for missing resources."""

    async def test_health_nonexistent_resource(self):
        """Health check on a missing resource returns healthy=False, not_found."""
        conn = FakeGCPConnector()

        health = await conn.get_health("ghost-instance")

        assert health.healthy is False
        assert health.status == "not_found"

    async def test_health_nonexistent_cloud_run_service(self):
        """Health check on a missing Cloud Run service returns healthy=False."""
        conn = FakeGCPConnector()

        health = await conn.get_health("run:ghost-svc")

        assert health.healthy is False
        assert health.status == "not_found"

    async def test_action_nonexistent_resource(self):
        """Executing an action on a missing resource returns FAILED."""
        conn = FakeGCPConnector()

        result = await conn.execute_action(_make_action("reboot_instance", "no-such-instance"))

        assert result.status == ExecutionStatus.FAILED
        assert "not found" in result.message.lower()

    async def test_rollback_nonexistent_snapshot(self):
        """Rolling back a non-existent snapshot returns FAILED."""
        conn = FakeGCPConnector()

        result = await conn.rollback("no-such-snapshot-id")

        assert result.status == ExecutionStatus.FAILED
        assert "not found" in result.message.lower()

    async def test_unsupported_action_type(self):
        """An unrecognised action_type returns FAILED."""
        conn = FakeGCPConnector()
        conn.add_instance("web-1")

        result = await conn.execute_action(_make_action("delete_universe", "web-1"))

        assert result.status == ExecutionStatus.FAILED
        assert "unsupported" in result.message.lower()


# ── Event Tracking ───────────────────────────────────────────────────


@pytest.mark.integration
class TestGCPEventTracking:
    """Actions are logged and retrievable through get_events."""

    async def test_events_logged_on_action(self):
        """Every execute_action call appends an event to the log."""
        conn = FakeGCPConnector()
        conn.add_instance("web-1")

        now = datetime.now(UTC)
        await conn.execute_action(_make_action("reboot_instance", "web-1", action_id="a1"))
        await conn.execute_action(_make_action("stop_instance", "web-1", action_id="a2"))

        time_range = TimeRange(start=now - timedelta(seconds=1), end=now + timedelta(seconds=10))
        events = await conn.get_events("web-1", time_range)

        assert len(events) == 2
        assert events[0]["action"] == "reboot_instance"
        assert events[1]["action"] == "stop_instance"

    async def test_events_filtered_by_resource(self):
        """get_events returns only events matching the requested resource_id."""
        conn = FakeGCPConnector()
        conn.add_instance("web-1")
        conn.add_instance("web-2")

        now = datetime.now(UTC)
        await conn.execute_action(_make_action("reboot_instance", "web-1", action_id="a1"))
        await conn.execute_action(_make_action("stop_instance", "web-2", action_id="a2"))
        await conn.execute_action(_make_action("start_instance", "web-2", action_id="a3"))

        time_range = TimeRange(start=now - timedelta(seconds=1), end=now + timedelta(seconds=10))

        web1_events = await conn.get_events("web-1", time_range)
        assert len(web1_events) == 1
        assert web1_events[0]["action"] == "reboot_instance"

        web2_events = await conn.get_events("web-2", time_range)
        assert len(web2_events) == 2

    async def test_events_filtered_by_time_range(self):
        """Events outside the requested time window are excluded."""
        conn = FakeGCPConnector()
        conn.add_instance("web-1")

        # Manually inject an old event
        old_timestamp = datetime(2020, 1, 1, tzinfo=UTC)
        conn._events.append(
            {"timestamp": old_timestamp, "resource_id": "web-1", "action": "ancient_reboot"}
        )

        # Execute a new action
        now = datetime.now(UTC)
        await conn.execute_action(_make_action("reboot_instance", "web-1"))

        # Query only recent events
        time_range = TimeRange(start=now - timedelta(seconds=1), end=now + timedelta(seconds=10))
        events = await conn.get_events("web-1", time_range)

        assert len(events) == 1
        assert events[0]["action"] == "reboot_instance"
