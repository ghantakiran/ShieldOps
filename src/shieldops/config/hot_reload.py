"""Configuration hot-reload manager.

Watches configuration sources for changes and notifies subscribers
without requiring a full application restart.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ConfigChangeEvent(BaseModel):
    """Record of a configuration change."""

    key: str
    old_value: Any = None
    new_value: Any = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = "api"


class ReloadableConfig:
    """Wrapper around config values that supports hot-reload.

    Callbacks are notified when specific keys change.
    """

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._config: dict[str, Any] = dict(initial or {})
        self._callbacks: dict[str, list[Callable[[str, Any, Any], None]]] = {}
        self._change_history: list[ConfigChangeEvent] = []

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any, source: str = "api") -> ConfigChangeEvent | None:
        """Set a config value and notify subscribers.

        Returns the change event if the value actually changed, else None.
        """
        old_value = self._config.get(key)
        if old_value == value:
            return None

        self._config[key] = value
        event = ConfigChangeEvent(
            key=key,
            old_value=old_value,
            new_value=value,
            source=source,
        )
        self._change_history.append(event)

        # Notify subscribers
        for cb in self._callbacks.get(key, []):
            try:
                cb(key, old_value, value)
            except Exception as e:
                logger.warning("config_callback_error", key=key, error=str(e))

        # Notify wildcard subscribers
        for cb in self._callbacks.get("*", []):
            try:
                cb(key, old_value, value)
            except Exception as e:
                logger.warning("config_wildcard_callback_error", key=key, error=str(e))

        logger.info("config_changed", key=key, source=source)
        return event

    def on_change(self, key: str, callback: Callable[[str, Any, Any], None]) -> None:
        """Register a callback for when a specific key changes.

        Use key="*" for wildcard subscription (all changes).
        """
        self._callbacks.setdefault(key, []).append(callback)

    def all(self) -> dict[str, Any]:
        return dict(self._config)

    @property
    def changes(self) -> list[ConfigChangeEvent]:
        return list(self._change_history)


class HotReloadManager:
    """Manages configuration hot-reload with validation.

    Features:
    - File watcher (polling) for config file changes
    - API-triggered reload
    - Safe reload: validates new config before applying
    - Change history tracking
    """

    def __init__(
        self,
        initial_config: dict[str, Any] | None = None,
        validator: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        self._config = ReloadableConfig(initial_config)
        self._validator = validator
        self._reload_count = 0
        self._last_reload: datetime | None = None
        self._watchers: dict[str, float] = {}  # file_path -> last_mtime

    @property
    def config(self) -> ReloadableConfig:
        return self._config

    def reload(self, new_config: dict[str, Any], source: str = "api") -> bool:
        """Reload configuration with new values.

        Validates before applying. Returns True on success.
        """
        # Validate new config
        if self._validator and not self._validator(new_config):
            logger.warning("config_reload_validation_failed", source=source)
            return False

        changes = []
        for key, value in new_config.items():
            event = self._config.set(key, value, source=source)
            if event:
                changes.append(event)

        self._reload_count += 1
        self._last_reload = datetime.now(UTC)

        logger.info(
            "config_reloaded",
            source=source,
            changes=len(changes),
            reload_count=self._reload_count,
        )
        return True

    def get_runtime_config(self, redact_secrets: bool = True) -> dict[str, Any]:
        """Get current runtime config with optional secret redaction."""
        config = self._config.all()
        if redact_secrets:
            config = self._redact(config)
        return config

    def get_change_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent config change history."""
        changes = self._config.changes[-limit:]
        result = []
        for c in reversed(changes):
            entry = c.model_dump()
            # Redact secrets in history
            if self._is_secret_key(c.key):
                entry["old_value"] = "***"
                entry["new_value"] = "***"
            result.append(entry)
        return result

    def watch_file(self, file_path: str) -> None:
        """Register a file to watch for changes."""
        self._watchers[file_path] = 0.0

    def check_files(self) -> list[str]:
        """Check watched files for changes. Returns list of changed files."""
        import os

        changed = []
        for path, last_mtime in self._watchers.items():
            try:
                mtime = os.path.getmtime(path)
                if mtime > last_mtime:
                    self._watchers[path] = mtime
                    if last_mtime > 0:  # Skip first check
                        changed.append(path)
            except OSError:
                pass
        return changed

    @property
    def reload_count(self) -> int:
        return self._reload_count

    @property
    def last_reload(self) -> datetime | None:
        return self._last_reload

    @staticmethod
    def _is_secret_key(key: str) -> bool:
        secret_patterns = {"password", "secret", "key", "token", "credential"}
        key_lower = key.lower()
        return any(p in key_lower for p in secret_patterns)

    @staticmethod
    def _redact(config: dict[str, Any]) -> dict[str, Any]:
        redacted = {}
        secret_patterns = {"password", "secret", "key", "token", "credential"}
        for k, v in config.items():
            k_lower = k.lower()
            if any(p in k_lower for p in secret_patterns) and v:
                redacted[k] = "***"
            else:
                redacted[k] = v
        return redacted
