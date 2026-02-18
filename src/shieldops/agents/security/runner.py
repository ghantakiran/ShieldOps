"""Security Agent runner — entry point for executing security scans.

Takes scan parameters, constructs the LangGraph, runs it end-to-end,
and returns the completed security scan state.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.security.graph import create_security_graph
from shieldops.agents.security.models import SecurityScanState
from shieldops.agents.security.nodes import set_toolkit
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
        )
        result = await runner.scan(environment=Environment.PRODUCTION)
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        cve_sources: list[Any] | None = None,
        credential_stores: list[Any] | None = None,
    ) -> None:
        self._toolkit = SecurityToolkit(
            connector_router=connector_router,
            cve_sources=cve_sources or [],
            credential_stores=credential_stores or [],
        )
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
    ) -> SecurityScanState:
        """Run a security scan.

        Args:
            environment: Target environment to scan.
            scan_type: Type of scan — full, cve_only, credentials_only, compliance_only.
            target_resources: Specific resources to scan (auto-discovers if empty).
            compliance_frameworks: Frameworks to check (defaults to soc2).

        Returns:
            The completed SecurityScanState with all findings.
        """
        scan_id = f"sec-{uuid4().hex[:12]}"

        logger.info(
            "security_scan_started",
            scan_id=scan_id,
            environment=environment.value,
            scan_type=scan_type,
        )

        initial_state = SecurityScanState(
            scan_id=scan_id,
            scan_type=scan_type,
            target_resources=target_resources or [],
            target_environment=environment,
            compliance_frameworks=compliance_frameworks or ["soc2"],
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),
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
                    (datetime.now(timezone.utc) - final_state.scan_start).total_seconds()
                    * 1000
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
                steps=len(final_state.reasoning_chain),
            )

            self._scans[scan_id] = final_state
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
            return error_state

    def get_scan(self, scan_id: str) -> SecurityScanState | None:
        """Retrieve a completed scan by ID."""
        return self._scans.get(scan_id)

    def list_scans(self) -> list[dict]:
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
                "duration_ms": state.scan_duration_ms,
                "error": state.error,
            }
            for scan_id, state in self._scans.items()
        ]
