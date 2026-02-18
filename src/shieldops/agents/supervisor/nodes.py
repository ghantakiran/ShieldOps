"""Node implementations for the Supervisor Agent LangGraph workflow.

Each node is an async function that:
1. Classifies, dispatches, monitors, or escalates via the SupervisorToolkit
2. Uses the LLM to enhance rule-based decisions
3. Updates the supervisor state with results
4. Records its reasoning step in the audit trail
"""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import structlog

from shieldops.agents.supervisor.models import (
    ChainedWorkflow,
    EscalationRecord,
    EventClassification,
    SupervisorState,
    SupervisorStep,
    TaskStatus,
    TaskType,
)
from shieldops.agents.supervisor.prompts import (
    SYSTEM_CHAIN_DECISION,
    SYSTEM_EVENT_CLASSIFICATION,
    ChainDecisionResult,
    EventClassificationResult,
)
from shieldops.agents.supervisor.tools import SupervisorToolkit
from shieldops.utils.llm import llm_structured

logger = structlog.get_logger()

# Module-level toolkit reference, set by the runner at graph construction time.
_toolkit: SupervisorToolkit | None = None


def set_toolkit(toolkit: SupervisorToolkit | None) -> None:
    """Configure the toolkit used by all nodes. Called once at startup."""
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> SupervisorToolkit:
    if _toolkit is None:
        return SupervisorToolkit()
    return _toolkit


def _elapsed_ms(start: datetime) -> int:
    return int((datetime.now(UTC) - start).total_seconds() * 1000)


async def classify_event(state: SupervisorState) -> dict[str, Any]:
    """Classify the incoming event and determine which agent should handle it."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "supervisor_classifying_event",
        session_id=state.session_id,
        event_type=state.event.get("type", "unknown"),
    )

    # Rule-based classification as baseline
    rules_result = toolkit.classify_event_rules(state.event)

    task_type = TaskType(rules_result["task_type"])
    priority = rules_result["priority"]
    confidence = rules_result["confidence"]
    reasoning = rules_result["reasoning"]

    # LLM enhancement for ambiguous events
    if confidence < 0.9:
        context_lines = [
            "## Incoming Event",
            f"Type: {state.event.get('type', 'unknown')}",
            f"Severity: {state.event.get('severity', 'unknown')}",
            f"Source: {state.event.get('source', 'unknown')}",
        ]
        if state.event.get("description"):
            context_lines.append(f"Description: {state.event['description']}")
        if state.event.get("resource_id"):
            context_lines.append(f"Resource: {state.event['resource_id']}")
        context_lines.extend(
            [
                "",
                (
                    f"Rule-based suggestion: {rules_result['task_type']} "
                    f"(confidence: {confidence:.0%})"
                ),
            ]
        )

        try:
            assessment = cast(
                EventClassificationResult,
                await llm_structured(
                    system_prompt=SYSTEM_EVENT_CLASSIFICATION,
                    user_prompt="\n".join(context_lines),
                    schema=EventClassificationResult,
                ),
            )
            task_type = TaskType(assessment.task_type)
            priority = assessment.priority
            confidence = assessment.confidence
            reasoning = assessment.reasoning
        except Exception as e:
            logger.error("llm_event_classification_failed", error=str(e))

    classification = EventClassification(
        event_type=state.event.get("type", "unknown"),
        task_type=task_type,
        priority=priority,
        confidence=confidence,
        reasoning=reasoning,
    )

    step = SupervisorStep(
        step_number=1,
        action="classify_event",
        input_summary=f"Classifying event: {state.event.get('type', 'unknown')}",
        output_summary=f"→ {task_type.value} (priority={priority}, confidence={confidence:.0%})",
        duration_ms=_elapsed_ms(start),
        tool_used="rules + llm",
    )

    return {
        "session_start": start,
        "classification": classification,
        "reasoning_chain": [step],
        "current_step": "classify_event",
    }


async def dispatch_to_agent(state: SupervisorState) -> dict[str, Any]:
    """Dispatch the classified task to the appropriate specialist agent."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    if not state.classification:
        return {"error": "No classification available", "current_step": "failed"}

    task_type = state.classification.task_type

    logger.info(
        "supervisor_dispatching",
        session_id=state.session_id,
        task_type=task_type.value,
    )

    task = await toolkit.dispatch_task(
        task_type=task_type,
        input_data=state.event,
    )

    step = SupervisorStep(
        step_number=len(state.reasoning_chain) + 1,
        action="dispatch_to_agent",
        input_summary=f"Dispatching to {task.agent_name} agent",
        output_summary=f"Task {task.task_id}: {task.status.value} ({task.duration_ms}ms)",
        duration_ms=_elapsed_ms(start),
        tool_used=f"{task.agent_name}_runner",
    )

    return {
        "active_task": task,
        "delegated_tasks": [*state.delegated_tasks, task],
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "dispatch_to_agent",
    }


