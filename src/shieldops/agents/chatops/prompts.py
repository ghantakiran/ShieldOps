"""LLM prompt templates and response schemas for the ChatOps Agent."""

from typing import Any

from pydantic import BaseModel, Field

# --- Response schemas for structured LLM output ---


class CommandParseResult(BaseModel):
    """Structured output from LLM command parsing."""

    intent: str = Field(
        description="Command intent: investigate, remediate, scan, cost_report, "
        "escalate, status, help, or unknown"
    )
    entity: str = Field(
        description="The resource, service, alert, or entity being acted on "
        "(e.g., 'api-gateway', 'payment-service', 'CVE-2024-1234', 'inv-abc123')"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted parameters (e.g., environment, namespace, severity, "
        "time_range, replica_count)",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the parse result from 0.0 to 1.0",
    )
    disambiguation: str | None = Field(
        default=None,
        description="Optional clarification question if the command is ambiguous",
    )


class ActionButton(BaseModel):
    """A button for interactive chat responses."""

    label: str = Field(description="Button display text")
    action: str = Field(description="Action identifier when button is clicked")
    style: str = Field(
        default="default",
        description="Button style: default, primary, danger",
    )


class ResponseFormatResult(BaseModel):
    """Structured output for formatting agent results into chat messages."""

    summary: str = Field(description="One-line summary of the result")
    details: list[str] = Field(
        default_factory=list,
        description="Detailed findings or action items as bullet points",
    )
    action_buttons: list[ActionButton] = Field(
        default_factory=list,
        description="Interactive buttons for follow-up actions",
    )
    severity_indicator: str = Field(
        default="info",
        description="Severity level for visual indicator: info, warning, error, critical",
    )


# --- Prompt templates ---

SYSTEM_COMMAND_PARSE = """\
You are an expert SRE assistant parsing natural language commands \
from enterprise chat platforms (Slack, Microsoft Teams, PagerDuty).

Your task is to parse the user's command into a structured format:
1. Identify the **intent** (what the user wants to do)
2. Extract the **entity** (the resource, service, alert, or item being acted on)
3. Extract **parameters** (environment, namespace, severity, counts, time ranges, etc.)
4. Assess your **confidence** in the parse

Supported intents:
- **investigate**: Root cause analysis. Examples: "/investigate api-gateway high latency", \
"why is checkout-service slow?", "look into alert ALT-12345"
- **remediate**: Execute infrastructure changes. Examples: "restart payment-service pods", \
"scale frontend to 5 replicas", "rollback deployment auth-service"
- **scan**: Security scanning. Examples: "scan CVE-2024-1234", \
"check for vulnerabilities in prod", "security audit on user-service"
- **cost_report**: Cost and billing analysis. Examples: "what's the cost trend for production?", \
"show AWS spend this month", "cost breakdown by team"
- **escalate**: Escalate to on-call or team. Examples: "escalate to oncall", \
"page the database team", "escalate incident INC-456"
- **status**: Check status of investigations, remediations, or services. Examples: \
"status of inv-abc123", "what's running?", "show active incidents"
- **help**: Show available commands. Examples: "help", "what can you do?"

If the command is ambiguous, set a lower confidence and provide a disambiguation question.

IMPORTANT:
- Extract specific resource names, CVE IDs, incident IDs, and service names as the entity.
- Parse environment (dev/staging/prod), namespace, replica counts, time ranges as parameters.
- For slash commands like "/investigate ...", the intent maps directly from the command name."""

SYSTEM_RESPONSE_FORMAT = """\
You are formatting the results of an SRE agent action into a human-readable \
chat message for enterprise communication tools.

Your task is to create a clear, concise response that:
1. Summarizes the key finding or action result in one line
2. Lists important details as bullet points (max 8 items)
3. Suggests follow-up actions as interactive buttons
4. Sets an appropriate severity indicator for visual styling

Formatting guidelines:
- Use clear, non-technical language where possible
- Bold important values like service names, metrics, and statuses
- Keep the summary under 120 characters
- Order details by importance
- Include timing information when relevant
- For errors, clearly state what went wrong and suggest next steps"""

SYSTEM_CONTEXT_ENRICH = """\
You are enriching a command with context from the conversation thread history.

Given the current command and prior messages in the thread, determine:
1. Whether this is a follow-up to a previous command
2. Any implicit context (e.g., "do it again" refers to the last action)
3. Referenced entities from earlier in the conversation
4. Whether the user is providing additional parameters for a prior request

Return the enriched command text with all implicit references resolved.
If the command is self-contained, return it unchanged."""
