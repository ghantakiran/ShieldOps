"""Enterprise Integration Agent runner — entry point for managing integrations.

Takes an integration ID and action, constructs the LangGraph, runs it
end-to-end, and returns the completed integration state.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.enterprise_integration.graph import create_integration_graph
from shieldops.agents.enterprise_integration.models import (
    IntegrationDirection,
    IntegrationHealth,
    IntegrationState,
)
from shieldops.agents.enterprise_integration.nodes import set_toolkit
from shieldops.agents.enterprise_integration.tools import IntegrationToolkit
from shieldops.observability.tracing import get_tracer

logger = structlog.get_logger()


class IntegrationRunner:
    """Runs enterprise integration agent workflows.

    Usage:
        runner = IntegrationRunner(
            connector_router=router,
            notification_dispatcher=dispatcher,
            repository=repo,
        )
        result = await runner.check_integration("slack-main")
    """

    def __init__(
        self,
        connector_router: Any | None = None,
        notification_dispatcher: Any | None = None,
        repository: Any | None = None,
        ws_manager: Any | None = None,
    ) -> None:
        self._toolkit = IntegrationToolkit(
            connector_router=connector_router,
            notification_dispatcher=notification_dispatcher,
            repository=repository,
        )
        # Configure the module-level toolkit for nodes
        set_toolkit(self._toolkit)

        # Build the compiled graph
        graph = create_integration_graph()
        self._app = graph.compile()

        # In-memory store of completed runs (fallback when no DB)
        self._runs: dict[str, IntegrationState] = {}
        self._repository = repository
        self._ws_manager = ws_manager

    async def _run_workflow(
        self,
        integration_id: str,
        action: str,
    ) -> IntegrationState:
        """Execute the integration workflow for a given action.

        Args:
            integration_id: The integration to operate on.
            action: The action to perform (health_check, sync, configure, etc.).

        Returns:
            The completed IntegrationState.
        """
        run_id = f"intg-{uuid4().hex[:12]}"

        logger.info(
            "integration_workflow_started",
            run_id=run_id,
            integration_id=integration_id,
            action=action,
        )

        initial_state = IntegrationState(
            integration_id=integration_id,
            action=action,
        )

        try:
            tracer = get_tracer("shieldops.agents")
            with tracer.start_as_current_span("enterprise_integration.run") as span:
                span.set_attribute("integration.run_id", run_id)
                span.set_attribute("integration.id", integration_id)
                span.set_attribute("integration.action", action)

                final_state_dict = await self._app.ainvoke(
                    initial_state.model_dump(),  # type: ignore[arg-type]
                    config={
                        "metadata": {
                            "run_id": run_id,
                            "integration_id": integration_id,
                            "action": action,
                        },
                    },
                )

                final_state = IntegrationState.model_validate(final_state_dict)

                # Calculate total duration
                if final_state.action_start:
                    final_state.processing_duration_ms = int(
                        (datetime.now(UTC) - final_state.action_start).total_seconds() * 1000
                    )

                span.set_attribute(
                    "integration.duration_ms",
                    final_state.processing_duration_ms,
                )
                span.set_attribute(
                    "integration.status",
                    final_state.health.status if final_state.health else "unknown",
                )
                span.set_attribute(
                    "integration.recommendations_count",
                    len(final_state.recommendations),
                )

            logger.info(
                "integration_workflow_completed",
                run_id=run_id,
                integration_id=integration_id,
                action=action,
                duration_ms=final_state.processing_duration_ms,
                status=final_state.health.status if final_state.health else "unknown",
                recommendations=len(final_state.recommendations),
                diagnostics=len(final_state.diagnostics),
                steps=len(final_state.reasoning_chain),
            )

            self._runs[run_id] = final_state
            await self._persist(run_id, final_state)
            await self._broadcast(run_id, final_state)
            return final_state

        except Exception as e:
            logger.error(
                "integration_workflow_failed",
                run_id=run_id,
                integration_id=integration_id,
                action=action,
                error=str(e),
            )
            error_state = IntegrationState(
                integration_id=integration_id,
                action=action,
                error=str(e),
                current_step="failed",
            )
            self._runs[run_id] = error_state
            await self._persist(run_id, error_state)
            return error_state

    async def check_integration(self, integration_id: str) -> IntegrationState:
        """Run a health-check workflow for the integration.

        Args:
            integration_id: The integration to health-check.

        Returns:
            The completed IntegrationState with health and recommendations.
        """
        return await self._run_workflow(integration_id, "health_check")

    async def diagnose_integration(self, integration_id: str) -> IntegrationState:
        """Run a full diagnostic workflow for the integration.

        Args:
            integration_id: The integration to diagnose.

        Returns:
            The completed IntegrationState with diagnostics and recommendations.
        """
        return await self._run_workflow(integration_id, "diagnose")

    async def sync_integration(
        self,
        integration_id: str,
        direction: IntegrationDirection = IntegrationDirection.BIDIRECTIONAL,
    ) -> IntegrationState:
        """Trigger a data sync for the integration.

        Args:
            integration_id: The integration to sync.
            direction: The sync direction.

        Returns:
            The completed IntegrationState.
        """
        # Trigger sync directly via toolkit before running the workflow
        await self._toolkit.trigger_sync(integration_id, direction)
        return await self._run_workflow(integration_id, "sync")

    async def configure_integration(
        self,
        integration_id: str,
        config: dict[str, Any],
    ) -> IntegrationState:
        """Update integration configuration and re-check health.

        Args:
            integration_id: The integration to configure.
            config: Configuration updates to apply.

        Returns:
            The completed IntegrationState after configuration update.
        """
        await self._toolkit.update_config(integration_id, config)
        return await self._run_workflow(integration_id, "configure")

    async def list_integrations(self) -> list[dict[str, Any]]:
        """List all integrations with their current status.

        Returns:
            A list of summary dicts for each integration.
        """
        if self._repository is not None and hasattr(self._repository, "list_integrations"):
            try:
                raw: list[dict[str, Any]] = await self._repository.list_integrations()  # type: ignore[attr-defined]
                return raw
            except Exception as e:
                logger.error("list_integrations_failed", error=str(e))

        # Fallback: return summaries from in-memory runs
        seen: dict[str, dict[str, Any]] = {}
        for run_id, state in self._runs.items():
            if state.integration_id not in seen:
                seen[state.integration_id] = {
                    "integration_id": state.integration_id,
                    "status": (state.health.status if state.health else "unknown"),
                    "last_action": state.action,
                    "last_run_id": run_id,
                    "recommendations": len(state.recommendations),
                    "diagnostics": len(state.diagnostics),
                    "error": state.error,
                }
        return list(seen.values())

    async def get_integration_health(
        self,
        integration_id: str,
    ) -> IntegrationHealth:
        """Get current health for an integration without running a full workflow.

        Args:
            integration_id: The integration to query.

        Returns:
            An IntegrationHealth snapshot.
        """
        return await self._toolkit.check_health(integration_id)

    async def _broadcast(
        self,
        run_id: str,
        state: IntegrationState,
    ) -> None:
        """Broadcast progress via WebSocket if manager is available."""
        if self._ws_manager is None:
            return
        try:
            event = {
                "type": "integration_update",
                "run_id": run_id,
                "integration_id": state.integration_id,
                "action": state.action,
                "status": state.health.status if state.health else "unknown",
                "recommendations_count": len(state.recommendations),
                "diagnostics_count": len(state.diagnostics),
            }
            await self._ws_manager.broadcast("global", event)  # type: ignore[attr-defined]
            await self._ws_manager.broadcast(  # type: ignore[attr-defined]
                f"integration:{state.integration_id}",
                event,
            )
        except Exception as e:
            logger.warning("ws_broadcast_failed", run_id=run_id, error=str(e))

    async def _persist(
        self,
        run_id: str,
        state: IntegrationState,
    ) -> None:
        """Persist to DB if repository is available."""
        if self._repository is None:
            return
        if not hasattr(self._repository, "save_integration_run"):
            return
        try:
            await self._repository.save_integration_run(run_id, state)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(
                "integration_persist_failed",
                run_id=run_id,
                error=str(e),
            )

    def get_run(self, run_id: str) -> IntegrationState | None:
        """Retrieve a completed workflow run by ID."""
        return self._runs.get(run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        """List all workflow runs with summary info."""
        return [
            {
                "run_id": run_id,
                "integration_id": state.integration_id,
                "action": state.action,
                "status": state.health.status if state.health else "unknown",
                "recommendations": len(state.recommendations),
                "diagnostics": len(state.diagnostics),
                "duration_ms": state.processing_duration_ms,
                "current_step": state.current_step,
                "error": state.error,
            }
            for run_id, state in self._runs.items()
        ]
