"""Investigation Agent runner — entry point for executing investigations.

Takes an AlertContext, constructs the LangGraph, runs it end-to-end,
and returns the completed investigation state.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.investigation.graph import create_investigation_graph
from shieldops.agents.investigation.models import InvestigationState
from shieldops.agents.investigation.nodes import set_toolkit
from shieldops.agents.investigation.tools import InvestigationToolkit
from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import AlertContext
from shieldops.observability.base import LogSource, MetricSource, TraceSource

if __import__("typing").TYPE_CHECKING:
    from shieldops.db.repository import Repository

logger = structlog.get_logger()


class InvestigationRunner:
    """Runs investigation agent workflows.

    Usage:
        runner = InvestigationRunner(
            connector_router=router,
            log_sources=[k8s_logs],
            metric_sources=[prometheus],
        )
        result = await runner.investigate(alert_context)
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        log_sources: list[LogSource] | None = None,
        metric_sources: list[MetricSource] | None = None,
        trace_sources: list[TraceSource] | None = None,
        repository: "Repository | None" = None,
        ws_manager: "object | None" = None,
    ) -> None:
        self._toolkit = InvestigationToolkit(
            connector_router=connector_router,
            log_sources=log_sources or [],
            metric_sources=metric_sources or [],
            trace_sources=trace_sources or [],
        )
        # Configure the module-level toolkit for nodes
        set_toolkit(self._toolkit)

        # Build the compiled graph
        graph = create_investigation_graph()
        self._app = graph.compile()

        # In-memory store of completed investigations (fallback when no DB)
        self._investigations: dict[str, InvestigationState] = {}
        self._repository = repository
        self._ws_manager = ws_manager

    async def investigate(self, alert: AlertContext) -> InvestigationState:
        """Run a full investigation for an alert.

        Args:
            alert: The alert context that triggered this investigation.

        Returns:
            The completed InvestigationState with hypotheses and reasoning chain.
        """
        investigation_id = f"inv-{uuid4().hex[:12]}"

        logger.info(
            "investigation_started",
            investigation_id=investigation_id,
            alert_id=alert.alert_id,
            alert_name=alert.alert_name,
            severity=alert.severity,
        )

        initial_state = InvestigationState(
            alert_id=alert.alert_id,
            alert_context=alert,
        )

        try:
            # Run the LangGraph workflow
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={
                    "metadata": {
                        "investigation_id": investigation_id,
                        "alert_id": alert.alert_id,
                    },
                },
            )

            final_state = InvestigationState.model_validate(final_state_dict)

            # Calculate total duration
            if final_state.investigation_start:
                final_state.investigation_duration_ms = int(
                    (datetime.now(UTC) - final_state.investigation_start).total_seconds() * 1000
                )

            logger.info(
                "investigation_completed",
                investigation_id=investigation_id,
                alert_id=alert.alert_id,
                duration_ms=final_state.investigation_duration_ms,
                hypotheses_count=len(final_state.hypotheses),
                confidence=final_state.confidence_score,
                steps=len(final_state.reasoning_chain),
            )

            # Store result
            self._investigations[investigation_id] = final_state
            await self._persist(investigation_id, final_state)
            await self._broadcast(investigation_id, final_state)
            return final_state

        except Exception as e:
            logger.error(
                "investigation_failed",
                investigation_id=investigation_id,
                alert_id=alert.alert_id,
                error=str(e),
            )
            # Return partial state with error
            error_state = InvestigationState(
                alert_id=alert.alert_id,
                alert_context=alert,
                error=str(e),
                current_step="failed",
            )
            self._investigations[investigation_id] = error_state
            await self._persist(investigation_id, error_state)
            return error_state

    async def _broadcast(self, investigation_id: str, state: InvestigationState) -> None:
        """Broadcast progress via WebSocket if manager is available."""
        if self._ws_manager is None:
            return
        try:
            event = {
                "type": "investigation_update",
                "investigation_id": investigation_id,
                "status": state.current_step,
                "confidence": state.confidence_score,
                "hypotheses_count": len(state.hypotheses),
            }
            await self._ws_manager.broadcast("global", event)  # type: ignore[attr-defined]
            await self._ws_manager.broadcast(f"investigation:{investigation_id}", event)  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning("ws_broadcast_failed", id=investigation_id, error=str(e))

    async def _persist(self, investigation_id: str, state: InvestigationState) -> None:
        """Persist to DB if repository is available."""
        if self._repository is None:
            return
        try:
            await self._repository.save_investigation(investigation_id, state)
        except Exception as e:
            logger.error("investigation_persist_failed", id=investigation_id, error=str(e))

    def get_investigation(self, investigation_id: str) -> InvestigationState | None:
        """Retrieve a completed investigation by ID."""
        return self._investigations.get(investigation_id)

    def list_investigations(self) -> list[dict[str, Any]]:
        """List all investigations with summary info."""
        return [
            {
                "investigation_id": inv_id,
                "alert_id": state.alert_id,
                "alert_name": state.alert_context.alert_name,
                "status": state.current_step,
                "confidence": state.confidence_score,
                "hypotheses_count": len(state.hypotheses),
                "duration_ms": state.investigation_duration_ms,
                "error": state.error,
            }
            for inv_id, state in self._investigations.items()
        ]
