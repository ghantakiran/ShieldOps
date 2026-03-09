"""Node implementations for the Automation Orchestrator LangGraph workflow.

Each node is an async function that:
1. Evaluates triggers, policies, or executes actions via the AutomationToolkit
2. Uses the LLM to plan and summarize automation execution
3. Updates the automation state with results
4. Records its reasoning step in the audit trail
"""

from datetime import UTC, datetime
from typing import Any, cast

import structlog

from shieldops.agents.automation_orchestrator.models import (
    ActionResult,
    ActionStep,
    ActionType,
    AutomationState,
    ReasoningStep,
)
from shieldops.agents.automation_orchestrator.prompts import (
    SYSTEM_EVALUATE_TRIGGER,
    SYSTEM_PLAN_EXECUTION,
    SYSTEM_SUMMARIZE_EXECUTION,
    ExecutionPlan,
    ExecutionSummary,
    TriggerEvalResult,
)
from shieldops.agents.automation_orchestrator.tools import AutomationToolkit
from shieldops.utils.llm import llm_structured

logger = structlog.get_logger()

# Module-level toolkit reference, set by the runner at graph construction time.
_toolkit: AutomationToolkit | None = None


def set_toolkit(toolkit: AutomationToolkit) -> None:
    """Configure the toolkit used by all nodes. Called once at startup."""
    global _toolkit  # noqa: PLW0603
    _toolkit = toolkit


def _get_toolkit() -> AutomationToolkit:
    if _toolkit is None:
        return AutomationToolkit()  # Empty toolkit — safe for tests
    return _toolkit


async def evaluate_trigger(state: AutomationState) -> dict[str, Any]:
    """Check if the incoming event matches the rule's trigger conditions.

    Performs deterministic checks first, then uses the LLM for complex
    condition expression evaluation.
    """
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "automation_evaluating_trigger",
        event_id=state.event.id,
        rule_id=state.rule.id,
        rule_name=state.rule.name,
    )

    # Check cooldown and concurrency first
    cooldown = await toolkit.check_cooldown(state.rule)
    if cooldown["in_cooldown"]:
        step = ReasoningStep(
            step_number=1,
            action="evaluate_trigger",
            input_summary=(f"Event {state.event.id} against rule {state.rule.name}"),
            output_summary=(f"Rule in cooldown — {cooldown['remaining_seconds']}s remaining"),
            duration_ms=_elapsed_ms(start),
            tool_used="check_cooldown",
        )
        return {
            "execution_start": start,
            "policy_allowed": False,
            "policy_reason": (f"Rule in cooldown: {cooldown['remaining_seconds']}s remaining"),
            "overall_status": "denied",
            "reasoning_chain": [step],
            "current_step": "evaluate_trigger",
        }

    concurrency = await toolkit.check_concurrency(state.rule)
    if concurrency["at_limit"]:
        step = ReasoningStep(
            step_number=1,
            action="evaluate_trigger",
            input_summary=(f"Event {state.event.id} against rule {state.rule.name}"),
            output_summary=(
                f"Max concurrent executions reached "
                f"({concurrency['current_executions']}/{concurrency['max_concurrent']})"
            ),
            duration_ms=_elapsed_ms(start),
            tool_used="check_concurrency",
        )
        return {
            "execution_start": start,
            "policy_allowed": False,
            "policy_reason": "Max concurrent executions reached",
            "overall_status": "denied",
            "reasoning_chain": [step],
            "current_step": "evaluate_trigger",
        }

    # Deterministic trigger evaluation
    trigger_result = await toolkit.evaluate_trigger(state.event, state.rule)

    # If deterministic checks fail, skip LLM evaluation
    if not trigger_result["deterministic_match"]:
        step = ReasoningStep(
            step_number=1,
            action="evaluate_trigger",
            input_summary=(
                f"Event {state.event.id} (source={state.event.source}) "
                f"against rule trigger (type={state.rule.trigger.type}, "
                f"source={state.rule.trigger.source})"
            ),
            output_summary=(
                f"No match — type_match={trigger_result['type_match']}, "
                f"source_match={trigger_result['source_match']}"
            ),
            duration_ms=_elapsed_ms(start),
            tool_used="evaluate_trigger",
        )
        return {
            "execution_start": start,
            "policy_allowed": False,
            "policy_reason": "Event does not match trigger conditions",
            "overall_status": "denied",
            "reasoning_chain": [step],
            "current_step": "evaluate_trigger",
        }

    # LLM evaluation for complex condition expressions
    trigger_context = _format_trigger_context(state, trigger_result)
    matched = True
    confidence = 1.0
    matched_conditions: list[str] = ["type_match", "source_match"]
    output_summary = "Deterministic match confirmed"

    if state.rule.trigger.condition_expression:
        try:
            llm_result = cast(
                TriggerEvalResult,
                await llm_structured(
                    system_prompt=SYSTEM_EVALUATE_TRIGGER,
                    user_prompt=trigger_context,
                    schema=TriggerEvalResult,
                ),
            )
            matched = llm_result.matches
            confidence = llm_result.confidence
            matched_conditions.extend(llm_result.matched_conditions)
            output_summary = (
                f"Match={matched}, confidence={confidence:.2f}, conditions={matched_conditions}"
            )
        except Exception as e:
            logger.error("llm_trigger_eval_failed", error=str(e))
            output_summary = f"LLM evaluation failed: {e}. Falling back to deterministic match."

    step = ReasoningStep(
        step_number=1,
        action="evaluate_trigger",
        input_summary=(
            f"Event {state.event.id} against rule {state.rule.name} "
            f"(condition: {state.rule.trigger.condition_expression or 'none'})"
        ),
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="evaluate_trigger + llm",
    )

    return {
        "execution_start": start,
        "policy_allowed": matched,
        "policy_reason": "Trigger matched" if matched else "Trigger condition not met",
        "reasoning_chain": [step],
        "current_step": "evaluate_trigger",
    }


