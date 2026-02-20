"""Output formatting utilities for the CLI."""

from __future__ import annotations

import json
import sys
from typing import Any

import click


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a formatted ASCII table with dynamic column widths.

    Calculates optimal column widths based on header and cell content,
    then renders a bordered ASCII table to stdout.
    """
    if not headers:
        return

    # Calculate column widths: max of header width and all cell widths per column
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Build format string for each row
    def _fmt_row(cells: list[str]) -> str:
        parts = []
        for i, cell in enumerate(cells):
            width = col_widths[i] if i < len(col_widths) else len(str(cell))
            parts.append(str(cell).ljust(width))
        return "| " + " | ".join(parts) + " |"

    # Separator line
    separator = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"

    click.echo(separator)
    click.echo(_fmt_row(headers))
    click.echo(separator)
    for row in rows:
        # Pad row to match header count if needed
        padded = list(row) + [""] * (len(headers) - len(row))
        click.echo(_fmt_row(padded[: len(headers)]))
    click.echo(separator)


def print_json(data: Any) -> None:
    """Print data as formatted JSON to stdout."""
    json.dump(data, sys.stdout, indent=2, default=str)
    click.echo()  # trailing newline


def print_status(label: str, value: str, *, ok: bool = True) -> None:
    """Print a status line with a pass/fail indicator."""
    indicator = "[OK]" if ok else "[FAIL]"
    click.echo(f"  {indicator} {label}: {value}")


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    click.echo(f"Error: {message}", err=True)


def print_detail(label: str, value: Any) -> None:
    """Print a key-value detail line."""
    click.echo(f"  {label}: {value}")
