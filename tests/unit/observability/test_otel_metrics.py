"""Tests for OpenTelemetry metrics pipeline.

Tests cover:
- init_metrics when OTel SDK dependencies are missing
- AgentMetrics.record_execution with a mock meter
- get_meter returns None before initialization
"""

from unittest.mock import MagicMock, patch

import pytest

from shieldops.observability.otel import metrics as metrics_mod
from shieldops.observability.otel.metrics import (
    AgentMetrics,
    get_meter,
    init_metrics,
)


@pytest.fixture(autouse=True)
def _reset_global_meter():
    """Reset the module-level _meter between tests."""
    original = metrics_mod._meter
    metrics_mod._meter = None
    yield
    metrics_mod._meter = original


class TestGetMeterReturnsNoneWithoutInit:
    def test_get_meter_returns_none_without_init(self) -> None:
        assert get_meter() is None


class TestInitMetricsWithMissingDeps:
    def test_init_metrics_with_missing_deps(self) -> None:
        """init_metrics should not raise when OTel is missing."""
        import builtins

        original_import = builtins.__import__

        def _mock_import(
            name: str,
            *args,
            **kwargs,  # noqa: ANN002, ANN003
        ):
            if name.startswith("opentelemetry"):
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_mock_import):
            init_metrics()  # should not raise

        assert get_meter() is None


class TestAgentMetricsRecordsExecution:
    def test_agent_metrics_records_execution(self) -> None:
        """AgentMetrics records counters/histograms via OTel."""
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_histogram = MagicMock()
        mock_error_counter = MagicMock()

        mock_meter.create_counter.side_effect = [
            mock_counter,
            mock_error_counter,
        ]
        mock_meter.create_histogram.return_value = mock_histogram

        # Inject mock meter
        metrics_mod._meter = mock_meter

        am = AgentMetrics("investigation")

        # Record a successful execution
        am.record_execution(duration_ms=150.0, success=True)
        mock_counter.add.assert_called_once_with(1, {"success": "True"})
        mock_histogram.record.assert_called_once_with(150.0)
        mock_error_counter.add.assert_not_called()

        # Record a failed execution
        mock_counter.reset_mock()
        mock_histogram.reset_mock()
        am.record_execution(duration_ms=500.0, success=False)
        mock_counter.add.assert_called_once_with(1, {"success": "False"})
        mock_histogram.record.assert_called_once_with(500.0)
        mock_error_counter.add.assert_called_once_with(1)

    def test_agent_metrics_noop_without_meter(self) -> None:
        """AgentMetrics is a safe no-op when meter is None."""
        am = AgentMetrics("remediation")
        # Should not raise
        am.record_execution(duration_ms=100.0, success=True)
        am.record_execution(duration_ms=200.0, success=False)
