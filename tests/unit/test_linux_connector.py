"""Unit tests for the Linux SSH Connector."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.connectors.linux.connector import LinuxConnector, _is_forbidden
from shieldops.models.base import Environment, ExecutionStatus, RemediationAction, RiskLevel


class MockSSHResult:
    def __init__(self, stdout="", stderr="", exit_status=0):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_status = exit_status


@pytest.fixture
def connector():
    """Create a LinuxConnector with a mocked SSH connection."""
    conn = LinuxConnector(host="10.0.0.1", username="admin")
    conn._conn = AsyncMock()
    return conn


# ── Security guardrails ──────────────────────────────────────────

def test_forbidden_rm_rf():
    assert _is_forbidden("rm -rf /") is True
    assert _is_forbidden("rm -rf /etc") is True


def test_forbidden_dd():
    assert _is_forbidden("dd if=/dev/zero of=/dev/sda") is True


def test_forbidden_drop_table():
    assert _is_forbidden("DROP TABLE users") is True


def test_forbidden_mkfs():
    assert _is_forbidden("mkfs.ext4 /dev/sda1") is True


def test_allowed_commands():
    assert _is_forbidden("systemctl restart nginx") is False
    assert _is_forbidden("apt-get install nginx") is False
    assert _is_forbidden("journalctl -u nginx") is False


# ── get_health ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_health_active(connector):
    connector._conn.run = AsyncMock(
        side_effect=[
            MockSSHResult(stdout="active\n"),
            MockSSHResult(stdout="ActiveState=active\nSubState=running\nNRestarts=0\n"),
        ]
    )
    health = await connector.get_health("nginx")
    assert health.healthy is True
    assert health.status == "active"


@pytest.mark.asyncio
async def test_get_health_inactive(connector):
    connector._conn.run = AsyncMock(
        side_effect=[
            MockSSHResult(stdout="inactive\n"),
            MockSSHResult(stdout="ActiveState=inactive\nSubState=dead\nNRestarts=2\n"),
        ]
    )
    health = await connector.get_health("nginx")
    assert health.healthy is False
    assert health.metrics["restarts"] == 2.0


# ── list_resources ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_resources(connector):
    connector._conn.run = AsyncMock(return_value=MockSSHResult(
        stdout="nginx.service  loaded active running\nsshd.service  loaded active running\n"
    ))
    resources = await connector.list_resources("service", Environment.PRODUCTION)
    assert len(resources) == 2
    assert resources[0].name == "nginx"
    assert resources[0].provider == "linux"
    assert resources[1].name == "sshd"


# ── execute_action ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_restart_service(connector):
    connector._conn.run = AsyncMock(return_value=MockSSHResult(exit_status=0))
    action = RemediationAction(
        id="act-001",
        action_type="restart_service",
        target_resource="nginx",
        environment=Environment.PRODUCTION,
        risk_level=RiskLevel.LOW,
        description="Restart nginx",
    )
    result = await connector.execute_action(action)
    assert result.status == ExecutionStatus.SUCCESS
    assert "restarted" in result.message


@pytest.mark.asyncio
async def test_restart_service_fails(connector):
    connector._conn.run = AsyncMock(
        return_value=MockSSHResult(stderr="Unit not found", exit_status=5)
    )
    action = RemediationAction(
        id="act-002",
        action_type="restart_service",
        target_resource="nonexistent",
        environment=Environment.DEVELOPMENT,
        risk_level=RiskLevel.LOW,
        description="Restart nonexistent",
    )
    result = await connector.execute_action(action)
    assert result.status == ExecutionStatus.FAILED


@pytest.mark.asyncio
async def test_stop_service(connector):
    connector._conn.run = AsyncMock(return_value=MockSSHResult(exit_status=0))
    action = RemediationAction(
        id="act-003",
        action_type="stop_service",
        target_resource="nginx",
        environment=Environment.DEVELOPMENT,
        risk_level=RiskLevel.LOW,
        description="Stop nginx",
    )
    result = await connector.execute_action(action)
    assert result.status == ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_start_service(connector):
    connector._conn.run = AsyncMock(return_value=MockSSHResult(exit_status=0))
    action = RemediationAction(
        id="act-004",
        action_type="start_service",
        target_resource="nginx",
        environment=Environment.DEVELOPMENT,
        risk_level=RiskLevel.LOW,
        description="Start nginx",
    )
    result = await connector.execute_action(action)
    assert result.status == ExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_unsupported_action(connector):
    action = RemediationAction(
        id="act-005",
        action_type="fly_to_mars",
        target_resource="nginx",
        environment=Environment.DEVELOPMENT,
        risk_level=RiskLevel.LOW,
        description="Unsupported",
    )
    result = await connector.execute_action(action)
    assert result.status == ExecutionStatus.FAILED
    assert "Unsupported" in result.message


# ── Snapshots ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_snapshot(connector):
    connector._conn.run = AsyncMock(
        side_effect=[
            MockSSHResult(stdout="ActiveState=active\n"),
            MockSSHResult(stdout="[Unit]\nDescription=nginx\n"),
        ]
    )
    snapshot = await connector.create_snapshot("nginx")
    assert snapshot.resource_id == "nginx"
    assert snapshot.snapshot_type == "linux_service"
    assert "show" in snapshot.state


@pytest.mark.asyncio
async def test_rollback_not_found(connector):
    result = await connector.rollback("nonexistent")
    assert result.status == ExecutionStatus.FAILED


@pytest.mark.asyncio
async def test_rollback_success(connector):
    connector._snapshots["snap-1"] = {"service": "nginx"}
    result = await connector.rollback("snap-1")
    assert result.status == ExecutionStatus.SUCCESS
