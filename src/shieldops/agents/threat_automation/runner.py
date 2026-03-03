"""Threat Automation Agent runner — entry point for executing threat automation workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.threat_automation.graph import create_threat_automation_graph
from shieldops.agents.threat_automation.models import ThreatAutomationState
from shieldops.agents.threat_automation.nodes import set_toolkit
from shieldops.agents.threat_automation.tools import ThreatAutomationToolkit

logger = structlog.get_logger()


class ThreatAutomationRunner:
    """Runner for the Threat Automation Agent."""

    def __init__(
        self,
        threat_detector: Any | None = None,
        behavior_analyzer: Any | None = None,
        intel_provider: Any | None = None,
        response_engine: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = ThreatAutomationToolkit(
            threat_detector=threat_detector,
            behavior_analyzer=behavior_analyzer,
            intel_provider=intel_provider,
            response_engine=response_engine,
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_threat_automation_graph()
        self._app = graph.compile()
        self._results: dict[str, ThreatAutomationState] = {}
        logger.info("threat_automation_runner.initialized")

    async def hunt(
        self,
        hunt_id: str,
        hunt_config: dict[str, Any] | None = None,
    ) -> ThreatAutomationState:
        """Run threat automation hunt workflow."""
        session_id = f"ta-{uuid4().hex[:12]}"
        initial_state = ThreatAutomationState(
            hunt_id=hunt_id,
            hunt_config=hunt_config or {},
        )

        logger.info(
            "threat_automation_runner.starting",
            session_id=session_id,
            hunt_id=hunt_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "threat_automation"}},
            )
            final_state = ThreatAutomationState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "threat_automation_runner.completed",
                session_id=session_id,
                threat_count=final_state.threat_count,
                critical_count=final_state.critical_count,
                automated_responses=final_state.automated_responses,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("threat_automation_runner.failed", session_id=session_id, error=str(e))
            error_state = ThreatAutomationState(
                hunt_id=hunt_id,
                hunt_config=hunt_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> ThreatAutomationState | None:
        return self._results.get(session_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": sid,
                "hunt_id": state.hunt_id,
                "threat_count": state.threat_count,
                "critical_count": state.critical_count,
                "automated_responses": state.automated_responses,
                "current_step": state.current_step,
                "error": state.error,
            }
            for sid, state in self._results.items()
        ]