async def check_policy(state: AutomationState) -> dict[str, Any]:
    """Evaluate OPA policy gate for this automation rule."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "automation_checking_policy",
        rule_id=state.rule.id,
        policy_gate=state.rule.policy_gate,
    )

    policy_result = await toolkit.check_policy_gate(state.rule, state.event)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="check_policy",
        input_summary=(
            f"Evaluating OPA policy '{state.rule.policy_gate or 'none'}' for rule {state.rule.name}"
        ),
        output_summary=(
            f"Allowed={policy_result['allowed']}, "
            f"reason={policy_result['reason']}, "
            f"requires_approval={policy_result['requires_approval']}"
        ),
        duration_ms=_elapsed_ms(start),
        tool_used="opa_policy_engine",
    )

    return {
        "policy_allowed": policy_result["allowed"],
        "policy_reason": policy_result["reason"],
        "requires_approval": policy_result["requires_approval"],
        "approval_status": (
            "pending"
            if policy_result["requires_approval"]
            else "not_required"
            if policy_result["allowed"]
            else "denied"
        ),
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "check_policy",
    }


async def plan_execution(state: AutomationState) -> dict[str, Any]:
    """Use the LLM to plan the optimal execution of the action chain."""
    start = datetime.now(UTC)

    logger.info(
        "automation_planning_execution",
        rule_id=state.rule.id,
        action_count=len(state.rule.actions),
    )

    plan_context = _format_plan_context(state)
    action_order = list(range(len(state.rule.actions)))
    skip_actions: list[int] = []
    output_summary = f"Executing {len(state.rule.actions)} actions in order"

    try:
        plan = cast(
            ExecutionPlan,
            await llm_structured(
                system_prompt=SYSTEM_PLAN_EXECUTION,
                user_prompt=plan_context,
                schema=ExecutionPlan,
            ),
        )

        if not plan.should_execute:
            step = ReasoningStep(
                step_number=len(state.reasoning_chain) + 1,
                action="plan_execution",
                input_summary=f"Planning {len(state.rule.actions)} actions",
                output_summary=f"Execution not recommended: {plan.reasoning}",
                duration_ms=_elapsed_ms(start),
                tool_used="llm",
            )
            return {
                "overall_status": "denied",
                "summary": f"Execution plan rejected: {plan.reasoning}",
                "reasoning_chain": [*state.reasoning_chain, step],
                "current_step": "plan_execution",
            }

        action_order = plan.action_order
        skip_actions = plan.skip_actions
        output_summary = (
            f"Plan: execute {len(action_order)} actions, "
            f"skip {len(skip_actions)}. {plan.reasoning[:100]}"
        )
    except Exception as e:
        logger.error("llm_plan_execution_failed", error=str(e))
        output_summary = f"LLM planning failed: {e}. Using default sequential order."

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="plan_execution",
        input_summary=f"Planning execution of {len(state.rule.actions)} actions",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="llm",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "plan_execution",
    }


async def execute_actions(state: AutomationState) -> dict[str, Any]:
    """Execute each action step in sequence, handling failures."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "automation_executing_actions",
        rule_id=state.rule.id,
        action_count=len(state.rule.actions),
    )

    toolkit.increment_active(state.rule.id)
    results: list[ActionResult] = []
    event_context = {
        "event_id": state.event.id,
        "rule_id": state.rule.id,
        "rule_name": state.rule.name,
        "source": state.event.source,
        "trigger_data": state.event.trigger_data,
    }

    try:
        for i, action in enumerate(state.rule.actions):
            logger.info(
                "automation_executing_action",
                step_index=i,
                action_type=action.type,
                target=action.target,
            )

            # Route to the appropriate execution method
            result = await _execute_single_action(toolkit, action, event_context)
            result.step_index = i
            results.append(result)

            logger.info(
                "automation_action_completed",
                step_index=i,
                action_type=action.type,
                status=result.status,
                duration_ms=result.duration_ms,
            )

            # Stop on failure unless continue_on_failure is set
            if result.status == "failed" and not action.continue_on_failure:
                logger.warning(
                    "automation_action_chain_halted",
                    step_index=i,
                    error=result.error,
                )
                break

        # Record execution to audit trail
        await toolkit.record_execution(state.rule.id, state.event, results)
    finally:
        toolkit.decrement_active(state.rule.id)

    # Determine overall status
    if all(r.status == "success" for r in results):
        overall_status = "completed"
    elif any(r.status == "success" for r in results):
        overall_status = "partial"
    else:
        overall_status = "failed"

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="execute_actions",
        input_summary=f"Executing {len(state.rule.actions)} actions for rule {state.rule.name}",
        output_summary=(
            f"Completed {len(results)}/{len(state.rule.actions)} actions. "
            f"Status: {overall_status}. "
            f"Successes: {sum(1 for r in results if r.status == 'success')}, "
            f"failures: {sum(1 for r in results if r.status == 'failed')}"
        ),
        duration_ms=_elapsed_ms(start),
        tool_used="action_executor",
    )

    return {
        "action_results": results,
        "overall_status": overall_status,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "execute_actions",
    }


