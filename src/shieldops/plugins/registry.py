"""Plugin registry — manages plugin lifecycle and state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from shieldops.plugins.base import PluginType, ShieldOpsPlugin

logger = structlog.get_logger()


class PluginStatus(BaseModel):
    """Runtime status of a registered plugin."""

    name: str
    version: str
    plugin_type: PluginType
    enabled: bool = True
    installed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    config: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class PluginRegistry:
    """Central registry for all ShieldOps plugins.

    Manages registration, enabling/disabling, and lifecycle operations.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, ShieldOpsPlugin] = {}
        self._status: dict[str, PluginStatus] = {}

    async def register(
        self,
        plugin: ShieldOpsPlugin,
        config: dict[str, Any] | None = None,
        auto_setup: bool = True,
    ) -> PluginStatus:
        """Register and optionally set up a plugin."""
        name = plugin.name

        if name in self._plugins:
            logger.warning("plugin_already_registered", name=name)
            return self._status[name]

        status = PluginStatus(
            name=name,
            version=plugin.version,
            plugin_type=plugin.plugin_type,
            config=config or {},
        )

        if auto_setup:
            try:
                await plugin.setup(config)
            except Exception as e:
                status.enabled = False
                status.error = str(e)
                logger.error("plugin_setup_failed", name=name, error=str(e))

        self._plugins[name] = plugin
        self._status[name] = status

        logger.info(
            "plugin_registered",
            name=name,
            version=plugin.version,
            plugin_type=plugin.plugin_type,
            enabled=status.enabled,
        )
        return status

    async def unregister(self, name: str) -> bool:
        """Unregister a plugin, calling teardown first."""
        plugin = self._plugins.get(name)
        if plugin is None:
            return False

        try:
            await plugin.teardown()
        except Exception as e:
            logger.warning("plugin_teardown_error", name=name, error=str(e))

        del self._plugins[name]
        del self._status[name]
        logger.info("plugin_unregistered", name=name)
        return True

    async def enable(self, name: str) -> bool:
        """Enable a disabled plugin."""
        status = self._status.get(name)
        plugin = self._plugins.get(name)
        if status is None or plugin is None:
            return False

        if status.enabled:
            return True

        try:
            await plugin.setup(status.config)
            status.enabled = True
            status.error = None
            logger.info("plugin_enabled", name=name)
            return True
        except Exception as e:
            status.error = str(e)
            logger.error("plugin_enable_failed", name=name, error=str(e))
            return False

    async def disable(self, name: str) -> bool:
        """Disable an enabled plugin."""
        status = self._status.get(name)
        plugin = self._plugins.get(name)
        if status is None or plugin is None:
            return False

        if not status.enabled:
            return True

        try:
            await plugin.teardown()
        except Exception as e:
            logger.warning("plugin_teardown_error", name=name, error=str(e))

        status.enabled = False
        logger.info("plugin_disabled", name=name)
        return True

    def get_plugin(self, name: str) -> ShieldOpsPlugin | None:
        """Get a registered plugin by name."""
        return self._plugins.get(name)

    def get_status(self, name: str) -> PluginStatus | None:
        """Get plugin status by name."""
        return self._status.get(name)

    def list_plugins(
        self,
        plugin_type: PluginType | None = None,
        enabled_only: bool = False,
    ) -> list[PluginStatus]:
        """List all registered plugins, optionally filtered."""
        results = list(self._status.values())

        if plugin_type is not None:
            results = [s for s in results if s.plugin_type == plugin_type]
        if enabled_only:
            results = [s for s in results if s.enabled]

        return results

    def is_registered(self, name: str) -> bool:
        """Check if a plugin is registered."""
        return name in self._plugins

    async def teardown_all(self) -> None:
        """Teardown all plugins (called during shutdown)."""
        for name in list(self._plugins.keys()):
            await self.unregister(name)
