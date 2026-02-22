"""Tests for Windows WinRM connector (F4)."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from shieldops.connectors.windows.connector import (
    WindowsConnector,
    _is_forbidden,
)
from shieldops.models.base import (
    Environment,
    ExecutionStatus,
    RemediationAction,
    RiskLevel,
    TimeRange,
)


class TestForbiddenPatterns:
    def test_format_volume_blocked(self):
        assert _is_forbidden("Format-Volume -DriveLetter C") is True

    def test_remove_item_recurse_blocked(self):
        assert _is_forbidden("Remove-Item -Recurse C:\\Windows") is True

    def test_clear_disk_blocked(self):
        assert _is_forbidden("Clear-Disk -Number 0") is True

    def test_stop_computer_force_blocked(self):
        assert _is_forbidden("Stop-Computer -Force") is True

    def test_remove_aduser_blocked(self):
        assert _is_forbidden("Remove-ADUser -Identity admin") is True

    def test_drop_table_blocked(self):
        assert _is_forbidden("DROP TABLE users") is True

    def test_safe_command_allowed(self):
        assert _is_forbidden("Get-Service -Name W3SVC") is False

    def test_restart_service_allowed(self):
        assert _is_forbidden("Restart-Service -Name nginx") is False

    def test_get_process_allowed(self):
        assert _is_forbidden("Get-Process | Sort-Object CPU") is False

    def test_case_insensitive_blocking(self):
        assert _is_forbidden("format-volume -DriveLetter D") is True

    def test_disable_admin_blocked(self):
        assert _is_forbidden("Disable-ADAccount -Identity Administrator") is True


class TestWindowsConnector:
    @pytest.fixture
    def connector(self):
        return WindowsConnector(
            host="192.168.1.100",
            username="admin",
            password="pass123",
            use_ssl=True,
            port=5986,
        )

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        result = MagicMock()
        result.std_out = b'{"Status": 4, "DisplayName": "IIS", "StartType": 2}'
        result.std_err = b""
        result.status_code = 0
        session.run_ps.return_value = result
        return session

    def test_provider(self, connector):
        assert connector.provider == "windows"

    @pytest.mark.asyncio
    async def test_get_health_running(self, connector, mock_session):
        connector._session = mock_session
        health = await connector.get_health("W3SVC")
        assert health.healthy is True
        assert health.status == "running"
        assert health.resource_id == "W3SVC"

    @pytest.mark.asyncio
    async def test_get_health_stopped(self, connector, mock_session):
        mock_session.run_ps.return_value.std_out = (
            b'{"Status": 1, "DisplayName": "IIS", "StartType": 2}'
        )
        connector._session = mock_session
        health = await connector.get_health("W3SVC")
        assert health.healthy is False
        assert health.status == "stopped"

    @pytest.mark.asyncio
    async def test_get_health_error(self, connector, mock_session):
        mock_session.run_ps.side_effect = Exception("WinRM timeout")
        connector._session = mock_session
        health = await connector.get_health("bad")
        assert health.healthy is False
        assert health.status == "error"

    @pytest.mark.asyncio
    async def test_list_resources(self, connector, mock_session):
        services = [
            {"Name": "W3SVC", "DisplayName": "IIS", "StartType": 2},
            {"Name": "MSSQLSERVER", "DisplayName": "SQL Server", "StartType": 2},
        ]
        mock_session.run_ps.return_value.std_out = json.dumps(services).encode()
        connector._session = mock_session

        resources = await connector.list_resources("service", Environment.PRODUCTION)
        assert len(resources) == 2
        assert resources[0].id == "W3SVC"
        assert resources[0].provider == "windows"

    @pytest.mark.asyncio
    async def test_list_resources_single(self, connector, mock_session):
        mock_session.run_ps.return_value.std_out = json.dumps(
            {"Name": "W3SVC", "DisplayName": "IIS", "StartType": 2}
        ).encode()
        connector._session = mock_session

        resources = await connector.list_resources("service", Environment.PRODUCTION)
        assert len(resources) == 1

    @pytest.mark.asyncio
    async def test_list_resources_empty(self, connector, mock_session):
        mock_session.run_ps.return_value.std_out = b""
        connector._session = mock_session
        resources = await connector.list_resources("service", Environment.PRODUCTION)
        assert resources == []

    @pytest.mark.asyncio
    async def test_list_resources_error(self, connector, mock_session):
        mock_session.run_ps.side_effect = Exception("fail")
        connector._session = mock_session
        resources = await connector.list_resources("service", Environment.PRODUCTION)
        assert resources == []

    @pytest.mark.asyncio
    async def test_get_events(self, connector, mock_session):
        events = [{"TimeGenerated": "2024-01-01", "EntryType": "Error", "Message": "Crash"}]
        mock_session.run_ps.return_value.std_out = json.dumps(events).encode()
        connector._session = mock_session

        tr = TimeRange(start=datetime.now(UTC), end=datetime.now(UTC))
        result = await connector.get_events("W3SVC", tr)
        assert len(result) == 1
        assert result[0]["level"] == "Error"

    @pytest.mark.asyncio
    async def test_get_events_error(self, connector, mock_session):
        mock_session.run_ps.side_effect = Exception("fail")
        connector._session = mock_session
        tr = TimeRange(start=datetime.now(UTC), end=datetime.now(UTC))
        result = await connector.get_events("W3SVC", tr)
        assert result == []

    @pytest.mark.asyncio
    async def test_restart_service_success(self, connector, mock_session):
        connector._session = mock_session
        action = RemediationAction(
            id="r1",
            action_type="restart_service",
            target_resource="W3SVC",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.MEDIUM,
            parameters={},
            description="restart",
        )
        result = await connector.execute_action(action)
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_restart_service_failure(self, connector, mock_session):
        mock_session.run_ps.return_value.status_code = 1
        mock_session.run_ps.return_value.std_err = b"Access denied"
        connector._session = mock_session
        action = RemediationAction(
            id="r1",
            action_type="restart_service",
            target_resource="W3SVC",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.MEDIUM,
            parameters={},
            description="restart",
        )
        result = await connector.execute_action(action)
        assert result.status == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_stop_service(self, connector, mock_session):
        connector._session = mock_session
        action = RemediationAction(
            id="s1",
            action_type="stop_service",
            target_resource="W3SVC",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="stop",
        )
        result = await connector.execute_action(action)
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_start_service(self, connector, mock_session):
        connector._session = mock_session
        action = RemediationAction(
            id="s1",
            action_type="start_service",
            target_resource="W3SVC",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="start",
        )
        result = await connector.execute_action(action)
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_update_package(self, connector, mock_session):
        connector._session = mock_session
        action = RemediationAction(
            id="u1",
            action_type="update_package",
            target_resource="openssl",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.MEDIUM,
            parameters={},
            description="update",
        )
        result = await connector.execute_action(action)
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_unsupported_action(self, connector, mock_session):
        connector._session = mock_session
        action = RemediationAction(
            id="x1",
            action_type="unsupported",
            target_resource="x",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="unsupported",
        )
        result = await connector.execute_action(action)
        assert result.status == ExecutionStatus.FAILED
        assert "Unsupported" in result.message

    @pytest.mark.asyncio
    async def test_forbidden_command_in_action(self, connector, mock_session):
        connector._session = mock_session
        # Override _run_ps to trigger guardrail
        action = RemediationAction(
            id="f1",
            action_type="restart_service",
            target_resource="Format-Volume",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.HIGH,
            parameters={},
            description="dangerous",
        )
        # The constructed command "Restart-Service -Name Format-Volume" triggers forbidden check
        result = await connector.execute_action(action)
        assert result.status == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_create_snapshot(self, connector, mock_session):
        connector._session = mock_session
        snapshot = await connector.create_snapshot("W3SVC")
        assert snapshot.resource_id == "W3SVC"
        assert snapshot.snapshot_type == "windows_service"

    @pytest.mark.asyncio
    async def test_rollback_success(self, connector, mock_session):
        connector._session = mock_session
        snapshot = await connector.create_snapshot("W3SVC")
        result = await connector.rollback(snapshot.id)
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_rollback_not_found(self, connector):
        result = await connector.rollback("nonexistent")
        assert result.status == ExecutionStatus.FAILED
        assert "not found" in result.message

    @pytest.mark.asyncio
    async def test_close(self, connector, mock_session):
        connector._session = mock_session
        await connector.close()
        assert connector._session is None

    @pytest.mark.asyncio
    async def test_security_guardrail_exception(self, connector, mock_session):
        connector._session = mock_session
        with pytest.raises(ValueError, match="Forbidden"):
            await connector._run_ps("Format-Volume -DriveLetter C")
