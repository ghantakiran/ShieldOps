"""Tool functions for the ChatOps Agent.

These bridge communication platforms, policy engines, and specialist agents
to the agent's LangGraph nodes. Each tool is a self-contained async function
that processes commands and routes to appropriate agents.
"""

import re
from typing import Any

import structlog

from shieldops.agents.chatops.models import (
    ChannelType,
    CommandIntent,
    ParsedCommand,
    PolicyResult,
    ResponseBlock,
)
from shieldops.connectors.base import ConnectorRouter

logger = structlog.get_logger()

# Slash command pattern: /command [args...]
_SLASH_PATTERN = re.compile(r"^/(\w+)\s*(.*)?$", re.DOTALL)

# Intent mapping from slash commands to CommandIntent
_SLASH_INTENT_MAP: dict[str, CommandIntent] = {
    "investigate": CommandIntent.INVESTIGATE,
    "inv": CommandIntent.INVESTIGATE,
    "remediate": CommandIntent.REMEDIATE,
    "fix": CommandIntent.REMEDIATE,
    "restart": CommandIntent.REMEDIATE,
    "scale": CommandIntent.REMEDIATE,
    "rollback": CommandIntent.REMEDIATE,
    "scan": CommandIntent.SCAN,
    "security": CommandIntent.SCAN,
    "cost": CommandIntent.COST_REPORT,
    "costs": CommandIntent.COST_REPORT,
    "billing": CommandIntent.COST_REPORT,
    "escalate": CommandIntent.ESCALATE,
    "page": CommandIntent.ESCALATE,
    "status": CommandIntent.STATUS,
    "help": CommandIntent.HELP,
}

# Agent type mapping from intent to agent runner key
_INTENT_AGENT_MAP: dict[CommandIntent, str] = {
    CommandIntent.INVESTIGATE: "investigation",
    CommandIntent.REMEDIATE: "remediation",
    CommandIntent.SCAN: "security",
    CommandIntent.COST_REPORT: "cost",
    CommandIntent.ESCALATE: "escalation",
    CommandIntent.STATUS: "status",
}


