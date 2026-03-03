"""SecurityConvergenceRunner — entry point for executing security_convergence workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.security_convergence.graph import create_security_convergence_graph
from shieldops.agents.security_convergence.models import SecurityConvergenceState
from shieldops.agents.security_convergence.nodes import set_toolkit
from shieldops.agents.security_convergence.tools import SecurityConvergenceToolkit

logger = structlog.get_logger()


class SecurityConvergenceRunner:
    """Runner for the SecurityConvergence Agent."""

    def __init__(
        self,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = SecurityConvergenceToolkit(
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_security_convergence_graph()
        self._app = graph.compile()
        self._results: dict[str, SecurityConvergenceState] = {}
        logger.info("security_convergence_runner.initialized")

    async def evaluate(
        self,
        evaluate_id: str,
        evaluate_config: dict[str, Any] | None = None,
    ) -> SecurityConvergenceState:
        """Run security_convergence workflow."""
        session_id = f"sc-{uuid4().hex[:12]}"
        initial_state = SecurityConvergenceState(
            session_id=evaluate_id,
            config=evaluate_config or {},
        )

        logger.info(
            "security_convergence_runner.starting",
            session_id=session_id,
            evaluate_id=evaluate_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "security_convergence"}},
            )
            final_state = SecurityConvergenceState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "security_convergence_runner.completed",
                session_id=session_id,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("security_convergence_runner.failed", session_id=session_id, error=str(e))
            error_state = SecurityConvergenceState(
                session_id=evaluate_id,
                config=evaluate_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> SecurityConvergenceState | None:
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
