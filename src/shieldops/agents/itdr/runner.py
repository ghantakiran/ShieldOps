"""ITDRRunner — entry point for executing itdr workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.itdr.graph import create_itdr_graph
from shieldops.agents.itdr.models import ITDRState
from shieldops.agents.itdr.nodes import set_toolkit
from shieldops.agents.itdr.tools import ITDRToolkit

logger = structlog.get_logger()


class ITDRRunner:
    """Runner for the Itdr Agent."""

    def __init__(
        self,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = ITDRToolkit(
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_itdr_graph()
        self._app = graph.compile()
        self._results: dict[str, ITDRState] = {}
        logger.info("itdr_runner.initialized")

    async def detect(
        self,
        detect_id: str,
        detection_config: dict[str, Any] | None = None,
    ) -> ITDRState:
        """Run itdr workflow."""
        session_id = f"itdr-{uuid4().hex[:12]}"
        initial_state = ITDRState(
            session_id=detect_id,
            detection_config=detection_config or {},
        )

        logger.info(
            "itdr_runner.starting",
            session_id=session_id,
            detect_id=detect_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "itdr"}},
            )
            final_state = ITDRState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "itdr_runner.completed",
                session_id=session_id,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("itdr_runner.failed", session_id=session_id, error=str(e))
            error_state = ITDRState(
                session_id=detect_id,
                detection_config=detection_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> ITDRState | None:
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
