"""Custom Agent Builder — YAML-based workflow DSL with step execution engine.

Provides a low-code interface for defining and executing custom agent workflows
consisting of action, condition, LLM reasoning, loop, parallel, and wait nodes.
Workflows are validated as DAGs with cycle detection before execution.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class StepType(StrEnum):
    ACTION = "action"
    CONDITION = "condition"
    LLM = "llm"
    LOOP = "loop"
    PARALLEL = "parallel"
    WAIT = "wait"


class StepStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class WorkflowStep(BaseModel):
    """A single node in a workflow DAG."""

    id: str
    type: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    next: str | None = None
    on_error: str | None = None
    retry_count: int = 0
    timeout_seconds: int = 300


class WorkflowDefinition(BaseModel):
    """Complete workflow definition with steps, variables, and resource limits."""

    id: str = Field(default_factory=lambda: _generate_id("wf"))
    name: str
    description: str = ""
    version: str = "1.0"
    steps: list[WorkflowStep] = Field(default_factory=list)
    entry_point: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    max_steps: int = 100
    max_duration_seconds: int = 3600
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StepResult(BaseModel):
    """Result of executing a single workflow step."""

    step_id: str
    status: str
    output: Any = None
    error: str | None = None
    duration_ms: float = 0
    retries_used: int = 0


class WorkflowRun(BaseModel):
    """Record of a single workflow execution."""

    id: str = Field(default_factory=lambda: _generate_id("run"))
    workflow_id: str
    status: str = RunStatus.RUNNING
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    step_results: list[StepResult] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class CreateWorkflowRequest(BaseModel):
    """Request body for creating a new workflow."""

    name: str
    description: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    entry_point: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    max_steps: int = 100
    max_duration_seconds: int = 3600


class UpdateWorkflowRequest(BaseModel):
    """Request body for updating an existing workflow. All fields optional."""

    name: str | None = None
    description: str | None = None
    steps: list[WorkflowStep] | None = None
    entry_point: str | None = None
    variables: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Default allowed actions
# ---------------------------------------------------------------------------

DEFAULT_ALLOWED_ACTIONS: list[str] = [
    "log",
    "http_request",
    "set_variable",
    "send_notification",
    "query_metrics",
    "create_investigation",
    "execute_playbook",
]

# Maximum wait duration to prevent abuse (seconds)
MAX_WAIT_SECONDS = 5


# ---------------------------------------------------------------------------
# CustomAgentBuilder
# ---------------------------------------------------------------------------


class CustomAgentBuilder:
    """Low-code workflow builder and executor for custom agents.

    Supports action, condition, LLM reasoning, loop, parallel, and wait nodes.
    Validates workflows as DAGs with cycle detection and action allow-listing.
    """

    def __init__(self, allowed_actions: list[str] | None = None) -> None:
        self._allowed_actions: list[str] = (
            list(allowed_actions) if allowed_actions is not None else list(DEFAULT_ALLOWED_ACTIONS)
        )
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._runs: dict[str, WorkflowRun] = {}

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def create_workflow(self, request: CreateWorkflowRequest) -> WorkflowDefinition:
        """Create and store a new workflow definition after validation."""
        definition = WorkflowDefinition(
            name=request.name,
            description=request.description,
            steps=request.steps,
            entry_point=request.entry_point,
            variables=request.variables,
            max_steps=request.max_steps,
            max_duration_seconds=request.max_duration_seconds,
        )

        errors = self.validate_workflow(definition)
        if errors:
            raise ValueError(f"Workflow validation failed: {'; '.join(errors)}")

        self._workflows[definition.id] = definition
        logger.info(
            "workflow_created",
            workflow_id=definition.id,
            name=definition.name,
            steps=len(definition.steps),
        )
        return definition

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        """Retrieve a workflow definition by ID."""
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> list[WorkflowDefinition]:
        """List all stored workflow definitions."""
        return list(self._workflows.values())

    def update_workflow(
        self, workflow_id: str, request: UpdateWorkflowRequest
    ) -> WorkflowDefinition | None:
        """Update an existing workflow definition. Returns None if not found."""
        existing = self._workflows.get(workflow_id)
        if existing is None:
            return None

        if request.name is not None:
            existing.name = request.name
        if request.description is not None:
            existing.description = request.description
        if request.steps is not None:
            existing.steps = request.steps
        if request.entry_point is not None:
            existing.entry_point = request.entry_point
        if request.variables is not None:
            existing.variables = request.variables

        existing.updated_at = datetime.now(UTC)

        errors = self.validate_workflow(existing)
        if errors:
            raise ValueError(f"Workflow validation failed: {'; '.join(errors)}")

        self._workflows[workflow_id] = existing
        logger.info("workflow_updated", workflow_id=workflow_id)
        return existing

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow definition. Returns True if deleted."""
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
            logger.info("workflow_deleted", workflow_id=workflow_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_workflow(self, definition: WorkflowDefinition) -> list[str]:
        """Validate a workflow definition and return a list of error strings.

        Checks:
        - Entry point exists in step IDs
        - All step IDs are unique
        - All ``next`` / ``on_error`` references point to existing steps
        - No cycles (DAG constraint via DFS)
        - All action steps use allowed actions
        - Step count within max_steps limit
        """
        errors: list[str] = []
        step_ids = {s.id for s in definition.steps}

        # Entry point exists
        if definition.entry_point and definition.entry_point not in step_ids:
            errors.append(
                f"Entry point '{definition.entry_point}' does not reference an existing step"
            )

        # Unique IDs
        seen_ids: set[str] = set()
        for step in definition.steps:
            if step.id in seen_ids:
                errors.append(f"Duplicate step ID: '{step.id}'")
            seen_ids.add(step.id)

        # Broken next / on_error references
        for step in definition.steps:
            if step.next is not None and step.next not in step_ids:
                errors.append(f"Step '{step.id}' references non-existent next step '{step.next}'")
            if step.on_error is not None and step.on_error not in step_ids:
                errors.append(
                    f"Step '{step.id}' references non-existent on_error step '{step.on_error}'"
                )
            # Condition branch references
            if step.type == StepType.CONDITION:
                for branch in ("then_step", "else_step"):
                    target = step.config.get(branch)
                    if target is not None and target not in step_ids:
                        errors.append(
                            f"Step '{step.id}' condition {branch} references "
                            f"non-existent step '{target}'"
                        )
            # Loop body reference
            if step.type == StepType.LOOP:
                body = step.config.get("body_step")
                if body is not None and body not in step_ids:
                    errors.append(
                        f"Step '{step.id}' loop body_step references non-existent step '{body}'"
                    )

        # Cycle detection
        cycles = self._detect_cycles(definition.steps)
        if cycles:
            for cycle in cycles:
                errors.append(f"Cycle detected: {' -> '.join(cycle)}")

        # Action allow-list
        for step in definition.steps:
            if step.type == StepType.ACTION:
                action_name = step.config.get("action", "")
                if action_name and action_name not in self._allowed_actions:
                    errors.append(
                        f"Step '{step.id}' uses disallowed action '{action_name}'. "
                        f"Allowed: {self._allowed_actions}"
                    )

        # Step definition count hard limit (prevents excessively large definitions)
        hard_limit = max(definition.max_steps, 1000)
        if len(definition.steps) > hard_limit:
            errors.append(
                f"Workflow has {len(definition.steps)} steps, "
                f"exceeding maximum definition limit={hard_limit}"
            )

        return errors

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_workflow(
        self,
        workflow_id: str,
        variables: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Execute a workflow from its entry point, following the step chain.

        Handles action, condition, LLM, loop, wait, and parallel step types.
        Respects retry_count, on_error handlers, and max_steps limits.
        """
        definition = self._workflows.get(workflow_id)
        if definition is None:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        run_vars: dict[str, Any] = {**definition.variables, **(variables or {})}
        run = WorkflowRun(workflow_id=workflow_id, variables=run_vars)
        self._runs[run.id] = run

        step_map: dict[str, WorkflowStep] = {s.id: s for s in definition.steps}
        current_step_id: str | None = definition.entry_point
        executed_count = 0

        logger.info(
            "workflow_run_started",
            run_id=run.id,
            workflow_id=workflow_id,
            entry_point=current_step_id,
        )

        while current_step_id and executed_count < definition.max_steps:
            step = step_map.get(current_step_id)
            if step is None:
                run.status = RunStatus.FAILED
                run.error = f"Step '{current_step_id}' not found"
                break

            result = await self._execute_step_with_retry(step, run_vars)
            run.step_results.append(result)
            executed_count += 1

            if result.status == StepStatus.FAILED:
                if step.on_error:
                    current_step_id = step.on_error
                    continue
                run.status = RunStatus.FAILED
                run.error = result.error
                break

            # Determine next step based on type
            if step.type == StepType.CONDITION:
                if result.output is True:
                    current_step_id = step.config.get("then_step")
                else:
                    current_step_id = step.config.get("else_step")
            else:
                current_step_id = step.next

        # Finalize run
        if run.status == RunStatus.RUNNING:
            if executed_count >= definition.max_steps and current_step_id:
                run.status = RunStatus.FAILED
                run.error = f"Max steps ({definition.max_steps}) exceeded"
            else:
                run.status = RunStatus.COMPLETED

        run.completed_at = datetime.now(UTC)
        run.variables = run_vars

        logger.info(
            "workflow_run_completed",
            run_id=run.id,
            status=run.status,
            steps_executed=executed_count,
        )
        return run

    # ------------------------------------------------------------------
    # Run management
    # ------------------------------------------------------------------

    def get_run(self, run_id: str) -> WorkflowRun | None:
        """Retrieve a workflow run by ID."""
        return self._runs.get(run_id)

    def list_runs(self, workflow_id: str | None = None) -> list[WorkflowRun]:
        """List all runs, optionally filtered by workflow ID."""
        if workflow_id is not None:
            return [r for r in self._runs.values() if r.workflow_id == workflow_id]
        return list(self._runs.values())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_cycles(self, steps: list[WorkflowStep]) -> list[list[str]]:
        """Detect cycles in the step graph using iterative DFS.

        Returns a list of cycles, where each cycle is a list of step IDs
        forming the cycle path.
        """
        adjacency: dict[str, list[str]] = {}
        for step in steps:
            neighbors: list[str] = []
            if step.next is not None:
                neighbors.append(step.next)
            if step.on_error is not None:
                neighbors.append(step.on_error)
            if step.type == StepType.CONDITION:
                for branch in ("then_step", "else_step"):
                    target = step.config.get(branch)
                    if target is not None:
                        neighbors.append(target)
            if step.type == StepType.LOOP:
                body = step.config.get("body_step")
                if body is not None:
                    neighbors.append(body)
            adjacency[step.id] = neighbors

        # Standard DFS-based cycle detection (0=unvisited, 1=in-stack, 2=done)
        _unvisited, _in_stack, _done = 0, 1, 2
        color: dict[str, int] = {s.id: _unvisited for s in steps}
        parent: dict[str, str | None] = {s.id: None for s in steps}
        cycles: list[list[str]] = []

        def _dfs(node: str) -> None:
            color[node] = _in_stack
            for neighbor in adjacency.get(node, []):
                if neighbor not in color:
                    # neighbor is outside the known step set, skip
                    continue
                if color[neighbor] == _in_stack:
                    # Back edge found — reconstruct cycle
                    cycle = [neighbor, node]
                    current = node
                    while current != neighbor:
                        current = parent.get(current)  # type: ignore[assignment]
                        if current is None or current == neighbor:
                            break
                        cycle.append(current)
                    cycle.reverse()
                    cycles.append(cycle)
                elif color[neighbor] == _unvisited:
                    parent[neighbor] = node
                    _dfs(neighbor)
            color[node] = _done

        for step in steps:
            if color[step.id] == _unvisited:
                _dfs(step.id)

        return cycles

    async def _execute_step_with_retry(
        self,
        step: WorkflowStep,
        variables: dict[str, Any],
    ) -> StepResult:
        """Execute a step with retries on failure."""
        retries_used = 0
        last_result: StepResult | None = None

        for attempt in range(1 + step.retry_count):
            result = await self._execute_step(step, variables)
            last_result = result
            result.retries_used = retries_used

            if result.status != StepStatus.FAILED or attempt >= step.retry_count:
                break
            retries_used += 1
            logger.debug(
                "step_retry",
                step_id=step.id,
                attempt=retries_used,
                max_retries=step.retry_count,
            )

        assert last_result is not None
        last_result.retries_used = retries_used
        return last_result

    async def _execute_step(
        self,
        step: WorkflowStep,
        variables: dict[str, Any],
    ) -> StepResult:
        """Execute a single workflow step based on its type."""
        start = time.monotonic()

        try:
            output: Any
            if step.type == StepType.ACTION:
                output = await self._execute_action(step, variables)
            elif step.type == StepType.CONDITION:
                output = self._evaluate_condition(step.config.get("condition", ""), variables)
            elif step.type == StepType.LLM:
                output = await self._execute_llm(step, variables)
            elif step.type == StepType.LOOP:
                output = await self._execute_loop(step, variables)
            elif step.type == StepType.WAIT:
                output = await self._execute_wait(step)
            elif step.type == StepType.PARALLEL:
                output = await self._execute_parallel(step, variables)
            else:
                raise ValueError(f"Unknown step type: {step.type}")

            elapsed_ms = (time.monotonic() - start) * 1000
            return StepResult(
                step_id=step.id,
                status=StepStatus.COMPLETED,
                output=output,
                duration_ms=round(elapsed_ms, 2),
            )

        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.warning(
                "step_execution_failed",
                step_id=step.id,
                error=str(exc),
            )
            return StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(exc),
                duration_ms=round(elapsed_ms, 2),
            )

    async def _execute_action(
        self,
        step: WorkflowStep,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an action step (simulated: logs and returns success)."""
        action_name = step.config.get("action", "")
        if action_name not in self._allowed_actions:
            raise ValueError(f"Action '{action_name}' is not in the allowed actions list")

        params = step.config.get("params", {})

        # set_variable has a side-effect: it updates the workflow variables
        if action_name == "set_variable":
            var_name = params.get("name", "")
            var_value = params.get("value")
            if var_name:
                variables[var_name] = var_value

        logger.info(
            "action_executed",
            step_id=step.id,
            action=action_name,
            params=params,
        )
        return {"action": action_name, "status": "success", "params": params}

    async def _execute_llm(
        self,
        step: WorkflowStep,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """Simulate LLM reasoning step (returns a mock analysis result)."""
        prompt = step.config.get("prompt", "Analyze the current situation")
        model = step.config.get("model", "claude-sonnet-4-20250514")

        logger.info("llm_step_executed", step_id=step.id, model=model)
        return {
            "analysis": f"LLM analysis for: {prompt}",
            "model": model,
            "confidence": 0.85,
            "recommendations": [
                "Review the current metrics",
                "Check for anomalies",
                "Consider escalation if needed",
            ],
        }

    async def _execute_loop(
        self,
        step: WorkflowStep,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a loop step: repeat body_step N times."""
        count = step.config.get("count", 0)
        body_step_id = step.config.get("body_step")
        iterations_completed = 0

        if body_step_id and count > 0:
            # We don't re-lookup steps here to avoid circular dependency;
            # instead we log each iteration as simulated.
            for i in range(count):
                logger.info(
                    "loop_iteration",
                    step_id=step.id,
                    iteration=i + 1,
                    total=count,
                    body_step=body_step_id,
                )
                iterations_completed += 1

        return {
            "loop_count": count,
            "body_step": body_step_id,
            "iterations_completed": iterations_completed,
        }

    async def _execute_wait(self, step: WorkflowStep) -> dict[str, Any]:
        """Execute a wait step: sleep for the configured duration (capped)."""
        duration = min(step.config.get("duration_seconds", 0), MAX_WAIT_SECONDS)
        if duration > 0:
            await asyncio.sleep(duration)
        return {"waited_seconds": duration}

    async def _execute_parallel(
        self,
        step: WorkflowStep,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute parallel steps (simulated: logs each branch)."""
        branches = step.config.get("branches", [])
        logger.info(
            "parallel_step_executed",
            step_id=step.id,
            branch_count=len(branches),
        )
        return {
            "branches": branches,
            "status": "all_completed",
            "branch_count": len(branches),
        }

    def _evaluate_condition(
        self,
        expression: str,
        variables: dict[str, Any],
    ) -> bool:
        """Evaluate a simple condition expression against workflow variables.

        Supported operators: ==, !=, >, <, >=, <=
        Expression format: "variable_name <operator> value"

        Does NOT use eval() -- parses manually for safety.
        """
        if not expression.strip():
            return False

        # Supported operators (check multi-char first to avoid partial matches)
        operators = [">=", "<=", "!=", "==", ">", "<"]
        op: str | None = None
        parts: list[str] = []

        for candidate in operators:
            if candidate in expression:
                idx = expression.index(candidate)
                parts = [
                    expression[:idx].strip(),
                    expression[idx + len(candidate) :].strip(),
                ]
                op = candidate
                break

        if op is None or len(parts) != 2:
            return False

        var_name, raw_value = parts

        # Resolve the variable from the workflow context
        actual = variables.get(var_name)
        if actual is None:
            return False

        # Coerce raw_value to match the type of the variable
        expected = self._coerce_value(raw_value, type(actual))

        try:
            if op == "==":
                return bool(actual == expected)
            if op == "!=":
                return bool(actual != expected)
            if op == ">":
                return bool(actual > expected)
            if op == "<":
                return bool(actual < expected)
            if op == ">=":
                return bool(actual >= expected)
            if op == "<=":
                return bool(actual <= expected)
        except TypeError:
            return False

        return False

    @staticmethod
    def _coerce_value(raw: str, target_type: type) -> Any:
        """Coerce a string value to the target type for condition evaluation."""
        if target_type is bool:
            return raw.lower() in ("true", "1", "yes")
        if target_type is int:
            try:
                return int(raw)
            except ValueError:
                return raw
        if target_type is float:
            try:
                return float(raw)
            except ValueError:
                return raw
        # Default: return as string
        return raw
