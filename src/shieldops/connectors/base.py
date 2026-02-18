"""Base connector interface and router for multi-cloud infrastructure operations."""

from abc import ABC, abstractmethod
from typing import Any

from shieldops.models.base import (
    ActionResult,
    Environment,
    HealthStatus,
    RemediationAction,
    Resource,
    Snapshot,
    TimeRange,
)


class InfraConnector(ABC):
    """Abstract base class for infrastructure connectors.

    All cloud/on-prem connectors implement this interface, allowing agents
    to operate across environments without cloud-specific logic.
    """

    provider: str  # aws, gcp, azure, kubernetes, linux

    @abstractmethod
    async def get_health(self, resource_id: str) -> HealthStatus:
        """Get health status of a resource."""

    @abstractmethod
    async def list_resources(
        self,
        resource_type: str,
        environment: Environment,
        filters: dict[str, Any] | None = None,
    ) -> list[Resource]:
        """List resources of a given type in an environment."""

    @abstractmethod
    async def get_events(self, resource_id: str, time_range: TimeRange) -> list[dict[str, Any]]:
        """Get events for a resource within a time range."""

    @abstractmethod
    async def execute_action(self, action: RemediationAction) -> ActionResult:
        """Execute a remediation action on a resource."""

    @abstractmethod
    async def create_snapshot(self, resource_id: str) -> Snapshot:
        """Create a state snapshot for rollback capability."""

    @abstractmethod
    async def rollback(self, snapshot_id: str) -> ActionResult:
        """Rollback to a previous snapshot."""

    @abstractmethod
    async def validate_health(self, resource_id: str, timeout_seconds: int = 300) -> bool:
        """Validate resource health after an action (with timeout)."""


class ConnectorRouter:
    """Routes operations to the correct infrastructure connector based on provider."""

    def __init__(self) -> None:
        self._connectors: dict[str, InfraConnector] = {}

    def register(self, connector: InfraConnector) -> None:
        """Register a connector for a provider."""
        self._connectors[connector.provider] = connector

    def get(self, provider: str) -> InfraConnector:
        """Get connector for a provider."""
        if provider not in self._connectors:
            raise ValueError(
                f"No connector registered for provider '{provider}'. "
                f"Available: {list(self._connectors.keys())}"
            )
        return self._connectors[provider]

    @property
    def providers(self) -> list[str]:
        """List registered providers."""
        return list(self._connectors.keys())
