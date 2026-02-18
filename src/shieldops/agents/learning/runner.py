"""Learning Agent runner — entry point for executing learning cycles.

Takes learning parameters, constructs the LangGraph, runs it end-to-end,
and returns the completed learning state with improvement recommendations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from shieldops.agents.learning.graph import create_learning_graph
from shieldops.agents.learning.models import LearningState
from shieldops.agents.learning.nodes import set_toolkit
from shieldops.agents.learning.tools import (
    IncidentStoreAdapter,
    LearningToolkit,
    PlaybookStoreAdapter,
)

if TYPE_CHECKING:
    from shieldops.db.repository import Repository
    from shieldops.playbooks.loader import PlaybookLoader

logger = structlog.get_logger()


class LearningRunner:
    """Runs learning agent workflows.

    Usage:
        runner = LearningRunner(
            repository=repo,
            playbook_loader=playbook_loader,
        )
        result = await runner.learn(period="30d")
    """

    def __init__(
        self,
        incident_store: Any | None = None,
        playbook_store: Any | None = None,
        alert_config_store: Any | None = None,
        repository: Repository | None = None,
        playbook_loader: PlaybookLoader | None = None,
    ) -> None:
        # Wire adapters when repository/loader are provided
        effective_incident_store = incident_store
        effective_playbook_store = playbook_store

        if repository is not None and effective_incident_store is None:
            effective_incident_store = IncidentStoreAdapter(repository)
        if playbook_loader is not None and effective_playbook_store is None:
            effective_playbook_store = PlaybookStoreAdapter(playbook_loader)

        self._toolkit = LearningToolkit(
            incident_store=effective_incident_store,
            playbook_store=effective_playbook_store,
            alert_config_store=alert_config_store,
        )
        set_toolkit(self._toolkit)

        graph = create_learning_graph()
        self._app = graph.compile()

        self._cycles: dict[str, LearningState] = {}

    async def learn(
        self,
        learning_type: str = "full",
        period: str = "30d",
    ) -> LearningState:
        """Run a learning cycle.

        Args:
            learning_type: Type of learning — full, pattern_only, playbook_only, threshold_only.
            period: Time period to analyze (e.g. 7d, 30d, 90d).

        Returns:
            The completed LearningState with all recommendations.
        """
        learning_id = f"learn-{uuid4().hex[:12]}"

        logger.info(
            "learning_cycle_started",
            learning_id=learning_id,
            learning_type=learning_type,
            period=period,
        )

        initial_state = LearningState(
            learning_id=learning_id,
            learning_type=learning_type,
            target_period=period,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),
                config={
                    "metadata": {
                        "learning_id": learning_id,
                        "learning_type": learning_type,
                    },
                },
            )

            final_state = LearningState.model_validate(final_state_dict)

            if final_state.learning_start:
                final_state.learning_duration_ms = int(
                    (datetime.now(timezone.utc) - final_state.learning_start).total_seconds()
                    * 1000
                )

            logger.info(
                "learning_cycle_completed",
                learning_id=learning_id,
                duration_ms=final_state.learning_duration_ms,
                incidents_analyzed=final_state.total_incidents_analyzed,
                patterns=len(final_state.pattern_insights),
                playbook_updates=len(final_state.playbook_updates),
                threshold_adjustments=len(final_state.threshold_adjustments),
                improvement_score=final_state.improvement_score,
                steps=len(final_state.reasoning_chain),
            )

            self._cycles[learning_id] = final_state
            return final_state

        except Exception as e:
            logger.error(
                "learning_cycle_failed",
                learning_id=learning_id,
                error=str(e),
            )
            error_state = LearningState(
                learning_id=learning_id,
                learning_type=learning_type,
                error=str(e),
                current_step="failed",
            )
            self._cycles[learning_id] = error_state
            return error_state

    def get_cycle(self, learning_id: str) -> LearningState | None:
        """Retrieve a completed learning cycle by ID."""
        return self._cycles.get(learning_id)

    def list_cycles(self) -> list[dict]:
        """List all learning cycles with summary info."""
        return [
            {
                "learning_id": learning_id,
                "learning_type": state.learning_type,
                "status": state.current_step,
                "incidents_analyzed": state.total_incidents_analyzed,
                "patterns_found": len(state.pattern_insights),
                "recurring_patterns": state.recurring_pattern_count,
                "playbook_updates": len(state.playbook_updates),
                "threshold_adjustments": len(state.threshold_adjustments),
                "improvement_score": state.improvement_score,
                "automation_accuracy": state.automation_accuracy,
                "duration_ms": state.learning_duration_ms,
                "error": state.error,
            }
            for learning_id, state in self._cycles.items()
        ]
