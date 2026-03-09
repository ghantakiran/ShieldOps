"""Automation Orchestrator runner — entry point for event-driven automation.

Processes incoming events against automation rules, evaluates OPA policy
gates, and executes action chains through the LangGraph workflow.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.automation_orchestrator.graph import create_automation_graph
from shieldops.agents.automation_orchestrator.models import (
    AutomationEvent,
    AutomationRule,
    AutomationState,
)
from shieldops.agents.automation_orchestrator.nodes import set_toolkit
from shieldops.agents.automation_orchestrator.tools import AutomationToolkit
from shieldops.observability.tracing import get_tracer

if __import__("typing").TYPE_CHECKING:
    from shieldops.db.repository import Repository

logger = structlog.get_logger()


class AutomationRunner:
    """Runs automation orchestrator workflows.

    Usage:
        runner = AutomationRunner(
            connector_router=router,
            policy_engine=opa_client,
            notification_dispatcher=dispatcher,
            agent_runners={"investigation_agent": inv_runner},
        )
        results = await runner.process_event(event_data, source="PagerDuty")
    """

    def __init__(
        self,
        connector_router: Any = None,
        policy_engine: Any = None,
        notification_dispatcher: Any = None,
        agent_runners: dict[str, Any] | None = None,
        repository: "Repository | None" = None,
        ws_manager: "object | None" = None,
    ) -> None:
        self._toolkit = AutomationToolkit(
            connector_router=connector_router,
            policy_engine=policy_engine,
            notification_dispatcher=notification_dispatcher,
            agent_runners=agent_runners or {},
            repository=repository,
        )
        # Configure the module-level toolkit for nodes
        set_toolkit(self._toolkit)

        # Build the compiled graph
        graph = create_automation_graph()
        self._app = graph.compile()

        # In-memory stores (fallback when no DB)
        self._rules: dict[str, AutomationRule] = {}
        self._executions: dict[str, AutomationState] = {}
        self._repository = repository
        self._ws_manager = ws_manager

    async def process_event(
        self,
        event_data: dict[str, Any],
        source: str = "",
    ) -> list[AutomationState]:
        """Process an incoming event against all enabled automation rules.

        Matches the event against every enabled rule and executes the
        workflow for each match.

        Args:
            event_data: Raw event payload.
            source: Event source identifier (e.g., "PagerDuty", "Kubernetes").

        Returns:
            List of completed AutomationState results for each matched rule.
        """
        event = AutomationEvent(
            id=f"evt-{uuid4().hex[:12]}",
            trigger_data=event_data,
            timestamp=datetime.now(UTC),
            source=source,
        )

        logger.info(
            "automation_processing_event",
            event_id=event.id,
            source=source,
            rules_count=len(self._rules),
        )

        results: list[AutomationState] = []
        enabled_rules = [r for r in self._rules.values() if r.enabled]

        for rule in enabled_rules:
            event_for_rule = event.model_copy(update={"rule_id": rule.id})
            try:
                state = await self.execute_rule_with_event(rule, event_for_rule)
                results.append(state)
            except Exception as e:
                logger.error(
                    "automation_rule_execution_failed",
                    rule_id=rule.id,
                    event_id=event.id,
                    error=str(e),
                )

        return results

    async def execute_rule(
        self,
        rule_id: str,
        event_data: dict[str, Any],
    ) -> AutomationState:
        """Execute a specific rule against an event.

        Args:
            rule_id: The automation rule ID.
            event_data: Raw event payload.

        Returns:
            The completed AutomationState.

        Raises:
            KeyError: If the rule does not exist.
        """
        rule = self._rules.get(rule_id)
        if rule is None:
            raise KeyError(f"Automation rule not found: {rule_id}")

        event = AutomationEvent(
            id=f"evt-{uuid4().hex[:12]}",
            rule_id=rule_id,
            trigger_data=event_data,
            timestamp=datetime.now(UTC),
            source=event_data.get("source", "manual"),
        )

        return await self.execute_rule_with_event(rule, event)

    async def execute_rule_with_event(
        self,
        rule: AutomationRule,
        event: AutomationEvent,
    ) -> AutomationState:
        """Execute a rule with a pre-constructed event."""
        execution_id = f"exec-{uuid4().hex[:12]}"

        logger.info(
            "automation_execution_started",
            execution_id=execution_id,
            rule_id=rule.id,
            rule_name=rule.name,
            event_id=event.id,
        )

        initial_state = AutomationState(
            event=event,
            rule=rule,
            execution_id=execution_id,
        )

        try:
            tracer = get_tracer("shieldops.agents")
            with tracer.start_as_current_span("automation_orchestrator.run") as span:
                span.set_attribute("automation.execution_id", execution_id)
                span.set_attribute("automation.rule_id", rule.id)
                span.set_attribute("automation.rule_name", rule.name)
                span.set_attribute("automation.event_id", event.id)

                final_state_dict = await self._app.ainvoke(
                    initial_state.model_dump(),  # type: ignore[arg-type]
                    config={
                        "metadata": {
                            "execution_id": execution_id,
                            "rule_id": rule.id,
                        },
                    },
                )

                final_state = AutomationState.model_validate(final_state_dict)

                # Calculate total duration
                if final_state.execution_start:
                    final_state.execution_duration_ms = int(
                        (datetime.now(UTC) - final_state.execution_start).total_seconds() * 1000
                    )

                span.set_attribute(
                    "automation.duration_ms",
                    final_state.execution_duration_ms,
                )
                span.set_attribute(
                    "automation.overall_status",
                    final_state.overall_status,
                )
                span.set_attribute(
                    "automation.actions_executed",
                    len(final_state.action_results),
                )

            logger.info(
                "automation_execution_completed",
                execution_id=execution_id,
                rule_id=rule.id,
                overall_status=final_state.overall_status,
                duration_ms=final_state.execution_duration_ms,
                actions_executed=len(final_state.action_results),
            )

            # Store result
            self._executions[execution_id] = final_state
            await self._persist(execution_id, final_state)
            await self._broadcast(execution_id, final_state)
            return final_state

        except Exception as e:
            logger.error(
                "automation_execution_failed",
                execution_id=execution_id,
                rule_id=rule.id,
                error=str(e),
            )
            error_state = AutomationState(
                event=event,
                rule=rule,
                execution_id=execution_id,
                error=str(e),
                overall_status="failed",
                current_step="failed",
            )
            self._executions[execution_id] = error_state
            await self._persist(execution_id, error_state)
            return error_state

    async def test_rule(
        self,
        rule_id: str,
        test_event: dict[str, Any],
    ) -> AutomationState:
        """Dry-run a rule without executing actions.

        Evaluates trigger and policy but skips actual action execution.

        Args:
            rule_id: The automation rule ID.
            test_event: Test event payload.

        Returns:
            The AutomationState showing what would happen.
        """
        rule = self._rules.get(rule_id)
        if rule is None:
            raise KeyError(f"Automation rule not found: {rule_id}")

        logger.info("automation_test_rule", rule_id=rule_id)

        event = AutomationEvent(
            id=f"test-{uuid4().hex[:12]}",
            rule_id=rule_id,
            trigger_data=test_event,
            timestamp=datetime.now(UTC),
            source=test_event.get("source", "test"),
        )

        # Run the graph but mark as test
        initial_state = AutomationState(
            event=event,
            rule=rule,
            execution_id=f"test-{uuid4().hex[:12]}",
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"dry_run": True}},
            )
            return AutomationState.model_validate(final_state_dict)
        except Exception as e:
            logger.error("automation_test_failed", rule_id=rule_id, error=str(e))
            return AutomationState(
                event=event,
                rule=rule,
                error=str(e),
                overall_status="failed",
                current_step="failed",
            )

    def create_rule(self, rule_config: dict[str, Any]) -> AutomationRule:
        """Create a new automation rule.

        Args:
            rule_config: Rule configuration dictionary.

        Returns:
            The created AutomationRule.
        """
        rule_id = rule_config.get("id", f"rule-{uuid4().hex[:12]}")
        rule_config["id"] = rule_id

        rule = AutomationRule.model_validate(rule_config)
        self._rules[rule_id] = rule

        logger.info(
            "automation_rule_created",
            rule_id=rule_id,
            rule_name=rule.name,
            category=rule.category,
        )
        return rule

    def update_rule(
        self,
        rule_id: str,
        updates: dict[str, Any],
    ) -> AutomationRule:
        """Update an existing automation rule.

        Args:
            rule_id: The rule ID to update.
            updates: Fields to update.

        Returns:
            The updated AutomationRule.

        Raises:
            KeyError: If the rule does not exist.
        """
        rule = self._rules.get(rule_id)
        if rule is None:
            raise KeyError(f"Automation rule not found: {rule_id}")

        updated_data = rule.model_dump()
        updated_data.update(updates)
        updated_rule = AutomationRule.model_validate(updated_data)
        self._rules[rule_id] = updated_rule

        logger.info("automation_rule_updated", rule_id=rule_id)
        return updated_rule

    def toggle_rule(self, rule_id: str, enabled: bool) -> AutomationRule:
        """Enable or disable an automation rule.

        Args:
            rule_id: The rule ID to toggle.
            enabled: Whether the rule should be enabled.

        Returns:
            The updated AutomationRule.
        """
        return self.update_rule(rule_id, {"enabled": enabled})

    def delete_rule(self, rule_id: str) -> None:
        """Delete an automation rule.

        Args:
            rule_id: The rule ID to delete.

        Raises:
            KeyError: If the rule does not exist.
        """
        if rule_id not in self._rules:
            raise KeyError(f"Automation rule not found: {rule_id}")

        del self._rules[rule_id]
        logger.info("automation_rule_deleted", rule_id=rule_id)

    def list_rules(
        self,
        category: str | None = None,
        enabled_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List automation rules with optional filters.

        Args:
            category: Filter by category if provided.
            enabled_only: If True, only return enabled rules.

        Returns:
            List of rule summaries.
        """
        rules = list(self._rules.values())

        if category:
            rules = [r for r in rules if r.category == category]
        if enabled_only:
            rules = [r for r in rules if r.enabled]

        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "category": r.category,
                "enabled": r.enabled,
                "trigger_type": r.trigger.type,
                "trigger_source": r.trigger.source,
                "action_count": len(r.actions),
                "policy_gate": r.policy_gate,
                "last_triggered": (r.last_triggered.isoformat() if r.last_triggered else None),
                "executions_24h": r.executions_24h,
                "total_executions": r.total_executions,
                "success_rate": r.success_rate,
            }
            for r in rules
        ]

    def get_rule(self, rule_id: str) -> AutomationRule | None:
        """Get a rule by ID."""
        return self._rules.get(rule_id)

    def get_execution_history(
        self,
        rule_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get execution history, optionally filtered by rule ID.

        Args:
            rule_id: Filter by rule ID if provided.
            limit: Maximum number of results.

        Returns:
            List of execution summaries.
        """
        executions = list(self._executions.values())

        if rule_id:
            executions = [e for e in executions if e.rule.id == rule_id]

        # Sort by execution start time, most recent first
        executions.sort(
            key=lambda e: e.execution_start or datetime.min,
            reverse=True,
        )

        return [
            {
                "execution_id": e.execution_id,
                "rule_id": e.rule.id,
                "rule_name": e.rule.name,
                "event_id": e.event.id,
                "event_source": e.event.source,
                "overall_status": e.overall_status,
                "actions_executed": len(e.action_results),
                "duration_ms": e.execution_duration_ms,
                "summary": e.summary,
                "error": e.error,
            }
            for e in executions[:limit]
        ]

    async def _broadcast(
        self,
        execution_id: str,
        state: AutomationState,
    ) -> None:
        """Broadcast progress via WebSocket if manager is available."""
        if self._ws_manager is None:
            return
        try:
            event = {
                "type": "automation_update",
                "execution_id": execution_id,
                "rule_id": state.rule.id,
                "status": state.overall_status,
                "actions_executed": len(state.action_results),
            }
            await self._ws_manager.broadcast("global", event)  # type: ignore[attr-defined]
            await self._ws_manager.broadcast(  # type: ignore[attr-defined]
                f"automation:{execution_id}", event
            )
        except Exception as e:
            logger.warning(
                "ws_broadcast_failed",
                id=execution_id,
                error=str(e),
            )

    async def _persist(
        self,
        execution_id: str,
        state: AutomationState,
    ) -> None:
        """Persist to DB if repository is available."""
        if self._repository is None:
            return
        if not hasattr(self._repository, "save_automation_execution"):
            logger.debug("repository_missing_save_automation_execution")
            return
        try:
            await self._repository.save_automation_execution(execution_id, state)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(
                "automation_persist_failed",
                id=execution_id,
                error=str(e),
            )
