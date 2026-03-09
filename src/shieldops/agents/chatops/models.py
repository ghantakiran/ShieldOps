"""State models for the ChatOps Agent."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ChannelType(StrEnum):
    """Supported communication channels."""

    SLACK = "slack"
    TEAMS = "teams"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"


class CommandIntent(StrEnum):
    """Recognized command intents."""

    INVESTIGATE = "investigate"
    REMEDIATE = "remediate"
    SCAN = "scan"
    COST_REPORT = "cost_report"
    ESCALATE = "escalate"
    STATUS = "status"
    HELP = "help"
    UNKNOWN = "unknown"


class ChatOpsApprovalStatus(StrEnum):
    """Approval status for policy-gated commands."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    NOT_REQUIRED = "not_required"


class ChatOpsExecutionStatus(StrEnum):
    """Execution status of a ChatOps command."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"


class ParsedCommand(BaseModel):
    """Structured representation of a parsed natural language command."""

    intent: CommandIntent = CommandIntent.UNKNOWN
    entity: str = ""  # resource/service/alert being acted on
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_command: str = ""


class PolicyResult(BaseModel):
    """Result from OPA policy evaluation."""

    allowed: bool = False
    reason: str = ""
    required_approval: bool = False


class ReasoningStep(BaseModel):
    """A single step in the agent's reasoning chain."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int
    tool_used: str | None = None


class ResponseBlock(BaseModel):
    """A structured message block for Slack/Teams adaptive cards."""

    block_type: str  # section, divider, actions, context, header
    text: str = ""
    fields: list[dict[str, str]] = Field(default_factory=list)
    accessory: dict[str, Any] | None = None
    elements: list[dict[str, Any]] = Field(default_factory=list)


class ChatOpsState(BaseModel):
    """Full state of a ChatOps command workflow (LangGraph state)."""

    # Input
    command_id: str = ""
    command_text: str = ""
    channel: ChannelType = ChannelType.SLACK
    user_id: str = ""
    user_name: str = ""
    channel_id: str = ""
    channel_name: str = ""
    thread_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Processing
    parsed_command: ParsedCommand = Field(default_factory=ParsedCommand)
    matched_agent: str = ""
    policy_evaluation: PolicyResult = Field(default_factory=PolicyResult)
    approval_status: ChatOpsApprovalStatus = ChatOpsApprovalStatus.NOT_REQUIRED

    # Output
    response_text: str = ""
    response_blocks: list[ResponseBlock] = Field(default_factory=list)
    agent_result: dict[str, Any] = Field(default_factory=dict)
    execution_status: ChatOpsExecutionStatus = ChatOpsExecutionStatus.QUEUED

    # Metadata
    command_received_at: datetime | None = None
    processing_duration_ms: int = 0
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
