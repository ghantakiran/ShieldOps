"""Playbook loader — parses YAML playbooks into Pydantic models."""

from pathlib import Path
from typing import Any

import structlog
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

logger = structlog.get_logger()

PLAYBOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "playbooks"


class PlaybookTrigger(BaseModel):
    """Trigger conditions for a playbook."""

    alert_type: str
    severity: list[str] = Field(default_factory=lambda: ["critical", "warning"])


class PlaybookCondition(BaseModel):
    """A single condition → action mapping in the decision tree."""

    condition: str
    action: str
    risk_level: str = "low"
    params: dict[str, Any] = Field(default_factory=dict)


class PlaybookStep(BaseModel):
    """An investigation or validation step."""

    name: str
    action: str | None = None
    query: str | None = None
    queries: list[str] | None = None
    extract: list[str] | None = None
    patterns: list[str] | None = None
    targets: list[str] | None = None
    time_range: str | None = None
    expected: str | None = None
    timeout_seconds: int | None = None


class PlaybookValidation(BaseModel):
    """Validation configuration for a playbook."""

    checks: list[PlaybookStep] = Field(default_factory=list)
    on_failure: dict[str, Any] = Field(default_factory=dict)


class Playbook(BaseModel):
    """A fully parsed remediation playbook."""

    name: str
    version: str = "1.0"
    description: str = ""
    trigger: PlaybookTrigger
    investigation: dict[str, Any] = Field(default_factory=dict)
    remediation: dict[str, Any] = Field(default_factory=dict)
    validation: PlaybookValidation | None = None

    @property
    def decision_tree(self) -> list[PlaybookCondition]:
        """Parse the remediation decision tree into typed conditions."""
        raw = self.remediation.get("decision_tree", [])
        return [PlaybookCondition(**item) for item in raw]


class PlaybookLoader:
    """Loads and indexes playbooks from YAML files."""

    def __init__(self, playbooks_dir: Path | None = None) -> None:
        self._dir = playbooks_dir or PLAYBOOKS_DIR
        self._playbooks: dict[str, Playbook] = {}
        self._trigger_index: dict[str, str] = {}  # alert_type → playbook name

    def load_all(self) -> None:
        """Parse all *.yaml files in the playbooks directory."""
        if not self._dir.exists():
            logger.warning("playbooks_dir_not_found", path=str(self._dir))
            return

        for yaml_file in sorted(self._dir.glob("*.yaml")):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                if not data or "name" not in data:
                    continue
                playbook = Playbook(**data)
                self._playbooks[playbook.name] = playbook
                self._trigger_index[playbook.trigger.alert_type] = playbook.name
                logger.info("playbook_loaded", name=playbook.name, file=yaml_file.name)
            except Exception as e:
                logger.error("playbook_load_error", file=yaml_file.name, error=str(e))

    def match(self, alert_name: str, severity: str | None = None) -> Playbook | None:
        """Find a matching playbook by alert type and optional severity."""
        playbook_name = self._trigger_index.get(alert_name)
        if playbook_name is None:
            return None

        playbook = self._playbooks[playbook_name]

        if severity and severity not in playbook.trigger.severity:
            return None

        return playbook

    def get(self, name: str) -> Playbook | None:
        """Fetch a playbook by name."""
        return self._playbooks.get(name)

    def all(self) -> list[Playbook]:
        """Return all loaded playbooks."""
        return list(self._playbooks.values())