async def evaluate_result(state: SupervisorState) -> dict[str, Any]:
    """Evaluate the completed task result and decide on chaining and escalation."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    if not state.active_task:
        return {"current_step": "failed", "error": "No active task to evaluate"}

    task = state.active_task

    logger.info(
        "supervisor_evaluating_result",
        session_id=state.session_id,
        task_id=task.task_id,
        status=task.status.value,
    )

    # Rule-based chain evaluation
    chain_result = toolkit.evaluate_chain_rules(task)
    should_chain = chain_result["should_chain"]
    chain_task_type = None

    if should_chain and chain_result["chain_task_type"] != "none":
        try:
            chain_task_type = TaskType(chain_result["chain_task_type"])
        except ValueError:
            should_chain = False

    # LLM enhancement for chain decision
    if task.status == TaskStatus.COMPLETED and task.result:
        context_lines = [
            "## Completed Task",
            f"Type: {task.task_type.value}",
            f"Agent: {task.agent_name}",
            f"Status: {task.status.value}",
            f"Duration: {task.duration_ms}ms",
            "",
            "## Result Summary",
        ]
        for key, value in (task.result or {}).items():
            context_lines.append(f"- {key}: {value}")
        context_lines.extend(
            [
                "",
                (
                    f"Rule-based chain suggestion: "
                    f"{chain_result['chain_task_type']} "
                    f"({chain_result['reasoning']})"
                ),
            ]
        )

        try:
            assessment = cast(
                ChainDecisionResult,
                await llm_structured(
                    system_prompt=SYSTEM_CHAIN_DECISION,
                    user_prompt="\n".join(context_lines),
                    schema=ChainDecisionResult,
                ),
            )
            should_chain = assessment.should_chain
            if should_chain and assessment.chain_task_type != "none":
                try:
                    chain_task_type = TaskType(assessment.chain_task_type)
                except ValueError:
                    should_chain = False
        except Exception as e:
            logger.error("llm_chain_decision_failed", error=str(e))

    # Rule-based escalation evaluation
    classification_dict = state.classification.model_dump() if state.classification else None
    esc_result = toolkit.evaluate_escalation_rules(task, classification_dict)
    needs_escalation = esc_result["needs_escalation"]

    output_parts = [f"Task {task.status.value}"]
    if should_chain:
        output_parts.append(f"chain→{chain_task_type.value if chain_task_type else 'none'}")
    if needs_escalation:
        output_parts.append(f"escalate via {esc_result['channel']}")

    step = SupervisorStep(
        step_number=len(state.reasoning_chain) + 1,
        action="evaluate_result",
        input_summary=f"Evaluating {task.agent_name} task result",
        output_summary=". ".join(output_parts),
        duration_ms=_elapsed_ms(start),
        tool_used="rules + llm",
    )

    return {
        "should_chain": should_chain,
        "chain_task_type": chain_task_type,
        "needs_escalation": needs_escalation,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "evaluate_result",
    }


async def chain_followup(state: SupervisorState) -> dict[str, Any]:
    """Chain a follow-up task to another specialist agent."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    if not state.chain_task_type or not state.active_task:
        return {"current_step": "chain_followup"}

    logger.info(
        "supervisor_chaining",
        session_id=state.session_id,
        from_task=state.active_task.task_id,
        chain_type=state.chain_task_type.value,
    )

    # Build input data for chained task
    chain_input = {
        "source_task_id": state.active_task.task_id,
        "source_task_type": state.active_task.task_type.value,
        "source_result": state.active_task.result,
        **state.event,
    }

    chained_task = await toolkit.dispatch_task(
        task_type=state.chain_task_type,
        input_data=chain_input,
    )

    workflow = ChainedWorkflow(
        source_task_id=state.active_task.task_id,
        source_task_type=state.active_task.task_type,
        chained_task_id=chained_task.task_id,
        chained_task_type=state.chain_task_type,
        trigger_reason=f"Chained from {state.active_task.agent_name} → {chained_task.agent_name}",
    )

    step = SupervisorStep(
        step_number=len(state.reasoning_chain) + 1,
        action="chain_followup",
        input_summary=f"Chaining {state.chain_task_type.value} from {state.active_task.agent_name}",
        output_summary=f"Chained task {chained_task.task_id}: {chained_task.status.value}",
        duration_ms=_elapsed_ms(start),
        tool_used=f"{chained_task.agent_name}_runner",
    )

    return {
        "delegated_tasks": [*state.delegated_tasks, chained_task],
        "chained_workflows": [*state.chained_workflows, workflow],
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "chain_followup",
    }


