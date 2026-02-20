"""Platform status command -- shieldops status."""
# mypy: disable-error-code="misc,untyped-decorator"

from __future__ import annotations

from typing import Any

import click

from shieldops.cli.http import api_request
from shieldops.cli.output import print_json, print_status, print_table


@click.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show platform health, API version, and agent fleet summary."""
    output_format: str = ctx.obj.get("format", "table")

    # -- Health check --
    health = api_request(ctx, "GET", "/health")
    if health is None:
        # Connection failed; already printed an error
        ctx.exit(1)
        return

    # -- Agent fleet summary --
    agents_data = api_request(ctx, "GET", "/agents")

    if output_format == "json":
        print_json({"health": health, "agents": agents_data})
        return

    # Table output
    click.echo("ShieldOps Platform Status")
    click.echo("=" * 40)
    if not isinstance(health, dict):
        print_status("API", "unexpected response", ok=False)
        return
    print_status(
        "API",
        f"v{health.get('version', 'unknown')}",
        ok=health.get("status") == "healthy",
    )

    if agents_data and isinstance(agents_data, dict):
        agent_list: list[dict[str, Any]] = agents_data.get("agents", [])
        total = agents_data.get("total", len(agent_list))
        print_status("Agents", f"{total} registered", ok=total > 0)

        if agent_list:
            click.echo()
            click.echo("Agent Fleet:")
            headers = ["ID", "Type", "Environment", "Status"]
            rows = [
                [
                    str(a.get("agent_id", a.get("id", ""))),
                    str(a.get("agent_type", "")),
                    str(a.get("environment", "")),
                    str(a.get("status", "")),
                ]
                for a in agent_list
            ]
            print_table(headers, rows)
    else:
        print_status("Agents", "unavailable", ok=False)
