"""Tests for connector router factory and lifespan wiring.

Covers:
- create_connector_router() always registers Kubernetes
- Router returns correct connector for known providers
- Unknown provider raises ValueError
- Lifespan passes connector_router to InvestigationRunner
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.config.settings import Settings
from shieldops.connectors.base import ConnectorRouter
from shieldops.connectors.factory import create_connector_router
from shieldops.connectors.kubernetes.connector import KubernetesConnector


def _make_settings(**overrides: str | bool) -> Settings:
    """Create a Settings instance with defaults."""
    return Settings(**overrides)


class TestCreateConnectorRouter:
    def test_returns_connector_router(self) -> None:
        settings = _make_settings()
        router = create_connector_router(settings)
        assert isinstance(router, ConnectorRouter)

    def test_kubernetes_always_registered(self) -> None:
        settings = _make_settings()
        router = create_connector_router(settings)
        assert "kubernetes" in router.providers

    def test_get_kubernetes_returns_connector(self) -> None:
        settings = _make_settings()
        router = create_connector_router(settings)
        connector = router.get("kubernetes")
        assert isinstance(connector, KubernetesConnector)

    def test_unknown_provider_raises(self) -> None:
        settings = _make_settings()
        router = create_connector_router(settings)
        with pytest.raises(ValueError, match="No connector registered for provider 'aws'"):
            router.get("aws")


class TestLifespanConnectorWiring:
    @pytest.mark.asyncio
    async def test_lifespan_passes_router_to_investigation_runner(self) -> None:
        """Verify the lifespan creates a connector router and passes it to InvestigationRunner."""
        from shieldops.api.routes import investigations
        from shieldops.observability.factory import ObservabilitySources

        mock_sources = ObservabilitySources(
            log_sources=[AsyncMock()],
            metric_sources=[AsyncMock()],
            trace_sources=[AsyncMock()],
        )
        mock_router = MagicMock(spec=ConnectorRouter)

        with (
            patch(
                "shieldops.api.app.create_observability_sources",
                return_value=mock_sources,
            ),
            patch(
                "shieldops.api.app.create_connector_router",
                return_value=mock_router,
            ) as mock_router_factory,
            patch(
                "shieldops.api.app.InvestigationRunner",
            ) as mock_runner_cls,
        ):
            from shieldops.api.app import create_app

            app = create_app()

            async with app.router.lifespan_context(app):
                # Factory was called with settings
                mock_router_factory.assert_called_once()

                # Runner was constructed with connector_router + sources
                mock_runner_cls.assert_called_once_with(
                    connector_router=mock_router,
                    log_sources=mock_sources.log_sources,
                    metric_sources=mock_sources.metric_sources,
                    trace_sources=mock_sources.trace_sources,
                )

                # Runner was injected via set_runner
                assert investigations._runner is mock_runner_cls.return_value
