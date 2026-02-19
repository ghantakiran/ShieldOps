"""OpenTelemetry tracing setup for ShieldOps.

Provides SDK initialization, tracer access, and graceful shutdown.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

if TYPE_CHECKING:
    from shieldops.config.settings import Settings

logger = structlog.get_logger()

_provider: TracerProvider | None = None


def init_tracing(settings: Settings) -> trace.Tracer:
    """Initialize the OpenTelemetry tracing pipeline.

    Creates a TracerProvider with an OTLP gRPC exporter and registers it
    as the global tracer provider.

    Args:
        settings: Application settings (reads otel_exporter_endpoint, environment, app_version).

    Returns:
        A configured Tracer instance for manual span creation.
    """
    global _provider  # noqa: PLW0603

    resource = Resource.create(
        {
            "service.name": "shieldops-api",
            "service.version": settings.app_version,
            "deployment.environment": settings.environment,
        }
    )

    _provider = TracerProvider(resource=resource)

    # Only add the OTLP exporter when an endpoint is configured and reachable
    endpoint = settings.otel_exporter_endpoint
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            _provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("otel_exporter_configured", endpoint=endpoint)
        except Exception as exc:
            logger.warning("otel_exporter_init_failed", error=str(exc))

    trace.set_tracer_provider(_provider)
    logger.info(
        "otel_tracing_initialized",
        service="shieldops-api",
        environment=settings.environment,
    )
    return _provider.get_tracer("shieldops")


def get_tracer(name: str = "shieldops") -> trace.Tracer:
    """Return a tracer from the global provider.

    Safe to call before ``init_tracing`` — will return a no-op tracer
    from the default provider until the real one is registered.
    """
    return trace.get_tracer(name)


def shutdown_tracing() -> None:
    """Flush pending spans and shut down the provider."""
    global _provider  # noqa: PLW0603
    if _provider is not None:
        _provider.force_flush()
        _provider.shutdown()
        logger.info("otel_tracing_shutdown")
        _provider = None
