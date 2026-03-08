"""Tests for shieldops.api.routes.scheduled_tasks — Scheduled Tasks API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.api.routes.scheduled_tasks import (
    CreateScheduledTaskBody,
    ScheduleFrequency,
    TriggerResult,
    UpdateScheduledTaskBody,
    _tasks,
    create_scheduled_task,
    delete_scheduled_task,
    get_scheduled_task,
    list_scheduled_tasks,
    trigger_scheduled_task,
    update_scheduled_task,
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


def _seed_task(
    *,
    task_id: str = "task-001",
    name: str = "Daily health check",
    prompt: str = "Check all services",
    workflow_type: str = "health_check",
    frequency: str = "daily",
    cron_expression: str | None = None,
    enabled: bool = True,
    run_count: int = 0,
    last_run_at: datetime | None = None,
    last_status: str | None = None,
    created_by: str = "user-001",
) -> dict[str, Any]:
    """Insert a task directly into _tasks and return it."""
    now = datetime.now(UTC)
    task: dict[str, Any] = {
        "id": task_id,
        "name": name,
        "prompt": prompt,
        "workflow_type": workflow_type,
        "frequency": frequency,
        "cron_expression": cron_expression,
        "enabled": enabled,
        "last_run_at": last_run_at,
        "next_run_at": None,
        "created_at": now,
        "created_by": created_by,
        "run_count": run_count,
        "last_status": last_status,
    }
    _tasks[task_id] = task
    return task


@pytest.fixture(autouse=True)
def _clear_task_store() -> None:
    """Reset in-memory task store between tests."""
    _tasks.clear()


# ---------------------------------------------------------------------------
# CreateScheduledTaskBody validation
# ---------------------------------------------------------------------------


class TestCreateScheduledTaskBodyValidation:
    def test_valid_daily_request(self) -> None:
        body = CreateScheduledTaskBody(
            name="Nightly backup scan",
            prompt="Verify backup integrity",
            workflow_type="backup_check",
            frequency=ScheduleFrequency.DAILY,
        )
        assert body.name == "Nightly backup scan"
        assert body.frequency == ScheduleFrequency.DAILY
        assert body.cron_expression is None
        assert body.enabled is True

    def test_valid_cron_request(self) -> None:
        body = CreateScheduledTaskBody(
            name="Custom schedule",
            prompt="Run analysis",
            workflow_type="analysis",
            frequency=ScheduleFrequency.CRON,
            cron_expression="0 */6 * * *",
        )
        assert body.cron_expression == "0 */6 * * *"

    def test_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateScheduledTaskBody(
                prompt="Do something",
                workflow_type="check",
                frequency=ScheduleFrequency.DAILY,
            )  # type: ignore[call-arg]

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateScheduledTaskBody(
                name="",
                prompt="Do something",
                workflow_type="check",
                frequency=ScheduleFrequency.DAILY,
            )

    def test_missing_prompt_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateScheduledTaskBody(
                name="Task",
                workflow_type="check",
                frequency=ScheduleFrequency.DAILY,
            )  # type: ignore[call-arg]

    def test_empty_prompt_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateScheduledTaskBody(
                name="Task",
                prompt="",
                workflow_type="check",
                frequency=ScheduleFrequency.DAILY,
            )

    def test_invalid_frequency_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateScheduledTaskBody(
                name="Task",
                prompt="Do something",
                workflow_type="check",
                frequency="every_second",  # type: ignore[arg-type]
            )

    def test_enabled_defaults_true(self) -> None:
        body = CreateScheduledTaskBody(
            name="Task",
            prompt="Prompt",
            workflow_type="wf",
            frequency=ScheduleFrequency.HOURLY,
        )
        assert body.enabled is True

    def test_enabled_can_be_false(self) -> None:
        body = CreateScheduledTaskBody(
            name="Task",
            prompt="Prompt",
            workflow_type="wf",
            frequency=ScheduleFrequency.HOURLY,
            enabled=False,
        )
        assert body.enabled is False


# ---------------------------------------------------------------------------
# UpdateScheduledTaskBody validation
# ---------------------------------------------------------------------------


class TestUpdateScheduledTaskBodyValidation:
    def test_all_none_is_valid_model(self) -> None:
        """Pydantic allows all-None; the endpoint checks for empty updates."""
        body = UpdateScheduledTaskBody()
        assert body.name is None
        assert body.prompt is None
        assert body.frequency is None
        assert body.cron_expression is None
        assert body.enabled is None

    def test_partial_fields(self) -> None:
        body = UpdateScheduledTaskBody(name="New name", enabled=False)
        assert body.name == "New name"
        assert body.enabled is False
        assert body.prompt is None

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            UpdateScheduledTaskBody(name="")


# ---------------------------------------------------------------------------
# create_scheduled_task
# ---------------------------------------------------------------------------


class TestCreateScheduledTask:
    @pytest.mark.asyncio
    async def test_create_daily_task(self) -> None:
        body = CreateScheduledTaskBody(
            name="Health check",
            prompt="Check services",
            workflow_type="health",
            frequency=ScheduleFrequency.DAILY,
        )
        result = await create_scheduled_task(body=body, user=_make_user())

        assert result["name"] == "Health check"
        assert result["prompt"] == "Check services"
        assert result["workflow_type"] == "health"
        assert result["frequency"] == "daily"
        assert result["enabled"] is True
        assert result["cron_expression"] is None
        assert result["run_count"] == 0
        assert result["last_run_at"] is None
        assert result["last_status"] is None
        assert result["created_by"] == "user-001"
        assert "id" in result
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_create_stores_in_memory(self) -> None:
        body = CreateScheduledTaskBody(
            name="Task",
            prompt="Prompt",
            workflow_type="wf",
            frequency=ScheduleFrequency.WEEKLY,
        )
        result = await create_scheduled_task(body=body, user=_make_user())
        assert result["id"] in _tasks

    @pytest.mark.asyncio
    async def test_create_cron_with_expression(self) -> None:
        body = CreateScheduledTaskBody(
            name="Cron job",
            prompt="Run at midnight",
            workflow_type="cleanup",
            frequency=ScheduleFrequency.CRON,
            cron_expression="0 0 * * *",
        )
        result = await create_scheduled_task(body=body, user=_make_user())
        assert result["frequency"] == "cron"
        assert result["cron_expression"] == "0 0 * * *"

    @pytest.mark.asyncio
    async def test_create_cron_without_expression_raises_400(self) -> None:
        body = CreateScheduledTaskBody(
            name="Bad cron",
            prompt="Missing expression",
            workflow_type="wf",
            frequency=ScheduleFrequency.CRON,
            cron_expression=None,
        )
        with pytest.raises(HTTPException) as exc_info:
            await create_scheduled_task(body=body, user=_make_user())
        assert exc_info.value.status_code == 400
        assert "cron_expression" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_non_cron_without_expression_succeeds(self) -> None:
        """Non-cron frequencies do not require cron_expression."""
        for freq in (
            ScheduleFrequency.HOURLY,
            ScheduleFrequency.DAILY,
            ScheduleFrequency.WEEKLY,
            ScheduleFrequency.MONTHLY,
        ):
            body = CreateScheduledTaskBody(
                name=f"{freq} task",
                prompt="Prompt",
                workflow_type="wf",
                frequency=freq,
            )
            result = await create_scheduled_task(body=body, user=_make_user())
            assert result["frequency"] == freq.value

    @pytest.mark.asyncio
    async def test_create_disabled_task(self) -> None:
        body = CreateScheduledTaskBody(
            name="Disabled task",
            prompt="Prompt",
            workflow_type="wf",
            frequency=ScheduleFrequency.DAILY,
            enabled=False,
        )
        result = await create_scheduled_task(body=body, user=_make_user())
        assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_create_uses_user_id_as_created_by(self) -> None:
        body = CreateScheduledTaskBody(
            name="Task",
            prompt="Prompt",
            workflow_type="wf",
            frequency=ScheduleFrequency.DAILY,
        )
        user = _make_user(id="custom-user-42")
        result = await create_scheduled_task(body=body, user=user)
        assert result["created_by"] == "custom-user-42"

    @pytest.mark.asyncio
    async def test_create_serialises_datetime_as_iso(self) -> None:
        body = CreateScheduledTaskBody(
            name="Task",
            prompt="Prompt",
            workflow_type="wf",
            frequency=ScheduleFrequency.DAILY,
        )
        result = await create_scheduled_task(body=body, user=_make_user())
        # created_at should be an ISO string, not a datetime object
        assert isinstance(result["created_at"], str)

    @pytest.mark.asyncio
    async def test_create_generates_unique_ids(self) -> None:
        body = CreateScheduledTaskBody(
            name="Task",
            prompt="Prompt",
            workflow_type="wf",
            frequency=ScheduleFrequency.DAILY,
        )
        r1 = await create_scheduled_task(body=body, user=_make_user())
        r2 = await create_scheduled_task(body=body, user=_make_user())
        assert r1["id"] != r2["id"]


# ---------------------------------------------------------------------------
# list_scheduled_tasks
# ---------------------------------------------------------------------------


class TestListScheduledTasks:
    @pytest.mark.asyncio
    async def test_empty_store(self) -> None:
        result = await list_scheduled_tasks(enabled=None, _user=_make_user())
        assert result == {"items": [], "total": 0}

    @pytest.mark.asyncio
    async def test_returns_all_tasks(self) -> None:
        _seed_task(task_id="t1", name="First")
        _seed_task(task_id="t2", name="Second")

        result = await list_scheduled_tasks(enabled=None, _user=_make_user())
        assert result["total"] == 2
        assert len(result["items"]) == 2

    @pytest.mark.asyncio
    async def test_filter_enabled_true(self) -> None:
        _seed_task(task_id="t1", enabled=True)
        _seed_task(task_id="t2", enabled=False)
        _seed_task(task_id="t3", enabled=True)

        result = await list_scheduled_tasks(enabled=True, _user=_make_user())
        assert result["total"] == 2
        ids = {item["id"] for item in result["items"]}
        assert ids == {"t1", "t3"}

    @pytest.mark.asyncio
    async def test_filter_enabled_false(self) -> None:
        _seed_task(task_id="t1", enabled=True)
        _seed_task(task_id="t2", enabled=False)

        result = await list_scheduled_tasks(enabled=False, _user=_make_user())
        assert result["total"] == 1
        assert result["items"][0]["id"] == "t2"

    @pytest.mark.asyncio
    async def test_no_filter_returns_all(self) -> None:
        _seed_task(task_id="t1", enabled=True)
        _seed_task(task_id="t2", enabled=False)

        result = await list_scheduled_tasks(enabled=None, _user=_make_user())
        assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_serialises_datetimes(self) -> None:
        _seed_task(task_id="t1")
        result = await list_scheduled_tasks(enabled=None, _user=_make_user())
        item = result["items"][0]
        assert isinstance(item["created_at"], str)


# ---------------------------------------------------------------------------
# get_scheduled_task
# ---------------------------------------------------------------------------


class TestGetScheduledTask:
    @pytest.mark.asyncio
    async def test_existing_task(self) -> None:
        _seed_task(task_id="t1", name="My Task", prompt="Do stuff")

        result = await get_scheduled_task(task_id="t1", _user=_make_user())
        assert result["id"] == "t1"
        assert result["name"] == "My Task"
        assert result["prompt"] == "Do stuff"

    @pytest.mark.asyncio
    async def test_nonexistent_task_returns_404(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await get_scheduled_task(task_id="ghost", _user=_make_user())
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_serialises_datetimes(self) -> None:
        _seed_task(task_id="t1")
        result = await get_scheduled_task(task_id="t1", _user=_make_user())
        assert isinstance(result["created_at"], str)


# ---------------------------------------------------------------------------
# update_scheduled_task
# ---------------------------------------------------------------------------


class TestUpdateScheduledTask:
    @pytest.mark.asyncio
    async def test_update_name(self) -> None:
        _seed_task(task_id="t1", name="Old name")
        body = UpdateScheduledTaskBody(name="New name")

        result = await update_scheduled_task(task_id="t1", body=body, user=_make_user())
        assert result["name"] == "New name"
        assert _tasks["t1"]["name"] == "New name"

    @pytest.mark.asyncio
    async def test_update_prompt(self) -> None:
        _seed_task(task_id="t1", prompt="Old prompt")
        body = UpdateScheduledTaskBody(prompt="New prompt")

        result = await update_scheduled_task(task_id="t1", body=body, user=_make_user())
        assert result["prompt"] == "New prompt"

    @pytest.mark.asyncio
    async def test_update_enabled(self) -> None:
        _seed_task(task_id="t1", enabled=True)
        body = UpdateScheduledTaskBody(enabled=False)

        result = await update_scheduled_task(task_id="t1", body=body, user=_make_user())
        assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_update_frequency_to_cron_with_expression(self) -> None:
        _seed_task(task_id="t1", frequency="daily")
        body = UpdateScheduledTaskBody(
            frequency=ScheduleFrequency.CRON,
            cron_expression="*/15 * * * *",
        )

        result = await update_scheduled_task(task_id="t1", body=body, user=_make_user())
        assert result["frequency"] == "cron"
        assert result["cron_expression"] == "*/15 * * * *"

    @pytest.mark.asyncio
    async def test_update_frequency_to_cron_without_expression_raises_400(self) -> None:
        _seed_task(task_id="t1", frequency="daily", cron_expression=None)
        body = UpdateScheduledTaskBody(frequency=ScheduleFrequency.CRON)

        with pytest.raises(HTTPException) as exc_info:
            await update_scheduled_task(task_id="t1", body=body, user=_make_user())
        assert exc_info.value.status_code == 400
        assert "cron_expression" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_existing_cron_task_keeps_expression(self) -> None:
        """If task already has cron freq and expression, updating name should still pass."""
        _seed_task(task_id="t1", frequency="cron", cron_expression="0 0 * * *")
        body = UpdateScheduledTaskBody(name="Renamed cron task")

        result = await update_scheduled_task(task_id="t1", body=body, user=_make_user())
        assert result["name"] == "Renamed cron task"
        assert result["frequency"] == "cron"
        assert result["cron_expression"] == "0 0 * * *"

    @pytest.mark.asyncio
    async def test_update_no_fields_raises_400(self) -> None:
        _seed_task(task_id="t1")
        body = UpdateScheduledTaskBody()  # All fields None

        with pytest.raises(HTTPException) as exc_info:
            await update_scheduled_task(task_id="t1", body=body, user=_make_user())
        assert exc_info.value.status_code == 400
        assert "No fields" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_nonexistent_task_returns_404(self) -> None:
        body = UpdateScheduledTaskBody(name="Anything")

        with pytest.raises(HTTPException) as exc_info:
            await update_scheduled_task(task_id="ghost", body=body, user=_make_user())
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self) -> None:
        _seed_task(task_id="t1", name="Old", prompt="Old prompt", enabled=True)
        body = UpdateScheduledTaskBody(
            name="New",
            prompt="New prompt",
            enabled=False,
        )

        result = await update_scheduled_task(task_id="t1", body=body, user=_make_user())
        assert result["name"] == "New"
        assert result["prompt"] == "New prompt"
        assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_update_preserves_unmodified_fields(self) -> None:
        _seed_task(
            task_id="t1",
            name="Original",
            prompt="Original prompt",
            workflow_type="scan",
            frequency="weekly",
            run_count=5,
        )
        body = UpdateScheduledTaskBody(name="Updated")

        result = await update_scheduled_task(task_id="t1", body=body, user=_make_user())
        assert result["name"] == "Updated"
        assert result["prompt"] == "Original prompt"
        assert result["workflow_type"] == "scan"
        assert result["frequency"] == "weekly"
        assert result["run_count"] == 5

    @pytest.mark.asyncio
    async def test_update_frequency_from_cron_to_daily_succeeds(self) -> None:
        """Switching away from cron should work even without cron_expression."""
        _seed_task(task_id="t1", frequency="cron", cron_expression="0 0 * * *")
        body = UpdateScheduledTaskBody(frequency=ScheduleFrequency.DAILY)

        result = await update_scheduled_task(task_id="t1", body=body, user=_make_user())
        assert result["frequency"] == "daily"


# ---------------------------------------------------------------------------
# delete_scheduled_task
# ---------------------------------------------------------------------------


class TestDeleteScheduledTask:
    @pytest.mark.asyncio
    async def test_delete_existing_task(self) -> None:
        _seed_task(task_id="t1")
        assert "t1" in _tasks

        result = await delete_scheduled_task(task_id="t1", user=_make_user())
        assert result is None
        assert "t1" not in _tasks

    @pytest.mark.asyncio
    async def test_delete_nonexistent_task_returns_404(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await delete_scheduled_task(task_id="ghost", user=_make_user())
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_delete_removes_only_target_task(self) -> None:
        _seed_task(task_id="t1")
        _seed_task(task_id="t2")

        await delete_scheduled_task(task_id="t1", user=_make_user())
        assert "t1" not in _tasks
        assert "t2" in _tasks

    @pytest.mark.asyncio
    async def test_delete_same_task_twice_returns_404(self) -> None:
        _seed_task(task_id="t1")
        await delete_scheduled_task(task_id="t1", user=_make_user())

        with pytest.raises(HTTPException) as exc_info:
            await delete_scheduled_task(task_id="t1", user=_make_user())
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# trigger_scheduled_task
# ---------------------------------------------------------------------------


class TestTriggerScheduledTask:
    @pytest.mark.asyncio
    async def test_trigger_existing_task(self) -> None:
        _seed_task(task_id="t1", run_count=0)

        result = await trigger_scheduled_task(task_id="t1", user=_make_user())

        assert isinstance(result, TriggerResult)
        assert result.task_id == "t1"
        assert result.status == "triggered"
        assert isinstance(result.triggered_at, datetime)

    @pytest.mark.asyncio
    async def test_trigger_increments_run_count(self) -> None:
        _seed_task(task_id="t1", run_count=0)

        await trigger_scheduled_task(task_id="t1", user=_make_user())
        assert _tasks["t1"]["run_count"] == 1

        await trigger_scheduled_task(task_id="t1", user=_make_user())
        assert _tasks["t1"]["run_count"] == 2

    @pytest.mark.asyncio
    async def test_trigger_updates_last_run_at(self) -> None:
        _seed_task(task_id="t1", last_run_at=None)
        assert _tasks["t1"]["last_run_at"] is None

        await trigger_scheduled_task(task_id="t1", user=_make_user())
        assert _tasks["t1"]["last_run_at"] is not None
        assert isinstance(_tasks["t1"]["last_run_at"], datetime)

    @pytest.mark.asyncio
    async def test_trigger_sets_last_status(self) -> None:
        _seed_task(task_id="t1", last_status=None)

        await trigger_scheduled_task(task_id="t1", user=_make_user())
        assert _tasks["t1"]["last_status"] == "triggered"

    @pytest.mark.asyncio
    async def test_trigger_nonexistent_task_returns_404(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await trigger_scheduled_task(task_id="ghost", user=_make_user())
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_trigger_with_existing_run_count(self) -> None:
        """Triggering a task that already has runs should increment from current count."""
        _seed_task(task_id="t1", run_count=10)

        await trigger_scheduled_task(task_id="t1", user=_make_user())
        assert _tasks["t1"]["run_count"] == 11

    @pytest.mark.asyncio
    async def test_trigger_result_timestamp_matches_task(self) -> None:
        _seed_task(task_id="t1")

        result = await trigger_scheduled_task(task_id="t1", user=_make_user())
        assert result.triggered_at == _tasks["t1"]["last_run_at"]
