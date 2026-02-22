"""Plugin validator — validates plugin interface compliance."""

from __future__ import annotations

import re

import structlog

from shieldops.plugins.base import PluginType, ShieldOpsPlugin

logger = structlog.get_logger()

# Semantic version pattern
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[\w.]+)?(\+[\w.]+)?$")

# Valid plugin name pattern (lowercase, hyphens, numbers)
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


class PluginValidator:
    """Validates that a plugin implements the required interface correctly."""

    def validate(self, plugin: ShieldOpsPlugin) -> list[str]:
        """Validate a plugin instance. Returns a list of error messages (empty = valid)."""
        errors: list[str] = []

        errors.extend(self._validate_name(plugin))
        errors.extend(self._validate_version(plugin))
        errors.extend(self._validate_type(plugin))
        errors.extend(self._validate_methods(plugin))
        errors.extend(self._validate_metadata(plugin))

        if errors:
            logger.warning(
                "plugin_validation_errors",
                plugin=getattr(plugin, "name", "unknown"),
                error_count=len(errors),
            )

        return errors

    def _validate_name(self, plugin: ShieldOpsPlugin) -> list[str]:
        """Validate plugin name."""
        errors: list[str] = []
        try:
            name = plugin.name
            if not name:
                errors.append("Plugin name is empty")
            elif not _NAME_RE.match(name):
                errors.append(
                    f"Plugin name '{name}' must be lowercase, start with a letter, "
                    "and contain only letters, numbers, and hyphens (2-64 chars)"
                )
        except Exception as e:
            errors.append(f"Plugin name property raised error: {e}")
        return errors

    def _validate_version(self, plugin: ShieldOpsPlugin) -> list[str]:
        """Validate version follows semver."""
        errors: list[str] = []
        try:
            version = plugin.version
            if not version:
                errors.append("Plugin version is empty")
            elif not _SEMVER_RE.match(version):
                errors.append(f"Plugin version '{version}' must follow semantic versioning (X.Y.Z)")
        except Exception as e:
            errors.append(f"Plugin version property raised error: {e}")
        return errors

    def _validate_type(self, plugin: ShieldOpsPlugin) -> list[str]:
        """Validate plugin type is a valid PluginType."""
        errors: list[str] = []
        try:
            ptype = plugin.plugin_type
            if ptype not in PluginType:
                errors.append(f"Plugin type '{ptype}' is not a valid PluginType")
        except Exception as e:
            errors.append(f"Plugin plugin_type property raised error: {e}")
        return errors

    def _validate_methods(self, plugin: ShieldOpsPlugin) -> list[str]:
        """Validate required methods exist and are callable."""
        errors: list[str] = []

        for method_name in ("setup", "teardown"):
            method = getattr(plugin, method_name, None)
            if method is None or not callable(method):
                errors.append(f"Plugin missing required method: {method_name}")

        # Type-specific method validation
        ptype = getattr(plugin, "plugin_type", None)
        type_methods: dict[PluginType, list[str]] = {
            PluginType.CONNECTOR: ["connect", "disconnect", "execute_command"],
            PluginType.SCANNER: ["scan"],
            PluginType.NOTIFICATION: ["send"],
            PluginType.AGENT: ["run"],
        }

        required = type_methods.get(ptype, [])  # type: ignore[arg-type]
        for method_name in required:
            method = getattr(plugin, method_name, None)
            if method is None or not callable(method):
                errors.append(f"Plugin type '{ptype}' requires method '{method_name}'")

        return errors

    def _validate_metadata(self, plugin: ShieldOpsPlugin) -> list[str]:
        """Validate metadata is consistent."""
        errors: list[str] = []
        try:
            meta = plugin.metadata
            if meta.name != plugin.name:
                errors.append(
                    f"Metadata name '{meta.name}' doesn't match plugin name '{plugin.name}'"
                )
            if meta.version != plugin.version:
                errors.append(
                    f"Metadata version '{meta.version}' doesn't match "
                    f"plugin version '{plugin.version}'"
                )
        except Exception as e:
            errors.append(f"Plugin metadata raised error: {e}")
        return errors
