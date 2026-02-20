"""Tests for the ShieldOps CLI commands.

Uses Click's CliRunner for invocation and unittest.mock.patch to stub
HTTP calls so tests run without a live API server.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from click.testing import CliRunner

from shieldops.cli.main import cli

# ---------------------------------------------------------------------------
# Shared patch target -- we mock the *get_client* function in http.py
# so every command that calls api_request uses our fake client.
# ---------------------------------------------------------------------------

_PATCH_GET_CLIENT = "shieldops.cli.http.get_client"


def _fake_client(
    *responses: tuple[int, dict | list],
) -> MagicMock:
    """Return a mock httpx.Client whose .request() yields *responses* in order.

    Each element is ``(status_code, json_body)``.
    """
    client = MagicMock()

    mocks = []
    for code, body in responses:
        resp = MagicMock()
        resp.status_code = code
        resp.json.return_value = body
        resp.text = ""
        mocks.append(resp)

    client.request.side_effect = mocks
    # context-manager protocol
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# General CLI tests
# ---------------------------------------------------------------------------


class TestCLIGeneral:
    """Top-level CLI tests: help, version, global options."""

    def test_cli_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "ShieldOps" in result.output
        assert "status" in result.output
        assert "investigate" in result.output
        assert "remediate" in result.output
        assert "agents" in result.output
        assert "scan" in result.output
        assert "serve" in result.output

    def test_version_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower() or "." in result.output


# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------


class TestStatusCommand:
    """Tests for ``shieldops status``."""

    @patch(_PATCH_GET_CLIENT)
    def test_status_command(self, mock_gc: MagicMock) -> None:
        """Status command shows health and agent summary."""
        mock_gc.return_value = _fake_client(
            (200, {"status": "healthy", "version": "0.1.0"}),
            (
                200,
                {
                    "agents": [
                        {
                            "agent_id": "inv-001",
                            "agent_type": "investigation",
                            "environment": "production",
                            "status": "active",
                        }
                    ],
                    "total": 1,
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "v0.1.0" in result.output
        assert "investigation" in result.output

    @patch(_PATCH_GET_CLIENT)
    def test_status_connection_error(self, mock_gc: MagicMock) -> None:
        """Status command handles connection failures gracefully."""
        client = MagicMock()
        client.request.side_effect = httpx.ConnectError("Connection refused")
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        mock_gc.return_value = client

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert "Could not connect" in result.output


# ---------------------------------------------------------------------------
# Investigate commands
# ---------------------------------------------------------------------------


class TestInvestigateCommands:
    """Tests for ``shieldops investigate`` subcommands."""

    @patch(_PATCH_GET_CLIENT)
    def test_investigate_list(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (
                200,
                {
                    "investigations": [
                        {
                            "investigation_id": "inv-abc",
                            "alert_name": "HighCPU",
                            "severity": "critical",
                            "status": "completed",
                            "created_at": "2025-01-01T00:00:00Z",
                        }
                    ],
                    "total": 1,
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["investigate", "list"])
        assert result.exit_code == 0
        assert "inv-abc" in result.output
        assert "HighCPU" in result.output

    @patch(_PATCH_GET_CLIENT)
    def test_investigate_get(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (
                200,
                {
                    "investigation_id": "inv-abc",
                    "alert_name": "HighCPU",
                    "severity": "critical",
                    "status": "completed",
                    "confidence": 0.95,
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["investigate", "get", "inv-abc"])
        assert result.exit_code == 0
        assert "inv-abc" in result.output
        assert "HighCPU" in result.output

    @patch(_PATCH_GET_CLIENT)
    def test_investigate_start(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (
                202,
                {
                    "status": "accepted",
                    "alert_id": "alert-123",
                    "message": "Investigation started.",
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["investigate", "start", "--alert-id", "alert-123"],
        )
        assert result.exit_code == 0
        assert "Investigation started" in result.output

    def test_investigate_start_missing_alert_id(self) -> None:
        """Start requires --alert-id."""
        runner = CliRunner()
        result = runner.invoke(cli, ["investigate", "start"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Remediate commands
# ---------------------------------------------------------------------------


class TestRemediateCommands:
    """Tests for ``shieldops remediate`` subcommands."""

    @patch(_PATCH_GET_CLIENT)
    def test_remediate_list(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (
                200,
                {
                    "remediations": [
                        {
                            "remediation_id": "rem-001",
                            "action_type": "restart_service",
                            "target_resource": "web-app",
                            "environment": "production",
                            "status": "completed",
                        }
                    ],
                    "total": 1,
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["remediate", "list"])
        assert result.exit_code == 0
        assert "rem-001" in result.output
        assert "restart_service" in result.output

    @patch(_PATCH_GET_CLIENT)
    def test_remediate_rollback(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (
                200,
                {
                    "remediation_id": "rem-001",
                    "action": "rollback_initiated",
                    "status": "rolling_back",
                    "message": "Restoring pre-action state.",
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["remediate", "rollback", "rem-001", "--reason", "bad deploy"],
        )
        assert result.exit_code == 0
        assert "Rollback initiated" in result.output


# ---------------------------------------------------------------------------
# Agents commands
# ---------------------------------------------------------------------------


class TestAgentsCommands:
    """Tests for ``shieldops agents`` subcommands."""

    @patch(_PATCH_GET_CLIENT)
    def test_agents_list(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (
                200,
                {
                    "agents": [
                        {
                            "agent_id": "agent-inv",
                            "agent_type": "investigation",
                            "environment": "production",
                            "status": "active",
                            "last_heartbeat": "2025-01-01T00:00:00Z",
                        },
                        {
                            "agent_id": "agent-sec",
                            "agent_type": "security",
                            "environment": "staging",
                            "status": "active",
                            "last_heartbeat": "2025-01-01T00:01:00Z",
                        },
                    ],
                    "total": 2,
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["agents", "list"])
        assert result.exit_code == 0
        assert "agent-inv" in result.output
        assert "agent-sec" in result.output
        assert "2 total" in result.output

    @patch(_PATCH_GET_CLIENT)
    def test_agents_get(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (
                200,
                {
                    "agent_id": "agent-inv",
                    "agent_type": "investigation",
                    "environment": "production",
                    "status": "active",
                    "last_heartbeat": "2025-01-01T00:00:00Z",
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["agents", "get", "agent-inv"])
        assert result.exit_code == 0
        assert "agent-inv" in result.output
        assert "investigation" in result.output


# ---------------------------------------------------------------------------
# Scan commands
# ---------------------------------------------------------------------------


class TestScanCommands:
    """Tests for ``shieldops scan`` subcommands."""

    @patch(_PATCH_GET_CLIENT)
    def test_scan_list(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (
                200,
                {
                    "scans": [
                        {
                            "scan_id": "scan-001",
                            "scan_type": "full",
                            "environment": "production",
                            "status": "complete",
                            "created_at": "2025-01-01T00:00:00Z",
                        }
                    ],
                    "total": 1,
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "list"])
        assert result.exit_code == 0
        assert "scan-001" in result.output
        assert "full" in result.output

    @patch(_PATCH_GET_CLIENT)
    def test_scan_start(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (
                202,
                {
                    "status": "accepted",
                    "scan_type": "cve_only",
                    "environment": "staging",
                    "message": "Security scan started.",
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scan", "start", "--type", "cve_only", "--environment", "staging"],
        )
        assert result.exit_code == 0
        assert "Security scan" in result.output
        assert "cve_only" in result.output


# ---------------------------------------------------------------------------
# Output format tests
# ---------------------------------------------------------------------------


class TestOutputFormats:
    """Tests for --format json and --format table global option."""

    @patch(_PATCH_GET_CLIENT)
    def test_json_output_format(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (
                200,
                {
                    "agents": [
                        {
                            "agent_id": "a1",
                            "agent_type": "investigation",
                            "environment": "prod",
                            "status": "active",
                            "last_heartbeat": "2025-01-01T00:00:00Z",
                        }
                    ],
                    "total": 1,
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "json", "agents", "list"])
        assert result.exit_code == 0
        import json

        parsed = json.loads(result.output)
        assert "agents" in parsed

    @patch(_PATCH_GET_CLIENT)
    def test_table_output_format(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (
                200,
                {
                    "agents": [
                        {
                            "agent_id": "a1",
                            "agent_type": "investigation",
                            "environment": "prod",
                            "status": "active",
                            "last_heartbeat": "2025-01-01",
                        }
                    ],
                    "total": 1,
                },
            ),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "table", "agents", "list"])
        assert result.exit_code == 0
        assert "+" in result.output
        assert "|" in result.output


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for graceful error handling across the CLI."""

    @patch(_PATCH_GET_CLIENT)
    def test_connection_error_handled(self, mock_gc: MagicMock) -> None:
        """Connection errors produce a user-friendly message, not a traceback."""
        client = MagicMock()
        client.request.side_effect = httpx.ConnectError("Connection refused")
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        mock_gc.return_value = client

        runner = CliRunner()
        result = runner.invoke(cli, ["agents", "list"])
        assert "Could not connect" in result.output
        assert "Traceback" not in result.output

    @patch(_PATCH_GET_CLIENT)
    def test_timeout_error_handled(self, mock_gc: MagicMock) -> None:
        client = MagicMock()
        client.request.side_effect = httpx.ReadTimeout("timed out")
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        mock_gc.return_value = client

        runner = CliRunner()
        result = runner.invoke(cli, ["agents", "list"])
        assert "timed out" in result.output.lower()

    @patch(_PATCH_GET_CLIENT)
    def test_401_error_handled(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (401, {"detail": "Not authenticated"}),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["agents", "list"])
        assert "Authentication required" in result.output

    @patch(_PATCH_GET_CLIENT)
    def test_404_error_handled(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (404, {"detail": "Agent not found"}),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["agents", "get", "nonexistent"])
        assert "Not found" in result.output


