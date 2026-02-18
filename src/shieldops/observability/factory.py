"""Factory for creating observability sources from application settings.

Reads configuration and conditionally instantiates Splunk, Datadog,
Prometheus, and Jaeger clients based on which URLs/keys are configured.
"""

from dataclasses import dataclass, field

import structlog

from shieldops.config.settings import Settings
from shieldops.observability.base import LogSource, MetricSource, TraceSource
from shieldops.observability.datadog import DatadogSource
from shieldops.observability.otel import JaegerSource
from shieldops.observability.prometheus import PrometheusSource
from shieldops.observability.splunk import SplunkSource

logger = structlog.get_logger()


@dataclass
class ObservabilitySources:
    """Container for all configured observability source instances."""

    log_sources: list[LogSource] = field(default_factory=list)
    metric_sources: list[MetricSource] = field(default_factory=list)
    trace_sources: list[TraceSource] = field(default_factory=list)

    async def close_all(self) -> None:
        """Close all underlying httpx clients."""
        for source in [*self.log_sources, *self.metric_sources, *self.trace_sources]:
            try:
                await source.close()  # type: ignore[attr-defined]
            except Exception as exc:
                logger.warning(
                    "observability_source_close_error",
                    source=getattr(source, "source_name", "unknown"),
                    error=str(exc),
                )


def create_observability_sources(settings: Settings) -> ObservabilitySources:
    """Create observability sources based on which settings are configured.

    Only instantiates a source if its required config values are non-empty.
    """
    sources = ObservabilitySources()

    # Prometheus — requires URL
    if settings.prometheus_url:
        sources.metric_sources.append(PrometheusSource(url=settings.prometheus_url))
        logger.info("observability_source_initialized", source="prometheus")

    # Splunk — requires both URL and token
    if settings.splunk_url and settings.splunk_token:
        sources.log_sources.append(
            SplunkSource(
                url=settings.splunk_url,
                token=settings.splunk_token,
                index=settings.splunk_index,
                verify_ssl=settings.splunk_verify_ssl,
            )
        )
        logger.info("observability_source_initialized", source="splunk")

    # Datadog — requires both api_key and app_key
    if settings.datadog_api_key and settings.datadog_app_key:
        sources.metric_sources.append(
            DatadogSource(
                api_key=settings.datadog_api_key,
                app_key=settings.datadog_app_key,
                site=settings.datadog_site,
            )
        )
        logger.info("observability_source_initialized", source="datadog")

    # Jaeger — requires URL
    if settings.jaeger_url:
        sources.trace_sources.append(JaegerSource(url=settings.jaeger_url))
        logger.info("observability_source_initialized", source="jaeger")

    logger.info(
        "observability_sources_ready",
        log_sources=len(sources.log_sources),
        metric_sources=len(sources.metric_sources),
        trace_sources=len(sources.trace_sources),
    )
    return sources
