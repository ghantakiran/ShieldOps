"""Observability as Code Engine — manage observability config as code."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ConfigType(StrEnum):
    DASHBOARD = "dashboard"
    ALERT_RULE = "alert_rule"
    SLO = "slo"
    RECORDING_RULE = "recording_rule"
    NOTIFICATION = "notification"


class ConfigStatus(StrEnum):
    APPLIED = "applied"
    PENDING = "pending"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    DRAFT = "draft"


class DiffAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    NO_CHANGE = "no_change"


# --- Models ---


class OaCConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    config_type: ConfigType = ConfigType.DASHBOARD
    status: ConfigStatus = ConfigStatus.DRAFT
    version: int = 1
    content: dict[str, Any] = Field(default_factory=dict)
    owner: str = ""
    created_at: float = Field(default_factory=time.time)


class ConfigDiff(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    config_name: str = ""
    action: DiffAction = DiffAction.NO_CHANGE
    old_version: int = 0
    new_version: int = 0
    changes: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class OaCReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_configs: int = 0
    applied_count: int = 0
    failed_count: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ObservabilityAsCodeEngine:
    """Manage observability configuration as code (dashboards, alerts, SLOs)."""

    def __init__(self, max_configs: int = 50000) -> None:
        self._max_configs = max_configs
        self._configs: list[OaCConfig] = []
        self._diffs: list[ConfigDiff] = []
        self._history: list[OaCConfig] = []
        logger.info("observability_as_code_engine.initialized", max_configs=max_configs)

    def add_config(
        self,
        name: str,
        config_type: ConfigType = ConfigType.DASHBOARD,
        content: dict[str, Any] | None = None,
        owner: str = "",
    ) -> OaCConfig:
        """Register a new observability config."""
        config = OaCConfig(
            name=name,
            config_type=config_type,
            content=content or {},
            owner=owner,
        )
        self._configs.append(config)
        if len(self._configs) > self._max_configs:
            self._configs = self._configs[-self._max_configs :]
        logger.info(
            "observability_as_code_engine.config_added",
            name=name,
            config_type=config_type.value,
        )
        return config

    def validate_config(self, name: str) -> dict[str, Any]:
        """Validate an observability config."""
        configs = [c for c in self._configs if c.name == name]
        if not configs:
            return {"name": name, "valid": False, "errors": ["config not found"]}
        config = configs[-1]
        errors: list[str] = []
        if not config.content:
            errors.append("empty content")
        if not config.owner:
            errors.append("no owner specified")
        return {
            "name": name,
            "valid": len(errors) == 0,
            "errors": errors,
            "config_type": config.config_type.value,
        }

    def apply_config(self, name: str) -> dict[str, Any]:
        """Apply an observability config."""
        configs = [c for c in self._configs if c.name == name]
        if not configs:
            return {"name": name, "status": "not_found"}
        config = configs[-1]
        validation = self.validate_config(name)
        if not validation["valid"]:
            config.status = ConfigStatus.FAILED
            return {"name": name, "status": "failed", "errors": validation["errors"]}
        self._history.append(config.model_copy())
        config.status = ConfigStatus.APPLIED
        config.version += 1
        logger.info("observability_as_code_engine.applied", name=name)
        return {"name": name, "status": "applied", "version": config.version}

    def diff_config(self, name: str, new_content: dict[str, Any]) -> ConfigDiff:
        """Diff current config against proposed changes."""
        configs = [c for c in self._configs if c.name == name]
        if not configs:
            diff = ConfigDiff(config_name=name, action=DiffAction.CREATE, new_version=1)
            self._diffs.append(diff)
            return diff
        current = configs[-1]
        changes: list[str] = []
        for key in set(list(current.content.keys()) + list(new_content.keys())):
            old_val = current.content.get(key)
            new_val = new_content.get(key)
            if old_val != new_val:
                changes.append(f"{key}: {old_val} -> {new_val}")
        action = DiffAction.UPDATE if changes else DiffAction.NO_CHANGE
        diff = ConfigDiff(
            config_name=name,
            action=action,
            old_version=current.version,
            new_version=current.version + 1 if changes else current.version,
            changes=changes,
        )
        self._diffs.append(diff)
        return diff

    def rollback_config(self, name: str) -> dict[str, Any]:
        """Rollback a config to its previous version."""
        history = [c for c in self._history if c.name == name]
        if not history:
            return {"name": name, "status": "no_history"}
        previous = history[-1]
        configs = [c for c in self._configs if c.name == name]
        if configs:
            current = configs[-1]
            current.content = previous.content
            current.status = ConfigStatus.ROLLED_BACK
            current.version = previous.version
        logger.info("observability_as_code_engine.rolled_back", name=name)
        return {"name": name, "status": "rolled_back", "version": previous.version}

    def export_config(self, name: str | None = None) -> list[dict[str, Any]]:
        """Export configs as serializable dicts."""
        targets = self._configs
        if name:
            targets = [c for c in targets if c.name == name]
        return [c.model_dump() for c in targets]

    def generate_report(self) -> OaCReport:
        """Generate OaC report."""
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for c in self._configs:
            by_type[c.config_type.value] = by_type.get(c.config_type.value, 0) + 1
            by_status[c.status.value] = by_status.get(c.status.value, 0) + 1
        applied = sum(1 for c in self._configs if c.status == ConfigStatus.APPLIED)
        failed = sum(1 for c in self._configs if c.status == ConfigStatus.FAILED)
        recs: list[str] = []
        if failed > 0:
            recs.append(f"{failed} config(s) in failed state — review needed")
        drafts = sum(1 for c in self._configs if c.status == ConfigStatus.DRAFT)
        if drafts > 0:
            recs.append(f"{drafts} draft config(s) pending application")
        if not recs:
            recs.append("All configs healthy")
        return OaCReport(
            total_configs=len(self._configs),
            applied_count=applied,
            failed_count=failed,
            by_type=by_type,
            by_status=by_status,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all configs and history."""
        self._configs.clear()
        self._diffs.clear()
        self._history.clear()
        logger.info("observability_as_code_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_configs": len(self._configs),
            "total_diffs": len(self._diffs),
            "total_history": len(self._history),
            "unique_owners": len({c.owner for c in self._configs}),
        }
