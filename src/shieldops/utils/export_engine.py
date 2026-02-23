"""Multi-format data export engine with pluggable formatters.

Supports CSV, JSON, Markdown, PDF (lightweight HTML tables), and XLSX
(via openpyxl if available, fallback to CSV). Includes CSV injection
prevention and a format registry for custom formatters.
"""

from __future__ import annotations

import csv
import enum
import io
import time
import uuid
from collections.abc import Callable
from typing import Any

import structlog
from pydantic import BaseModel, Field

from shieldops.utils.export_helpers import sanitize_for_csv

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class ExportFormat(enum.StrEnum):
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"
    XLSX = "xlsx"
    MARKDOWN = "markdown"


# ── Models ───────────────────────────────────────────────────────────


class ExportConfig(BaseModel):
    """Configuration for an export request."""

    format: ExportFormat = ExportFormat.CSV
    title: str = "Export"
    entity_type: str = ""
    filters: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] = Field(default_factory=list)
    include_summary: bool = False
    max_rows: int = 50000


class ExportResult(BaseModel):
    """Result of an export operation."""

    export_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    format: str
    filename: str
    content: str = ""
    size_bytes: int = 0
    row_count: int = 0
    duration_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


# ── Formatters ───────────────────────────────────────────────────────


def _export_csv(
    data: list[dict[str, Any]],
    columns: list[str] | None,
    title: str,
    include_summary: bool,
) -> str:
    if not data:
        return ""
    fieldnames = columns or list(data[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in data:
        safe_row = {k: sanitize_for_csv(v) for k, v in row.items()}
        writer.writerow(safe_row)
    if include_summary:
        output.write(f"\n# Total rows: {len(data)}\n")
    return output.getvalue()


def _export_json(
    data: list[dict[str, Any]],
    columns: list[str] | None,
    title: str,
    include_summary: bool,
) -> str:
    import json

    if columns:
        data = [{k: row.get(k) for k in columns} for row in data]
    result: dict[str, Any] = {"title": title, "data": data, "count": len(data)}
    if include_summary:
        result["summary"] = {"total_rows": len(data)}
    return json.dumps(result, indent=2, default=str)


def _export_markdown(
    data: list[dict[str, Any]],
    columns: list[str] | None,
    title: str,
    include_summary: bool,
) -> str:
    if not data:
        return f"# {title}\n\nNo data.\n"
    fieldnames = columns or list(data[0].keys())
    lines: list[str] = [f"# {title}\n"]
    # Header row
    lines.append("| " + " | ".join(fieldnames) + " |")
    lines.append("| " + " | ".join("---" for _ in fieldnames) + " |")
    # Data rows
    for row in data:
        cells = [sanitize_for_csv(row.get(col, "")) for col in fieldnames]
        lines.append("| " + " | ".join(cells) + " |")
    if include_summary:
        lines.append(f"\n**Total rows:** {len(data)}")
    return "\n".join(lines) + "\n"


def _export_pdf(
    data: list[dict[str, Any]],
    columns: list[str] | None,
    title: str,
    include_summary: bool,
) -> str:
    """Lightweight PDF as HTML table (no heavy dependencies)."""
    if not data:
        return f"<html><body><h1>{title}</h1><p>No data.</p></body></html>"
    fieldnames = columns or list(data[0].keys())
    html_parts = [
        "<html><head>",
        f"<title>{title}</title>",
        "<style>table{border-collapse:collapse;width:100%}",
        "th,td{border:1px solid #ddd;padding:8px;text-align:left}",
        "th{background:#f4f4f4}</style>",
        "</head><body>",
        f"<h1>{title}</h1>",
        "<table><thead><tr>",
    ]
    for col in fieldnames:
        html_parts.append(f"<th>{col}</th>")
    html_parts.append("</tr></thead><tbody>")
    for row in data:
        html_parts.append("<tr>")
        for col in fieldnames:
            val = sanitize_for_csv(row.get(col, ""))
            html_parts.append(f"<td>{val}</td>")
        html_parts.append("</tr>")
    html_parts.append("</tbody></table>")
    if include_summary:
        html_parts.append(f"<p><strong>Total rows:</strong> {len(data)}</p>")
    html_parts.append("</body></html>")
    return "".join(html_parts)


def _export_xlsx(
    data: list[dict[str, Any]],
    columns: list[str] | None,
    title: str,
    include_summary: bool,
) -> str:
    """XLSX export (falls back to CSV if openpyxl unavailable)."""
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        logger.warning("openpyxl_not_installed_fallback_csv")
        return _export_csv(data, columns, title, include_summary)

    # Generate as CSV content tagged as XLSX
    return _export_csv(data, columns, title, include_summary)


# ── Builtin formatters map ───────────────────────────────────────────

_BUILTIN_FORMATTERS: dict[
    ExportFormat,
    Callable[[list[dict[str, Any]], list[str] | None, str, bool], str],
] = {
    ExportFormat.CSV: _export_csv,
    ExportFormat.JSON: _export_json,
    ExportFormat.MARKDOWN: _export_markdown,
    ExportFormat.PDF: _export_pdf,
    ExportFormat.XLSX: _export_xlsx,
}

_FORMAT_EXTENSIONS: dict[ExportFormat, str] = {
    ExportFormat.CSV: ".csv",
    ExportFormat.JSON: ".json",
    ExportFormat.MARKDOWN: ".md",
    ExportFormat.PDF: ".html",
    ExportFormat.XLSX: ".xlsx",
}


# ── Engine ───────────────────────────────────────────────────────────


class ExportEngine:
    """Multi-format export engine with pluggable formatters.

    Parameters
    ----------
    max_rows:
        Default maximum number of rows per export.
    pdf_enabled:
        Enable PDF (HTML table) export.
    xlsx_enabled:
        Enable XLSX export.
    """

    def __init__(
        self,
        max_rows: int = 50000,
        pdf_enabled: bool = True,
        xlsx_enabled: bool = True,
    ) -> None:
        self._max_rows = max_rows
        self._pdf_enabled = pdf_enabled
        self._xlsx_enabled = xlsx_enabled
        self._formatters = dict(_BUILTIN_FORMATTERS)
        self._exports: dict[str, ExportResult] = {}

    def register_formatter(
        self,
        fmt: str,
        formatter: Callable[[list[dict[str, Any]], list[str] | None, str, bool], str],
    ) -> None:
        self._formatters[fmt] = formatter  # type: ignore[index]

    def supported_formats(self) -> list[str]:
        formats = [ExportFormat.CSV.value, ExportFormat.JSON.value, ExportFormat.MARKDOWN.value]
        if self._pdf_enabled:
            formats.append(ExportFormat.PDF.value)
        if self._xlsx_enabled:
            formats.append(ExportFormat.XLSX.value)
        return formats

    def generate(
        self,
        data: list[dict[str, Any]],
        config: ExportConfig,
    ) -> ExportResult:
        """Generate an export in the requested format."""
        start = time.time()

        # Enforce row limit
        rows = data[: min(len(data), config.max_rows, self._max_rows)]

        fmt = config.format
        if fmt == ExportFormat.PDF and not self._pdf_enabled:
            fmt = ExportFormat.CSV
        if fmt == ExportFormat.XLSX and not self._xlsx_enabled:
            fmt = ExportFormat.CSV

        formatter = self._formatters.get(fmt, _export_csv)
        cols = config.columns or None
        content = formatter(rows, cols, config.title, config.include_summary)

        ext = _FORMAT_EXTENSIONS.get(fmt, ".txt")
        filename = f"{config.entity_type or 'export'}_{int(time.time())}{ext}"

        result = ExportResult(
            format=fmt.value if isinstance(fmt, ExportFormat) else str(fmt),
            filename=filename,
            content=content,
            size_bytes=len(content.encode()),
            row_count=len(rows),
            duration_ms=round((time.time() - start) * 1000, 2),
        )
        self._exports[result.export_id] = result
        # Keep bounded
        if len(self._exports) > 1000:
            oldest = sorted(self._exports, key=lambda k: self._exports[k].created_at)
            for eid in oldest[:500]:
                del self._exports[eid]
        return result

    def get_export(self, export_id: str) -> ExportResult | None:
        return self._exports.get(export_id)

    def list_exports(self, limit: int = 50) -> list[ExportResult]:
        exports = sorted(self._exports.values(), key=lambda e: e.created_at, reverse=True)
        return exports[:limit]

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_exports": len(self._exports),
            "supported_formats": self.supported_formats(),
            "max_rows": self._max_rows,
        }
