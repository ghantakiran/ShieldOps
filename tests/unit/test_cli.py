"""Tests for the ShieldOps CLI entry point."""

from unittest.mock import patch

from click.testing import CliRunner

from shieldops.cli import main


class TestCLI:
    """Tests for the Click CLI commands."""

    def test_main_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "ShieldOps" in result.output

    def test_status_command(self):
        runner = CliRunner()
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "ShieldOps v" in result.output
        assert "Environment:" in result.output

    def test_serve_command_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--reload" in result.output

    @patch("shieldops.cli.uvicorn.run")
    def test_serve_command(self, mock_uvicorn_run):
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--host", "127.0.0.1", "--port", "9000"])
        assert result.exit_code == 0
        mock_uvicorn_run.assert_called_once_with(
            "shieldops.api.app:app",
            host="127.0.0.1",
            port=9000,
            reload=False,
        )

    def test_version_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
