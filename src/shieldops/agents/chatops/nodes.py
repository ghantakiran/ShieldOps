"""Node implementations for the ChatOps Agent LangGraph workflow.

Each node is an async function that:
1. Processes command input or agent output
2. Uses the LLM to parse natural language or format responses
3. Updates the ChatOps state with results
4. Records its reasoning step in the audit trail
"""

from datetime import UTC, datetime
from typing import Any, cast

import structlog

from shieldops.agents.chatops.models import (
    ChatOpsApprovalStatus,
    ChatOpsExecutionStatus,
    ChatOpsState,
    CommandIntent,
    ParsedCommand,
    PolicyResult,
    ReasoningStep,
)
from shieldops.agents.chatops.prompts import (
    SYSTEM_COMMAND_PARSE,
    SYSTEM_CONTEXT_ENRICH,
    SYSTEM_RESPONSE_FORMAT,
    CommandParseResult,
    ResponseFormatResult,
)
from shieldops.agents.chatops.tools import ChatOpsToolkit
from shieldops.utils.llm import llm_structured

logger = structlog.get_logger()

# Module-level toolkit reference, set by the runner at graph construction time.
_toolkit: ChatOpsToolkit | None = None


def set_toolkit(toolkit: ChatOpsToolkit) -> None:
    """Configure the toolkit used by all nodes. Called once at startup."""
    global _toolkit
    _toolkit = toolkit


def get_toolkit() -> ChatOpsToolkit:
    """Get the configured toolkit, falling back to an empty one for tests."""
    if _toolkit is None:
        return ChatOpsToolkit()
    return _toolkit


async def parse_command(state: ChatOpsState) -> dict[str, Any]:
    """Parse the incoming command into a structured format.

    Handles both /slash commands (parsed deterministically) and
    natural language commands (parsed via LLM).
    """
    start = datetime.now(UTC)
    toolkit = get_toolkit()
    command_text = state.command_text.strip()

    logger.info(
        "chatops_parsing_command",
        command_id=state.command_id,
        channel=state.channel,
        user_id=state.user_id,
        command_preview=command_text[:80],
    )

    # Try deterministic slash command parsing first
    slash_result = toolkit.parse_slash_command(command_text)
    if slash_result is not None and slash_result.intent != CommandIntent.UNKNOWN:
        parsed = slash_result
        output_summary = (
            f"Slash command parsed: intent={parsed.intent}, "
            f"entity={parsed.entity}, confidence={parsed.confidence:.2f}"
        )
    else:
        # Enrich with thread context if available
        enriched_command = command_text
        if state.thread_id:
            thread_ctx = await toolkit.get_thread_context(state.channel_id, state.thread_id)
            if thread_ctx:
                context_text = "\n".join(
                    f"[{m.get('user', '?')}]: {m.get('text', '')}" for m in thread_ctx[-5:]
                )
                try:
                    enriched = await llm_structured(
                        system_prompt=SYSTEM_CONTEXT_ENRICH,
                        user_prompt=(
                            f"## Thread History\n{context_text}\n\n"
                            f"## Current Command\n{command_text}"
                        ),
                        schema=CommandParseResult,
                    )
                    if hasattr(enriched, "entity") and enriched.entity:
                        enriched_command = command_text  # keep original but use enriched parse
                except Exception as e:
                    logger.warning("chatops_context_enrichment_failed", error=str(e))

        # LLM-based natural language parsing
        try:
            user_prompt = (
                f"## Command\n{enriched_command}\n\n"
                f"## Context\n"
                f"User: {state.user_name} ({state.user_id})\n"
                f"Channel: {state.channel_name} ({state.channel})\n"
            )

            result = cast(
                CommandParseResult,
                await llm_structured(
                    system_prompt=SYSTEM_COMMAND_PARSE,
                    user_prompt=user_prompt,
                    schema=CommandParseResult,
                ),
            )

            try:
                intent = CommandIntent(result.intent)
            except ValueError:
                intent = CommandIntent.UNKNOWN

            parsed = ParsedCommand(
                intent=intent,
                entity=result.entity,
                parameters=result.parameters,
                confidence=result.confidence,
                raw_command=command_text,
            )

            output_summary = (
                f"NLP parsed: intent={parsed.intent}, entity={parsed.entity}, "
                f"confidence={parsed.confidence:.2f}"
            )
            if result.disambiguation:
                output_summary += f" (disambiguation: {result.disambiguation})"

        except Exception as e:
            logger.error("chatops_llm_parse_failed", error=str(e))
            parsed = ParsedCommand(
                intent=CommandIntent.UNKNOWN,
                entity="",
                parameters={},
                confidence=0.0,
                raw_command=command_text,
            )
            output_summary = f"Parse failed: {e}"

    # Resolve the matched agent
    matched_agent = toolkit.resolve_agent(parsed.intent) or ""

    step = ReasoningStep(
        step_number=1,
        action="parse_command",
        input_summary=f"Command: {command_text[:100]}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="slash_parser" if slash_result else "llm",
    )

    return {
        "parsed_command": parsed,
        "matched_agent": matched_agent,
        "reasoning_chain": [step],
        "current_step": "parse_command",
        "command_received_at": start,
    }


