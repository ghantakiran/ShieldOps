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

    # AWS — registered when aws_region is configured
    if settings.aws_region:
        from shieldops.connectors.aws.connector import AWSConnector

        aws = AWSConnector(region=settings.aws_region)
        router.register(aws)
        logger.info("connector_registered", provider="aws")

    # Linux SSH — registered when linux_host is configured
    if settings.linux_host:
        from shieldops.connectors.linux.connector import LinuxConnector

        linux = LinuxConnector(
            host=settings.linux_host,
            username=settings.linux_username,
            private_key_path=settings.linux_private_key_path or None,
        )
        router.register(linux)
        logger.info("connector_registered", provider="linux")

    # GCP — registered when gcp_project_id is configured
    if settings.gcp_project_id:
        from shieldops.connectors.gcp.connector import GCPConnector

        gcp = GCPConnector(
            project_id=settings.gcp_project_id,
            region=settings.gcp_region,
        )
        router.register(gcp)
        logger.info("connector_registered", provider="gcp")

    # Azure — registered when azure_subscription_id is configured
    if settings.azure_subscription_id:
        from shieldops.connectors.azure.connector import AzureConnector

        azure = AzureConnector(
            subscription_id=settings.azure_subscription_id,
            resource_group=settings.azure_resource_group,
            location=settings.azure_location,
        )
        router.register(azure)
        logger.info("connector_registered", provider="azure")

    # Windows WinRM — registered when windows_host is configured
    if settings.windows_host:
        from shieldops.connectors.windows.connector import WindowsConnector

        windows = WindowsConnector(
            host=settings.windows_host,
            username=settings.windows_username,
            password=settings.windows_password,
            use_ssl=settings.windows_use_ssl,
            port=settings.windows_port,
        )
        router.register(windows)
        logger.info("connector_registered", provider="windows")

    logger.info("connector_router_ready", providers=router.providers)
    return router
