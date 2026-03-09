"""Tool functions for the Automation Orchestrator Agent.

These bridge automation rule evaluation, policy enforcement, and action
execution to the agent's LangGraph nodes. Each tool is a self-contained
async function that interacts with external systems and returns structured data.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from shieldops.agents.automation_orchestrator.models import (
    ActionResult,
    ActionStep,
    ActionType,
    AutomationEvent,
    AutomationRule,
)

logger = structlog.get_logger()


class AutomationToolkit:
    """Collection of tools available to the automation orchestrator agent.

    Injected into nodes at graph construction time to decouple agent logic
    from specific connector implementations.
    """

    def __init__(
        self,
        connector_router: Any = None,
        policy_engine: Any = None,
        notification_dispatcher: Any = None,
        agent_runners: dict[str, Any] | None = None,
        repository: Any = None,
    ) -> None:
        self._router = connector_router
        self._policy_engine = policy_engine
        self._notification_dispatcher = notification_dispatcher
        self._agent_runners = agent_runners or {}
        self._repository = repository
        self._active_executions: dict[str, int] = {}  # rule_id -> count

    async def evaluate_trigger(
        self,
        event: AutomationEvent,
        rule: AutomationRule,
    ) -> dict[str, Any]:
        """Check if an event matches a rule's trigger conditions.

        Performs deterministic checks (type, source) and returns the raw
        event context for LLM-based expression evaluation.
        """
        logger.info(
            "evaluating_trigger",
            event_id=event.id,
            rule_id=rule.id,
            trigger_type=rule.trigger.type,
        )

        type_match = event.trigger_data.get("type", "") == rule.trigger.type
        source_match = (
            not rule.trigger.source or event.source.lower() == rule.trigger.source.lower()
        )

        return {
            "type_match": type_match,
            "source_match": source_match,
            "deterministic_match": type_match and source_match,
            "condition_expression": rule.trigger.condition_expression,
            "event_data": event.trigger_data,
            "event_source": event.source,
        }

    async def check_policy_gate(
        self,
        rule: AutomationRule,
        event: AutomationEvent,
    ) -> dict[str, Any]:
        """Evaluate OPA policy for this automation rule.

        Returns whether the policy allows execution and the reason.
        """
        if not rule.policy_gate:
            return {
                "allowed": True,
                "reason": "No policy gate configured",
                "requires_approval": False,
            }

        if self._policy_engine is None:
            logger.warning("policy_engine_not_configured", rule_id=rule.id)
            return {
                "allowed": True,
                "reason": "Policy engine not available — defaulting to allow",
                "requires_approval": False,
            }

        try:
            input_data = {
                "rule_id": rule.id,
                "rule_name": rule.name,
                "category": rule.category,
                "trigger_type": rule.trigger.type,
                "event_source": event.source,
                "event_data": event.trigger_data,
                "actions": [{"type": a.type, "target": a.target} for a in rule.actions],
            }

            result = await self._policy_engine.evaluate(
                policy=rule.policy_gate,
                input_data=input_data,
            )

            return {
                "allowed": result.get("allow", False),
                "reason": result.get("reason", "Policy evaluation completed"),
                "requires_approval": result.get("requires_approval", False),
            }
        except Exception as e:
            logger.error(
                "policy_evaluation_failed",
                rule_id=rule.id,
                policy=rule.policy_gate,
                error=str(e),
            )
            return {
                "allowed": False,
                "reason": f"Policy evaluation error: {e}",
                "requires_approval": False,
            }

    async def check_cooldown(self, rule: AutomationRule) -> dict[str, Any]:
        """Check if a rule is in its cooldown period.

        Returns whether the rule can execute and remaining cooldown time.
        """
        if rule.trigger.cooldown_seconds <= 0:
            return {"in_cooldown": False, "remaining_seconds": 0}

        if rule.last_triggered is None:
            return {"in_cooldown": False, "remaining_seconds": 0}

        cooldown_end = rule.last_triggered + timedelta(seconds=rule.trigger.cooldown_seconds)
        now = datetime.now(UTC)

        if now < cooldown_end:
            remaining = int((cooldown_end - now).total_seconds())
            return {"in_cooldown": True, "remaining_seconds": remaining}

        return {"in_cooldown": False, "remaining_seconds": 0}

    async def check_concurrency(self, rule: AutomationRule) -> dict[str, Any]:
        """Check if max concurrent executions for this rule have been reached."""
        current = self._active_executions.get(rule.id, 0)
        at_limit = current >= rule.max_concurrent

        return {
            "at_limit": at_limit,
            "current_executions": current,
            "max_concurrent": rule.max_concurrent,
        }

    async def execute_agent_action(
        self,
        action: ActionStep,
        event_context: dict[str, Any],
    ) -> ActionResult:
        """Execute an agent-based action (launch_agent, investigate, analyze)."""
        start = datetime.now(UTC)

        agent_name = action.target.lower().replace(" ", "_")
        runner = self._agent_runners.get(agent_name)

        if runner is None:
            logger.warning(
                "agent_runner_not_found",
                agent=agent_name,
                available=list(self._agent_runners.keys()),
            )
            return ActionResult(
                step_index=-1,
                action_type=action.type,
                target=action.target,
                status="failed",
                error=f"Agent runner not found: {agent_name}",
                duration_ms=_elapsed_ms(start),
            )

        try:
            result = await runner.run(
                event_context=event_context,
                parameters=action.parameters,
            )

            return ActionResult(
                step_index=-1,
                action_type=action.type,
                target=action.target,
                status="success",
                output=result if isinstance(result, dict) else {"result": str(result)},
                duration_ms=_elapsed_ms(start),
            )
        except Exception as e:
            logger.error(
                "agent_action_failed",
                agent=agent_name,
                error=str(e),
            )
            return ActionResult(
                step_index=-1,
                action_type=action.type,
                target=action.target,
                status="failed",
                error=str(e),
                duration_ms=_elapsed_ms(start),
            )

    async def send_notification(
        self,
        action: ActionStep,
        event_context: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> ActionResult:
        """Send a notification via the configured dispatcher."""
        start = datetime.now(UTC)

        if self._notification_dispatcher is None:
            logger.warning("notification_dispatcher_not_configured")
            return ActionResult(
                step_index=-1,
                action_type=ActionType.NOTIFY,
                target=action.target,
                status="skipped",
                error="Notification dispatcher not available",
                duration_ms=_elapsed_ms(start),
            )

        try:
            payload = {
                "channel": action.target,
                "message": action.detail or "Automation rule triggered",
                "event_context": event_context,
                "action_result": result,
                **action.parameters,
            }

            await self._notification_dispatcher.send(payload)

            return ActionResult(
                step_index=-1,
                action_type=ActionType.NOTIFY,
                target=action.target,
                status="success",
                output={"channel": action.target, "sent": True},
                duration_ms=_elapsed_ms(start),
            )
        except Exception as e:
            logger.error(
                "notification_failed",
                target=action.target,
                error=str(e),
            )
            return ActionResult(
                step_index=-1,
                action_type=ActionType.NOTIFY,
                target=action.target,
                status="failed",
                error=str(e),
                duration_ms=_elapsed_ms(start),
            )

    async def create_ticket(
        self,
        action: ActionStep,
        event_context: dict[str, Any],
    ) -> ActionResult:
        """Create a ticket in Jira/ServiceNow via connector router."""
        start = datetime.now(UTC)

        if self._router is None:
            return ActionResult(
                step_index=-1,
                action_type=ActionType.CREATE_TICKET,
                target=action.target,
                status="skipped",
                error="Connector router not available",
                duration_ms=_elapsed_ms(start),
            )

        try:
            ticket_data = {
                "project": action.parameters.get("project", "OPS"),
                "summary": action.detail or f"Automation: {event_context.get('rule_name', '')}",
                "description": (
                    f"Triggered by event from {event_context.get('source', 'unknown')}\n\n"
                    f"Event data: {event_context.get('trigger_data', {})}"
                ),
                "priority": action.parameters.get("priority", "medium"),
                **action.parameters,
            }

            connector = self._router.get(action.target.lower())
            result = await connector.create_ticket(ticket_data)

            return ActionResult(
                step_index=-1,
                action_type=ActionType.CREATE_TICKET,
                target=action.target,
                status="success",
                output=result if isinstance(result, dict) else {"ticket_id": str(result)},
                duration_ms=_elapsed_ms(start),
            )
        except Exception as e:
            logger.error(
                "ticket_creation_failed",
                target=action.target,
                error=str(e),
            )
            return ActionResult(
                step_index=-1,
                action_type=ActionType.CREATE_TICKET,
                target=action.target,
                status="failed",
                error=str(e),
                duration_ms=_elapsed_ms(start),
            )

    async def execute_remediation(
        self,
        action: ActionStep,
        event_context: dict[str, Any],
    ) -> ActionResult:
        """Execute an infrastructure remediation action."""
        start = datetime.now(UTC)

        if self._router is None:
            return ActionResult(
                step_index=-1,
                action_type=action.type,
                target=action.target,
                status="skipped",
                error="Connector router not available",
                duration_ms=_elapsed_ms(start),
            )

        try:
            provider = action.parameters.get("provider", "kubernetes")
            connector = self._router.get(provider)

            remediation_params = {
                "action": action.type,
                "target": action.target,
                "event_context": event_context,
                **action.parameters,
            }

            result = await connector.execute_action(remediation_params)

            return ActionResult(
                step_index=-1,
                action_type=action.type,
                target=action.target,
                status="success",
                output=result if isinstance(result, dict) else {"result": str(result)},
                duration_ms=_elapsed_ms(start),
            )
        except Exception as e:
            logger.error(
                "remediation_failed",
                action_type=action.type,
                target=action.target,
                error=str(e),
            )
            return ActionResult(
                step_index=-1,
                action_type=action.type,
                target=action.target,
                status="failed",
                error=str(e),
                duration_ms=_elapsed_ms(start),
            )

    async def record_execution(
        self,
        rule_id: str,
        event: AutomationEvent,
        results: list[ActionResult],
    ) -> None:
        """Record an execution to the audit trail."""
        if self._repository is None:
            logger.debug("repository_not_available_skipping_record")
            return

        try:
            record = {
                "rule_id": rule_id,
                "event_id": event.id,
                "event_source": event.source,
                "trigger_data": event.trigger_data,
                "timestamp": datetime.now(UTC).isoformat(),
                "results": [r.model_dump() for r in results],
                "overall_status": (
                    "success"
                    if all(r.status == "success" for r in results)
                    else "partial"
                    if any(r.status == "success" for r in results)
                    else "failed"
                ),
            }
            await self._repository.save_automation_execution(record)
        except Exception as e:
            logger.error(
                "execution_record_failed",
                rule_id=rule_id,
                error=str(e),
            )

    async def get_execution_history(
        self,
        rule_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get recent executions for a rule."""
        if self._repository is None:
            return []

        try:
            result: list[dict[str, Any]] = await self._repository.get_automation_executions(
                rule_id=rule_id,
                limit=limit,
            )
            return result
        except Exception as e:
            logger.warning(
                "execution_history_query_failed",
                rule_id=rule_id,
                error=str(e),
            )
            return []

    def increment_active(self, rule_id: str) -> None:
        """Increment active execution count for a rule."""
        self._active_executions[rule_id] = self._active_executions.get(rule_id, 0) + 1

    def decrement_active(self, rule_id: str) -> None:
        """Decrement active execution count for a rule."""
        current = self._active_executions.get(rule_id, 0)
        self._active_executions[rule_id] = max(0, current - 1)


def _elapsed_ms(start: datetime) -> int:
    return int((datetime.now(UTC) - start).total_seconds() * 1000)
