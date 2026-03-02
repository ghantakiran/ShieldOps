"""SOC Analyst Agent runner — entry point for executing SOC analysis workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.soc_analyst.graph import create_soc_analyst_graph
from shieldops.agents.soc_analyst.models import SOCAnalystState
from shieldops.agents.soc_analyst.nodes import set_toolkit
from shieldops.agents.soc_analyst.tools import SOCAnalystToolkit

logger = structlog.get_logger()


class SOCAnalystRunner:
    """Runner for the SOC Analyst Agent."""

    def __init__(
        self,
        mitre_mapper: Any | None = None,
        threat_intel: Any | None = None,
        soar_engine: Any | None = None,
        chain_reconstructor: Any | None = None,
        soc_metrics: Any | None = None,
        triage_scorer: Any | None = None,
        signal_correlator: Any | None = None,
        policy_engine: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = SOCAnalystToolkit(
            mitre_mapper=mitre_mapper,
            threat_intel=threat_intel,
            soar_engine=soar_engine,
            chain_reconstructor=chain_reconstructor,
            soc_metrics=soc_metrics,
            triage_scorer=triage_scorer,
            signal_correlator=signal_correlator,
            policy_engine=policy_engine,
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_soc_analyst_graph()
        self._app = graph.compile()
        self._results: dict[str, SOCAnalystState] = {}
        logger.info("soc_analyst_runner.initialized")

    async def analyze(
        self,
        alert_id: str,
        alert_data: dict[str, Any] | None = None,
    ) -> SOCAnalystState:
        """Run SOC analysis on an alert."""
        session_id = f"soc-{uuid4().hex[:12]}"
        initial_state = SOCAnalystState(
            alert_id=alert_id,
            alert_data=alert_data or {},
        )

        logger.info(
            "soc_analyst_runner.starting",
            session_id=session_id,
            alert_id=alert_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "soc_analyst"}},
            )
            final_state = SOCAnalystState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "soc_analyst_runner.completed",
                session_id=session_id,
                tier=final_state.tier,
                triage_score=final_state.triage_score,
                containment_count=len(final_state.containment_recommendations),
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("soc_analyst_runner.failed", session_id=session_id, error=str(e))
            error_state = SOCAnalystState(
                alert_id=alert_id,
                alert_data=alert_data or {},
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> SOCAnalystState | None:
        return self._results.get(session_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": sid,
                "alert_id": state.alert_id,
                "tier": state.tier,
                "triage_score": state.triage_score,
                "current_step": state.current_step,
                "error": state.error,
            }
            for sid, state in self._results.items()
        ]
