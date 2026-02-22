"""AI-powered playbook generation using LLM structured output.

Generates remediation playbooks for novel vulnerability patterns that
don't match any static YAML playbook in the library.
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class GeneratedStep(BaseModel):
    """A single remediation step in a generated playbook."""

    order: int
    description: str
    command: str = ""
    risk_level: str = "low"
    rollback_command: str = ""
    validation: str = ""


class GeneratedPlaybook(BaseModel):
    """An AI-generated remediation playbook."""

    name: str
    description: str
    severity: str = "medium"
    target_type: str = ""
    steps: list[GeneratedStep] = Field(default_factory=list)
    estimated_duration_minutes: int = 15
    requires_approval: bool = False
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class AIPlaybookGenerator:
    """Generates remediation playbooks using LLM structured output.

    Falls back from static playbook matching for novel vulnerability
    patterns. Can refine generated playbooks based on feedback.

    Args:
        repository: Optional DB repository for historical remediations.
    """

    def __init__(self, repository: Any | None = None) -> None:
        self._repository = repository

    async def generate(
        self,
        vulnerability: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> GeneratedPlaybook:
        """Generate a playbook for a vulnerability.

        Args:
            vulnerability: Vulnerability dict with severity, cve_id, description, etc.
            context: Optional additional context (infrastructure, team, environment).

        Returns:
            A GeneratedPlaybook with structured remediation steps.
        """
        logger.info(
            "ai_playbook_generate_start",
            cve_id=vulnerability.get("cve_id", ""),
            severity=vulnerability.get("severity", ""),
        )

        # Gather historical context if available
        historical = await self._get_historical_context(vulnerability)

        system_prompt = self._build_system_prompt(historical)
        user_prompt = self._build_user_prompt(vulnerability, context)

        try:
            from shieldops.utils.llm import llm_structured

            result = await llm_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=GeneratedPlaybook,
            )

            if isinstance(result, GeneratedPlaybook):
                playbook = result
            else:
                playbook = GeneratedPlaybook.model_validate(result)

            logger.info(
                "ai_playbook_generated",
                name=playbook.name,
                steps=len(playbook.steps),
                confidence=playbook.confidence,
            )
            return playbook

        except Exception as e:
            logger.error("ai_playbook_generate_failed", error=str(e))
            return self._fallback_playbook(vulnerability)

    async def generate_batch(
        self,
        vulnerabilities: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> list[GeneratedPlaybook]:
        """Generate playbooks for multiple vulnerabilities."""
        playbooks: list[GeneratedPlaybook] = []
        for vuln in vulnerabilities:
            playbook = await self.generate(vuln, context)
            playbooks.append(playbook)
        return playbooks

    async def refine(
        self,
        playbook: GeneratedPlaybook,
        feedback: str,
    ) -> GeneratedPlaybook:
        """Refine a generated playbook based on operator feedback.

        Args:
            playbook: The playbook to refine.
            feedback: Human feedback describing desired changes.

        Returns:
            A refined GeneratedPlaybook.
        """
        logger.info("ai_playbook_refine_start", name=playbook.name, feedback=feedback[:100])

        system_prompt = (
            "You are a senior SRE security engineer. Refine the given remediation "
            "playbook based on the operator's feedback. Maintain the same structured "
            "format. Adjust steps, commands, risk levels, and validation as needed."
        )

        user_prompt = (
            f"Current playbook:\n{playbook.model_dump_json(indent=2)}\n\n"
            f"Operator feedback:\n{feedback}\n\n"
            "Generate the refined playbook with all improvements applied."
        )

        try:
            from shieldops.utils.llm import llm_structured

            result = await llm_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=GeneratedPlaybook,
            )

            if isinstance(result, GeneratedPlaybook):
                refined = result
            else:
                refined = GeneratedPlaybook.model_validate(result)

            logger.info(
                "ai_playbook_refined",
                name=refined.name,
                steps=len(refined.steps),
            )
            return refined

        except Exception as e:
            logger.error("ai_playbook_refine_failed", error=str(e))
            return playbook

    async def _get_historical_context(self, vulnerability: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch historical remediations for similar vulnerabilities."""
        if self._repository is None:
            return []

        try:
            remediations = await self._repository.list_remediations(
                status="completed",
                limit=5,
            )
            return [r for r in remediations if isinstance(r, dict)]
        except Exception as e:
            logger.warning("historical_context_failed", error=str(e))
            return []

    def _build_system_prompt(self, historical: list[dict[str, Any]]) -> str:
        prompt = (
            "You are a senior SRE security engineer generating remediation playbooks "
            "for ShieldOps, an autonomous SRE platform. Generate structured, actionable "
            "playbooks with specific commands, validation steps, and rollback plans.\n\n"
            "Guidelines:\n"
            "- Each step must have a clear description and optional command\n"
            "- Include rollback commands for risky steps\n"
            "- Include validation commands to verify success\n"
            "- Set requires_approval=true for production changes\n"
            "- Estimate realistic duration\n"
            "- Rate confidence (0-1) based on how well you understand the issue\n"
        )

        if historical:
            prompt += "\nHistorical successful remediations for context:\n"
            for h in historical[:3]:
                prompt += f"- {h.get('action_type', '')}: {h.get('description', '')[:100]}\n"

        return prompt

    def _build_user_prompt(
        self,
        vulnerability: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> str:
        parts = [
            "Generate a remediation playbook for this vulnerability:\n",
            f"CVE/ID: {vulnerability.get('cve_id', vulnerability.get('finding_id', 'N/A'))}",
            f"Severity: {vulnerability.get('severity', 'unknown')}",
            f"Title: {vulnerability.get('title', '')}",
            f"Description: {vulnerability.get('description', '')[:500]}",
            f"Package: {vulnerability.get('package_name', '')}",
            f"Affected Resource: {vulnerability.get('affected_resource', '')}",
            f"Fixed Version: {vulnerability.get('fixed_version', '')}",
            f"Scanner Type: {vulnerability.get('scanner_type', '')}",
        ]

        if context:
            parts.append(f"\nAdditional context: {str(context)[:500]}")

        return "\n".join(parts)

    def _fallback_playbook(self, vulnerability: dict[str, Any]) -> GeneratedPlaybook:
        """Generate a minimal fallback playbook when LLM fails."""
        severity = vulnerability.get("severity", "medium")
        cve_id = vulnerability.get("cve_id", vulnerability.get("finding_id", "unknown"))

        return GeneratedPlaybook(
            name=f"Remediation for {cve_id}",
            description=f"Auto-generated remediation steps for {severity} vulnerability {cve_id}",
            severity=severity,
            steps=[
                GeneratedStep(
                    order=1,
                    description="Assess the vulnerability impact and affected resources",
                    risk_level="low",
                ),
                GeneratedStep(
                    order=2,
                    description="Test the fix in a staging environment",
                    risk_level="low",
                ),
                GeneratedStep(
                    order=3,
                    description="Apply the fix with rollback plan ready",
                    risk_level="medium",
                ),
                GeneratedStep(
                    order=4,
                    description="Verify the fix resolves the vulnerability",
                    risk_level="low",
                    validation="Re-run vulnerability scan to confirm fix",
                ),
            ],
            estimated_duration_minutes=30,
            requires_approval=severity in ("critical", "high"),
            tags=[severity, "auto-generated", "fallback"],
            confidence=0.3,
        )
