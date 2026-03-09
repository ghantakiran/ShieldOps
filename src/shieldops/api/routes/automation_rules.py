"""Automation Rules API endpoints.

Provides REST endpoints for creating, managing, and executing
automation rules that trigger agent actions based on incoming events.
"""

from __future__ import annotations

from datetime import UTC, datetime
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

from shieldops.agents.automation_orchestrator.runner import AutomationRunner
from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

if TYPE_CHECKING:
    from shieldops.db.repository import Repository

router = APIRouter()

# Application-level runner instance (initialized on first use or at startup)
_runner: AutomationRunner | None = None
_repository: Repository | None = None


def get_runner() -> AutomationRunner:
    """Get or create the automation rules runner singleton."""
    global _runner
    if _runner is None:
        _runner = AutomationRunner()
    return _runner


def set_runner(runner: AutomationRunner) -> None:
    """Override the runner instance (used for testing and dependency injection)."""
    global _runner
    _runner = runner


def set_repository(repo: Repository | None) -> None:
    """Set the persistence repository for read queries."""
    global _repository
    _repository = repo


# --- Request/Response models ---


class EventPayload(BaseModel):
    """Incoming event to match against automation rules."""

    event_type: str = Field(description="Event type (e.g., 'alert.fired', 'deploy.failed')")
    source: str = Field(description="Event source system (e.g., 'prometheus', 'github')")
    severity: str = Field(default="info", description="Event severity level")
    resource_id: str | None = Field(None, description="Affected resource identifier")
    labels: dict[str, str] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Full event payload for rule condition evaluation",
    )
    timestamp: str | None = Field(
        None,
        description="Event timestamp (ISO 8601). Defaults to server time.",
    )


class CreateRuleRequest(BaseModel):
    """Request body to create a new automation rule."""

    name: str = Field(description="Human-readable rule name")
    description: str = Field(default="", description="Rule description")
    category: str = Field(
        default="general",
        description="Rule category (e.g., 'incident', 'security', 'cost', 'compliance')",
    )
    enabled: bool = Field(default=True)
    conditions: dict[str, Any] = Field(
        description="Condition expression evaluated against incoming events",
    )
    actions: list[dict[str, Any]] = Field(
        description="Actions to execute when conditions match",
    )
    cooldown_seconds: int = Field(
        default=300,
        ge=0,
        le=86400,
        description="Minimum seconds between rule executions (0-86400)",
    )
    priority: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Rule priority (lower = higher priority)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateRuleRequest(BaseModel):
    """Request body to update an existing automation rule."""

    name: str | None = None
    description: str | None = None
    category: str | None = None
    enabled: bool | None = None
    conditions: dict[str, Any] | None = None
    actions: list[dict[str, Any]] | None = None
    cooldown_seconds: int | None = Field(None, ge=0, le=86400)
    priority: int | None = Field(None, ge=1, le=1000)
    metadata: dict[str, Any] | None = None


class ToggleRequest(BaseModel):
    """Request body to enable or disable a rule."""

    enabled: bool = Field(description="Set to true to enable, false to disable")


class RuleSummary(BaseModel):
    """Brief rule summary for list responses."""

    rule_id: str
    name: str
    category: str
    enabled: bool
    priority: int
    last_triggered_at: str | None = None
    total_executions: int = 0
    error: str | None = None


class ExecutionResult(BaseModel):
    """Result of a rule execution or event processing."""

    execution_id: str
    rule_id: str
    status: str
    matched: bool
    actions_executed: int = 0
    duration_ms: int = 0
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ExecutionHistory(BaseModel):
    """Historical execution entry for a rule."""

    execution_id: str
    rule_id: str
    event_type: str
    status: str
    matched: bool
    actions_executed: int = 0
    duration_ms: int = 0
    triggered_at: str
    completed_at: str | None = None
    error: str | None = None


# --- Endpoints ---


@router.post(
    "/events",
    response_model=list[ExecutionResult],
    status_code=status.HTTP_200_OK,
)
async def process_event(
    request: EventPayload,
    background_tasks: BackgroundTasks,
    _user: UserResponse = Depends(get_current_user),
) -> list[ExecutionResult]:
    """Process an incoming event against all enabled automation rules.

    Evaluates the event against rule conditions and executes matched
    actions. Returns the list of rules that matched and their results.
    """
    runner = get_runner()
    event_data: dict[str, Any] = {
        "type": request.event_type,
        "severity": request.severity,
        "resource_id": request.resource_id,
        "labels": request.labels,
        "timestamp": request.timestamp or datetime.now(UTC).isoformat(),
        **request.payload,
    }
    states = await runner.process_event(event_data=event_data, source=request.source)
    return [
        ExecutionResult(
            execution_id=s.execution_id,
            rule_id=s.rule.id,
            status=s.overall_status,
            matched=s.overall_status != "denied",
            actions_executed=len(s.action_results),
            duration_ms=s.execution_duration_ms,
            output={"summary": s.summary},
            error=s.error,
        )
        for s in states
    ]


@router.post(
    "/rules/{rule_id}/execute",
    response_model=ExecutionResult,
    status_code=status.HTTP_200_OK,
)
async def execute_rule(
    rule_id: str,
    background_tasks: BackgroundTasks,
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN, UserRole.OPERATOR),
    ),
) -> ExecutionResult:
    """Execute a specific rule manually.

    Runs the rule's actions regardless of conditions. Useful for
    testing and manual intervention scenarios.
    """
    runner = get_runner()
    try:
        state = await runner.execute_rule(rule_id=rule_id, event_data={})
    except KeyError:
        raise HTTPException(status_code=404, detail="Rule not found") from None
    return ExecutionResult(
        execution_id=state.execution_id,
        rule_id=state.rule.id,
        status=state.overall_status,
        matched=state.overall_status != "denied",
        actions_executed=len(state.action_results),
        duration_ms=state.execution_duration_ms,
        output={"summary": state.summary},
        error=state.error,
    )


