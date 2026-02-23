"""Configuration Audit Trail — per-key config versioning with diff, blame, and restore."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ConfigScope(StrEnum):
    SERVICE = "service"
    ENVIRONMENT = "environment"
    GLOBAL = "global"
    NAMESPACE = "namespace"


class ChangeAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


# --- Models ---


class ConfigEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    config_key: str
    value: str = ""
    previous_value: str = ""
    scope: ConfigScope = ConfigScope.SERVICE
    action: ChangeAction = ChangeAction.CREATE
    approval_status: ApprovalStatus = ApprovalStatus.AUTO_APPROVED
    changed_by: str = ""
    reason: str = ""
    version: int = 1
    created_at: float = Field(default_factory=time.time)


class ConfigDiff(BaseModel):
    config_key: str
    from_version: int
    to_version: int
    from_value: str = ""
    to_value: str = ""
    changed_by: str = ""


# --- Audit Trail ---


class ConfigurationAuditTrail:
    """Per-key config versioning with diff, blame, and restore."""

    def __init__(
        self,
        max_entries: int = 100000,
        max_versions_per_key: int = 50,
    ) -> None:
        self._max_entries = max_entries
        self._max_versions_per_key = max_versions_per_key
        self._entries: list[ConfigEntry] = []
        self._key_versions: dict[str, list[ConfigEntry]] = {}
        logger.info(
            "config_audit.initialized",
            max_entries=max_entries,
            max_versions_per_key=max_versions_per_key,
        )

    def record_change(
        self,
        config_key: str,
        value: str,
        changed_by: str = "",
        scope: ConfigScope = ConfigScope.SERVICE,
        reason: str = "",
        **kw: Any,
    ) -> ConfigEntry:
        """Record a configuration change."""
        existing = self._key_versions.get(config_key, [])
        version = len(existing) + 1
        previous = existing[-1].value if existing else ""
        action = ChangeAction.CREATE if not existing else ChangeAction.UPDATE
        entry = ConfigEntry(
            config_key=config_key,
            value=value,
            previous_value=previous,
            scope=scope,
            action=action,
            changed_by=changed_by,
            reason=reason,
            version=version,
            **kw,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]
        self._key_versions.setdefault(config_key, []).append(entry)
        if len(self._key_versions[config_key]) > self._max_versions_per_key:
            trimmed = self._key_versions[config_key]
            self._key_versions[config_key] = trimmed[-self._max_versions_per_key :]
        logger.info(
            "config_audit.change_recorded",
            config_key=config_key,
            version=version,
            action=action,
            changed_by=changed_by,
        )
        return entry

    def get_current(self, config_key: str) -> ConfigEntry | None:
        """Get current (latest) config entry for a key."""
        versions = self._key_versions.get(config_key, [])
        return versions[-1] if versions else None

    def get_history(self, config_key: str) -> list[ConfigEntry]:
        """Get full version history for a key."""
        return list(self._key_versions.get(config_key, []))

    def get_diff(
        self,
        config_key: str,
        from_version: int,
        to_version: int,
    ) -> ConfigDiff | None:
        """Get diff between two versions of a key."""
        versions = self._key_versions.get(config_key, [])
        from_entry: ConfigEntry | None = None
        to_entry: ConfigEntry | None = None
        for v in versions:
            if v.version == from_version:
                from_entry = v
            if v.version == to_version:
                to_entry = v
        if from_entry is None or to_entry is None:
            return None
        return ConfigDiff(
            config_key=config_key,
            from_version=from_version,
            to_version=to_version,
            from_value=from_entry.value,
            to_value=to_entry.value,
            changed_by=to_entry.changed_by,
        )

    def restore_version(
        self,
        config_key: str,
        version: int,
        restored_by: str = "",
    ) -> ConfigEntry | None:
        """Restore a specific version of a config key."""
        versions = self._key_versions.get(config_key, [])
        target: ConfigEntry | None = None
        for v in versions:
            if v.version == version:
                target = v
                break
        if target is None:
            return None
        return self.record_change(
            config_key=config_key,
            value=target.value,
            changed_by=restored_by,
            scope=target.scope,
            reason=f"Restored from version {version}",
        )

    def blame(self, config_key: str) -> list[dict[str, Any]]:
        """Get blame information for all versions of a key."""
        versions = self._key_versions.get(config_key, [])
        return [
            {
                "version": v.version,
                "changed_by": v.changed_by,
                "action": v.action,
                "value": v.value,
                "created_at": v.created_at,
            }
            for v in versions
        ]

    def search(self, query: str) -> list[ConfigEntry]:
        """Search config entries by key substring."""
        q = query.lower()
        seen_keys: set[str] = set()
        results: list[ConfigEntry] = []
        for entry in reversed(self._entries):
            if q in entry.config_key.lower() and entry.config_key not in seen_keys:
                results.append(entry)
                seen_keys.add(entry.config_key)
        return results

    def list_recent_changes(self, limit: int = 50) -> list[ConfigEntry]:
        """List most recent config changes."""
        return list(reversed(self._entries[-limit:]))

    def delete_key(self, config_key: str, deleted_by: str = "") -> bool:
        """Delete a config key (records as a DELETE action)."""
        if config_key not in self._key_versions:
            return False
        current = self.get_current(config_key)
        entry = ConfigEntry(
            config_key=config_key,
            value="",
            previous_value=current.value if current else "",
            action=ChangeAction.DELETE,
            changed_by=deleted_by,
            version=len(self._key_versions[config_key]) + 1,
        )
        self._entries.append(entry)
        self._key_versions[config_key].append(entry)
        logger.info("config_audit.key_deleted", config_key=config_key, deleted_by=deleted_by)
        return True

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        scope_counts: dict[str, int] = {}
        action_counts: dict[str, int] = {}
        for e in self._entries:
            scope_counts[e.scope] = scope_counts.get(e.scope, 0) + 1
            action_counts[e.action] = action_counts.get(e.action, 0) + 1
        return {
            "total_entries": len(self._entries),
            "total_keys": len(self._key_versions),
            "scope_distribution": scope_counts,
            "action_distribution": action_counts,
        }