async def validate_permissions(state: ChatOpsState) -> dict[str, Any]:
    """Check user permissions and OPA policy for the requested action."""
    start = datetime.now(UTC)
    toolkit = get_toolkit()
    parsed = state.parsed_command

    logger.info(
        "chatops_validating_permissions",
        command_id=state.command_id,
        user_id=state.user_id,
        intent=parsed.intent,
        entity=parsed.entity,
    )

    # Help and status commands are always allowed
    if parsed.intent in (CommandIntent.HELP, CommandIntent.STATUS):
        policy_result = PolicyResult(allowed=True, reason="informational command")
        approval_status = ChatOpsApprovalStatus.NOT_REQUIRED
        output_summary = "Informational command — no policy check required"
    else:
        policy_result = await toolkit.check_policy(
            action=f"{parsed.intent}:{parsed.entity}",
            user_id=state.user_id,
            channel=state.channel_id,
        )

        if not policy_result.allowed:
            approval_status = ChatOpsApprovalStatus.DENIED
            output_summary = f"Denied: {policy_result.reason}"
        elif policy_result.required_approval:
            approval_status = ChatOpsApprovalStatus.PENDING
            output_summary = (
                f"Approval required: {policy_result.reason}. Queuing for approval workflow."
            )
        else:
            approval_status = ChatOpsApprovalStatus.NOT_REQUIRED
            output_summary = "Allowed by policy"

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="validate_permissions",
        input_summary=(
            f"Checking policy for {parsed.intent}:{parsed.entity} by user {state.user_id}"
        ),
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="opa_policy_engine",
    )

    return {
        "policy_evaluation": policy_result,
        "approval_status": approval_status,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "validate_permissions",
    }


async def route_to_agent(state: ChatOpsState) -> dict[str, Any]:
    """Route the command to the appropriate specialist agent."""
    start = datetime.now(UTC)
    parsed = state.parsed_command

    logger.info(
        "chatops_routing_to_agent",
        command_id=state.command_id,
        intent=parsed.intent,
        matched_agent=state.matched_agent,
    )

    output_summary = f"Routing to agent: {state.matched_agent}"
    if not state.matched_agent:
        output_summary = f"No agent found for intent: {parsed.intent}"

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="route_to_agent",
        input_summary=f"Intent: {parsed.intent}, entity: {parsed.entity}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used=None,
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "route_to_agent",
        "execution_status": ChatOpsExecutionStatus.RUNNING,
    }