async def escalate(state: SupervisorState) -> dict[str, Any]:
    """Escalate the situation to a human operator."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "supervisor_escalating",
        session_id=state.session_id,
    )

    # Determine escalation details
    task = state.active_task
    classification = state.classification

    reason = "Agent requires human review"
    channel = "slack"

    if task and task.status == TaskStatus.FAILED:
        reason = f"Agent {task.agent_name} failed: {task.error}"
        channel = (
            "pagerduty" if (classification and classification.priority == "critical") else "slack"
        )
    elif classification and classification.confidence < 0.5:
        reason = (
            f"Low confidence ({classification.confidence:.0%}) "
            f"classification for {classification.event_type}"
        )

    message = (
        f"ShieldOps Escalation: {reason}\n"
        f"Session: {state.session_id}\n"
        f"Event: {state.event.get('type', 'unknown')}\n"
    )

    await toolkit.send_escalation(
        channel=channel,
        message=message,
        urgency="immediate" if channel == "pagerduty" else "soon",
    )

    escalation = EscalationRecord(
        escalation_id=f"esc-{uuid4().hex[:8]}",
        reason=reason,
        task_id=task.task_id if task else None,
        task_type=task.task_type if task else None,
        channel=channel,
        notified_at=datetime.now(UTC),
    )

    step = SupervisorStep(
        step_number=len(state.reasoning_chain) + 1,
        action="escalate",
        input_summary=f"Escalating via {channel}",
        output_summary=f"Escalation {escalation.escalation_id}: {reason[:100]}",
        duration_ms=_elapsed_ms(start),
        tool_used=f"{channel}_notifier",
    )

    return {
        "escalations": [*state.escalations, escalation],
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "escalate",
    }


async def finalize(state: SupervisorState) -> dict[str, Any]:
    """Finalize the supervisor session with summary."""
    start = datetime.now(UTC)

    logger.info(
        "supervisor_finalizing",
        session_id=state.session_id,
        tasks=len(state.delegated_tasks),
        chains=len(state.chained_workflows),
        escalations=len(state.escalations),
    )

    summary_parts = [
        f"Tasks: {len(state.delegated_tasks)}",
        f"Chains: {len(state.chained_workflows)}",
        f"Escalations: {len(state.escalations)}",
    ]

    step = SupervisorStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize",
        input_summary="Finalizing supervisor session",
        output_summary=". ".join(summary_parts),
        duration_ms=_elapsed_ms(start),
        tool_used="supervisor",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
        "session_duration_ms": int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)
        if state.session_start
        else 0,
    }
