"""Supervisor Agent runner — entry point for orchestrating specialist agents.

Takes incoming events, constructs the LangGraph, runs the supervisor
workflow end-to-end, and returns the completed orchestration state.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.supervisor.graph import create_supervisor_graph
from shieldops.agents.supervisor.models import SupervisorState
from shieldops.agents.supervisor.nodes import set_toolkit
from shieldops.agents.supervisor.tools import SupervisorToolkit

logger = structlog.get_logger()


class SupervisorRunner:
    """Runs supervisor orchestration workflows.

    Usage:
        runner = SupervisorRunner(
            agent_runners={"investigation": inv_runner, "remediation": rem_runner},
        )
        result = await runner.handle_event({"type": "alert", "severity": "critical"})
    """

    def __init__(
        self,
        agent_runners: dict[str, Any] | None = None,
        notification_channels: dict[str, Any] | None = None,
        playbook_loader: Any = None,
    ) -> None:
        self._toolkit = SupervisorToolkit(
            agent_runners=agent_runners or {},
            notification_channels=notification_channels or {},
            playbook_loader=playbook_loader,
        )
        set_toolkit(self._toolkit)

        graph = create_supervisor_graph()
        self._app = graph.compile()

        self._sessions: dict[str, SupervisorState] = {}

    async def handle_event(
        self,
        event: dict[str, Any],
    ) -> SupervisorState:
        """Handle an incoming event through the supervisor workflow.

        Args:
            event: The incoming event dict with at least a "type" field.

        Returns:
            The completed SupervisorState with all delegation and escalation records.
        """
        session_id = f"sup-{uuid4().hex[:12]}"

        logger.info(
            "supervisor_session_started",
            session_id=session_id,
            event_type=event.get("type", "unknown"),
        )

        initial_state = SupervisorState(
            session_id=session_id,
            event=event,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),
                config={
                    "metadata": {
                        "session_id": session_id,
                        "event_type": event.get("type", "unknown"),
                    },
                },
            )

            final_state = SupervisorState.model_validate(final_state_dict)

            if final_state.session_start:
                final_state.session_duration_ms = int(
                    (datetime.now(timezone.utc) - final_state.session_start).total_seconds()
                    * 1000
                )

            logger.info(
                "supervisor_session_completed",
                session_id=session_id,
                duration_ms=final_state.session_duration_ms,
                tasks=len(final_state.delegated_tasks),
                chains=len(final_state.chained_workflows),
                escalations=len(final_state.escalations),
                steps=len(final_state.reasoning_chain),
            )

            self._sessions[session_id] = final_state
            return final_state

        except Exception as e:
            logger.error(
                "supervisor_session_failed",
                session_id=session_id,
                error=str(e),
            )
            error_state = SupervisorState(
                session_id=session_id,
                event=event,
                error=str(e),
                current_step="failed",
            )
            self._sessions[session_id] = error_state
            return error_state

    def get_session(self, session_id: str) -> SupervisorState | None:
        """Retrieve a completed session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict]:
        """List all sessions with summary info."""
        return [
            {
                "session_id": session_id,
                "event_type": state.event.get("type", "unknown"),
                "status": state.current_step,
                "classification": state.classification.task_type.value if state.classification else None,
                "priority": state.classification.priority if state.classification else None,
                "tasks_delegated": len(state.delegated_tasks),
                "chains": len(state.chained_workflows),
                "escalations": len(state.escalations),
                "duration_ms": state.session_duration_ms,
                "error": state.error,
            }
            for session_id, state in self._sessions.items()
        ]
