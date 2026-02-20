"""ShieldOps CLI -- command-line interface for SRE operations."""
# mypy: disable-error-code="misc,untyped-decorator"

from __future__ import annotations

import click

from shieldops.cli.commands.agents import agents
from shieldops.cli.commands.investigate import investigate
from shieldops.cli.commands.remediate import remediate
from shieldops.cli.commands.scan import scan
from shieldops.cli.commands.status import status


@click.group()
@click.option(
    "--api-url",
    envvar="SHIELDOPS_API_URL",
    default="http://localhost:8000/api/v1",
    help="Base URL of the ShieldOps API.",
)
@click.option(
    "--api-key",
    envvar="SHIELDOPS_API_KEY",
    default=None,
    help="API key for authentication.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format.",
)
@click.version_option(package_name="shieldops")
@click.pass_context
def cli(
    ctx: click.Context,
    api_url: str,
    api_key: str | None,
    output_format: str,
) -> None:
    """ShieldOps -- AI-Powered Autonomous SRE Platform CLI."""
    ctx.ensure_object(dict)
    ctx.obj["api_url"] = api_url
    ctx.obj["api_key"] = api_key
    ctx.obj["format"] = output_format


# -- Subcommands that talk to the API --
cli.add_command(status)
cli.add_command(investigate)
cli.add_command(remediate)
cli.add_command(agents)
cli.add_command(scan)


# -- Local-only commands (no API required) --


@cli.command()
@click.option("--host", default="0.0.0.0", help="API server host.")  # noqa: S104  # nosec B104
@click.option("--port", default=8000, type=int, help="API server port.")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development.")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the ShieldOps API server."""
    import uvicorn

    uvicorn.run(
        "shieldops.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    cli()