async def summarize_execution(state: AutomationState) -> dict[str, Any]:
    """Use the LLM to summarize the automation execution."""
    start = datetime.now(UTC)

    logger.info(
        "automation_summarizing",
        rule_id=state.rule.id,
        overall_status=state.overall_status,
    )

    summary_context = _format_summary_context(state)
    summary = (
        f"Rule '{state.rule.name}' executed with status: {state.overall_status}. "
        f"{len(state.action_results)} actions processed."
    )

    try:
        result = cast(
            ExecutionSummary,
            await llm_structured(
                system_prompt=SYSTEM_SUMMARIZE_EXECUTION,
                user_prompt=summary_context,
                schema=ExecutionSummary,
            ),
        )
        summary = result.summary
    except Exception as e:
        logger.error("llm_summarize_failed", error=str(e))

    duration_ms = 0
    if state.execution_start:
        duration_ms = int((datetime.now(UTC) - state.execution_start).total_seconds() * 1000)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="summarize_execution",
        input_summary=(
            f"Summarizing execution of rule {state.rule.name} ({len(state.action_results)} actions)"
        ),
        output_summary=summary[:200],
        duration_ms=_elapsed_ms(start),
        tool_used="llm",
    )

    return {
        "summary": summary,
        "execution_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "summarize_execution",
    }


