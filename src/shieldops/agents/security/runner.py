"""Security Agent runner — entry point for executing security scans.

Takes scan parameters, constructs the LangGraph, runs it end-to-end,
and returns the completed security scan state.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.security.graph import create_security_graph
from shieldops.agents.security.models import SecurityScanState
from shieldops.agents.security.nodes import set_toolkit
from shieldops.agents.security.protocols import (
    CredentialStore,
    CVESource,
    SecurityScanner,
)
from shieldops.agents.security.tools import SecurityToolkit
from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import Environment

logger = structlog.get_logger()


class SecurityRunner:
    """Runs security agent workflows.

    Usage:
        runner = SecurityRunner(
            connector_router=router,
            cve_sources=[nvd_source],
            credential_stores=[vault_store],
            policy_engine=policy_engine,
            approval_workflow=approval_workflow,
            repository=repository,
        )
        result = await runner.scan(environment=Environment.PRODUCTION)
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        cve_sources: list[CVESource] | None = None,
        credential_stores: list[CredentialStore] | None = None,
        security_scanners: list[SecurityScanner] | None = None,
        policy_engine: Any | None = None,
        approval_workflow: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = SecurityToolkit(
            connector_router=connector_router,
            cve_sources=cve_sources or [],
            credential_stores=credential_stores or [],
            security_scanners=security_scanners or [],
            policy_engine=policy_engine,
            approval_workflow=approval_workflow,
            repository=repository,
        )
        self._repository = repository
        set_toolkit(self._toolkit)

        graph = create_security_graph()
        self._app = graph.compile()

        self._scans: dict[str, SecurityScanState] = {}

    async def scan(
        self,
        environment: Environment = Environment.PRODUCTION,
        scan_type: str = "full",
        target_resources: list[str] | None = None,
        compliance_frameworks: list[str] | None = None,
        execute_actions: bool = False,
    ) -> SecurityScanState:
        """Run a security scan.

        Args:
            environment: Target environment to scan.
            scan_type: Type of scan — full, cve_only, credentials_only, compliance_only.
            target_resources: Specific resources to scan (auto-discovers if empty).
            compliance_frameworks: Frameworks to check (defaults to soc2).
            execute_actions: If True, apply patches and rotate credentials after scan.

        Returns:
            The completed SecurityScanState with all findings.
        """
        scan_id = f"sec-{uuid4().hex[:12]}"

        logger.info(
            "security_scan_started",
            scan_id=scan_id,
            environment=environment.value,
            scan_type=scan_type,
            execute_actions=execute_actions,
        )

        initial_state = SecurityScanState(
            scan_id=scan_id,
            scan_type=scan_type,
            target_resources=target_resources or [],
            target_environment=environment,
            compliance_frameworks=compliance_frameworks or ["soc2"],
            execute_actions=execute_actions,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={
                    "metadata": {
                        "scan_id": scan_id,
                        "scan_type": scan_type,
                    },
                },
            )

            final_state = SecurityScanState.model_validate(final_state_dict)

            if final_state.scan_start:
                final_state.scan_duration_ms = int(
                    (datetime.now(UTC) - final_state.scan_start).total_seconds() * 1000
                )

            logger.info(
                "security_scan_completed",
                scan_id=scan_id,
                duration_ms=final_state.scan_duration_ms,
                cve_count=len(final_state.cve_findings),
                critical_cves=final_state.critical_cve_count,
                credentials_at_risk=final_state.credentials_needing_rotation,
                compliance_score=final_state.compliance_score,
                posture_score=final_state.posture.overall_score if final_state.posture else 0,
                patches_applied=final_state.patches_applied,
                credentials_rotated=final_state.credentials_rotated,
                steps=len(final_state.reasoning_chain),
            )

            self._scans[scan_id] = final_state
            await self._persist(scan_id, final_state)
            await self._write_audit(scan_id, final_state)
            return final_state

        except Exception as e:
            logger.error(
                "security_scan_failed",
                scan_id=scan_id,
                error=str(e),
            )
            error_state = SecurityScanState(
                scan_id=scan_id,
                scan_type=scan_type,
                target_environment=environment,
                error=str(e),
                current_step="failed",
            )
            self._scans[scan_id] = error_state
            await self._persist(scan_id, error_state)
            return error_state

    def get_scan(self, scan_id: str) -> SecurityScanState | None:
        """Retrieve a completed scan by ID."""
        return self._scans.get(scan_id)

    def list_scans(self) -> list[dict[str, Any]]:
        """List all scans with summary info."""
        return [
            {
                "scan_id": scan_id,
                "scan_type": state.scan_type,
                "environment": state.target_environment.value,
                "status": state.current_step,
                "cve_count": len(state.cve_findings),
                "critical_cves": state.critical_cve_count,
                "credentials_at_risk": state.credentials_needing_rotation,
                "compliance_score": state.compliance_score,
                "posture_score": state.posture.overall_score if state.posture else 0,
                "patches_applied": state.patches_applied,
                "credentials_rotated": state.credentials_rotated,
                "duration_ms": state.scan_duration_ms,
                "error": state.error,
            }
            for scan_id, state in self._scans.items()
        ]

    async def _persist(self, scan_id: str, state: SecurityScanState) -> None:
        """Save scan result to DB via repository."""
        if self._repository is None:
            return
        try:
            await self._repository.save_security_scan(scan_id, state)
        except Exception as e:
            logger.warning("security_scan_persist_failed", scan_id=scan_id, error=str(e))

    async def _write_audit(self, scan_id: str, state: SecurityScanState) -> None:
        """Write an audit log entry for completed scan actions."""
        if self._repository is None:
            return
        if not state.patches_applied and not state.credentials_rotated:
            return  # No actions taken — nothing to audit

        try:
            from shieldops.models.base import (
                AuditEntry,
                ExecutionStatus,
                RiskLevel,
            )

            entry = AuditEntry(
                id=f"aud-sec-{uuid4().hex[:12]}",
                timestamp=datetime.now(UTC),
                agent_type="security",
                action="security_remediation",
                target_resource=state.target_resources[0] if state.target_resources else "*",
                environment=state.target_environment,
                risk_level=RiskLevel.MEDIUM,
                policy_evaluation=(
                    "allowed"
                    if state.action_policy_result and state.action_policy_result.allowed
                    else "denied"
                ),
                outcome=ExecutionStatus.SUCCESS if not state.error else ExecutionStatus.FAILED,
                reasoning=(
                    f"Patches applied: {state.patches_applied}, "
                    f"Credentials rotated: {state.credentials_rotated}"
                ),
                actor="security-agent",
            )
            await self._repository.append_audit_log(entry)
        except Exception as e:
            logger.warning("security_audit_write_failed", scan_id=scan_id, error=str(e))