# ---------------------------------------------------------------------------
# API key propagation
# ---------------------------------------------------------------------------


class TestAPIKeyPropagation:
    """Tests that --api-key is forwarded to the HTTP client builder."""

    @patch(_PATCH_GET_CLIENT)
    def test_api_key_header_sent(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (200, {"status": "healthy", "version": "0.1.0"}),
            (200, {"agents": [], "total": 0}),
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--api-key", "test-secret-key", "status"],
        )
        assert result.exit_code == 0

        # get_client is called with the Click context -- inspect it
        ctx_arg = mock_gc.call_args[0][0]
        assert ctx_arg.obj["api_key"] == "test-secret-key"

    @patch(_PATCH_GET_CLIENT)
    def test_no_auth_header_when_no_key(self, mock_gc: MagicMock) -> None:
        mock_gc.return_value = _fake_client(
            (200, {"status": "healthy", "version": "0.1.0"}),
            (200, {"agents": [], "total": 0}),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

        ctx_arg = mock_gc.call_args[0][0]
        assert ctx_arg.obj["api_key"] is None


# ---------------------------------------------------------------------------
# Serve command (local, no API needed)
# ---------------------------------------------------------------------------


class TestServeCommand:
    """Tests for ``shieldops serve``."""

    def test_serve_command_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--reload" in result.output

    @patch("uvicorn.run")
    def test_serve_command(self, mock_uvicorn_run: MagicMock) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["serve", "--host", "127.0.0.1", "--port", "9000"],
        )
        assert result.exit_code == 0
        mock_uvicorn_run.assert_called_once_with(
            "shieldops.api.app:app",
            host="127.0.0.1",
            port=9000,
            reload=False,
        )


# ---------------------------------------------------------------------------
# Output module unit tests
# ---------------------------------------------------------------------------


class TestOutputHelpers:
    """Unit tests for the output formatting module."""

    def test_print_table_empty_headers(self, capsys: pytest.CaptureFixture[str]) -> None:
        """print_table with empty headers should be a no-op."""
        from shieldops.cli.output import print_table

        print_table([], [])
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_table_alignment(self, capsys: pytest.CaptureFixture[str]) -> None:
        """print_table aligns columns correctly."""
        from shieldops.cli.output import print_table

        print_table(
            ["Name", "Value"],
            [["short", "x"], ["longer-name", "y"]],
        )
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        sep_lines = [ln for ln in lines if ln.startswith("+")]
        assert len(sep_lines) >= 2
        assert all(len(s) == len(sep_lines[0]) for s in sep_lines)
