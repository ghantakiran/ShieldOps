"""Plugin loader — discovers and loads plugins from directories or packages."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import structlog

from shieldops.plugins.base import ShieldOpsPlugin
from shieldops.plugins.registry import PluginRegistry
from shieldops.plugins.validator import PluginValidator

logger = structlog.get_logger()


class PluginLoadError(Exception):
    """Raised when a plugin fails to load."""


class PluginLoader:
    """Discovers and loads ShieldOps plugins from filesystem or packages.

    Scans directories for Python modules that export ShieldOpsPlugin subclasses.
    """

    def __init__(
        self,
        registry: PluginRegistry,
        validator: PluginValidator | None = None,
    ) -> None:
        self._registry = registry
        self._validator = validator or PluginValidator()

    async def load_from_directory(
        self,
        directory: str | Path,
        config: dict[str, Any] | None = None,
    ) -> list[str]:
        """Load all plugins from a directory.

        Each .py file is inspected for ShieldOpsPlugin subclasses.
        Returns list of loaded plugin names.
        """
        directory = Path(directory)
        loaded: list[str] = []

        if not directory.is_dir():
            logger.warning("plugin_directory_not_found", directory=str(directory))
            return loaded

        for py_file in sorted(directory.glob("*.py")):
            if py_file.name.startswith("_"):
                continue

            try:
                plugins = self._discover_plugins_in_file(py_file)
                for plugin_cls in plugins:
                    plugin = plugin_cls()

                    # Validate plugin interface
                    errors = self._validator.validate(plugin)
                    if errors:
                        logger.warning(
                            "plugin_validation_failed",
                            file=str(py_file),
                            plugin=plugin.name,
                            errors=errors,
                        )
                        continue

                    plugin_config = (config or {}).get(plugin.name, {})
                    await self._registry.register(plugin, config=plugin_config)
                    loaded.append(plugin.name)

            except Exception as e:
                logger.error(
                    "plugin_load_error",
                    file=str(py_file),
                    error=str(e),
                )

        logger.info("plugins_loaded_from_directory", directory=str(directory), count=len(loaded))
        return loaded

    async def load_from_package(
        self,
        package_name: str,
        config: dict[str, Any] | None = None,
    ) -> str | None:
        """Load a plugin from an installed Python package.

        The package must export a `create_plugin()` factory function
        or a `Plugin` class that subclasses ShieldOpsPlugin.
        """
        try:
            module = importlib.import_module(package_name)
        except ImportError as e:
            logger.error("plugin_package_not_found", package=package_name, error=str(e))
            return None

        plugin: ShieldOpsPlugin | None = None

        # Try factory function first
        factory = getattr(module, "create_plugin", None)
        if callable(factory):
            plugin = factory()
        else:
            # Try Plugin class
            plugin_cls = getattr(module, "Plugin", None)
            if (
                plugin_cls
                and isinstance(plugin_cls, type)
                and issubclass(plugin_cls, ShieldOpsPlugin)
            ):
                plugin = plugin_cls()

        if plugin is None:
            logger.warning(
                "plugin_no_entry_point",
                package=package_name,
            )
            return None

        errors = self._validator.validate(plugin)
        if errors:
            logger.warning(
                "plugin_validation_failed",
                package=package_name,
                errors=errors,
            )
            return None

        await self._registry.register(plugin, config=config)
        logger.info("plugin_loaded_from_package", package=package_name, name=plugin.name)
        return plugin.name

    def _discover_plugins_in_file(self, file_path: Path) -> list[type[ShieldOpsPlugin]]:
        """Discover ShieldOpsPlugin subclasses in a Python file."""
        module_name = f"shieldops_plugin_{file_path.stem}"

        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            return []

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error("plugin_exec_error", file=str(file_path), error=str(e))
            del sys.modules[module_name]
            return []

        plugins: list[type[ShieldOpsPlugin]] = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, ShieldOpsPlugin)
                and attr is not ShieldOpsPlugin
                and not getattr(attr, "__abstractmethods__", set())
            ):
                plugins.append(attr)

        return plugins