@router.post(
    "/rules/{rule_id}/test",
    response_model=ExecutionResult,
    status_code=status.HTTP_200_OK,
)
async def test_rule(
    rule_id: str,
    request: EventPayload,
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN, UserRole.OPERATOR),
    ),
) -> ExecutionResult:
    """Dry-run test a rule against a sample event.

    Evaluates conditions and simulates actions without actually
    executing them. Returns what would happen if the event were real.
    """
    runner = get_runner()
    test_event: dict[str, Any] = {
        "type": request.event_type,
        "source": request.source,
        "severity": request.severity,
        "resource_id": request.resource_id,
        "labels": request.labels,
        **request.payload,
    }
    try:
        state = await runner.test_rule(rule_id=rule_id, test_event=test_event)
    except KeyError:
        raise HTTPException(status_code=404, detail="Rule not found") from None
    return ExecutionResult(
        execution_id=state.execution_id,
        rule_id=state.rule.id,
        status=state.overall_status,
        matched=state.overall_status != "denied",
        actions_executed=len(state.action_results),
        duration_ms=state.execution_duration_ms,
        output={"summary": state.summary},
        error=state.error,
    )


@router.post("/rules", status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: CreateRuleRequest,
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN, UserRole.OPERATOR),
    ),
) -> dict[str, Any]:
    """Create a new automation rule.

    Only ADMIN and OPERATOR users can create rules. The rule is
    immediately active if enabled=true (the default).
    """
    runner = get_runner()
    rule_config: dict[str, Any] = {
        "name": request.name,
        "description": request.description,
        "category": request.category,
        "enabled": request.enabled,
        "conditions": request.conditions,
        "actions": request.actions,
        "cooldown_seconds": request.cooldown_seconds,
        "priority": request.priority,
        "metadata": request.metadata,
    }
    rule = runner.create_rule(rule_config)
    return rule.model_dump()


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    request: UpdateRuleRequest,
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN, UserRole.OPERATOR),
    ),
) -> dict[str, Any]:
    """Update an existing automation rule.

    Only non-None fields in the request body are updated.
    """
    runner = get_runner()
    update_data = request.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    try:
        rule = runner.update_rule(rule_id=rule_id, updates=update_data)
    except KeyError:
        raise HTTPException(status_code=404, detail="Rule not found") from None
    return rule.model_dump()


@router.patch("/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: str,
    request: ToggleRequest,
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN, UserRole.OPERATOR),
    ),
) -> dict[str, str]:
    """Enable or disable an automation rule.

    A disabled rule will not match any incoming events until
    re-enabled.
    """
    runner = get_runner()
    try:
        runner.toggle_rule(rule_id=rule_id, enabled=request.enabled)
    except KeyError:
        raise HTTPException(status_code=404, detail="Rule not found") from None
    state = "enabled" if request.enabled else "disabled"
    return {"rule_id": rule_id, "status": state}


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_rule(
    rule_id: str,
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN),
    ),
) -> None:
    """Delete an automation rule.

    Only ADMIN users can delete rules. This is a permanent action.
    """
    runner = get_runner()
    try:
        runner.delete_rule(rule_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Rule not found") from None


@router.get("/rules", response_model=list[RuleSummary])
async def list_rules(
    category: str | None = Query(None, description="Filter by rule category"),
    enabled: bool | None = Query(None, description="Filter by enabled status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: UserResponse = Depends(get_current_user),
) -> list[RuleSummary]:
    """List automation rules with optional filters.

    Queries from PostgreSQL when available, falls back to in-memory.
    """
    if _repository and hasattr(_repository, "list_automation_rules"):
        items = await _repository.list_automation_rules(  # type: ignore[attr-defined]
            category=category,
            enabled=enabled,
            limit=limit,
            offset=offset,
        )
        return [RuleSummary(**item) for item in items]

    runner = get_runner()
    all_rules = runner.list_rules()

    if category:
        all_rules = [r for r in all_rules if r.get("category") == category]
    if enabled is not None:
        all_rules = [r for r in all_rules if r.get("enabled") == enabled]

    paginated = all_rules[offset : offset + limit]
    return [RuleSummary(**item) for item in paginated]


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get full rule details including conditions, actions, and metadata."""
    if _repository and hasattr(_repository, "get_automation_rule"):
        db_result: dict[str, Any] | None = await _repository.get_automation_rule(  # type: ignore[attr-defined]
            rule_id,
        )
        if db_result is not None:
            return db_result

    runner = get_runner()
    rule = runner.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule.model_dump()


@router.get(
    "/rules/{rule_id}/history",
    response_model=list[ExecutionHistory],
)
async def get_execution_history(
    rule_id: str,
    limit: int = Query(20, ge=1, le=100),
    _user: UserResponse = Depends(get_current_user),
) -> list[ExecutionHistory]:
    """Get execution history for a specific rule.

    Returns a chronological list of executions with match results,
    action counts, and any errors encountered.
    """
    if _repository and hasattr(_repository, "get_rule_execution_history"):
        items = await _repository.get_rule_execution_history(  # type: ignore[attr-defined]
            rule_id=rule_id,
            limit=limit,
        )
        return [ExecutionHistory(**item) for item in items]

    runner = get_runner()
    history = runner.get_execution_history(rule_id=rule_id, limit=limit)
    return [ExecutionHistory(**item) for item in history]
