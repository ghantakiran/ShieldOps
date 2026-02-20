"""Helpers for data export formatting."""

from __future__ import annotations

import csv
import io
from typing import Any


def dicts_to_csv(data: list[dict[str, Any]], fieldnames: list[str] | None = None) -> str:
    """Convert a list of dicts to CSV string.

    If *data* is empty an empty string is returned (no header row).
    Values are sanitized against CSV formula injection before writing.
    """
    if not data:
        return ""
    fieldnames = fieldnames or list(data[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    # Sanitize every cell value before writing
    for row in data:
        safe_row = {k: sanitize_for_csv(v) for k, v in row.items()}
        writer.writerow(safe_row)
    return output.getvalue()


def sanitize_for_csv(value: Any) -> str:
    """Sanitize a value for CSV output (prevent formula injection).

    Prefixes a single-quote when the string starts with characters that
    spreadsheet applications interpret as formula starters (``=``, ``+``,
    ``-``, ``@``, tab, or carriage-return).
    See OWASP CSV Injection guidelines.
    """
    s = str(value) if value is not None else ""
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s
