"""ChatOps Agent runner — entry point for processing chat commands.

Takes a command from Slack/Teams/PagerDuty, constructs the LangGraph,
runs it end-to-end, and returns the completed ChatOps state.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.chatops.graph import create_chatops_graph
from shieldops.agents.chatops.models import (
    ChannelType,
    ChatOpsApprovalStatus,
    ChatOpsExecutionStatus,
    ChatOpsState,
)
from shieldops.agents.chatops.nodes import set_toolkit
from shieldops.agents.chatops.tools import ChatOpsToolkit
from shieldops.connectors.base import ConnectorRouter
from shieldops.observability.tracing import get_tracer

if __import__("typing").TYPE_CHECKING:
    from shieldops.db.repository import Repository

logger = structlog.get_logger()


class ChatOpsRunner:
    """Runs ChatOps agent workflows.

    Usage:
        runner = ChatOpsRunner(
            connector_router=router,
            notification_dispatcher=dispatcher,
            policy_engine=opa_client,
            agent_runners={"investigation": inv_runner, ...},
        )
        result = await runner.process_command(
            command="/investigate api-gateway",
            channel="slack",
            user_id="U12345",
            ...
        )
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        notification_dispatcher: Any = None,
        policy_engine: Any = None,
        agent_runners: dict[str, Any] | None = None,
        repository: "Repository | None" = None,
        ws_manager: "object | None" = None,
    ) -> None:
        self._toolkit = ChatOpsToolkit(
            connector_router=connector_router,
            notification_dispatcher=notification_dispatcher,
            policy_engine=policy_engine,
            agent_registry=agent_runners or {},
        )
        # Configure the module-level toolkit for nodes
        set_toolkit(self._toolkit)

        # Build the compiled graph
        graph = create_chatops_graph()
        self._app = graph.compile()

        # In-memory store of processed commands (fallback when no DB)
        self._commands: dict[str, ChatOpsState] = {}
        self._pending_approvals: dict[str, ChatOpsState] = {}
        self._repository = repository
        self._ws_manager = ws_manager

    async def process_command(
        self,
        command: str,
        channel: str,
        user_id: str,
        user_name: str,
        channel_id: str,
        channel_name: str,
        thread_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatOpsState:
        """Process a command from a chat platform.

        Args:
            command: The raw command text.
            channel: Channel type (slack, teams, pagerduty, webhook).
            user_id: ID of the user who sent the command.
            user_name: Display name of the user.
            channel_id: ID of the channel where the command was sent.
            channel_name: Name of the channel.
            thread_id: Optional thread ID for threaded conversations.
            metadata: Additional metadata from the platform.

        Returns:
            The completed ChatOpsState with response and reasoning chain.
        """
        command_id = f"cmd-{uuid4().hex[:12]}"

        try:
            channel_type = ChannelType(channel)
        except ValueError:
            channel_type = ChannelType.WEBHOOK

        logger.info(
            "chatops_command_received",
            command_id=command_id,
            channel=channel_type,
            user_id=user_id,
            user_name=user_name,
            command_preview=command[:80],
        )

        initial_state = ChatOpsState(
            command_id=command_id,
            command_text=command,
            channel=channel_type,
            user_id=user_id,
            user_name=user_name,
            channel_id=channel_id,
            channel_name=channel_name,
            thread_id=thread_id,
            metadata=metadata or {},
        )

        # Record incoming message in thread context
        if thread_id:
            self._toolkit.record_thread_message(
                channel_id=channel_id,
                thread_id=thread_id,
                message={
                    "user": user_name,
                    "text": command,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        try:
            tracer = get_tracer("shieldops.agents")
            with tracer.start_as_current_span("chatops.run") as span:
                span.set_attribute("chatops.command_id", command_id)
                span.set_attribute("chatops.channel", channel_type.value)
                span.set_attribute("chatops.user_id", user_id)

                # Run the LangGraph workflow
                final_state_dict = await self._app.ainvoke(
                    initial_state.model_dump(),  # type: ignore[arg-type]
                    config={
                        "metadata": {
                            "command_id": command_id,
                            "user_id": user_id,
                            "channel": channel_type.value,
                        },
                    },
                )

                final_state = ChatOpsState.model_validate(final_state_dict)

                span.set_attribute("chatops.duration_ms", final_state.processing_duration_ms)
                span.set_attribute("chatops.execution_status", final_state.execution_status.value)
                span.set_attribute("chatops.intent", final_state.parsed_command.intent.value)

            logger.info(
                "chatops_command_completed",
                command_id=command_id,
                intent=final_state.parsed_command.intent,
                execution_status=final_state.execution_status,
                duration_ms=final_state.processing_duration_ms,
                steps=len(final_state.reasoning_chain),
            )

            # Store result
            self._commands[command_id] = final_state
            if final_state.execution_status == ChatOpsExecutionStatus.AWAITING_APPROVAL:
                self._pending_approvals[command_id] = final_state
            await self._persist(command_id, final_state)
            await self._broadcast(command_id, final_state)
            return final_state

        except Exception as e:
            logger.error(
                "chatops_command_failed",
                command_id=command_id,
                user_id=user_id,
                error=str(e),
            )
            error_state = ChatOpsState(
                command_id=command_id,
                command_text=command,
                channel=channel_type,
                user_id=user_id,
                user_name=user_name,
                channel_id=channel_id,
                channel_name=channel_name,
                error=str(e),
                current_step="failed",
                execution_status=ChatOpsExecutionStatus.FAILED,
                response_text=f"[ERROR] Command processing failed: {e}",
            )
            self._commands[command_id] = error_state
            await self._persist(command_id, error_state)
            return error_state

    async def handle_slash_command(
        self,
        command_text: str,
        context: dict[str, Any],
    ) -> ChatOpsState:
        """Shortcut for processing /command syntax.

        Args:
            command_text: The full slash command text (e.g., "/investigate api-gw").
            context: Dict with user_id, user_name, channel_id, channel_name,
                     channel (type), thread_id (optional).

        Returns:
            The completed ChatOpsState.
        """
        return await self.process_command(
            command=command_text,
            channel=context.get("channel", "slack"),
            user_id=context.get("user_id", ""),
            user_name=context.get("user_name", ""),
            channel_id=context.get("channel_id", ""),
            channel_name=context.get("channel_name", ""),
            thread_id=context.get("thread_id"),
            metadata=context.get("metadata", {}),
        )

    async def handle_approval(
        self,
        command_id: str,
        approved_by: str,
        approved: bool,
    ) -> ChatOpsState | None:
        """Handle an approval callback for a pending command.

        Args:
            command_id: The command awaiting approval.
            approved_by: User ID of the approver.
            approved: Whether the command was approved.

        Returns:
            The updated ChatOpsState, or None if command not found.
        """
        pending = self._pending_approvals.pop(command_id, None)
        if pending is None:
            logger.warning("chatops_approval_not_found", command_id=command_id)
            return None

        logger.info(
            "chatops_approval_received",
            command_id=command_id,
            approved_by=approved_by,
            approved=approved,
        )

        if approved:
            # Re-run the command with approval granted
            pending.approval_status = ChatOpsApprovalStatus.APPROVED
            pending.policy_evaluation.allowed = True
            pending.policy_evaluation.required_approval = False

            # Re-process through the graph from route_to_agent onwards
            return await self.process_command(
                command=pending.command_text,
                channel=pending.channel.value,
                user_id=pending.user_id,
                user_name=pending.user_name,
                channel_id=pending.channel_id,
                channel_name=pending.channel_name,
                thread_id=pending.thread_id,
                metadata={
                    **pending.metadata,
                    "approved_by": approved_by,
                    "original_command_id": command_id,
                },
            )
        else:
            pending.approval_status = ChatOpsApprovalStatus.DENIED
            pending.execution_status = ChatOpsExecutionStatus.FAILED
            pending.response_text = f"[DENIED] Command denied by {approved_by}."
            self._commands[command_id] = pending
            await self._persist(command_id, pending)
            return pending

    def get_command(self, command_id: str) -> ChatOpsState | None:
        """Retrieve a processed command by ID."""
        return self._commands.get(command_id)

    def list_commands(
        self,
        user_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List recent commands with summary info.

        Args:
            user_id: Optional filter by user ID.
            limit: Maximum number of commands to return.

        Returns:
            List of command summary dicts.
        """
        commands = list(self._commands.items())
        if user_id:
            commands = [(cid, s) for cid, s in commands if s.user_id == user_id]

        return [
            {
                "command_id": cmd_id,
                "command_text": state.command_text[:80],
                "intent": state.parsed_command.intent,
                "entity": state.parsed_command.entity,
                "user_id": state.user_id,
                "user_name": state.user_name,
                "channel": state.channel,
                "execution_status": state.execution_status,
                "duration_ms": state.processing_duration_ms,
                "error": state.error,
            }
            for cmd_id, state in commands[-limit:]
        ]

    async def _broadcast(self, command_id: str, state: ChatOpsState) -> None:
        """Broadcast progress via WebSocket if manager is available."""
        if self._ws_manager is None:
            return
        try:
            event = {
                "type": "chatops_update",
                "command_id": command_id,
                "status": state.execution_status,
                "intent": state.parsed_command.intent,
                "user_id": state.user_id,
            }
            await self._ws_manager.broadcast("global", event)  # type: ignore[attr-defined]
            await self._ws_manager.broadcast(  # type: ignore[attr-defined]
                f"chatops:{command_id}", event
            )
        except Exception as e:
            logger.warning("ws_broadcast_failed", id=command_id, error=str(e))

    async def _persist(self, command_id: str, state: ChatOpsState) -> None:
        """Persist to DB if repository is available."""
        if self._repository is None:
            return
        if not hasattr(self._repository, "save_chatops_command"):
            logger.debug("repository_missing_save_chatops_command")
            return
        try:
            await self._repository.save_chatops_command(command_id, state)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("chatops_persist_failed", id=command_id, error=str(e))
