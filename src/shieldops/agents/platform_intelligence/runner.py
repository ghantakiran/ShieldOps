"""PlatformIntelligenceRunner — entry point for executing platform_intelligence workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.platform_intelligence.graph import create_platform_intelligence_graph
from shieldops.agents.platform_intelligence.models import PlatformIntelligenceState
from shieldops.agents.platform_intelligence.nodes import set_toolkit
from shieldops.agents.platform_intelligence.tools import PlatformIntelligenceToolkit

logger = structlog.get_logger()


class PlatformIntelligenceRunner:
    """Runner for the PlatformIntelligence Agent."""

    def __init__(
        self,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = PlatformIntelligenceToolkit(
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_platform_intelligence_graph()
        self._app = graph.compile()
        self._results: dict[str, PlatformIntelligenceState] = {}
        logger.info("platform_intelligence_runner.initialized")

    async def analyze(
        self,
        analyze_id: str,
        analyze_config: dict[str, Any] | None = None,
    ) -> PlatformIntelligenceState:
        """Run platform_intelligence workflow."""
        session_id = f"pi-{uuid4().hex[:12]}"
        initial_state = PlatformIntelligenceState(
            session_id=analyze_id,
            config=analyze_config or {},
        )

        logger.info(
            "platform_intelligence_runner.starting",
            session_id=session_id,
            analyze_id=analyze_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "platform_intelligence"}},
            )
            final_state = PlatformIntelligenceState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "platform_intelligence_runner.completed",
                session_id=session_id,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("platform_intelligence_runner.failed", session_id=session_id, error=str(e))
            error_state = PlatformIntelligenceState(
                session_id=analyze_id,
                config=analyze_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> PlatformIntelligenceState | None:
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
