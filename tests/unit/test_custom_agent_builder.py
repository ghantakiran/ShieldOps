"""Tests for the Custom Agent Builder — workflow DSL, execution, and API routes.

Covers:
- Workflow CRUD (create, get, list, update, delete)
- Validation (entry point, duplicate IDs, broken refs, cycles, action allow-list, limits)
- Action execution, retry, unknown action
- Condition branching (==, !=, >, <, missing variable)
- LLM step mock analysis
- Loop execution (N iterations, zero count)
- Full workflow runs (happy path, error + on_error, max_steps limit, timing)
- Run management (get, list, list by workflow)
- Cycle detection (no cycle, simple, complex, self-referencing)
- API routes (CRUD, run, validate, 503 without builder)
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from shieldops.agents.custom.builder import (
    CreateWorkflowRequest,
    CustomAgentBuilder,
    RunStatus,
    StepStatus,
    UpdateWorkflowRequest,
    WorkflowDefinition,
    WorkflowStep,
)
from shieldops.api.routes import custom_agents as custom_agents_routes

# ── Autouse fixture to reset the route-level singleton ──────────────


@pytest.fixture(autouse=True)
def reset_builder():
    custom_agents_routes._builder = None
    yield
    custom_agents_routes._builder = None


# ── Helper to build a simple valid workflow request ─────────────────


def _simple_workflow_request(
    name: str = "test-workflow",
    entry: str = "step1",
    steps: list[WorkflowStep] | None = None,
    variables: dict[str, Any] | None = None,
) -> CreateWorkflowRequest:
    if steps is None:
        steps = [
            WorkflowStep(
                id="step1",
                type="action",
                name="Log start",
                config={"action": "log", "params": {"message": "hello"}},
                next="step2",
            ),
            WorkflowStep(
                id="step2",
                type="action",
                name="Log end",
                config={"action": "log"},
            ),
        ]
    return CreateWorkflowRequest(
        name=name,
        description="A test workflow",
        steps=steps,
        entry_point=entry,
        variables=variables or {},
    )


# =========================================================================
# Workflow CRUD
# =========================================================================


class TestWorkflowCRUD:
    """Tests for create, get, list, update, delete operations."""

    def test_create_workflow(self):
        builder = CustomAgentBuilder()
        req = _simple_workflow_request()
        wf = builder.create_workflow(req)
        assert wf.id.startswith("wf-")
        assert wf.name == "test-workflow"
        assert len(wf.steps) == 2

    def test_get_workflow(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        result = builder.get_workflow(wf.id)
        assert result is not None
        assert result.id == wf.id

    def test_get_workflow_not_found(self):
        builder = CustomAgentBuilder()
        assert builder.get_workflow("nonexistent") is None

    def test_list_workflows(self):
        builder = CustomAgentBuilder()
        builder.create_workflow(_simple_workflow_request("wf-a"))
        builder.create_workflow(_simple_workflow_request("wf-b"))
        workflows = builder.list_workflows()
        assert len(workflows) == 2

    def test_update_workflow(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        updated = builder.update_workflow(wf.id, UpdateWorkflowRequest(name="updated-name"))
        assert updated is not None
        assert updated.name == "updated-name"
        assert updated.updated_at >= wf.updated_at

    def test_update_workflow_not_found(self):
        builder = CustomAgentBuilder()
        result = builder.update_workflow("nonexistent", UpdateWorkflowRequest(name="x"))
        assert result is None

    def test_delete_workflow(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        assert builder.delete_workflow(wf.id) is True
        assert builder.get_workflow(wf.id) is None

    def test_delete_workflow_not_found(self):
        builder = CustomAgentBuilder()
        assert builder.delete_workflow("nonexistent") is False


# =========================================================================
# Workflow Validation
# =========================================================================


class TestWorkflowValidation:
    """Tests for DAG validation, cycle detection, and action allow-listing."""

    def test_valid_workflow(self):
        builder = CustomAgentBuilder()
        req = _simple_workflow_request()
        wf = builder.create_workflow(req)
        errors = builder.validate_workflow(wf)
        assert errors == []

    def test_missing_entry_point(self):
        builder = CustomAgentBuilder()
        definition = WorkflowDefinition(
            name="bad",
            entry_point="nonexistent",
            steps=[WorkflowStep(id="s1", type="action", name="s1")],
        )
        errors = builder.validate_workflow(definition)
        assert any("Entry point" in e for e in errors)

    def test_duplicate_step_ids(self):
        builder = CustomAgentBuilder()
        definition = WorkflowDefinition(
            name="dup",
            entry_point="s1",
            steps=[
                WorkflowStep(id="s1", type="action", name="first"),
                WorkflowStep(id="s1", type="action", name="second"),
            ],
        )
        errors = builder.validate_workflow(definition)
        assert any("Duplicate step ID" in e for e in errors)

    def test_broken_next_reference(self):
        builder = CustomAgentBuilder()
        definition = WorkflowDefinition(
            name="broken",
            entry_point="s1",
            steps=[
                WorkflowStep(id="s1", type="action", name="s1", next="missing"),
            ],
        )
        errors = builder.validate_workflow(definition)
        assert any("non-existent next step" in e for e in errors)

    def test_cycle_detection(self):
        builder = CustomAgentBuilder()
        definition = WorkflowDefinition(
            name="cyclic",
            entry_point="s1",
            steps=[
                WorkflowStep(id="s1", type="action", name="s1", next="s2"),
                WorkflowStep(id="s2", type="action", name="s2", next="s1"),
            ],
        )
        errors = builder.validate_workflow(definition)
        assert any("Cycle detected" in e for e in errors)

    def test_disallowed_action(self):
        builder = CustomAgentBuilder()
        definition = WorkflowDefinition(
            name="forbidden",
            entry_point="s1",
            steps=[
                WorkflowStep(
                    id="s1",
                    type="action",
                    name="s1",
                    config={"action": "drop_database"},
                ),
            ],
        )
        errors = builder.validate_workflow(definition)
        assert any("disallowed action" in e for e in errors)

    def test_too_many_steps(self):
        builder = CustomAgentBuilder()
        # Create a workflow exceeding the hard definition limit
        # (hard_limit = max(max_steps, 1000); with max_steps=5, hard_limit=1000)
        # Use a low max_steps and manually set a very large step list
        steps = [WorkflowStep(id=f"s{i}", type="action", name=f"s{i}") for i in range(1005)]
        definition = WorkflowDefinition(
            name="large",
            entry_point="s0",
            steps=steps,
            max_steps=100,
        )
        errors = builder.validate_workflow(definition)
        assert any("exceeding maximum definition limit" in e for e in errors)


# =========================================================================
# Action Execution
# =========================================================================


class TestActionExecution:
    """Tests for action step execution, unknown actions, and retries."""

    @pytest.mark.asyncio
    async def test_execute_action_step(self):
        builder = CustomAgentBuilder()
        step = WorkflowStep(
            id="a1",
            type="action",
            name="test action",
            config={"action": "log", "params": {"message": "hi"}},
        )
        result = await builder._execute_step(step, {})
        assert result.status == StepStatus.COMPLETED
        assert result.output["action"] == "log"
        assert result.output["status"] == "success"

    @pytest.mark.asyncio
    async def test_unknown_action_fails(self):
        builder = CustomAgentBuilder()
        step = WorkflowStep(
            id="a2",
            type="action",
            name="bad action",
            config={"action": "rm_rf"},
        )
        result = await builder._execute_step(step, {})
        assert result.status == StepStatus.FAILED
        assert "not in the allowed actions" in result.error

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        builder = CustomAgentBuilder()
        call_count = 0

        original_execute = builder._execute_step

        async def _flaky_execute(step, variables):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                from shieldops.agents.custom.builder import StepResult, StepStatus

                return StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error="Transient error",
                )
            return await original_execute(step, variables)

        step = WorkflowStep(
            id="retry1",
            type="action",
            name="flaky action",
            config={"action": "log"},
            retry_count=3,
        )
        # Patch _execute_step to simulate transient failures
        builder._execute_step = _flaky_execute  # type: ignore[method-assign]
        result = await builder._execute_step_with_retry(step, {})
        assert result.status == StepStatus.COMPLETED
        assert result.retries_used == 2


# =========================================================================
# Condition Branching
# =========================================================================


class TestConditionBranching:
    """Tests for condition evaluation with various operators."""

    @pytest.mark.asyncio
    async def test_true_branch(self):
        builder = CustomAgentBuilder()
        step = WorkflowStep(
            id="c1",
            type="condition",
            name="check status",
            config={
                "condition": "status == active",
                "then_step": "on_true",
                "else_step": "on_false",
            },
        )
        result = await builder._execute_step(step, {"status": "active"})
        assert result.status == StepStatus.COMPLETED
        assert result.output is True

    @pytest.mark.asyncio
    async def test_false_branch(self):
        builder = CustomAgentBuilder()
        step = WorkflowStep(
            id="c2",
            type="condition",
            name="check status",
            config={
                "condition": "status == active",
                "then_step": "on_true",
                "else_step": "on_false",
            },
        )
        result = await builder._execute_step(step, {"status": "inactive"})
        assert result.status == StepStatus.COMPLETED
        assert result.output is False

    @pytest.mark.asyncio
    async def test_missing_variable_defaults_false(self):
        builder = CustomAgentBuilder()
        step = WorkflowStep(
            id="c3",
            type="condition",
            name="missing var",
            config={"condition": "unknown == yes"},
        )
        result = await builder._execute_step(step, {})
        assert result.output is False

    @pytest.mark.asyncio
    async def test_greater_than_operator(self):
        builder = CustomAgentBuilder()
        result = builder._evaluate_condition("count > 5", {"count": 10})
        assert result is True

    @pytest.mark.asyncio
    async def test_less_than_operator(self):
        builder = CustomAgentBuilder()
        result = builder._evaluate_condition("count < 5", {"count": 3})
        assert result is True

    @pytest.mark.asyncio
    async def test_not_equal_operator(self):
        builder = CustomAgentBuilder()
        result = builder._evaluate_condition("env != production", {"env": "staging"})
        assert result is True

    @pytest.mark.asyncio
    async def test_greater_equal_operator(self):
        builder = CustomAgentBuilder()
        result = builder._evaluate_condition("count >= 5", {"count": 5})
        assert result is True

    @pytest.mark.asyncio
    async def test_less_equal_operator(self):
        builder = CustomAgentBuilder()
        result = builder._evaluate_condition("count <= 5", {"count": 5})
        assert result is True


# =========================================================================
# LLM Step
# =========================================================================


class TestLLMStep:
    """Tests for the LLM reasoning step."""

    @pytest.mark.asyncio
    async def test_llm_step_returns_analysis(self):
        builder = CustomAgentBuilder()
        step = WorkflowStep(
            id="llm1",
            type="llm",
            name="analyze",
            config={"prompt": "What is wrong?", "model": "claude-sonnet-4-20250514"},
        )
        result = await builder._execute_step(step, {})
        assert result.status == StepStatus.COMPLETED
        assert "analysis" in result.output
        assert "confidence" in result.output
        assert "recommendations" in result.output
        assert result.output["model"] == "claude-sonnet-4-20250514"


# =========================================================================
# Loop Step
# =========================================================================


class TestLoopStep:
    """Tests for loop step execution."""

    @pytest.mark.asyncio
    async def test_loop_executes_n_times(self):
        builder = CustomAgentBuilder()
        step = WorkflowStep(
            id="loop1",
            type="loop",
            name="repeat",
            config={"count": 3, "body_step": "body_action"},
        )
        result = await builder._execute_step(step, {})
        assert result.status == StepStatus.COMPLETED
        assert result.output["iterations_completed"] == 3
        assert result.output["loop_count"] == 3

    @pytest.mark.asyncio
    async def test_loop_with_zero_count(self):
        builder = CustomAgentBuilder()
        step = WorkflowStep(
            id="loop2",
            type="loop",
            name="no-op loop",
            config={"count": 0, "body_step": "body_action"},
        )
        result = await builder._execute_step(step, {})
        assert result.status == StepStatus.COMPLETED
        assert result.output["iterations_completed"] == 0


# =========================================================================
# Workflow Run (end-to-end)
# =========================================================================


class TestWorkflowRun:
    """Tests for full workflow execution."""

    @pytest.mark.asyncio
    async def test_full_workflow_run(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        run = await builder.run_workflow(wf.id)
        assert run.status == RunStatus.COMPLETED
        assert len(run.step_results) == 2
        assert all(r.status == StepStatus.COMPLETED for r in run.step_results)
        assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_run_with_error_and_on_error_handler(self):
        # Use an allowed action so validation passes, then patch _execute_action
        # to raise so the step fails at runtime.
        builder = CustomAgentBuilder()
        steps = [
            WorkflowStep(
                id="s1",
                type="action",
                name="will-fail",
                config={"action": "log"},
                on_error="s_err",
            ),
            WorkflowStep(
                id="s_err",
                type="action",
                name="error handler",
                config={"action": "log", "params": {"message": "handling error"}},
            ),
        ]
        wf = builder.create_workflow(
            _simple_workflow_request(name="err-flow", entry="s1", steps=steps)
        )

        # Make the first action call raise to simulate a runtime failure
        original = builder._execute_action
        call_count = 0

        async def _failing_action(step: Any, variables: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated failure")
            return await original(step, variables)

        builder._execute_action = _failing_action  # type: ignore[method-assign]
        run = await builder.run_workflow(wf.id)

        # The first step fails, on_error handler runs successfully
        assert run.status == RunStatus.COMPLETED
        assert run.step_results[0].status == StepStatus.FAILED
        assert run.step_results[1].step_id == "s_err"
        assert run.step_results[1].status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_with_max_steps_limit(self):
        builder = CustomAgentBuilder()
        # Create a workflow with chained steps but a low max_steps
        steps = [
            WorkflowStep(
                id="s1",
                type="action",
                name="step 1",
                config={"action": "log"},
                next="s2",
            ),
            WorkflowStep(
                id="s2",
                type="action",
                name="step 2",
                config={"action": "log"},
                next="s3",
            ),
            WorkflowStep(
                id="s3",
                type="action",
                name="step 3",
                config={"action": "log"},
            ),
        ]
        wf = builder.create_workflow(
            CreateWorkflowRequest(
                name="limited",
                steps=steps,
                entry_point="s1",
                max_steps=2,
            )
        )
        run = await builder.run_workflow(wf.id)
        assert run.status == RunStatus.FAILED
        assert "Max steps" in run.error

    @pytest.mark.asyncio
    async def test_run_tracks_timing(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        run = await builder.run_workflow(wf.id)
        assert run.started_at is not None
        assert run.completed_at is not None
        for result in run.step_results:
            assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_run_with_condition_branching(self):
        builder = CustomAgentBuilder()
        steps = [
            WorkflowStep(
                id="check",
                type="condition",
                name="check env",
                config={
                    "condition": "env == production",
                    "then_step": "prod_action",
                    "else_step": "dev_action",
                },
            ),
            WorkflowStep(
                id="prod_action",
                type="action",
                name="production path",
                config={"action": "log", "params": {"message": "prod"}},
            ),
            WorkflowStep(
                id="dev_action",
                type="action",
                name="dev path",
                config={"action": "log", "params": {"message": "dev"}},
            ),
        ]
        wf = builder.create_workflow(
            _simple_workflow_request(
                name="branching",
                entry="check",
                steps=steps,
                variables={"env": "production"},
            )
        )
        run = await builder.run_workflow(wf.id)
        assert run.status == RunStatus.COMPLETED
        assert run.step_results[1].step_id == "prod_action"

    @pytest.mark.asyncio
    async def test_run_nonexistent_workflow(self):
        builder = CustomAgentBuilder()
        with pytest.raises(ValueError, match="not found"):
            await builder.run_workflow("wf-nonexistent")

    @pytest.mark.asyncio
    async def test_run_with_runtime_variables(self):
        builder = CustomAgentBuilder()
        steps = [
            WorkflowStep(
                id="check",
                type="condition",
                name="check flag",
                config={
                    "condition": "dry_run == yes",
                    "then_step": "skip",
                    "else_step": "execute",
                },
            ),
            WorkflowStep(
                id="skip",
                type="action",
                name="skip",
                config={"action": "log", "params": {"message": "skipped"}},
            ),
            WorkflowStep(
                id="execute",
                type="action",
                name="execute",
                config={"action": "log", "params": {"message": "executed"}},
            ),
        ]
        wf = builder.create_workflow(
            _simple_workflow_request(name="runtime-vars", entry="check", steps=steps)
        )
        run = await builder.run_workflow(wf.id, variables={"dry_run": "yes"})
        assert run.status == RunStatus.COMPLETED
        assert run.step_results[1].step_id == "skip"


# =========================================================================
# Run Management
# =========================================================================


class TestRunManagement:
    """Tests for run retrieval and listing."""

    @pytest.mark.asyncio
    async def test_get_run(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        run = await builder.run_workflow(wf.id)
        fetched = builder.get_run(run.id)
        assert fetched is not None
        assert fetched.id == run.id

    @pytest.mark.asyncio
    async def test_get_run_not_found(self):
        builder = CustomAgentBuilder()
        assert builder.get_run("run-nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_runs(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        await builder.run_workflow(wf.id)
        await builder.run_workflow(wf.id)
        runs = builder.list_runs()
        assert len(runs) == 2

    @pytest.mark.asyncio
    async def test_list_runs_by_workflow(self):
        builder = CustomAgentBuilder()
        wf1 = builder.create_workflow(_simple_workflow_request("wf-a"))
        wf2 = builder.create_workflow(_simple_workflow_request("wf-b"))
        await builder.run_workflow(wf1.id)
        await builder.run_workflow(wf1.id)
        await builder.run_workflow(wf2.id)
        runs_wf1 = builder.list_runs(workflow_id=wf1.id)
        runs_wf2 = builder.list_runs(workflow_id=wf2.id)
        assert len(runs_wf1) == 2
        assert len(runs_wf2) == 1


# =========================================================================
# Cycle Detection
# =========================================================================


class TestCycleDetection:
    """Tests for the DFS-based cycle detection algorithm."""

    def test_no_cycle(self):
        builder = CustomAgentBuilder()
        steps = [
            WorkflowStep(id="a", type="action", name="a", next="b"),
            WorkflowStep(id="b", type="action", name="b", next="c"),
            WorkflowStep(id="c", type="action", name="c"),
        ]
        cycles = builder._detect_cycles(steps)
        assert cycles == []

    def test_simple_cycle(self):
        builder = CustomAgentBuilder()
        steps = [
            WorkflowStep(id="a", type="action", name="a", next="b"),
            WorkflowStep(id="b", type="action", name="b", next="a"),
        ]
        cycles = builder._detect_cycles(steps)
        assert len(cycles) >= 1

    def test_complex_multi_node_cycle(self):
        builder = CustomAgentBuilder()
        steps = [
            WorkflowStep(id="a", type="action", name="a", next="b"),
            WorkflowStep(id="b", type="action", name="b", next="c"),
            WorkflowStep(id="c", type="action", name="c", next="a"),
        ]
        cycles = builder._detect_cycles(steps)
        assert len(cycles) >= 1

    def test_self_referencing_step(self):
        builder = CustomAgentBuilder()
        steps = [
            WorkflowStep(id="a", type="action", name="a", next="a"),
        ]
        cycles = builder._detect_cycles(steps)
        assert len(cycles) >= 1


# =========================================================================
# Wait Step
# =========================================================================


class TestWaitStep:
    """Tests for the wait step."""

    @pytest.mark.asyncio
    async def test_wait_step_caps_duration(self):
        builder = CustomAgentBuilder()
        step = WorkflowStep(
            id="w1",
            type="wait",
            name="long wait",
            config={"duration_seconds": 999},
        )
        result = await builder._execute_step(step, {})
        assert result.status == StepStatus.COMPLETED
        # Should be capped at MAX_WAIT_SECONDS (5)
        assert result.output["waited_seconds"] == 5

    @pytest.mark.asyncio
    async def test_wait_step_zero_duration(self):
        builder = CustomAgentBuilder()
        step = WorkflowStep(
            id="w2",
            type="wait",
            name="no wait",
            config={"duration_seconds": 0},
        )
        result = await builder._execute_step(step, {})
        assert result.status == StepStatus.COMPLETED
        assert result.output["waited_seconds"] == 0


# =========================================================================
# Set Variable Action
# =========================================================================


class TestSetVariableAction:
    """Tests for the set_variable action side-effect."""

    @pytest.mark.asyncio
    async def test_set_variable_updates_context(self):
        builder = CustomAgentBuilder()
        step = WorkflowStep(
            id="sv1",
            type="action",
            name="set var",
            config={
                "action": "set_variable",
                "params": {"name": "my_key", "value": "my_value"},
            },
        )
        variables: dict[str, Any] = {}
        result = await builder._execute_step(step, variables)
        assert result.status == StepStatus.COMPLETED
        assert variables["my_key"] == "my_value"


# =========================================================================
# API Routes
# =========================================================================


class TestAPIRoutes:
    """Tests for the FastAPI route layer.

    Uses a standalone FastAPI app to avoid route conflicts with the main
    app's ``/agents/{agent_id}`` catch-all parameter path.
    """

    def _make_client(self, builder: CustomAgentBuilder | None = None) -> TestClient:
        """Create a TestClient with the custom_agents router and auth override."""
        from fastapi import FastAPI

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole

        test_app = FastAPI()
        test_app.include_router(custom_agents_routes.router, prefix="/api/v1")
        test_app.dependency_overrides[get_current_user] = lambda: UserResponse(
            id="test-admin",
            email="admin@shieldops.test",
            name="Test Admin",
            role=UserRole.ADMIN,
            is_active=True,
        )
        if builder is not None:
            custom_agents_routes.set_builder(builder)
        return TestClient(test_app)

    def test_503_without_builder(self):
        client = self._make_client(builder=None)
        resp = client.get("/api/v1/agents/custom")
        assert resp.status_code == 503

    def test_create_workflow_via_api(self):
        builder = CustomAgentBuilder()
        client = self._make_client(builder)
        body = {
            "name": "api-workflow",
            "description": "created via API",
            "steps": [
                {
                    "id": "s1",
                    "type": "action",
                    "name": "log",
                    "config": {"action": "log"},
                }
            ],
            "entry_point": "s1",
        }
        resp = client.post("/api/v1/agents/custom", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow"]["name"] == "api-workflow"
        assert data["workflow"]["id"].startswith("wf-")

    def test_list_workflows_via_api(self):
        builder = CustomAgentBuilder()
        builder.create_workflow(_simple_workflow_request())
        client = self._make_client(builder)
        resp = client.get("/api/v1/agents/custom")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_get_workflow_via_api(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        client = self._make_client(builder)
        resp = client.get(f"/api/v1/agents/custom/{wf.id}")
        assert resp.status_code == 200
        assert resp.json()["workflow"]["id"] == wf.id

    def test_get_workflow_not_found_via_api(self):
        builder = CustomAgentBuilder()
        client = self._make_client(builder)
        resp = client.get("/api/v1/agents/custom/wf-nonexistent")
        assert resp.status_code == 404

    def test_update_workflow_via_api(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        client = self._make_client(builder)
        resp = client.put(
            f"/api/v1/agents/custom/{wf.id}",
            json={"name": "updated-via-api"},
        )
        assert resp.status_code == 200
        assert resp.json()["workflow"]["name"] == "updated-via-api"

    def test_delete_workflow_via_api(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        client = self._make_client(builder)
        resp = client.delete(f"/api/v1/agents/custom/{wf.id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_run_workflow_via_api(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        client = self._make_client(builder)
        resp = client.post(
            f"/api/v1/agents/custom/{wf.id}/run",
            json={"variables": {}},
        )
        assert resp.status_code == 200
        run_data = resp.json()["run"]
        assert run_data["status"] == "completed"
        assert len(run_data["step_results"]) == 2

    def test_run_workflow_not_found_via_api(self):
        builder = CustomAgentBuilder()
        client = self._make_client(builder)
        resp = client.post("/api/v1/agents/custom/wf-nonexistent/run", json={})
        assert resp.status_code == 404

    def test_validate_workflow_via_api(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        client = self._make_client(builder)
        resp = client.post(f"/api/v1/agents/custom/{wf.id}/validate")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True
        assert resp.json()["errors"] == []

    def test_get_run_via_api(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        client = self._make_client(builder)
        # First, create a run
        run_resp = client.post(f"/api/v1/agents/custom/{wf.id}/run", json={"variables": {}})
        run_id = run_resp.json()["run"]["id"]
        # Fetch the run via the /runs/{run_id} endpoint
        resp = client.get(f"/api/v1/agents/custom/runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["run"]["id"] == run_id

    def test_get_run_not_found_via_api(self):
        builder = CustomAgentBuilder()
        client = self._make_client(builder)
        resp = client.get("/api/v1/agents/custom/runs/run-nonexistent")
        assert resp.status_code == 404

    def test_list_workflow_runs_via_api(self):
        builder = CustomAgentBuilder()
        wf = builder.create_workflow(_simple_workflow_request())
        client = self._make_client(builder)
        client.post(f"/api/v1/agents/custom/{wf.id}/run", json={})
        resp = client.get(f"/api/v1/agents/custom/{wf.id}/runs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_create_invalid_workflow_via_api(self):
        builder = CustomAgentBuilder()
        client = self._make_client(builder)
        body = {
            "name": "invalid",
            "steps": [
                {
                    "id": "s1",
                    "type": "action",
                    "name": "s1",
                    "config": {"action": "log"},
                    "next": "s2",
                },
                {
                    "id": "s2",
                    "type": "action",
                    "name": "s2",
                    "config": {"action": "log"},
                    "next": "s1",
                },
            ],
            "entry_point": "s1",
        }
        resp = client.post("/api/v1/agents/custom", json=body)
        assert resp.status_code == 400
        assert "Cycle" in resp.json()["detail"]
