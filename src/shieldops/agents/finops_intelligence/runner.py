"""FinOps Intelligence Agent runner — entry point for executing FinOps workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.finops_intelligence.graph import create_finops_intelligence_graph
from shieldops.agents.finops_intelligence.models import FinOpsIntelligenceState
from shieldops.agents.finops_intelligence.nodes import set_toolkit
from shieldops.agents.finops_intelligence.tools import FinOpsIntelligenceToolkit

logger = structlog.get_logger()


class FinOpsIntelligenceRunner:
    """Runner for the FinOps Intelligence Agent."""

    def __init__(
        self,
        cost_analyzer: Any | None = None,
        optimization_engine: Any | None = None,
        budget_manager: Any | None = None,
        policy_engine: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = FinOpsIntelligenceToolkit(
            cost_analyzer=cost_analyzer,
            optimization_engine=optimization_engine,
            budget_manager=budget_manager,
            policy_engine=policy_engine,
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_finops_intelligence_graph()
        self._app = graph.compile()
        self._results: dict[str, FinOpsIntelligenceState] = {}
        logger.info("finops_intelligence_runner.initialized")

    async def analyze(
        self,
        session_id: str,
        analysis_config: dict[str, Any] | None = None,
    ) -> FinOpsIntelligenceState:
        """Run FinOps intelligence analysis workflow."""
        run_id = f"fi-{uuid4().hex[:12]}"
        initial_state = FinOpsIntelligenceState(
            session_id=session_id,
            analysis_config=analysis_config or {},
        )

        logger.info(
            "finops_intelligence_runner.starting",
            run_id=run_id,
            session_id=session_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": run_id, "agent": "finops_intelligence"}},
            )
            final_state = FinOpsIntelligenceState.model_validate(final_state_dict)
            self._results[run_id] = final_state

            logger.info(
                "finops_intelligence_runner.completed",
                run_id=run_id,
                finding_count=final_state.finding_count,
                savings_potential=final_state.savings_potential,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("finops_intelligence_runner.failed", run_id=run_id, error=str(e))
            error_state = FinOpsIntelligenceState(
                session_id=session_id,
                analysis_config=analysis_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[run_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> FinOpsIntelligenceState | None:
        return self._results.get(session_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": sid,
                "analysis_session_id": state.session_id,
                "finding_count": state.finding_count,
                "savings_potential": state.savings_potential,
                "high_impact_count": state.high_impact_count,
                "current_step": state.current_step,
                "error": state.error,
            }
            for sid, state in self._results.items()
        ]
