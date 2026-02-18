"""ShieldOps CLI entry point."""

import click
import uvicorn

from shieldops.config import settings


@click.group()  # type: ignore[untyped-decorator]
@click.version_option(version=settings.app_version)  # type: ignore[untyped-decorator]
def main() -> None:
    """ShieldOps - AI-Powered Autonomous SRE Platform."""


@main.command()  # type: ignore[untyped-decorator]
@click.option("--host", default=settings.api_host, help="API host")  # type: ignore[untyped-decorator]
@click.option("--port", default=settings.api_port, type=int, help="API port")  # type: ignore[untyped-decorator]
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")  # type: ignore[untyped-decorator]
def serve(host: str, port: int, reload: bool) -> None:
    """Start the ShieldOps API server."""
    uvicorn.run(
        "shieldops.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


@main.command()  # type: ignore[untyped-decorator]
def status() -> None:
    """Show ShieldOps agent status."""
    click.echo(f"ShieldOps v{settings.app_version}")
    click.echo(f"Environment: {settings.environment}")
    click.echo("Agent status: Not connected (run 'shieldops serve' first)")


if __name__ == "__main__":
    main()
