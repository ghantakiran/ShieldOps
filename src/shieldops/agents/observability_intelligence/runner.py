"""ObservabilityIntelligenceRunner — observability intelligence workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.observability_intelligence.graph import (
    create_observability_intelligence_graph,
)
from shieldops.agents.observability_intelligence.models import ObservabilityIntelligenceState
from shieldops.agents.observability_intelligence.nodes import set_toolkit
from shieldops.agents.observability_intelligence.tools import ObservabilityIntelligenceToolkit

logger = structlog.get_logger()


class ObservabilityIntelligenceRunner:
    """Runner for the ObservabilityIntelligence Agent."""

    def __init__(
        self,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = ObservabilityIntelligenceToolkit(
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_observability_intelligence_graph()
        self._app = graph.compile()
        self._results: dict[str, ObservabilityIntelligenceState] = {}
        logger.info("observability_intelligence_runner.initialized")

    async def analyze(
        self,
        analyze_id: str,
        analyze_config: dict[str, Any] | None = None,
    ) -> ObservabilityIntelligenceState:
        """Run observability_intelligence workflow."""
        session_id = f"oi-{uuid4().hex[:12]}"
        initial_state = ObservabilityIntelligenceState(
            session_id=analyze_id,
            config=analyze_config or {},
        )

        logger.info(
            "observability_intelligence_runner.starting",
            session_id=session_id,
            analyze_id=analyze_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={
                    "metadata": {
                        "session_id": session_id,
                        "agent": "observability_intelligence",
                    },
                },
            )
            final_state = ObservabilityIntelligenceState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "observability_intelligence_runner.completed",
                session_id=session_id,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error(
                "observability_intelligence_runner.failed",
                session_id=session_id,
                error=str(e),
            )
            error_state = ObservabilityIntelligenceState(
                session_id=analyze_id,
                config=analyze_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> ObservabilityIntelligenceState | None:
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