class ChatOpsToolkit:
    """Collection of tools available to the ChatOps agent.

    Injected into nodes at graph construction time to decouple agent logic
    from specific connector and agent implementations.
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        notification_dispatcher: Any = None,
        policy_engine: Any = None,
        agent_registry: dict[str, Any] | None = None,
    ) -> None:
        self._router = connector_router
        self._notification_dispatcher = notification_dispatcher
        self._policy_engine = policy_engine
        self._agent_registry = agent_registry or {}
        self._command_history: dict[str, list[dict[str, Any]]] = {}
        self._thread_context: dict[str, list[dict[str, Any]]] = {}

    def parse_slash_command(self, text: str) -> ParsedCommand | None:
        """Parse /command syntax into intent + args.

        Returns None if the text is not a slash command.
        """
        match = _SLASH_PATTERN.match(text.strip())
        if not match:
            return None

        command_name = match.group(1).lower()
        args_text = (match.group(2) or "").strip()

        intent = _SLASH_INTENT_MAP.get(command_name, CommandIntent.UNKNOWN)

        # Extract entity from the first argument token
        args_parts = args_text.split() if args_text else []
        entity = args_parts[0] if args_parts else ""

        # Remaining tokens become raw parameters
        parameters: dict[str, Any] = {}
        if len(args_parts) > 1:
            parameters["args"] = args_parts[1:]
            parameters["raw_args"] = " ".join(args_parts[1:])

        # Handle specific slash commands with implicit parameters
        if command_name in ("restart", "scale", "rollback"):
            parameters["action_type"] = command_name
        if command_name == "scale" and len(args_parts) >= 2:
            # "/scale frontend 5" → entity=frontend, replicas=5
            try:
                parameters["replicas"] = int(args_parts[-1])
                if entity == args_parts[-1]:
                    entity = args_parts[0] if len(args_parts) > 1 else ""
            except ValueError:
                pass

        return ParsedCommand(
            intent=intent,
            entity=entity,
            parameters=parameters,
            confidence=0.95 if intent != CommandIntent.UNKNOWN else 0.3,
            raw_command=text,
        )

    def resolve_agent(self, intent: CommandIntent) -> str | None:
        """Map a command intent to the corresponding agent type.

        Returns the agent registry key or None if no agent handles this intent.
        """
        return _INTENT_AGENT_MAP.get(intent)

    async def check_policy(
        self,
        action: str,
        user_id: str,
        channel: str,
    ) -> PolicyResult:
        """Evaluate OPA policy for the requested action.

        Returns a PolicyResult indicating whether the action is allowed.
        """
        if self._policy_engine is None:
            # No policy engine configured — allow by default in dev
            logger.warning(
                "chatops_no_policy_engine",
                action=action,
                user_id=user_id,
            )
            return PolicyResult(allowed=True, reason="no policy engine configured")

        try:
            result = await self._policy_engine.evaluate(
                policy="chatops/command_auth",
                input_data={
                    "action": action,
                    "user_id": user_id,
                    "channel": channel,
                },
            )
            return PolicyResult(
                allowed=result.get("allowed", False),
                reason=result.get("reason", ""),
                required_approval=result.get("required_approval", False),
            )
        except Exception as e:
            logger.error(
                "chatops_policy_evaluation_failed",
                action=action,
                user_id=user_id,
                error=str(e),
            )
            return PolicyResult(
                allowed=False,
                reason=f"Policy evaluation failed: {e}",
            )

    async def execute_agent(
        self,
        agent_type: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the matched agent and return results.

        Args:
            agent_type: Key in the agent registry (e.g., 'investigation').
            parameters: Parameters to pass to the agent runner.

        Returns:
            Dict with execution results or error information.
        """
        runner = self._agent_registry.get(agent_type)
        if runner is None:
            return {
                "status": "error",
                "message": f"No agent registered for type: {agent_type}",
            }

        try:
            result = await runner.execute(parameters)
            if hasattr(result, "model_dump"):
                result_dict: dict[str, Any] = result.model_dump()
                return result_dict
            return result if isinstance(result, dict) else {"result": str(result)}
        except Exception as e:
            logger.error(
                "chatops_agent_execution_failed",
                agent_type=agent_type,
                error=str(e),
            )
            return {"status": "error", "message": str(e)}

    def format_response(
        self,
        result: dict[str, Any],
        channel_type: ChannelType,
    ) -> list[ResponseBlock]:
        """Format agent results into channel-appropriate response blocks.

        Args:
            result: Raw agent result dict.
            channel_type: Target channel type for formatting.

        Returns:
            List of ResponseBlock objects for the target channel.
        """
        blocks: list[ResponseBlock] = []

        # Header block
        status = result.get("status", "completed")
        status_emoji = {
            "completed": "[OK]",
            "error": "[ERROR]",
            "warning": "[WARN]",
            "success": "[OK]",
            "failed": "[ERROR]",
        }.get(status, "[INFO]")

        summary = result.get("summary", result.get("message", "Command processed"))
        blocks.append(
            ResponseBlock(
                block_type="header",
                text=f"{status_emoji} {summary}",
            )
        )

        # Details section
        details = result.get("details", [])
        if isinstance(details, list) and details:
            detail_text = "\n".join(f"- {d}" for d in details[:8])
            blocks.append(
                ResponseBlock(
                    block_type="section",
                    text=detail_text,
                )
            )

        # Key-value fields (for Slack fields / Teams facts)
        fields: list[dict[str, str]] = []
        for key in ("confidence", "duration_ms", "hypotheses_count", "severity"):
            if key in result:
                fields.append({"title": key.replace("_", " ").title(), "value": str(result[key])})
        if fields:
            blocks.append(
                ResponseBlock(
                    block_type="section",
                    text="",
                    fields=fields,
                )
            )

        # Divider
        blocks.append(ResponseBlock(block_type="divider"))

        # Context footer
        if channel_type == ChannelType.SLACK:
            blocks.append(
                ResponseBlock(
                    block_type="context",
                    elements=[{"type": "mrkdwn", "text": "Powered by ShieldOps ChatOps Agent"}],
                )
            )
        elif channel_type == ChannelType.TEAMS:
            blocks.append(
                ResponseBlock(
                    block_type="context",
                    elements=[{"type": "TextBlock", "text": "Powered by ShieldOps ChatOps Agent"}],
                )
            )

        return blocks

    async def send_response(
        self,
        channel_type: ChannelType,
        channel_id: str,
        thread_id: str | None,
        response: dict[str, Any],
    ) -> bool:
        """Send formatted response back to the originating channel.

        Args:
            channel_type: The channel platform (slack, teams, etc.).
            channel_id: Target channel identifier.
            thread_id: Optional thread to reply in.
            response: Response payload to send.

        Returns:
            True if the message was sent successfully.
        """
        if self._notification_dispatcher is None:
            logger.warning(
                "chatops_no_notification_dispatcher",
                channel_type=channel_type,
                channel_id=channel_id,
            )
            return False

        try:
            await self._notification_dispatcher.send(
                channel=channel_type.value,
                target=channel_id,
                thread_id=thread_id,
                payload=response,
            )
            return True
        except Exception as e:
            logger.error(
                "chatops_send_response_failed",
                channel_type=channel_type,
                channel_id=channel_id,
                error=str(e),
            )
            return False

    async def get_thread_context(
        self,
        channel_id: str,
        thread_id: str | None,
    ) -> list[dict[str, Any]]:
        """Get conversation context for follow-up commands.

        Returns recent messages in the thread for context enrichment.
        """
        if thread_id is None:
            return []

        key = f"{channel_id}:{thread_id}"
        return self._thread_context.get(key, [])

    async def get_command_history(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get recent command history for a user.

        Args:
            user_id: The user whose history to retrieve.
            limit: Maximum number of history entries.

        Returns:
            List of recent command records.
        """
        history = self._command_history.get(user_id, [])
        return history[-limit:]

    def record_command(
        self,
        user_id: str,
        command: dict[str, Any],
    ) -> None:
        """Record a command in the user's history."""
        if user_id not in self._command_history:
            self._command_history[user_id] = []
        self._command_history[user_id].append(command)
        # Cap history at 100 entries per user
        if len(self._command_history[user_id]) > 100:
            self._command_history[user_id] = self._command_history[user_id][-100:]

    def record_thread_message(
        self,
        channel_id: str,
        thread_id: str,
        message: dict[str, Any],
    ) -> None:
        """Record a message in thread context for follow-up resolution."""
        key = f"{channel_id}:{thread_id}"
        if key not in self._thread_context:
            self._thread_context[key] = []
        self._thread_context[key].append(message)
        # Cap thread context at 50 messages
        if len(self._thread_context[key]) > 50:
            self._thread_context[key] = self._thread_context[key][-50:]
