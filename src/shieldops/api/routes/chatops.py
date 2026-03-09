"""ChatOps API endpoints.

Provides REST and webhook endpoints for processing ChatOps commands
from enterprise communication tools (Slack, Teams, PagerDuty).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status,
)
from pydantic import BaseModel, Field

from shieldops.agents.chatops.runner import ChatOpsRunner
from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

if TYPE_CHECKING:
    from shieldops.db.repository import Repository

router = APIRouter()

_runner: ChatOpsRunner | None = None
_repository: Repository | None = None


def get_runner() -> ChatOpsRunner:
    """Get or create the ChatOps runner singleton."""
    global _runner
    if _runner is None:
        _runner = ChatOpsRunner()
    return _runner


def set_runner(runner: ChatOpsRunner) -> None:
    """Override the runner instance (used for testing and dependency injection)."""
    global _runner
    _runner = runner


def set_repository(repo: Repository | None) -> None:
    """Set the persistence repository for read queries."""
    global _repository
    _repository = repo


# --- Request/Response models ---


class ChatOpsCommandRequest(BaseModel):
    """Request body to process a ChatOps command."""

    command: str = Field(description="The command text (e.g., '/investigate api-gateway')")
    channel: str = Field(
        default="slack", description="Channel type: slack, teams, pagerduty, webhook"
    )
    user_id: str = Field(default="api-user")
    user_name: str = Field(default="API User")
    channel_id: str = Field(default="api")
    channel_name: str = Field(default="api-channel")
    thread_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatOpsCommandResponse(BaseModel):
    """Response from a ChatOps command execution."""

    command_id: str
    status: str
    response_text: str | None = None
    execution_status: str
    agent_result: dict[str, Any] | None = None
    processing_duration_ms: int = 0


class ChatOpsApprovalRequest(BaseModel):
    """Request body to approve or deny a pending command."""

    command_id: str
    approved: bool
    approved_by: str


class SlackWebhookPayload(BaseModel):
    """Slack Events API / slash command payload."""

    type: str | None = None
    token: str | None = None
    challenge: str | None = None
    event: dict[str, Any] | None = None
    command: str | None = None
    text: str | None = None
    user_id: str | None = None
    user_name: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    response_url: str | None = None
    trigger_id: str | None = None


class TeamsWebhookPayload(BaseModel):
    """Microsoft Teams Bot Framework payload."""

    type: str | None = None
    text: str | None = None
    from_user: dict[str, Any] | None = Field(None, alias="from")
    conversation: dict[str, Any] | None = None
    channel_data: dict[str, Any] | None = Field(None, alias="channelData")


# --- Endpoints ---


@router.post(
    "/command",
    response_model=ChatOpsCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def process_command(
    request: ChatOpsCommandRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
) -> ChatOpsCommandResponse:
    """Process a ChatOps command via API."""
    runner = get_runner()
    state = await runner.process_command(
        command=request.command,
        channel=request.channel,
        user_id=request.user_id or current_user.id,
        user_name=request.user_name or current_user.name,
        channel_id=request.channel_id,
        channel_name=request.channel_name,
        thread_id=request.thread_id,
        metadata=request.metadata,
    )
    return ChatOpsCommandResponse(
        command_id=state.command_id or "",
        status=state.current_step,
        response_text=state.response_text,
        execution_status=state.execution_status.value
        if hasattr(state.execution_status, "value")
        else str(state.execution_status),
        agent_result=state.agent_result,
        processing_duration_ms=state.processing_duration_ms,
    )


@router.post("/webhook/slack")
async def slack_webhook(
    payload: SlackWebhookPayload,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Handle Slack Events API and slash command webhooks."""
    if payload.type == "url_verification" and payload.challenge:
        return {"challenge": payload.challenge}

    runner = get_runner()

    if payload.command and payload.text is not None:
        background_tasks.add_task(
            runner.process_command,
            command=f"{payload.command} {payload.text}".strip(),
            channel="slack",
            user_id=payload.user_id or "unknown",
            user_name=payload.user_name or "unknown",
            channel_id=payload.channel_id or "unknown",
            channel_name=payload.channel_name or "unknown",
            metadata={"response_url": payload.response_url},
        )
        return {"response_type": "ephemeral", "text": "Processing your command..."}

    if payload.event and payload.event.get("type") == "message":
        event = payload.event
        text = event.get("text", "")
        if text.startswith("/") or text.startswith("@shieldops"):
            background_tasks.add_task(
                runner.process_command,
                command=text.removeprefix("@shieldops").strip(),
                channel="slack",
                user_id=event.get("user", "unknown"),
                user_name=event.get("user", "unknown"),
                channel_id=event.get("channel", "unknown"),
                channel_name=event.get("channel", "unknown"),
                thread_id=event.get("thread_ts"),
            )

    return {"ok": True}


@router.post("/webhook/teams")
async def teams_webhook(
    payload: TeamsWebhookPayload,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Handle Microsoft Teams Bot Framework webhooks."""
    runner = get_runner()
    text = payload.text or ""

    if text:
        from_data = payload.from_user or {}
        conv_data = payload.conversation or {}
        background_tasks.add_task(
            runner.process_command,
            command=text,
            channel="teams",
            user_id=from_data.get("id", "unknown"),
            user_name=from_data.get("name", "unknown"),
            channel_id=conv_data.get("id", "unknown"),
            channel_name=conv_data.get("name", "unknown"),
        )

    return {"type": "message", "text": "Processing your command..."}


@router.post("/approve", status_code=status.HTTP_200_OK)
async def approve_command(
    request: ChatOpsApprovalRequest,
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN, UserRole.OPERATOR),
    ),
) -> dict[str, str]:
    """Approve or deny a pending ChatOps command."""
    runner = get_runner()
    await runner.handle_approval(
        command_id=request.command_id,
        approved_by=request.approved_by or _user.id,
        approved=request.approved,
    )
    action = "approved" if request.approved else "denied"
    return {"status": action, "command_id": request.command_id}


@router.get("/commands", response_model=list[dict[str, Any]])
async def list_commands(
    user_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    _user: UserResponse = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List recent ChatOps commands."""
    runner = get_runner()
    uid = user_id or _user.id
    return runner.list_commands(user_id=uid, limit=limit)


@router.get("/commands/{command_id}")
async def get_command(
    command_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get details of a specific command execution."""
    runner = get_runner()
    result = runner.get_command(command_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Command not found")
    return result.model_dump()
