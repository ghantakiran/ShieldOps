"""Deception Agent runner -- entry point for executing deception campaign workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.deception.graph import create_deception_graph
from shieldops.agents.deception.models import DeceptionState
from shieldops.agents.deception.nodes import set_toolkit
from shieldops.agents.deception.tools import DeceptionToolkit

logger = structlog.get_logger()


class DeceptionRunner:
    """Runner for the Deception Agent."""

    def __init__(
        self,
        honeypot_manager: Any | None = None,
        interaction_monitor: Any | None = None,
        behavior_analyzer: Any | None = None,
        threat_intel: Any | None = None,
        policy_engine: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = DeceptionToolkit(
            honeypot_manager=honeypot_manager,
            interaction_monitor=interaction_monitor,
            behavior_analyzer=behavior_analyzer,
            threat_intel=threat_intel,
            policy_engine=policy_engine,
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_deception_graph()
        self._app = graph.compile()
        self._results: dict[str, DeceptionState] = {}
        logger.info("deception_runner.initialized")

    async def run_campaign(
        self,
        campaign_type: str,
        config: dict[str, Any] | None = None,
    ) -> DeceptionState:
        """Run a deception campaign."""
        session_id = f"deception-{uuid4().hex[:12]}"
        campaign_id = f"camp-{uuid4().hex[:8]}"

        initial_state = DeceptionState(
            campaign_id=campaign_id,
            campaign_type=campaign_type,
        )

        logger.info(
            "deception_runner.starting",
            session_id=session_id,
            campaign_id=campaign_id,
            campaign_type=campaign_type,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "deception"}},
            )
            final_state = DeceptionState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "deception_runner.completed",
                session_id=session_id,
                interaction_detected=final_state.interaction_detected,
                severity=final_state.severity_level,
                containment=final_state.containment_triggered,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("deception_runner.failed", session_id=session_id, error=str(e))
            error_state = DeceptionState(
                campaign_id=campaign_id,
                campaign_type=campaign_type,
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> DeceptionState | None:
        return self._results.get(session_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": sid,
                "campaign_id": state.campaign_id,
                "campaign_type": state.campaign_type,
                "interaction_detected": state.interaction_detected,
                "severity_level": state.severity_level,
                "containment_triggered": state.containment_triggered,
                "current_step": state.current_step,
                "error": state.error,
            }
            for sid, state in self._results.items()
        ]