async def execute_action(state: ChatOpsState) -> dict[str, Any]:
    """Execute the agent action or handle non-agent intents."""
    start = datetime.now(UTC)
    toolkit = get_toolkit()
    parsed = state.parsed_command

    logger.info(
        "chatops_executing_action",
        command_id=state.command_id,
        matched_agent=state.matched_agent,
        intent=parsed.intent,
    )

    agent_result: dict[str, Any] = {}
    execution_status = ChatOpsExecutionStatus.COMPLETED
    output_summary: str

    # Handle help intent directly
    if parsed.intent == CommandIntent.HELP:
        agent_result = {
            "status": "completed",
            "summary": "Available ShieldOps ChatOps Commands",
            "details": [
                "/investigate <service> — investigate an incident or alert",
                "/remediate <service> — execute remediation actions",
                "/restart <service> — restart service pods",
                "/scale <service> <count> — scale service replicas",
                "/rollback <service> — rollback a deployment",
                "/scan <target> — run security scan",
                "/cost <query> — cost and billing reports",
                "/escalate [team] — escalate to on-call",
                "/status <id> — check command or incident status",
                "/help — show this help message",
            ],
        }
        output_summary = "Help text generated"
    elif not state.matched_agent:
        agent_result = {
            "status": "error",
            "message": (
                f"I couldn't understand the command: '{parsed.raw_command}'. "
                "Type /help to see available commands."
            ),
        }
        execution_status = ChatOpsExecutionStatus.FAILED
        output_summary = f"No agent for intent: {parsed.intent}"
    else:
        # Execute via agent registry
        parameters = {
            "entity": parsed.entity,
            "intent": parsed.intent,
            "user_id": state.user_id,
            "channel": state.channel,
            "channel_id": state.channel_id,
            **parsed.parameters,
        }
        agent_result = await toolkit.execute_agent(state.matched_agent, parameters)
        exec_status = agent_result.get("status", "completed")
        if exec_status in ("error", "failed"):
            execution_status = ChatOpsExecutionStatus.FAILED
        output_summary = (
            f"Agent {state.matched_agent} returned: "
            f"{agent_result.get('summary', agent_result.get('message', 'done'))[:100]}"
        )

    # Record command in user history
    toolkit.record_command(
        user_id=state.user_id,
        command={
            "command_id": state.command_id,
            "command_text": state.command_text,
            "intent": parsed.intent,
            "entity": parsed.entity,
            "status": execution_status,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="execute_action",
        input_summary=f"Executing {state.matched_agent or 'builtin'} for {parsed.intent}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used=state.matched_agent or "builtin",
    )

    return {
        "agent_result": agent_result,
        "execution_status": execution_status,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "execute_action",
    }


async def format_response(state: ChatOpsState) -> dict[str, Any]:
    """Format the agent result into channel-appropriate response blocks."""
    start = datetime.now(UTC)
    toolkit = get_toolkit()
    result = state.agent_result

    logger.info(
        "chatops_formatting_response",
        command_id=state.command_id,
        execution_status=state.execution_status,
    )

    # Try LLM-based formatting for richer responses
    response_text = result.get("summary", result.get("message", "Command processed."))
    response_blocks = toolkit.format_response(result, state.channel)

    if state.execution_status == ChatOpsExecutionStatus.COMPLETED and result.get("details"):
        try:
            format_input = (
                f"## Agent Result\n"
                f"Status: {result.get('status', 'unknown')}\n"
                f"Summary: {result.get('summary', 'N/A')}\n"
                f"Details: {result.get('details', [])}\n\n"
                f"## Context\n"
                f"Command: {state.command_text}\n"
                f"Channel: {state.channel}\n"
                f"User: {state.user_name}"
            )
            formatted = cast(
                ResponseFormatResult,
                await llm_structured(
                    system_prompt=SYSTEM_RESPONSE_FORMAT,
                    user_prompt=format_input,
                    schema=ResponseFormatResult,
                ),
            )
            response_text = formatted.summary
        except Exception as e:
            logger.warning("chatops_llm_format_failed", error=str(e))

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="format_response",
        input_summary=f"Formatting result for {state.channel}",
        output_summary=f"Response: {response_text[:100]}",
        duration_ms=_elapsed_ms(start),
        tool_used="formatter",
    )

    return {
        "response_text": response_text,
        "response_blocks": response_blocks,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "format_response",
    }


async def format_denial_response(state: ChatOpsState) -> dict[str, Any]:
    """Format a permission denial response."""
    start = datetime.now(UTC)
    toolkit = get_toolkit()

    reason = state.policy_evaluation.reason or "Insufficient permissions"
    response_text = f"[ACCESS DENIED] {reason}"
    response_blocks = toolkit.format_response(
        {
            "status": "error",
            "summary": "Permission Denied",
            "details": [
                f"Action: {state.parsed_command.intent} {state.parsed_command.entity}",
                f"Reason: {reason}",
                f"User: {state.user_name} ({state.user_id})",
                "Contact your administrator for access.",
            ],
        },
        state.channel,
    )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="format_denial_response",
        input_summary=f"Denied: {reason}",
        output_summary=f"Denial response formatted for {state.channel}",
        duration_ms=_elapsed_ms(start),
        tool_used="formatter",
    )

    return {
        "response_text": response_text,
        "response_blocks": response_blocks,
        "execution_status": ChatOpsExecutionStatus.FAILED,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "format_denial_response",
    }


