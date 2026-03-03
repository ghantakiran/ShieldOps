"""IntelligentAutomationRunner — entry point for executing intelligent_automation workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.intelligent_automation.graph import create_intelligent_automation_graph
from shieldops.agents.intelligent_automation.models import IntelligentAutomationState
from shieldops.agents.intelligent_automation.nodes import set_toolkit
from shieldops.agents.intelligent_automation.tools import IntelligentAutomationToolkit

logger = structlog.get_logger()


class IntelligentAutomationRunner:
    """Runner for the IntelligentAutomation Agent."""

    def __init__(
        self,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = IntelligentAutomationToolkit(
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_intelligent_automation_graph()
        self._app = graph.compile()
        self._results: dict[str, IntelligentAutomationState] = {}
        logger.info("intelligent_automation_runner.initialized")

    async def execute(
        self,
        execute_id: str,
        execute_config: dict[str, Any] | None = None,
    ) -> IntelligentAutomationState:
        """Run intelligent_automation workflow."""
        session_id = f"ia-{uuid4().hex[:12]}"
        initial_state = IntelligentAutomationState(
            session_id=execute_id,
            config=execute_config or {},
        )

        logger.info(
            "intelligent_automation_runner.starting",
            session_id=session_id,
            execute_id=execute_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "intelligent_automation"}},
            )
            final_state = IntelligentAutomationState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "intelligent_automation_runner.completed",
                session_id=session_id,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error(
                "intelligent_automation_runner.failed",
                session_id=session_id,
                error=str(e),
            )
            error_state = IntelligentAutomationState(
                session_id=execute_id,
                config=execute_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> IntelligentAutomationState | None:
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
