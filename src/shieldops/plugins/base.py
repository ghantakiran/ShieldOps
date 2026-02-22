"""Base plugin classes — ABCs for all ShieldOps plugin types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PluginType(StrEnum):
    CONNECTOR = "connector"
    SCANNER = "scanner"
    NOTIFICATION = "notification"
    AGENT = "agent"


class PluginMetadata(BaseModel):
    """Metadata describing a plugin."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    plugin_type: PluginType
    tags: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)  # dependency plugin names


class ShieldOpsPlugin(ABC):
    """Abstract base class for all ShieldOps plugins.

    Every plugin must provide name, version, metadata, setup(), and teardown().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin name."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version string."""

    @property
    @abstractmethod
    def plugin_type(self) -> PluginType:
        """The type of plugin."""

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata (can be overridden for extra fields)."""
        return PluginMetadata(
            name=self.name,
            version=self.version,
            plugin_type=self.plugin_type,
        )

    @abstractmethod
    async def setup(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the plugin with optional configuration."""

    @abstractmethod
    async def teardown(self) -> None:
        """Clean up plugin resources."""

    def health_check(self) -> dict[str, Any]:
        """Check plugin health (override for custom checks)."""
        return {"status": "ok", "plugin": self.name, "version": self.version}


class ConnectorPlugin(ShieldOpsPlugin, ABC):
    """Plugin that provides a new infrastructure connector."""

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.CONNECTOR

    @abstractmethod
    async def connect(self, **kwargs: Any) -> None:
        """Establish connection to the target system."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection."""

    @abstractmethod
    async def execute_command(self, command: str, **kwargs: Any) -> dict[str, Any]:
        """Execute a command on the target system."""


class ScannerPlugin(ShieldOpsPlugin, ABC):
    """Plugin that provides a new scanning capability."""

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.SCANNER

    @abstractmethod
    async def scan(self, target: str, **kwargs: Any) -> dict[str, Any]:
        """Run a scan against the specified target."""


class NotificationPlugin(ShieldOpsPlugin, ABC):
    """Plugin that provides a new notification channel."""

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.NOTIFICATION

    @abstractmethod
    async def send(self, message: str, **kwargs: Any) -> dict[str, Any]:
        """Send a notification."""


class AgentPlugin(ShieldOpsPlugin, ABC):
    """Plugin that provides a new agent type."""

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.AGENT

    @abstractmethod
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's main logic."""