async def send_notifications(state: AutomationState) -> dict[str, Any]:
    """Notify relevant channels about the automation execution."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "automation_sending_notifications",
        rule_id=state.rule.id,
        overall_status=state.overall_status,
    )

    notifications_sent: list[str] = []
    event_context = {
        "event_id": state.event.id,
        "rule_id": state.rule.id,
        "rule_name": state.rule.name,
        "overall_status": state.overall_status,
        "summary": state.summary,
        "action_results": [r.model_dump() for r in state.action_results],
    }

    # Send notifications for each notify-type action in the rule
    for action in state.rule.actions:
        if action.type == ActionType.NOTIFY:
            result = await toolkit.send_notification(
                action=action,
                event_context=event_context,
            )
            if result.status == "success":
                notifications_sent.append(action.target)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="send_notifications",
        input_summary=f"Sending notifications for rule {state.rule.name}",
        output_summary=f"Sent {len(notifications_sent)} notifications: {notifications_sent}",
        duration_ms=_elapsed_ms(start),
        tool_used="notification_dispatcher",
    )

    return {
        "notifications_sent": notifications_sent,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }


async def send_denial_notification(state: AutomationState) -> dict[str, Any]:
    """Notify about a denied automation execution."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "automation_sending_denial_notification",
        rule_id=state.rule.id,
        reason=state.policy_reason,
    )

    notifications_sent: list[str] = []

    # Find notification targets from the rule's actions
    for action in state.rule.actions:
        if action.type == ActionType.NOTIFY:
            result = await toolkit.send_notification(
                action=action,
                event_context={
                    "rule_name": state.rule.name,
                    "status": "denied",
                    "reason": state.policy_reason,
                },
            )
            if result.status == "success":
                notifications_sent.append(action.target)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="send_denial_notification",
        input_summary=(f"Notifying denial for rule {state.rule.name}: {state.policy_reason}"),
        output_summary=f"Sent {len(notifications_sent)} denial notifications",
        duration_ms=_elapsed_ms(start),
        tool_used="notification_dispatcher",
    )

    return {
        "notifications_sent": notifications_sent,
        "overall_status": "denied",
        "summary": f"Automation denied: {state.policy_reason}",
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }


async def queue_for_approval(state: AutomationState) -> dict[str, Any]:
    """Queue the automation execution for manual approval."""
    start = datetime.now(UTC)

    logger.info(
        "automation_queued_for_approval",
        rule_id=state.rule.id,
        event_id=state.event.id,
    )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="queue_for_approval",
        input_summary=f"Rule {state.rule.name} requires manual approval",
        output_summary="Execution queued for approval",
        duration_ms=_elapsed_ms(start),
        tool_used=None,
    )

    return {
        "approval_status": "pending",
        "overall_status": "awaiting_approval",
        "summary": (
            f"Rule '{state.rule.name}' requires manual approval. "
            f"Event: {state.event.id} from {state.event.source}"
        ),
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }


# --- Action routing ---


