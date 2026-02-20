"""Remediation commands -- shieldops remediate."""
# mypy: disable-error-code="misc,untyped-decorator"

from __future__ import annotations

from typing import Any

import click

from shieldops.cli.http import api_request
from shieldops.cli.output import print_detail, print_error, print_json, print_table


@click.group()
def remediate() -> None:
    """Manage remediation workflows."""


@remediate.command("list")
@click.option("--status", "filter_status", default=None, help="Filter by status.")
@click.option("--environment", default=None, help="Filter by environment.")
@click.option("--limit", default=50, type=int, help="Max results to return.")
@click.pass_context
def list_remediations(
    ctx: click.Context,
    filter_status: str | None,
    environment: str | None,
    limit: int,
) -> None:
    """List remediation actions."""
    params: dict[str, Any] = {"limit": limit}
    if filter_status:
        params["status"] = filter_status
    if environment:
        params["environment"] = environment

    data = api_request(ctx, "GET", "/remediations", params=params)
    if data is None:
        ctx.exit(1)
        return

    output_format: str = ctx.obj.get("format", "table")
    if output_format == "json":
        print_json(data)
        return

    remediations: list[dict[str, Any]] = data.get("remediations", [])  # type: ignore[union-attr]
    total: int = data.get("total", 0)  # type: ignore[union-attr]

    if not remediations:
        click.echo("No remediations found.")
        return

    click.echo(f"Remediations ({total} total):")
    headers = ["ID", "Action", "Target", "Environment", "Status"]
    rows = [
        [
            str(r.get("remediation_id", r.get("id", ""))),
            str(r.get("action_type", "")),
            str(r.get("target_resource", "")),
            str(r.get("environment", "")),
            str(r.get("status", "")),
        ]
        for r in remediations
    ]
    print_table(headers, rows)


@remediate.command("get")
@click.argument("remediation_id")
@click.pass_context
def get_remediation(ctx: click.Context, remediation_id: str) -> None:
    """Show details for a specific remediation."""
    data = api_request(ctx, "GET", f"/remediations/{remediation_id}")
    if data is None:
        ctx.exit(1)
        return

    output_format: str = ctx.obj.get("format", "table")
    if output_format == "json":
        print_json(data)
        return

    click.echo(f"Remediation: {remediation_id}")
    click.echo("-" * 40)
    for key in (
        "action_type",
        "target_resource",
        "environment",
        "risk_level",
        "status",
        "description",
        "created_at",
    ):
        value = data.get(key)  # type: ignore[union-attr]
        if value is not None:
            print_detail(key.replace("_", " ").title(), value)


@remediate.command("rollback")
@click.argument("remediation_id")
@click.option("--reason", default="", help="Reason for rollback.")
@click.pass_context
def rollback_remediation(
    ctx: click.Context,
    remediation_id: str,
    reason: str,
) -> None:
    """Rollback a completed remediation to its pre-action state."""
    body = {"reason": reason} if reason else {}

    data = api_request(
        ctx,
        "POST",
        f"/remediations/{remediation_id}/rollback",
        json_body=body,
    )
    if data is None:
        ctx.exit(1)
        return

    output_format: str = ctx.obj.get("format", "table")
    if output_format == "json":
        print_json(data)
        return

    action = data.get("action", "unknown")  # type: ignore[union-attr]
    status_val = data.get("status", "")  # type: ignore[union-attr]
    msg = data.get("message", "")  # type: ignore[union-attr]

    if action == "rollback_initiated":
        click.echo(f"Rollback initiated for remediation '{remediation_id}'.")
        if status_val:
            click.echo(f"  Status: {status_val}")
        if msg:
            click.echo(f"  {msg}")
    else:
        print_error(f"Unexpected response: {data}")