async def queue_for_approval(state: ChatOpsState) -> dict[str, Any]:
    """Queue the command for approval and notify the user."""
    start = datetime.now(UTC)
    toolkit = get_toolkit()

    response_text = (
        f"[APPROVAL REQUIRED] Your command requires approval: "
        f"{state.parsed_command.intent} {state.parsed_command.entity}"
    )
    response_blocks = toolkit.format_response(
        {
            "status": "warning",
            "summary": "Approval Required",
            "details": [
                f"Command: {state.command_text}",
                f"Reason: {state.policy_evaluation.reason}",
                "An approver has been notified. You will receive a "
                "notification when the command is approved or denied.",
            ],
        },
        state.channel,
    )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="queue_for_approval",
        input_summary=f"Queuing {state.parsed_command.intent}:{state.parsed_command.entity}",
        output_summary="Command queued for approval",
        duration_ms=_elapsed_ms(start),
        tool_used="approval_workflow",
    )

    return {
        "response_text": response_text,
        "response_blocks": response_blocks,
        "execution_status": ChatOpsExecutionStatus.AWAITING_APPROVAL,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "queue_for_approval",
    }


async def format_error_response(state: ChatOpsState) -> dict[str, Any]:
    """Format an error response when agent execution fails."""
    start = datetime.now(UTC)
    toolkit = get_toolkit()

    error_msg = state.agent_result.get("message", state.error or "An unexpected error occurred")
    response_text = f"[ERROR] {error_msg}"
    response_blocks = toolkit.format_response(
        {
            "status": "error",
            "summary": "Command Failed",
            "details": [
                f"Command: {state.command_text}",
                f"Error: {error_msg}",
                "Try again or contact support if the issue persists.",
            ],
        },
        state.channel,
    )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="format_error_response",
        input_summary=f"Error: {error_msg[:80]}",
        output_summary="Error response formatted",
        duration_ms=_elapsed_ms(start),
        tool_used="formatter",
    )

    return {
        "response_text": response_text,
        "response_blocks": response_blocks,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "format_error_response",
    }


async def deliver_response(state: ChatOpsState) -> dict[str, Any]:
    """Send the formatted response back to the originating channel."""
    start = datetime.now(UTC)
    toolkit = get_toolkit()

    logger.info(
        "chatops_delivering_response",
        command_id=state.command_id,
        channel=state.channel,
        channel_id=state.channel_id,
        execution_status=state.execution_status,
    )

    payload = {
        "text": state.response_text,
        "blocks": [b.model_dump() for b in state.response_blocks],
        "command_id": state.command_id,
    }

    sent = await toolkit.send_response(
        channel_type=state.channel,
        channel_id=state.channel_id,
        thread_id=state.thread_id,
        response=payload,
    )

    # Record in thread context for follow-up resolution
    if state.thread_id:
        toolkit.record_thread_message(
            channel_id=state.channel_id,
            thread_id=state.thread_id,
            message={
                "user": "shieldops-bot",
                "text": state.response_text,
                "command_id": state.command_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    output_summary = f"Response {'sent' if sent else 'failed to send'} to {state.channel}"

    # Calculate total processing duration
    processing_duration_ms = 0
    if state.command_received_at:
        processing_duration_ms = _elapsed_ms(state.command_received_at)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="deliver_response",
        input_summary=f"Sending to {state.channel}:{state.channel_id}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="notification_dispatcher",
    )

    return {
        "processing_duration_ms": processing_duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }


# --- Private helpers ---


def _elapsed_ms(start: datetime) -> int:
    """Calculate elapsed milliseconds since start."""
    return int((datetime.now(UTC) - start).total_seconds() * 1000)
