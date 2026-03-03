"""SOAROrchestrationRunner — entry point for executing soar orchestration workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.soar_orchestration.graph import create_soar_orchestration_graph
from shieldops.agents.soar_orchestration.models import SOAROrchestrationState
from shieldops.agents.soar_orchestration.nodes import set_toolkit
from shieldops.agents.soar_orchestration.tools import SOAROrchestrationToolkit

logger = structlog.get_logger()


class SOAROrchestrationRunner:
    """Runner for the Soar Orchestration Agent."""

    def __init__(
        self,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = SOAROrchestrationToolkit(
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_soar_orchestration_graph()
        self._app = graph.compile()
        self._results: dict[str, SOAROrchestrationState] = {}
        logger.info("soar_orchestration_runner.initialized")

    async def orchestrate(
        self,
        orchestrate_id: str,
        incident_config: dict[str, Any] | None = None,
    ) -> SOAROrchestrationState:
        """Run soar orchestration workflow."""
        session_id = f"soar-{uuid4().hex[:12]}"
        initial_state = SOAROrchestrationState(
            session_id=orchestrate_id,
            incident_config=incident_config or {},
        )

        logger.info(
            "soar_orchestration_runner.starting",
            session_id=session_id,
            orchestrate_id=orchestrate_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "soar_orchestration"}},
            )
            final_state = SOAROrchestrationState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "soar_orchestration_runner.completed",
                session_id=session_id,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("soar_orchestration_runner.failed", session_id=session_id, error=str(e))
            error_state = SOAROrchestrationState(
                session_id=orchestrate_id,
                incident_config=incident_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> SOAROrchestrationState | None:
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