async def _execute_single_action(
    toolkit: AutomationToolkit,
    action: ActionStep,
    event_context: dict[str, Any],
) -> ActionResult:
    """Route a single action to the appropriate toolkit method."""
    if action.type in (
        ActionType.LAUNCH_AGENT,
        ActionType.INVESTIGATE,
        ActionType.ANALYZE,
        ActionType.BENCHMARK,
    ):
        return await toolkit.execute_agent_action(action, event_context)

    if action.type == ActionType.NOTIFY:
        return await toolkit.send_notification(action, event_context)

    if action.type == ActionType.CREATE_TICKET:
        return await toolkit.create_ticket(action, event_context)

    if action.type in (
        ActionType.REMEDIATE,
        ActionType.PATCH,
        ActionType.SCALE,
        ActionType.SCAN,
        ActionType.TAG,
    ):
        return await toolkit.execute_remediation(action, event_context)

    if action.type in (ActionType.GATE, ActionType.CHECK):
        result = await toolkit.check_policy_gate(
            rule=action,  # type: ignore[arg-type]
            event=None,  # type: ignore[arg-type]
        )
        return ActionResult(
            step_index=-1,
            action_type=action.type,
            target=action.target,
            status="success" if result.get("allowed") else "failed",
            output=result,
        )

    logger.warning("unknown_action_type", action_type=action.type)
    return ActionResult(
        step_index=-1,
        action_type=action.type,
        target=action.target,
        status="skipped",
        error=f"Unknown action type: {action.type}",
    )


# --- Context formatting helpers ---


def _elapsed_ms(start: datetime) -> int:
    return int((datetime.now(UTC) - start).total_seconds() * 1000)


def _format_trigger_context(
    state: AutomationState,
    trigger_result: dict[str, Any],
) -> str:
    """Format trigger evaluation context for LLM analysis."""
    lines = [
        "## Automation Rule",
        f"Name: {state.rule.name}",
        f"Description: {state.rule.description}",
        f"Category: {state.rule.category}",
        "",
        "## Trigger Condition",
        f"Type: {state.rule.trigger.type}",
        f"Source: {state.rule.trigger.source}",
        f"Condition Expression: {state.rule.trigger.condition_expression}",
        "",
        "## Incoming Event",
        f"Event ID: {state.event.id}",
        f"Source: {state.event.source}",
        f"Timestamp: {state.event.timestamp}",
        "",
        "## Event Data",
    ]
    for key, value in state.event.trigger_data.items():
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("## Deterministic Check Results")
    lines.append(f"Type match: {trigger_result['type_match']}")
    lines.append(f"Source match: {trigger_result['source_match']}")

    return "\n".join(lines)


def _format_plan_context(state: AutomationState) -> str:
    """Format execution planning context for LLM."""
    lines = [
        "## Automation Rule",
        f"Name: {state.rule.name}",
        f"Description: {state.rule.description}",
        "",
        "## Event Context",
        f"Source: {state.event.source}",
        f"Trigger Data: {state.event.trigger_data}",
        "",
        "## Action Chain",
    ]
    for i, action in enumerate(state.rule.actions):
        lines.append(
            f"Step {i}: [{action.type}] target={action.target}, "
            f"detail={action.detail}, "
            f"timeout={action.timeout_seconds}s, "
            f"continue_on_failure={action.continue_on_failure}"
        )

    lines.append("")
    lines.append("## Policy Evaluation")
    lines.append(f"Allowed: {state.policy_allowed}")
    lines.append(f"Reason: {state.policy_reason}")

    return "\n".join(lines)


def _format_summary_context(state: AutomationState) -> str:
    """Format execution results for LLM summarization."""
    lines = [
        "## Automation Rule",
        f"Name: {state.rule.name}",
        f"Description: {state.rule.description}",
        f"Category: {state.rule.category}",
        "",
        "## Triggering Event",
        f"Source: {state.event.source}",
        f"Trigger Data: {state.event.trigger_data}",
        "",
        f"## Action Results ({len(state.action_results)} actions)",
    ]
    for r in state.action_results:
        status_icon = "OK" if r.status == "success" else "FAIL"
        lines.append(
            f"- [{status_icon}] Step {r.step_index}: {r.action_type} -> {r.target} "
            f"({r.duration_ms}ms)"
        )
        if r.error:
            lines.append(f"  Error: {r.error}")

    lines.append("")
    lines.append(f"Overall Status: {state.overall_status}")

    if state.reasoning_chain:
        lines.append("")
        lines.append("## Reasoning Chain")
        for step in state.reasoning_chain:
            lines.append(f"Step {step.step_number} ({step.action}): {step.output_summary}")

    return "\n".join(lines)
