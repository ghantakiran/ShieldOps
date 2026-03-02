"""Attack Surface Agent runner — entry point for executing attack surface workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.attack_surface.graph import create_attack_surface_graph
from shieldops.agents.attack_surface.models import AttackSurfaceState
from shieldops.agents.attack_surface.nodes import set_toolkit
from shieldops.agents.attack_surface.tools import AttackSurfaceToolkit

logger = structlog.get_logger()


class AttackSurfaceRunner:
    """Runner for the Attack Surface Agent."""

    def __init__(
        self,
        asset_discovery: Any | None = None,
        exposure_scanner: Any | None = None,
        remediation_engine: Any | None = None,
        policy_engine: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = AttackSurfaceToolkit(
            asset_discovery=asset_discovery,
            exposure_scanner=exposure_scanner,
            remediation_engine=remediation_engine,
            policy_engine=policy_engine,
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_attack_surface_graph()
        self._app = graph.compile()
        self._results: dict[str, AttackSurfaceState] = {}
        logger.info("attack_surface_runner.initialized")

    async def scan(
        self,
        scan_id: str,
        scan_config: dict[str, Any] | None = None,
    ) -> AttackSurfaceState:
        """Run attack surface scan workflow."""
        session_id = f"as-{uuid4().hex[:12]}"
        initial_state = AttackSurfaceState(
            scan_id=scan_id,
            scan_config=scan_config or {},
        )

        logger.info(
            "attack_surface_runner.starting",
            session_id=session_id,
            scan_id=scan_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "attack_surface"}},
            )
            final_state = AttackSurfaceState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "attack_surface_runner.completed",
                session_id=session_id,
                asset_count=final_state.asset_count,
                critical_count=final_state.critical_count,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("attack_surface_runner.failed", session_id=session_id, error=str(e))
            error_state = AttackSurfaceState(
                scan_id=scan_id,
                scan_config=scan_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> AttackSurfaceState | None:
        return self._results.get(session_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": sid,
                "scan_id": state.scan_id,
                "asset_count": state.asset_count,
                "critical_count": state.critical_count,
                "risk_score": state.risk_score,
                "current_step": state.current_step,
                "error": state.error,
            }
            for sid, state in self._results.items()
        ]
