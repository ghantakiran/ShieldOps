"""Unit tests for OpenTelemetry tracing setup."""

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from shieldops.observability.tracing import get_tracer, init_tracing, shutdown_tracing


def _force_reset_tracer_provider() -> None:
    """Reset the OTEL global tracer provider so tests can set it again."""
    import opentelemetry.trace as _mod

    _mod._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    _mod._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _reset_tracing():
    """Reset the global tracing state between tests."""
    import shieldops.observability.tracing as mod

    _force_reset_tracer_provider()
    original = mod._provider
    yield
    mod._provider = original
    _force_reset_tracer_provider()


class TestInitTracing:
    def test_creates_provider_with_correct_service_name(self):
        settings = MagicMock()
        settings.app_version = "0.1.0"
        settings.environment = "test"
        settings.otel_exporter_endpoint = ""

        init_tracing(settings)

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        resource = provider.resource  # type: ignore[attr-defined]
        attrs = dict(resource.attributes)
        assert attrs["service.name"] == "shieldops-api"
        assert attrs["service.version"] == "0.1.0"
        assert attrs["deployment.environment"] == "test"

    def test_returns_valid_tracer(self):
        settings = MagicMock()
        settings.app_version = "0.1.0"
        settings.environment = "test"
        settings.otel_exporter_endpoint = ""

        tracer = init_tracing(settings)
        assert tracer is not None
        # Tracer should be able to create spans
        with tracer.start_as_current_span("test-span") as span:
            assert span is not None

    def test_configures_otlp_exporter_when_endpoint_set(self):
        settings = MagicMock()
        settings.app_version = "0.1.0"
        settings.environment = "test"
        settings.otel_exporter_endpoint = "http://localhost:4317"

        with (
            patch(
                "shieldops.observability.tracing.OTLPSpanExporter",
                create=True,
            ) as mock_exporter_cls,
            patch.dict(
                "sys.modules",
                {
                    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(
                        OTLPSpanExporter=mock_exporter_cls
                    )
                },
            ),
        ):
            init_tracing(settings)

    def test_handles_missing_exporter_gracefully(self):
        settings = MagicMock()
        settings.app_version = "0.1.0"
        settings.environment = "test"
        settings.otel_exporter_endpoint = "http://nonexistent:4317"

        # Should not raise even if exporter fails to connect
        tracer = init_tracing(settings)
        assert tracer is not None


class TestGetTracer:
    def test_returns_tracer_before_init(self):
        tracer = get_tracer()
        assert tracer is not None

    def test_returns_tracer_after_init(self):
        settings = MagicMock()
        settings.app_version = "0.1.0"
        settings.environment = "test"
        settings.otel_exporter_endpoint = ""

        init_tracing(settings)
        tracer = get_tracer("test-module")
        assert tracer is not None

    def test_custom_name_returns_tracer(self):
        tracer = get_tracer("shieldops.agents")
        assert tracer is not None


class TestShutdownTracing:
    def test_shutdown_flushes_cleanly(self):
        settings = MagicMock()
        settings.app_version = "0.1.0"
        settings.environment = "test"
        settings.otel_exporter_endpoint = ""

        init_tracing(settings)
        # Should not raise
        shutdown_tracing()

    def test_shutdown_without_init_is_noop(self):
        import shieldops.observability.tracing as mod

        mod._provider = None
        # Should not raise
        shutdown_tracing()

    def test_double_shutdown_is_safe(self):
        settings = MagicMock()
        settings.app_version = "0.1.0"
        settings.environment = "test"
        settings.otel_exporter_endpoint = ""

        init_tracing(settings)
        shutdown_tracing()
        shutdown_tracing()  # Second call should be no-op
