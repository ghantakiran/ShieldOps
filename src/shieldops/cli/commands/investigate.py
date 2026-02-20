"""Investigation commands -- shieldops investigate."""
# mypy: disable-error-code="misc,untyped-decorator"

from __future__ import annotations

from typing import Any

import click

from shieldops.cli.http import api_request
from shieldops.cli.output import print_detail, print_error, print_json, print_table


@click.group()
def investigate() -> None:
    """Manage investigation workflows."""


@investigate.command("list")
@click.option("--status", "filter_status", default=None, help="Filter by status.")
@click.option("--limit", default=50, type=int, help="Max results to return.")
@click.pass_context
def list_investigations(
    ctx: click.Context,
    filter_status: str | None,
    limit: int,
) -> None:
    """List active and recent investigations."""
    params: dict[str, Any] = {"limit": limit}
    if filter_status:
        params["status"] = filter_status

    data = api_request(ctx, "GET", "/investigations", params=params)
    if data is None:
        ctx.exit(1)
        return

    output_format: str = ctx.obj.get("format", "table")
    if output_format == "json":
        print_json(data)
        return

    investigations: list[dict[str, Any]] = data.get("investigations", [])  # type: ignore[union-attr]
    total: int = data.get("total", 0)  # type: ignore[union-attr]

    if not investigations:
        click.echo("No investigations found.")
        return

    click.echo(f"Investigations ({total} total):")
    headers = ["ID", "Alert", "Severity", "Status", "Created"]
    rows = [
        [
            str(inv.get("investigation_id", inv.get("id", ""))),
            str(inv.get("alert_name", inv.get("alert_id", ""))),
            str(inv.get("severity", "")),
            str(inv.get("status", "")),
            str(inv.get("created_at", inv.get("triggered_at", ""))),
        ]
        for inv in investigations
    ]
    print_table(headers, rows)


@investigate.command("get")
@click.argument("investigation_id")
@click.pass_context
def get_investigation(ctx: click.Context, investigation_id: str) -> None:
    """Show details for a specific investigation."""
    data = api_request(ctx, "GET", f"/investigations/{investigation_id}")
    if data is None:
        ctx.exit(1)
        return

    output_format: str = ctx.obj.get("format", "table")
    if output_format == "json":
        print_json(data)
        return

    click.echo(f"Investigation: {investigation_id}")
    click.echo("-" * 40)
    for key in ("alert_name", "severity", "status", "confidence", "created_at"):
        value = data.get(key)  # type: ignore[union-attr]
        if value is not None:
            print_detail(key.replace("_", " ").title(), value)

    # Show hypotheses if present
    hypotheses = data.get("hypotheses", [])  # type: ignore[union-attr]
    if hypotheses:
        click.echo()
        click.echo("Hypotheses:")
        for i, hyp in enumerate(hypotheses, 1):
            if isinstance(hyp, dict):
                click.echo(f"  {i}. {hyp.get('description', hyp.get('title', str(hyp)))}")
            else:
                click.echo(f"  {i}. {hyp}")


@investigate.command("start")
@click.option("--alert-id", required=True, help="Alert ID to investigate.")
@click.option("--alert-name", default="", help="Human-readable alert name.")
@click.option(
    "--severity",
    default="warning",
    type=click.Choice(["critical", "warning", "info"]),
    help="Alert severity.",
)
@click.option("--environment", default="production", help="Target environment.")
@click.pass_context
def start_investigation(
    ctx: click.Context,
    alert_id: str,
    alert_name: str,
    severity: str,
    environment: str,
) -> None:
    """Start a new investigation for an alert."""
    body = {
        "alert_id": alert_id,
        "alert_name": alert_name or alert_id,
        "severity": severity,
        "source": "cli",
        "labels": {"environment": environment},
    }

    data = api_request(ctx, "POST", "/investigations", json_body=body)
    if data is None:
        ctx.exit(1)
        return

    output_format: str = ctx.obj.get("format", "table")
    if output_format == "json":
        print_json(data)
        return

    status_val = data.get("status", "unknown")  # type: ignore[union-attr]
    msg = data.get("message", "")  # type: ignore[union-attr]
    if status_val == "accepted":
        click.echo(f"Investigation started for alert '{alert_id}'.")
        if msg:
            click.echo(f"  {msg}")
    else:
        print_error(f"Unexpected response: {data}")
