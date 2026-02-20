"""Security scan commands -- shieldops scan."""
# mypy: disable-error-code="misc,untyped-decorator"

from __future__ import annotations

from typing import Any

import click

from shieldops.cli.http import api_request
from shieldops.cli.output import print_error, print_json, print_table


@click.group()
def scan() -> None:
    """Manage security scans."""


@scan.command("list")
@click.option("--type", "scan_type", default=None, help="Filter by scan type.")
@click.option("--limit", default=50, type=int, help="Max results to return.")
@click.pass_context
def list_scans(
    ctx: click.Context,
    scan_type: str | None,
    limit: int,
) -> None:
    """List security scans."""
    params: dict[str, Any] = {"limit": limit}
    if scan_type:
        params["scan_type"] = scan_type

    data = api_request(ctx, "GET", "/security/scans", params=params)
    if data is None:
        ctx.exit(1)
        return

    output_format: str = ctx.obj.get("format", "table")
    if output_format == "json":
        print_json(data)
        return

    scans: list[dict[str, Any]] = data.get("scans", [])  # type: ignore[union-attr]
    total: int = data.get("total", 0)  # type: ignore[union-attr]

    if not scans:
        click.echo("No security scans found.")
        return

    click.echo(f"Security Scans ({total} total):")
    headers = ["ID", "Type", "Environment", "Status", "Created"]
    rows = [
        [
            str(s.get("scan_id", s.get("id", ""))),
            str(s.get("scan_type", "")),
            str(s.get("environment", "")),
            str(s.get("status", "")),
            str(s.get("created_at", s.get("started_at", ""))),
        ]
        for s in scans
    ]
    print_table(headers, rows)


@scan.command("start")
@click.option(
    "--type",
    "scan_type",
    default="full",
    type=click.Choice(["full", "cve_only", "credentials_only", "compliance_only"]),
    help="Type of security scan.",
)
@click.option("--environment", default="production", help="Target environment.")
@click.pass_context
def start_scan(
    ctx: click.Context,
    scan_type: str,
    environment: str,
) -> None:
    """Start a new security scan."""
    body = {
        "scan_type": scan_type,
        "environment": environment,
    }

    data = api_request(ctx, "POST", "/security/scans", json_body=body)
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
        click.echo(f"Security scan ({scan_type}) started for '{environment}'.")
        if msg:
            click.echo(f"  {msg}")
    else:
        print_error(f"Unexpected response: {data}")
