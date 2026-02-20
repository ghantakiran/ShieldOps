"""Agent management commands -- shieldops agents."""
# mypy: disable-error-code="misc,untyped-decorator"

from __future__ import annotations

from typing import Any

import click

from shieldops.cli.http import api_request
from shieldops.cli.output import print_detail, print_json, print_table


@click.group()
def agents() -> None:
    """Manage the agent fleet."""


@agents.command("list")
@click.option("--environment", default=None, help="Filter by environment.")
@click.option("--status", "filter_status", default=None, help="Filter by status.")
@click.pass_context
def list_agents(
    ctx: click.Context,
    environment: str | None,
    filter_status: str | None,
) -> None:
    """List all deployed agents with status and health."""
    params: dict[str, Any] = {}
    if environment:
        params["environment"] = environment
    if filter_status:
        params["status"] = filter_status

    data = api_request(ctx, "GET", "/agents", params=params)
    if data is None:
        ctx.exit(1)
        return

    output_format: str = ctx.obj.get("format", "table")
    if output_format == "json":
        print_json(data)
        return

    agent_list: list[dict[str, Any]] = data.get("agents", [])  # type: ignore[union-attr]
    total: int = data.get("total", len(agent_list))  # type: ignore[union-attr]

    if not agent_list:
        click.echo("No agents found.")
        return

    click.echo(f"Agents ({total} total):")
    headers = ["ID", "Type", "Environment", "Status", "Last Heartbeat"]
    rows = [
        [
            str(a.get("agent_id", a.get("id", ""))),
            str(a.get("agent_type", "")),
            str(a.get("environment", "")),
            str(a.get("status", "")),
            str(a.get("last_heartbeat", "")),
        ]
        for a in agent_list
    ]
    print_table(headers, rows)


@agents.command("get")
@click.argument("agent_id")
@click.pass_context
def get_agent(ctx: click.Context, agent_id: str) -> None:
    """Show detailed information for a specific agent."""
    data = api_request(ctx, "GET", f"/agents/{agent_id}")
    if data is None:
        ctx.exit(1)
        return

    output_format: str = ctx.obj.get("format", "table")
    if output_format == "json":
        print_json(data)
        return

    click.echo(f"Agent: {agent_id}")
    click.echo("-" * 40)
    for key in (
        "agent_type",
        "environment",
        "status",
        "last_heartbeat",
        "created_at",
        "version",
    ):
        value = data.get(key)  # type: ignore[union-attr]
        if value is not None:
            print_detail(key.replace("_", " ").title(), value)
