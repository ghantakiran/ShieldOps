"""AutonomousDefenseRunner — entry point for executing autonomous_defense workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.autonomous_defense.graph import create_autonomous_defense_graph
from shieldops.agents.autonomous_defense.models import AutonomousDefenseState
from shieldops.agents.autonomous_defense.nodes import set_toolkit
from shieldops.agents.autonomous_defense.tools import AutonomousDefenseToolkit

logger = structlog.get_logger()


class AutonomousDefenseRunner:
    """Runner for the AutonomousDefense Agent."""

    def __init__(
        self,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = AutonomousDefenseToolkit(
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_autonomous_defense_graph()
        self._app = graph.compile()
        self._results: dict[str, AutonomousDefenseState] = {}
        logger.info("autonomous_defense_runner.initialized")

    async def protect(
        self,
        protect_id: str,
        protect_config: dict[str, Any] | None = None,
    ) -> AutonomousDefenseState:
        """Run autonomous_defense workflow."""
        session_id = f"ad-{uuid4().hex[:12]}"
        initial_state = AutonomousDefenseState(
            session_id=protect_id,
            config=protect_config or {},
        )

        logger.info(
            "autonomous_defense_runner.starting",
            session_id=session_id,
            protect_id=protect_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "autonomous_defense"}},
            )
            final_state = AutonomousDefenseState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "autonomous_defense_runner.completed",
                session_id=session_id,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("autonomous_defense_runner.failed", session_id=session_id, error=str(e))
            error_state = AutonomousDefenseState(
                session_id=protect_id,
                config=protect_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> AutonomousDefenseState | None:
        return self._results.get(session_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": sid,
                "current_step": state.current_step,
                "session_duration_ms": state.session_duration_ms,
                "error": state.error,
            }
            for sid, state in self._results.items()
        ]
