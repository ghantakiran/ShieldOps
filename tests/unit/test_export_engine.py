"""Tests for shieldops.utils.export_engine – ExportEngine multi-format exporter."""

from __future__ import annotations

import json
from unittest.mock import patch

from shieldops.utils.export_engine import (
    ExportConfig,
    ExportEngine,
    ExportFormat,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_data(n: int = 3) -> list[dict]:
    return [{"id": i, "name": f"item-{i}", "value": i * 10} for i in range(1, n + 1)]


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


class TestExportCSV:
    def test_csv_basic_export(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV, title="Test")
        result = engine.generate(_sample_data(), config)
        assert result.format == "csv"
        assert "id,name,value" in result.content
        assert "item-1" in result.content

    def test_csv_sanitizes_formula_injection(self):
        engine = ExportEngine()
        data = [{"name": "=cmd|'/C calc'!A0", "score": "+1"}]
        config = ExportConfig(format=ExportFormat.CSV)
        result = engine.generate(data, config)
        # Values starting with = or + should be prefixed with '
        assert "'=cmd" in result.content
        assert "'+1" in result.content

    def test_csv_empty_data(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV)
        result = engine.generate([], config)
        assert result.content == ""
        assert result.row_count == 0

    def test_csv_with_include_summary(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV, include_summary=True)
        result = engine.generate(_sample_data(5), config)
        assert "Total rows: 5" in result.content

    def test_csv_custom_columns(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV, columns=["id", "name"])
        result = engine.generate(_sample_data(), config)
        lines = result.content.strip().split("\n")
        header = lines[0]
        assert "id" in header
        assert "name" in header
        # value column should not appear in header
        assert header.count("value") == 0


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


class TestExportJSON:
    def test_json_basic_export(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.JSON, title="Report")
        result = engine.generate(_sample_data(), config)
        parsed = json.loads(result.content)
        assert parsed["title"] == "Report"
        assert parsed["count"] == 3
        assert len(parsed["data"]) == 3

    def test_json_with_columns_filter(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.JSON, columns=["id", "name"])
        result = engine.generate(_sample_data(), config)
        parsed = json.loads(result.content)
        for row in parsed["data"]:
            assert "id" in row
            assert "name" in row
            assert "value" not in row or row.get("value") is None

    def test_json_include_summary(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.JSON, include_summary=True)
        result = engine.generate(_sample_data(2), config)
        parsed = json.loads(result.content)
        assert "summary" in parsed
        assert parsed["summary"]["total_rows"] == 2

    def test_json_empty_data(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.JSON)
        result = engine.generate([], config)
        parsed = json.loads(result.content)
        assert parsed["count"] == 0
        assert parsed["data"] == []


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------


class TestExportMarkdown:
    def test_markdown_table_format(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.MARKDOWN, title="MD Report")
        result = engine.generate(_sample_data(), config)
        assert "# MD Report" in result.content
        assert "| id | name | value |" in result.content
        assert "| --- | --- | --- |" in result.content
        assert "| item-1 |" in result.content

    def test_markdown_empty_data(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.MARKDOWN, title="Empty")
        result = engine.generate([], config)
        assert "No data." in result.content

    def test_markdown_with_summary(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.MARKDOWN, include_summary=True)
        result = engine.generate(_sample_data(4), config)
        assert "**Total rows:** 4" in result.content


# ---------------------------------------------------------------------------
# PDF (HTML table) export
# ---------------------------------------------------------------------------


class TestExportPDF:
    def test_pdf_produces_html_table(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.PDF, title="PDF Report")
        result = engine.generate(_sample_data(), config)
        assert "<html>" in result.content
        assert "<table>" in result.content
        assert "<th>id</th>" in result.content
        assert "PDF Report" in result.content

    def test_pdf_empty_data(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.PDF, title="Empty PDF")
        result = engine.generate([], config)
        assert "No data." in result.content
        assert "<html>" in result.content

    def test_pdf_with_summary(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.PDF, include_summary=True)
        result = engine.generate(_sample_data(2), config)
        assert "Total rows:" in result.content
        assert "<strong>" in result.content

    def test_pdf_disabled_falls_back_to_csv(self):
        engine = ExportEngine(pdf_enabled=False)
        config = ExportConfig(format=ExportFormat.PDF)
        result = engine.generate(_sample_data(), config)
        assert result.format == "csv"
        assert "<html>" not in result.content


# ---------------------------------------------------------------------------
# XLSX export
# ---------------------------------------------------------------------------


class TestExportXLSX:
    def test_xlsx_fallback_to_csv_when_openpyxl_missing(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.XLSX)
        with patch.dict("sys.modules", {"openpyxl": None}):
            result = engine.generate(_sample_data(), config)
        # Should still produce valid content (CSV fallback)
        assert result.row_count == 3

    def test_xlsx_disabled_falls_back_to_csv(self):
        engine = ExportEngine(xlsx_enabled=False)
        config = ExportConfig(format=ExportFormat.XLSX)
        result = engine.generate(_sample_data(), config)
        assert result.format == "csv"


# ---------------------------------------------------------------------------
# Row limit enforcement
# ---------------------------------------------------------------------------


class TestRowLimits:
    def test_engine_max_rows_enforced(self):
        engine = ExportEngine(max_rows=5)
        config = ExportConfig(format=ExportFormat.JSON)
        result = engine.generate(_sample_data(10), config)
        parsed = json.loads(result.content)
        assert len(parsed["data"]) == 5
        assert result.row_count == 5

    def test_config_max_rows_enforced(self):
        engine = ExportEngine(max_rows=100)
        config = ExportConfig(format=ExportFormat.JSON, max_rows=3)
        result = engine.generate(_sample_data(10), config)
        parsed = json.loads(result.content)
        assert len(parsed["data"]) == 3

    def test_min_of_engine_and_config_max_rows(self):
        engine = ExportEngine(max_rows=4)
        config = ExportConfig(format=ExportFormat.JSON, max_rows=6)
        result = engine.generate(_sample_data(10), config)
        parsed = json.loads(result.content)
        assert len(parsed["data"]) == 4


# ---------------------------------------------------------------------------
# ExportResult properties
# ---------------------------------------------------------------------------


class TestExportResult:
    def test_result_has_correct_filename_extension_csv(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV, entity_type="alerts")
        result = engine.generate(_sample_data(), config)
        assert result.filename.startswith("alerts_")
        assert result.filename.endswith(".csv")

    def test_result_has_correct_filename_extension_json(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.JSON, entity_type="events")
        result = engine.generate(_sample_data(), config)
        assert result.filename.endswith(".json")

    def test_result_size_bytes_matches_content(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV)
        result = engine.generate(_sample_data(), config)
        assert result.size_bytes == len(result.content.encode())

    def test_result_row_count_matches_data(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV)
        result = engine.generate(_sample_data(7), config)
        assert result.row_count == 7

    def test_result_duration_ms_is_nonnegative(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV)
        result = engine.generate(_sample_data(), config)
        assert result.duration_ms >= 0

    def test_result_has_export_id(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV)
        result = engine.generate(_sample_data(), config)
        assert result.export_id
        assert len(result.export_id) > 0


# ---------------------------------------------------------------------------
# Custom formatter registration
# ---------------------------------------------------------------------------


class TestCustomFormatter:
    def test_register_custom_formatter_overrides_csv(self):
        engine = ExportEngine()

        def custom_fmt(data, columns, title, include_summary):
            return f"CUSTOM:{len(data)}"

        engine.register_formatter(ExportFormat.CSV, custom_fmt)
        config = ExportConfig(format=ExportFormat.CSV, title="X")
        result = engine.generate(_sample_data(4), config)
        assert result.content == "CUSTOM:4"

    def test_register_overrides_builtin(self):
        engine = ExportEngine()
        original_config = ExportConfig(format=ExportFormat.CSV)
        original = engine.generate(_sample_data(), original_config)
        assert "id" in original.content

        def override_csv(data, columns, title, include_summary):
            return "OVERRIDDEN"

        engine.register_formatter(ExportFormat.CSV, override_csv)
        result = engine.generate(_sample_data(), original_config)
        assert result.content == "OVERRIDDEN"


# ---------------------------------------------------------------------------
# Supported formats
# ---------------------------------------------------------------------------


class TestSupportedFormats:
    def test_all_formats_listed_by_default(self):
        engine = ExportEngine()
        fmts = engine.supported_formats()
        assert "csv" in fmts
        assert "json" in fmts
        assert "markdown" in fmts
        assert "pdf" in fmts
        assert "xlsx" in fmts

    def test_pdf_disabled_excluded(self):
        engine = ExportEngine(pdf_enabled=False)
        fmts = engine.supported_formats()
        assert "pdf" not in fmts
        assert "csv" in fmts

    def test_xlsx_disabled_excluded(self):
        engine = ExportEngine(xlsx_enabled=False)
        fmts = engine.supported_formats()
        assert "xlsx" not in fmts
        assert "csv" in fmts


# ---------------------------------------------------------------------------
# Get / list exports and stats
# ---------------------------------------------------------------------------


class TestExportStorage:
    def test_get_export_by_id(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV)
        result = engine.generate(_sample_data(), config)
        fetched = engine.get_export(result.export_id)
        assert fetched is not None
        assert fetched.export_id == result.export_id

    def test_get_export_unknown_id_returns_none(self):
        engine = ExportEngine()
        assert engine.get_export("nonexistent") is None

    def test_list_exports_returns_recent_first(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV)
        engine.generate(_sample_data(), config)
        engine.generate(_sample_data(), config)
        exports = engine.list_exports()
        assert len(exports) >= 2
        assert exports[0].created_at >= exports[1].created_at

    def test_list_exports_respects_limit(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV)
        for _ in range(5):
            engine.generate(_sample_data(), config)
        exports = engine.list_exports(limit=3)
        assert len(exports) == 3

    def test_stats_tracking(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV)
        engine.generate(_sample_data(), config)
        engine.generate(_sample_data(), config)
        stats = engine.get_stats()
        assert stats["total_exports"] == 2
        assert stats["max_rows"] == engine._max_rows
        assert "supported_formats" in stats


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_default_entity_type_in_filename(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV)
        result = engine.generate(_sample_data(), config)
        assert result.filename.startswith("export_")

    def test_markdown_filename_extension(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.MARKDOWN, entity_type="alerts")
        result = engine.generate(_sample_data(), config)
        assert result.filename.endswith(".md")

    def test_pdf_filename_extension(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.PDF, entity_type="events")
        result = engine.generate(_sample_data(), config)
        assert result.filename.endswith(".html")

    def test_single_row_export(self):
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.JSON)
        result = engine.generate([{"a": 1}], config)
        parsed = json.loads(result.content)
        assert parsed["count"] == 1

    def test_large_export_prunes_storage(self):
        """Generating >1000 exports should prune oldest entries."""
        engine = ExportEngine()
        config = ExportConfig(format=ExportFormat.CSV)
        for _ in range(1005):
            engine.generate([{"x": 1}], config)
        # After pruning, should have at most ~505 entries
        assert len(engine._exports) <= 600
