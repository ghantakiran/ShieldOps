"""Incident Response Agent runner — entry point for executing incident response workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.incident_response.graph import create_incident_response_graph
from shieldops.agents.incident_response.models import IncidentResponseState
from shieldops.agents.incident_response.nodes import set_toolkit
from shieldops.agents.incident_response.tools import IncidentResponseToolkit

logger = structlog.get_logger()


class IncidentResponseRunner:
    """Runner for the Incident Response Agent."""

    def __init__(
        self,
        containment_engine: Any | None = None,
        eradication_planner: Any | None = None,
        recovery_orchestrator: Any | None = None,
        policy_engine: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = IncidentResponseToolkit(
            containment_engine=containment_engine,
            eradication_planner=eradication_planner,
            recovery_orchestrator=recovery_orchestrator,
            policy_engine=policy_engine,
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_incident_response_graph()
        self._app = graph.compile()
        self._results: dict[str, IncidentResponseState] = {}
        logger.info("incident_response_runner.initialized")

    async def respond(
        self,
        incident_id: str,
        incident_data: dict[str, Any] | None = None,
    ) -> IncidentResponseState:
        """Run incident response workflow."""
        session_id = f"ir-{uuid4().hex[:12]}"
        initial_state = IncidentResponseState(
            incident_id=incident_id,
            incident_data=incident_data or {},
        )

        logger.info(
            "incident_response_runner.starting",
            session_id=session_id,
            incident_id=incident_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "incident_response"}},
            )
            final_state = IncidentResponseState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "incident_response_runner.completed",
                session_id=session_id,
                severity=final_state.severity,
                containment_complete=final_state.containment_complete,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("incident_response_runner.failed", session_id=session_id, error=str(e))
            error_state = IncidentResponseState(
                incident_id=incident_id,
                incident_data=incident_data or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> IncidentResponseState | None:
        return self._results.get(session_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": sid,
                "incident_id": state.incident_id,
                "severity": state.severity,
                "assessment_score": state.assessment_score,
                "containment_complete": state.containment_complete,
                "current_step": state.current_step,
                "error": state.error,
            }
            for sid, state in self._results.items()
        ]
