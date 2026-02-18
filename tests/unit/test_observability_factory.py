"""Tests for observability source factory and API lifespan wiring.

Covers:
- create_observability_sources() with various setting combinations
- ObservabilitySources.close_all() cleanup
- Lifespan integration — runner receives sources via set_runner()
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.config.settings import Settings
from shieldops.observability.datadog.client import DatadogSource
from shieldops.observability.factory import (
    ObservabilitySources,
    create_observability_sources,
)
from shieldops.observability.otel.client import JaegerSource
from shieldops.observability.prometheus.client import PrometheusSource
from shieldops.observability.splunk.client import SplunkSource


def _make_settings(**overrides: str | bool) -> Settings:
    """Create a Settings instance with all observability URLs empty by default."""
    defaults = {
        "prometheus_url": "",
        "splunk_url": "",
        "splunk_token": "",
        "datadog_api_key": "",
        "datadog_app_key": "",
        "jaeger_url": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# --- create_observability_sources() ---


class TestCreateObservabilitySources:
    def test_no_sources_configured(self) -> None:
        settings = _make_settings()
        sources = create_observability_sources(settings)

        assert sources.log_sources == []
        assert sources.metric_sources == []
        assert sources.trace_sources == []

    def test_prometheus_only(self) -> None:
        settings = _make_settings(prometheus_url="http://prom:9090")
        sources = create_observability_sources(settings)

        assert len(sources.metric_sources) == 1
        assert isinstance(sources.metric_sources[0], PrometheusSource)
        assert sources.log_sources == []
        assert sources.trace_sources == []

    def test_splunk_requires_url_and_token(self) -> None:
        # URL only — no source created
        sources = create_observability_sources(_make_settings(splunk_url="http://splunk:8089"))
        assert sources.log_sources == []

        # Token only — no source created
        sources = create_observability_sources(_make_settings(splunk_token="my-token"))
        assert sources.log_sources == []

    def test_splunk_with_url_and_token(self) -> None:
        settings = _make_settings(splunk_url="http://splunk:8089", splunk_token="tok-123")
        sources = create_observability_sources(settings)

        assert len(sources.log_sources) == 1
        assert isinstance(sources.log_sources[0], SplunkSource)

    def test_datadog_requires_both_keys(self) -> None:
        # api_key only
        sources = create_observability_sources(_make_settings(datadog_api_key="ak"))
        assert len(sources.metric_sources) == 0

        # app_key only
        sources = create_observability_sources(_make_settings(datadog_app_key="apk"))
        assert len(sources.metric_sources) == 0

    def test_datadog_with_both_keys(self) -> None:
        settings = _make_settings(datadog_api_key="ak-123", datadog_app_key="apk-456")
        sources = create_observability_sources(settings)

        assert len(sources.metric_sources) == 1
        assert isinstance(sources.metric_sources[0], DatadogSource)

    def test_jaeger_only(self) -> None:
        settings = _make_settings(jaeger_url="http://jaeger:16686")
        sources = create_observability_sources(settings)

        assert len(sources.trace_sources) == 1
        assert isinstance(sources.trace_sources[0], JaegerSource)
        assert sources.log_sources == []
        assert sources.metric_sources == []

    def test_all_sources_configured(self) -> None:
        settings = _make_settings(
            prometheus_url="http://prom:9090",
            splunk_url="http://splunk:8089",
            splunk_token="tok",
            datadog_api_key="ak",
            datadog_app_key="apk",
            jaeger_url="http://jaeger:16686",
        )
        sources = create_observability_sources(settings)

        assert len(sources.log_sources) == 1  # Splunk
        assert len(sources.metric_sources) == 2  # Prometheus + Datadog
        assert len(sources.trace_sources) == 1  # Jaeger


# --- ObservabilitySources.close_all() ---


class TestCloseAll:
    @pytest.mark.asyncio
    async def test_close_all_calls_close_on_each_source(self) -> None:
        mock_log = AsyncMock()
        mock_log.close = AsyncMock()
        mock_metric = AsyncMock()
        mock_metric.close = AsyncMock()
        mock_trace = AsyncMock()
        mock_trace.close = AsyncMock()

        sources = ObservabilitySources(
            log_sources=[mock_log],
            metric_sources=[mock_metric],
            trace_sources=[mock_trace],
        )
        await sources.close_all()

        mock_log.close.assert_awaited_once()
        mock_metric.close.assert_awaited_once()
        mock_trace.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_all_handles_errors_gracefully(self) -> None:
        mock_source = AsyncMock()
        mock_source.close = AsyncMock(side_effect=RuntimeError("connection reset"))
        mock_source.source_name = "broken"

        sources = ObservabilitySources(log_sources=[mock_source])
        # Should not raise
        await sources.close_all()

    @pytest.mark.asyncio
    async def test_close_all_empty_sources(self) -> None:
        sources = ObservabilitySources()
        # Should not raise
        await sources.close_all()


# --- Lifespan integration ---


class TestLifespanWiring:
    @pytest.mark.asyncio
    async def test_lifespan_injects_runner_with_sources(self) -> None:
        """Verify the lifespan creates sources and injects them into the investigations module."""
        from shieldops.api.app import create_app
        from shieldops.api.routes import investigations

        mock_sources = ObservabilitySources(
            log_sources=[AsyncMock()],
            metric_sources=[AsyncMock()],
            trace_sources=[AsyncMock()],
        )
        mock_router = MagicMock()

        with (
            patch(
                "shieldops.api.app.create_observability_sources",
                return_value=mock_sources,
            ) as mock_factory,
            patch(
                "shieldops.api.app.create_connector_router",
                return_value=mock_router,
            ),
            patch(
                "shieldops.api.app.InvestigationRunner",
            ) as mock_runner_cls,
        ):
            app = create_app()

            async with app.router.lifespan_context(app):
                # Factory was called with settings
                mock_factory.assert_called_once()

                # Runner was constructed with connector_router + sources
                mock_runner_cls.assert_called_once_with(
                    connector_router=mock_router,
                    log_sources=mock_sources.log_sources,
                    metric_sources=mock_sources.metric_sources,
                    trace_sources=mock_sources.trace_sources,
                )

                # Runner was injected via set_runner
                assert investigations._runner is mock_runner_cls.return_value

        # After lifespan exit, close_all should have been called
        # (mock_sources is a real ObservabilitySources with AsyncMock sources)
        for src in mock_sources.log_sources:
            src.close.assert_awaited_once()
