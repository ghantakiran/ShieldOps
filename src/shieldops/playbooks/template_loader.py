"""Template loader — parses agent template YAML files from the templates directory."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import structlog
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

logger = structlog.get_logger()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "playbooks" / "templates"


class TemplateParameter(BaseModel):
    """A single configurable parameter for a template."""

    name: str
    type: str = "string"
    required: bool = True
    default: Any = None
    description: str = ""


class TemplateStep(BaseModel):
    """A single step in the template execution plan."""

    name: str
    action: str
    config: dict[str, Any] = Field(default_factory=dict)


class AgentTemplate(BaseModel):
    """A fully parsed agent template."""

    id: str = ""
    name: str
    description: str = ""
    category: str = "remediation"
    cloud_providers: list[str] = Field(default_factory=list)
    agent_type: str = "remediation"
    risk_level: str = "low"
    tags: list[str] = Field(default_factory=list)
    estimated_setup_minutes: int = 5
    featured: bool = False
    parameters: list[TemplateParameter] = Field(default_factory=list)
    steps: list[TemplateStep] = Field(default_factory=list)


class TemplateLoader:
    """Loads and indexes agent templates from YAML files."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._dir = templates_dir or TEMPLATES_DIR
        self._templates: dict[str, AgentTemplate] = {}

    def load_all(self) -> None:
        """Parse all *.yaml files in the templates directory."""
        if not self._dir.exists():
            logger.warning("templates_dir_not_found", path=str(self._dir))
            return

        for yaml_file in sorted(self._dir.glob("*.yaml")):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                if not data or "name" not in data:
                    continue

                # Generate stable ID from filename
                template_id = self._make_id(yaml_file.stem)
                template = AgentTemplate(id=template_id, **data)
                self._templates[template_id] = template
                logger.info(
                    "template_loaded",
                    template_id=template_id,
                    name=template.name,
                    file=yaml_file.name,
                )
            except Exception as e:
                logger.error(
                    "template_load_error",
                    file=yaml_file.name,
                    error=str(e),
                )

    def get_template(self, template_id: str) -> AgentTemplate | None:
        """Fetch a template by its ID."""
        return self._templates.get(template_id)

    def all_templates(self) -> list[AgentTemplate]:
        """Return all loaded templates."""
        return list(self._templates.values())

    def search(
        self,
        category: str | None = None,
        cloud: str | None = None,
        tags: list[str] | None = None,
        query: str | None = None,
    ) -> list[AgentTemplate]:
        """Filter templates by category, cloud provider, tags, and/or free-text query."""
        results = self.all_templates()

        if category:
            results = [t for t in results if t.category == category]

        if cloud:
            results = [t for t in results if cloud in t.cloud_providers]

        if tags:
            tag_set = set(tags)
            results = [t for t in results if tag_set.intersection(t.tags)]

        if query:
            q = query.lower()
            results = [
                t
                for t in results
                if q in t.name.lower()
                or q in t.description.lower()
                or any(q in tag.lower() for tag in t.tags)
            ]

        return results

    def featured(self) -> list[AgentTemplate]:
        """Return templates marked as featured."""
        return [t for t in self.all_templates() if t.featured]

    def categories(self) -> dict[str, int]:
        """Return category names with template counts."""
        counts: dict[str, int] = {}
        for t in self.all_templates():
            counts[t.category] = counts.get(t.category, 0) + 1
        return counts

    def deploy(
        self,
        template_id: str,
        org_id: str,
        environment: str = "production",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Instantiate a template into a deployable agent configuration.

        Validates required parameters and returns a configuration dict
        suitable for agent registration and playbook creation.
        """
        template = self.get_template(template_id)
        if template is None:
            raise ValueError(f"Template '{template_id}' not found")

        # Merge defaults with provided params
        resolved_params: dict[str, Any] = {}
        provided = params or {}

        for param in template.parameters:
            if param.name in provided:
                resolved_params[param.name] = provided[param.name]
            elif param.default is not None and param.default != "":
                resolved_params[param.name] = param.default
            elif param.required:
                raise ValueError(
                    f"Required parameter '{param.name}' not provided for template '{template.name}'"
                )
            else:
                resolved_params[param.name] = param.default

        deployment_id = hashlib.sha256(
            f"{template_id}:{org_id}:{environment}".encode()
        ).hexdigest()[:12]

        return {
            "deployment_id": f"deploy-{deployment_id}",
            "template_id": template_id,
            "template_name": template.name,
            "org_id": org_id,
            "environment": environment,
            "agent_type": template.agent_type,
            "category": template.category,
            "risk_level": template.risk_level,
            "parameters": resolved_params,
            "steps": [step.model_dump() for step in template.steps],
            "status": "deployed",
        }

    @staticmethod
    def _make_id(stem: str) -> str:
        """Generate a stable template ID from a filename stem."""
        return f"tmpl-{stem}"
