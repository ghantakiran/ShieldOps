"""Legacy CLI test file -- delegates to tests/unit/cli/test_cli.py.

This file is kept for backwards compatibility. The old shieldops.cli module
has been restructured into a package (shieldops.cli.*). The comprehensive
CLI tests now live in tests/unit/cli/test_cli.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from shieldops.cli.main import cli


class TestCLI:
    """Minimal smoke tests that mirror the original test_cli.py contract."""

    def test_main_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "ShieldOps" in result.output

    @patch("shieldops.cli.http.get_client")
    def test_status_command(self, mock_gc: MagicMock) -> None:
        client = MagicMock()
        health_resp = MagicMock()
        health_resp.status_code = 200
        health_resp.json.return_value = {"status": "healthy", "version": "0.1.0"}
        agents_resp = MagicMock()
        agents_resp.status_code = 200
        agents_resp.json.return_value = {"agents": [], "total": 0}
        client.request.side_effect = [health_resp, agents_resp]
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        mock_gc.return_value = client

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "ShieldOps" in result.output

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
        result = runner.invoke(cli, ["serve", "--host", "127.0.0.1", "--port", "9000"])
        assert result.exit_code == 0
        mock_uvicorn_run.assert_called_once_with(
            "shieldops.api.app:app",
            host="127.0.0.1",
            port=9000,
            reload=False,
        )

    def test_version_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
