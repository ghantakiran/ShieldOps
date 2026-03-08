"""Tests for shieldops.api.routes.agent_tasks — Agent Tasks API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.api.routes.agent_tasks import (
    CreateTaskRequest,
    StepApprovalRequest,
    StepDetail,
    TaskDetail,
    TaskSummary,
    _run_to_detail,
    _run_to_summary,
    _task_runs,
    approve_step,
    cancel_task,
    get_task,
    list_tasks,
    set_engine,
)
from shieldops.orchestration.models import (
    AgentType,
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user(**overrides: Any) -> UserResponse:
    defaults: dict[str, Any] = {
        "id": "user-001",
        "email": "ops@example.com",
        "name": "Test Operator",
        "role": UserRole.OPERATOR,
        "is_active": True,
    }
    defaults.update(overrides)
    return UserResponse(**defaults)


def _make_step(
    *,
    status: WorkflowStatus = WorkflowStatus.PENDING,
    agent_type: AgentType = AgentType.INVESTIGATION,
    action: str = "analyse_logs",
    step_id: str = "step-abc",
    **kwargs: Any,
) -> WorkflowStep:
    return WorkflowStep(
        step_id=step_id,
        agent_type=agent_type,
        action=action,
        status=status,
        **kwargs,
    )


def _make_run(
    *,
    run_id: str = "wfrun-test001",
    workflow_name: str = "incident_response",
    trigger: str = "manual",
    status: WorkflowStatus = WorkflowStatus.RUNNING,
    steps: list[WorkflowStep] | None = None,
    created_at: datetime | None = None,
    **kwargs: Any,
) -> WorkflowRun:
    return WorkflowRun(
        run_id=run_id,
        workflow_name=workflow_name,
        trigger=trigger,
        status=status,
        steps=steps or [],
        created_at=created_at or datetime.now(UTC),
        **kwargs,
    )


@pytest.fixture(autouse=True)
def _clear_task_store() -> None:
    """Reset in-memory task store between tests."""
    _task_runs.clear()


# ---------------------------------------------------------------------------
# CreateTaskRequest validation
# ---------------------------------------------------------------------------


class TestCreateTaskRequestValidation:
    def test_valid_request(self) -> None:
        req = CreateTaskRequest(prompt="Investigate high latency on api-gateway")
        assert req.prompt == "Investigate high latency on api-gateway"
        assert req.persona is None
        assert req.workflow_type is None
        assert req.context is None

    def test_missing_prompt_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateTaskRequest()  # type: ignore[call-arg]

    def test_empty_prompt_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateTaskRequest(prompt="")

    def test_optional_fields(self) -> None:
        req = CreateTaskRequest(
            prompt="Scan containers",
            persona="security",
            workflow_type="security_scan",
            context={"cluster": "prod-east"},
        )
        assert req.persona == "security"
        assert req.workflow_type == "security_scan"
        assert req.context == {"cluster": "prod-east"}


# ---------------------------------------------------------------------------
# Helper converters
# ---------------------------------------------------------------------------


class TestRunToSummary:
    def test_basic_conversion(self) -> None:
        now = datetime.now(UTC)
        step = _make_step()
        run = _make_run(steps=[step], created_at=now)

        summary = _run_to_summary(run)

        assert isinstance(summary, TaskSummary)
        assert summary.task_id == run.run_id
        assert summary.workflow_name == "incident_response"
        assert summary.status == WorkflowStatus.RUNNING.value
        assert summary.created_at == now
        assert summary.step_count == 1
        assert summary.completed_at is None

    def test_completed_run(self) -> None:
        now = datetime.now(UTC)
        run = _make_run(
            status=WorkflowStatus.COMPLETED,
            completed_at=now,
            steps=[_make_step(), _make_step(step_id="step-def")],
        )
        summary = _run_to_summary(run)

        assert summary.status == "completed"
        assert summary.completed_at == now
        assert summary.step_count == 2

    def test_zero_steps(self) -> None:
        run = _make_run(steps=[])
        summary = _run_to_summary(run)
        assert summary.step_count == 0


class TestRunToDetail:
    def test_basic_conversion(self) -> None:
        step = _make_step(
            status=WorkflowStatus.COMPLETED,
            result={"finding": "timeout"},
        )
        run = _make_run(
            steps=[step],
            metadata={"source": "alert-123"},
            initiated_by="admin@example.com",
        )

        detail = _run_to_detail(run)

        assert isinstance(detail, TaskDetail)
        assert detail.task_id == run.run_id
        assert detail.trigger == "manual"
        assert detail.metadata == {"source": "alert-123"}
        assert detail.initiated_by == "admin@example.com"
        assert len(detail.steps) == 1

    def test_step_fields_mapped(self) -> None:
        now = datetime.now(UTC)
        step = _make_step(
            step_id="step-xyz",
            agent_type=AgentType.REMEDIATION,
            action="restart_service",
            status=WorkflowStatus.FAILED,
            error="timeout reached",
            started_at=now,
            completed_at=now,
            result={"attempt": 1},
        )
        run = _make_run(steps=[step])
        detail = _run_to_detail(run)

        sd = detail.steps[0]
        assert isinstance(sd, StepDetail)
        assert sd.step_id == "step-xyz"
        assert sd.agent_type == AgentType.REMEDIATION.value
        assert sd.action == "restart_service"
        assert sd.status == "failed"
        assert sd.error == "timeout reached"
        assert sd.result == {"attempt": 1}
        assert sd.started_at == now
        assert sd.completed_at == now

    def test_multiple_steps_ordered(self) -> None:
        steps = [
            _make_step(step_id="s1", action="investigate"),
            _make_step(step_id="s2", action="remediate"),
            _make_step(step_id="s3", action="verify"),
        ]
        run = _make_run(steps=steps)
        detail = _run_to_detail(run)

        assert [s.step_id for s in detail.steps] == ["s1", "s2", "s3"]


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------


class TestListTasks:
    @pytest.mark.asyncio
    async def test_empty_store(self) -> None:
        result = await list_tasks(status=None, limit=50, _user=_make_user())
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_sorted_newest_first(self) -> None:
        old = _make_run(
            run_id="old",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        new = _make_run(
            run_id="new",
            created_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        _task_runs["old"] = old
        _task_runs["new"] = new

        result = await list_tasks(status=None, limit=50, _user=_make_user())
        assert [r.task_id for r in result] == ["new", "old"]

    @pytest.mark.asyncio
    async def test_filter_by_status(self) -> None:
        running = _make_run(run_id="r1", status=WorkflowStatus.RUNNING)
        completed = _make_run(run_id="r2", status=WorkflowStatus.COMPLETED)
        _task_runs["r1"] = running
        _task_runs["r2"] = completed

        result = await list_tasks(status="completed", limit=50, _user=_make_user())
        assert len(result) == 1
        assert result[0].task_id == "r2"

    @pytest.mark.asyncio
    async def test_invalid_status_raises_400(self) -> None:
        _task_runs["r1"] = _make_run(run_id="r1")

        with pytest.raises(HTTPException) as exc_info:
            await list_tasks(status="bogus", limit=50, _user=_make_user())
        assert exc_info.value.status_code == 400
        assert "bogus" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_limit_applied(self) -> None:
        for i in range(5):
            run = _make_run(
                run_id=f"r{i}",
                created_at=datetime(2025, 1, i + 1, tzinfo=UTC),
            )
            _task_runs[f"r{i}"] = run

        result = await list_tasks(status=None, limit=2, _user=_make_user())
        assert len(result) == 2


# ---------------------------------------------------------------------------
# get_task
# ---------------------------------------------------------------------------


class TestGetTask:
    @pytest.mark.asyncio
    async def test_existing_task(self) -> None:
        run = _make_run(run_id="t1", steps=[_make_step()])
        _task_runs["t1"] = run

        result = await get_task(task_id="t1", _user=_make_user())
        assert isinstance(result, TaskDetail)
        assert result.task_id == "t1"

    @pytest.mark.asyncio
    async def test_nonexistent_id_returns_404(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await get_task(task_id="does-not-exist", _user=_make_user())
        assert exc_info.value.status_code == 404
        assert "does-not-exist" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# approve_step
# ---------------------------------------------------------------------------


class TestApproveStep:
    @pytest.mark.asyncio
    async def test_approve_paused_step(self) -> None:
        step = _make_step(step_id="s1", status=WorkflowStatus.PAUSED)
        run = _make_run(run_id="t1", steps=[step])
        _task_runs["t1"] = run

        body = StepApprovalRequest(approved=True, comment="LGTM")
        result = await approve_step(
            task_id="t1",
            step_id="s1",
            body=body,
            user=_make_user(),
        )

        assert result["approved"] is True
        assert result["step_status"] == "running"
        assert step.status == WorkflowStatus.RUNNING

    @pytest.mark.asyncio
    async def test_reject_paused_step(self) -> None:
        step = _make_step(step_id="s1", status=WorkflowStatus.PAUSED)
        run = _make_run(run_id="t1", steps=[step])
        _task_runs["t1"] = run

        body = StepApprovalRequest(approved=False, comment="Too risky")
        result = await approve_step(
            task_id="t1",
            step_id="s1",
            body=body,
            user=_make_user(),
        )

        assert result["approved"] is False
        assert result["step_status"] == "failed"
        assert result["task_status"] == "cancelled"
        assert step.error == "Too risky"
        assert run.status == WorkflowStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_wrong_status_returns_409(self) -> None:
        step = _make_step(step_id="s1", status=WorkflowStatus.RUNNING)
        run = _make_run(run_id="t1", steps=[step])
        _task_runs["t1"] = run

        body = StepApprovalRequest(approved=True)
        with pytest.raises(HTTPException) as exc_info:
            await approve_step(
                task_id="t1",
                step_id="s1",
                body=body,
                user=_make_user(),
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_nonexistent_task_returns_404(self) -> None:
        body = StepApprovalRequest(approved=True)
        with pytest.raises(HTTPException) as exc_info:
            await approve_step(
                task_id="nope",
                step_id="s1",
                body=body,
                user=_make_user(),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_nonexistent_step_returns_404(self) -> None:
        run = _make_run(run_id="t1", steps=[_make_step(step_id="s1")])
        _task_runs["t1"] = run

        body = StepApprovalRequest(approved=True)
        with pytest.raises(HTTPException) as exc_info:
            await approve_step(
                task_id="t1",
                step_id="bad-step",
                body=body,
                user=_make_user(),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_reject_without_comment_uses_default(self) -> None:
        step = _make_step(step_id="s1", status=WorkflowStatus.PAUSED)
        run = _make_run(run_id="t1", steps=[step])
        _task_runs["t1"] = run

        body = StepApprovalRequest(approved=False)
        await approve_step(
            task_id="t1",
            step_id="s1",
            body=body,
            user=_make_user(),
        )
        assert step.error == "Rejected by reviewer"


# ---------------------------------------------------------------------------
# cancel_task
# ---------------------------------------------------------------------------


class TestCancelTask:
    @pytest.mark.asyncio
    async def test_cancel_running_task(self) -> None:
        step = _make_step(step_id="s1", status=WorkflowStatus.RUNNING)
        run = _make_run(run_id="t1", status=WorkflowStatus.RUNNING, steps=[step])
        _task_runs["t1"] = run

        result = await cancel_task(task_id="t1", user=_make_user())

        assert result["cancelled"] is True
        assert result["status"] == "cancelled"
        assert run.status == WorkflowStatus.CANCELLED
        assert run.completed_at is not None
        assert step.status == WorkflowStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self) -> None:
        run = _make_run(run_id="t1", status=WorkflowStatus.PENDING)
        _task_runs["t1"] = run

        result = await cancel_task(task_id="t1", user=_make_user())
        assert result["cancelled"] is True

    @pytest.mark.asyncio
    async def test_cancel_completed_task_returns_409(self) -> None:
        run = _make_run(run_id="t1", status=WorkflowStatus.COMPLETED)
        _task_runs["t1"] = run

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task(task_id="t1", user=_make_user())
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_failed_task_returns_409(self) -> None:
        run = _make_run(run_id="t1", status=WorkflowStatus.FAILED)
        _task_runs["t1"] = run

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task(task_id="t1", user=_make_user())
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task_returns_404(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await cancel_task(task_id="ghost", user=_make_user())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_leaves_completed_steps_untouched(self) -> None:
        done_step = _make_step(step_id="s1", status=WorkflowStatus.COMPLETED)
        pending_step = _make_step(step_id="s2", status=WorkflowStatus.PENDING)
        run = _make_run(
            run_id="t1",
            status=WorkflowStatus.RUNNING,
            steps=[done_step, pending_step],
        )
        _task_runs["t1"] = run

        await cancel_task(task_id="t1", user=_make_user())

        assert done_step.status == WorkflowStatus.COMPLETED
        assert pending_step.status == WorkflowStatus.CANCELLED


# ---------------------------------------------------------------------------
# set_engine
# ---------------------------------------------------------------------------


class TestSetEngine:
    def test_set_engine_stores_reference(self) -> None:
        mock_engine = MagicMock()
        set_engine(mock_engine)

        # Verify by reading module global (import again to check)
        from shieldops.api.routes import agent_tasks

        assert agent_tasks._engine is mock_engine

        # Clean up
        agent_tasks._engine = None
