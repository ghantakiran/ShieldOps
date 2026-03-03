"""XDRRunner — entry point for executing xdr workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.xdr.graph import create_xdr_graph
from shieldops.agents.xdr.models import XDRState
from shieldops.agents.xdr.nodes import set_toolkit
from shieldops.agents.xdr.tools import XDRToolkit

logger = structlog.get_logger()


class XDRRunner:
    """Runner for the XDR Agent."""

    def __init__(
        self,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = XDRToolkit(
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_xdr_graph()
        self._app = graph.compile()
        self._results: dict[str, XDRState] = {}
        logger.info("xdr_runner.initialized")

    async def investigate(
        self,
        investigate_id: str,
        investigate_config: dict[str, Any] | None = None,
    ) -> XDRState:
        """Run xdr workflow."""
        session_id = f"xdr-{uuid4().hex[:12]}"
        initial_state = XDRState(
            session_id=investigate_id,
            config=investigate_config or {},
        )

        logger.info(
            "xdr_runner.starting",
            session_id=session_id,
            investigate_id=investigate_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "xdr"}},
            )
            final_state = XDRState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "xdr_runner.completed",
                session_id=session_id,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("xdr_runner.failed", session_id=session_id, error=str(e))
            error_state = XDRState(
                session_id=investigate_id,
                config=investigate_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> XDRState | None:
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
