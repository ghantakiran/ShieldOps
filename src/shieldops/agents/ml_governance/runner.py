"""ML Governance Agent runner — entry point for executing ML governance workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.ml_governance.graph import create_ml_governance_graph
from shieldops.agents.ml_governance.models import MLGovernanceState
from shieldops.agents.ml_governance.nodes import set_toolkit
from shieldops.agents.ml_governance.tools import MLGovernanceToolkit

logger = structlog.get_logger()


class MLGovernanceRunner:
    """Runner for the ML Governance Agent."""

    def __init__(
        self,
        model_registry: Any | None = None,
        fairness_engine: Any | None = None,
        risk_assessor: Any | None = None,
        policy_engine: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = MLGovernanceToolkit(
            model_registry=model_registry,
            fairness_engine=fairness_engine,
            risk_assessor=risk_assessor,
            policy_engine=policy_engine,
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_ml_governance_graph()
        self._app = graph.compile()
        self._results: dict[str, MLGovernanceState] = {}
        logger.info("ml_governance_runner.initialized")

    async def evaluate(
        self,
        audit_id: str,
        audit_config: dict[str, Any] | None = None,
    ) -> MLGovernanceState:
        """Run ML governance evaluation workflow."""
        session_id = f"mg-{uuid4().hex[:12]}"
        initial_state = MLGovernanceState(
            session_id=audit_id,
            audit_config=audit_config or {},
        )

        logger.info(
            "ml_governance_runner.starting",
            session_id=session_id,
            audit_id=audit_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "ml_governance"}},
            )
            final_state = MLGovernanceState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "ml_governance_runner.completed",
                session_id=session_id,
                audit_count=final_state.audit_count,
                critical_count=final_state.critical_count,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("ml_governance_runner.failed", session_id=session_id, error=str(e))
            error_state = MLGovernanceState(
                session_id=audit_id,
                audit_config=audit_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> MLGovernanceState | None:
        return self._results.get(session_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": sid,
                "audit_id": state.session_id,
                "audit_count": state.audit_count,
                "critical_count": state.critical_count,
                "risk_score": state.risk_score,
                "current_step": state.current_step,
                "error": state.error,
            }
            for sid, state in self._results.items()
        ]
