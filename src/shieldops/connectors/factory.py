"""Factory for creating a ConnectorRouter with registered infrastructure connectors."""

import structlog

from shieldops.config.settings import Settings
from shieldops.connectors.base import ConnectorRouter
from shieldops.connectors.kubernetes.connector import KubernetesConnector

logger = structlog.get_logger()


def create_connector_router(settings: Settings) -> ConnectorRouter:
    """Create a ConnectorRouter with all configured infrastructure connectors.

    Kubernetes is always registered (falls back to in-cluster config).
    AWS/GCP/Azure connectors will be added when those modules are implemented.

    Args:
        settings: Application settings (used for future cloud connector config).

    Returns:
        A ConnectorRouter with registered connectors.
    """
    router = ConnectorRouter()

    # Kubernetes is always available — falls back to in-cluster config
    k8s = KubernetesConnector()
    router.register(k8s)
    logger.info("connector_registered", provider="kubernetes")

    # TODO: Register AWS connector when settings.aws_region is configured
    # TODO: Register GCP connector when settings.gcp_project_id is configured
    # TODO: Register Azure connector when settings.azure_subscription_id is configured

    logger.info("connector_router_ready", providers=router.providers)
    return router
