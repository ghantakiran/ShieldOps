"""AutoRemediationRunner — entry point for executing auto remediation workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.auto_remediation.graph import create_auto_remediation_graph
from shieldops.agents.auto_remediation.models import AutoRemediationState
from shieldops.agents.auto_remediation.nodes import set_toolkit
from shieldops.agents.auto_remediation.tools import AutoRemediationToolkit

logger = structlog.get_logger()


class AutoRemediationRunner:
    """Runner for the Auto Remediation Agent."""

    def __init__(
        self,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = AutoRemediationToolkit(
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_auto_remediation_graph()
        self._app = graph.compile()
        self._results: dict[str, AutoRemediationState] = {}
        logger.info("auto_remediation_runner.initialized")

    async def execute(
        self,
        execute_id: str,
        remediation_config: dict[str, Any] | None = None,
    ) -> AutoRemediationState:
        """Run auto remediation workflow."""
        session_id = f"ar-{uuid4().hex[:12]}"
        initial_state = AutoRemediationState(
            session_id=execute_id,
            remediation_config=remediation_config or {},
        )

        logger.info(
            "auto_remediation_runner.starting",
            session_id=session_id,
            execute_id=execute_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "auto_remediation"}},
            )
            final_state = AutoRemediationState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "auto_remediation_runner.completed",
                session_id=session_id,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("auto_remediation_runner.failed", session_id=session_id, error=str(e))
            error_state = AutoRemediationState(
                session_id=execute_id,
                remediation_config=remediation_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> AutoRemediationState | None:
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
