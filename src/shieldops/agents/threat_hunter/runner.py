"""Threat Hunter Agent runner — entry point for executing threat hunting workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.threat_hunter.graph import create_threat_hunter_graph
from shieldops.agents.threat_hunter.models import ThreatHunterState
from shieldops.agents.threat_hunter.nodes import set_toolkit
from shieldops.agents.threat_hunter.tools import ThreatHunterToolkit

logger = structlog.get_logger()


class ThreatHunterRunner:
    """Runner for the Threat Hunter Agent."""

    def __init__(
        self,
        mitre_mapper: Any | None = None,
        threat_intel: Any | None = None,
        ioc_scanner: Any | None = None,
        behavior_analyzer: Any | None = None,
        hunt_metrics: Any | None = None,
        policy_engine: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = ThreatHunterToolkit(
            mitre_mapper=mitre_mapper,
            threat_intel=threat_intel,
            ioc_scanner=ioc_scanner,
            behavior_analyzer=behavior_analyzer,
            hunt_metrics=hunt_metrics,
            policy_engine=policy_engine,
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_threat_hunter_graph()
        self._app = graph.compile()
        self._results: dict[str, ThreatHunterState] = {}
        logger.info("threat_hunter_runner.initialized")

    async def hunt(
        self,
        hypothesis: str,
        context: dict[str, Any] | None = None,
    ) -> ThreatHunterState:
        """Run a threat hunting campaign from a hypothesis."""
        session_id = f"hunt-{uuid4().hex[:12]}"
        hypothesis_id = f"hyp-{uuid4().hex[:8]}"
        ctx = context or {}

        initial_state = ThreatHunterState(
            hypothesis_id=hypothesis_id,
            hypothesis=hypothesis,
            hunt_scope=ctx.get("hunt_scope", {}),
            data_sources=ctx.get("data_sources", []),
        )

        logger.info(
            "threat_hunter_runner.starting",
            session_id=session_id,
            hypothesis_id=hypothesis_id,
            hypothesis=hypothesis[:100],
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "threat_hunter"}},
            )
            final_state = ThreatHunterState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "threat_hunter_runner.completed",
                session_id=session_id,
                threat_found=final_state.threat_found,
                effectiveness=final_state.effectiveness_score,
                recommendations=len(final_state.response_recommendations),
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("threat_hunter_runner.failed", session_id=session_id, error=str(e))
            error_state = ThreatHunterState(
                hypothesis_id=hypothesis_id,
                hypothesis=hypothesis,
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> ThreatHunterState | None:
        return self._results.get(session_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": sid,
                "hypothesis_id": state.hypothesis_id,
                "hypothesis": state.hypothesis[:80],
                "threat_found": state.threat_found,
                "effectiveness_score": state.effectiveness_score,
                "current_step": state.current_step,
                "error": state.error,
            }
            for sid, state in self._results.items()
        ]
