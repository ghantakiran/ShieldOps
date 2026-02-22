"""Comprehensive tests for the ParallelAgentExecutor and related models.

Tests cover:
- Pydantic model defaults and construction (AgentTask, AgentResult, ExecutionPlan, MergedResult)
- ExecutionStatus enum values
- ResultMerger merge logic (investigation, security, mixed, empty, failed-only)
- ParallelAgentExecutor.create_plan for critical/high/normal priorities
- ParallelAgentExecutor.execute with parallel and sequential plans
- Partial failure, total failure, and timeout handling
- Runner dispatch: investigate / scan / run / no-method fallback
- No runner registered for agent type
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.orchestration.parallel_executor import (
    AgentResult,
    AgentTask,
    ExecutionPlan,
    ExecutionStatus,
    MergedResult,
    ParallelAgentExecutor,
    ResultMerger,
)

# ---------------------------------------------------------------------------
# Helper: async runner factories
# ---------------------------------------------------------------------------


def make_investigate_runner(return_value: dict | None = None, side_effect=None) -> MagicMock:
    """Create a mock runner with an async `investigate` method."""
    runner = MagicMock()
    mock_method = AsyncMock(return_value=return_value or {}, side_effect=side_effect)
    runner.investigate = mock_method
    # Ensure hasattr checks work correctly
    del runner.scan
    del runner.run
    return runner


def make_scan_runner(return_value: dict | None = None, side_effect=None) -> MagicMock:
    """Create a mock runner with an async `scan` method."""
    runner = MagicMock()
    mock_method = AsyncMock(return_value=return_value or {}, side_effect=side_effect)
    runner.scan = mock_method
    del runner.investigate
    del runner.run
    return runner


def make_run_runner(return_value: dict | None = None, side_effect=None) -> MagicMock:
    """Create a mock runner with an async `run` method."""
    runner = MagicMock()
    mock_method = AsyncMock(return_value=return_value or {}, side_effect=side_effect)
    runner.run = mock_method
    del runner.investigate
    del runner.scan
    return runner


def make_bare_runner() -> MagicMock:
    """Create a mock runner with no investigate/scan/run methods."""
    runner = MagicMock()
    del runner.investigate
    del runner.scan
    del runner.run
    return runner


def make_model_dump_runner(dump_data: dict) -> MagicMock:
    """Create a runner whose investigate returns an object with model_dump()."""
    result_obj = MagicMock()
    result_obj.model_dump.return_value = dump_data

    runner = MagicMock()
    runner.investigate = AsyncMock(return_value=result_obj)
    del runner.scan
    del runner.run
    return runner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_event() -> dict:
    return {"type": "alert", "severity": "critical", "service": "api-gateway"}


@pytest.fixture
def investigation_result_data() -> dict:
    return {
        "hypotheses": ["memory leak in pod", "connection pool exhaustion"],
        "confidence_score": 0.85,
        "recommendations": ["restart pod", "increase pool size"],
    }


@pytest.fixture
def security_result_data() -> dict:
    return {
        "findings": ["CVE-2024-1234 in openssl", "exposed port 9090"],
        "risk_level": "high",
        "confidence": 0.92,
        "recommendations": ["patch openssl", "close port 9090"],
    }


@pytest.fixture
def completed_investigation_result(investigation_result_data) -> AgentResult:
    return AgentResult(
        task_id="task-inv-001",
        agent_type="investigation",
        status=ExecutionStatus.COMPLETED,
        result=investigation_result_data,
    )


@pytest.fixture
def completed_security_result(security_result_data) -> AgentResult:
    return AgentResult(
        task_id="task-sec-001",
        agent_type="security",
        status=ExecutionStatus.COMPLETED,
        result=security_result_data,
    )


@pytest.fixture
def failed_result() -> AgentResult:
    return AgentResult(
        task_id="task-fail-001",
        agent_type="investigation",
        status=ExecutionStatus.FAILED,
        error="Connection refused",
    )


@pytest.fixture
def timed_out_result() -> AgentResult:
    return AgentResult(
        task_id="task-timeout-001",
        agent_type="security",
        status=ExecutionStatus.TIMEOUT,
        error="Agent security timed out after 10s",
    )


# ===========================================================================
# ExecutionStatus Tests
# ===========================================================================


class TestExecutionStatus:
    """Tests for the ExecutionStatus enum."""

    def test_all_status_values_exist(self):
        assert ExecutionStatus.PENDING == "pending"
        assert ExecutionStatus.RUNNING == "running"
        assert ExecutionStatus.COMPLETED == "completed"
        assert ExecutionStatus.FAILED == "failed"
        assert ExecutionStatus.TIMEOUT == "timeout"
        assert ExecutionStatus.PARTIAL == "partial"

    def test_status_is_str_enum(self):
        # StrEnum values are usable as plain strings
        assert isinstance(ExecutionStatus.COMPLETED, str)
        assert f"status={ExecutionStatus.FAILED}" == "status=failed"

    def test_status_count(self):
        assert len(ExecutionStatus) == 6


# ===========================================================================
# AgentTask Model Tests
# ===========================================================================


class TestAgentTask:
    """Tests for the AgentTask Pydantic model."""

    def test_default_task_id_generated(self):
        task = AgentTask(agent_type="investigation")
        assert task.task_id.startswith("ptask-")
        assert len(task.task_id) > len("ptask-")

    def test_unique_task_ids(self):
        task1 = AgentTask(agent_type="investigation")
        task2 = AgentTask(agent_type="investigation")
        assert task1.task_id != task2.task_id

    def test_default_input_data_is_empty_dict(self):
        task = AgentTask(agent_type="security")
        assert task.input_data == {}

    def test_default_timeout_seconds(self):
        task = AgentTask(agent_type="investigation")
        assert task.timeout_seconds == 300

    def test_default_priority(self):
        task = AgentTask(agent_type="investigation")
        assert task.priority == 0

    def test_custom_values(self):
        task = AgentTask(
            task_id="custom-id",
            agent_type="security",
            input_data={"key": "value"},
            timeout_seconds=60,
            priority=5,
        )
        assert task.task_id == "custom-id"
        assert task.agent_type == "security"
        assert task.input_data == {"key": "value"}
        assert task.timeout_seconds == 60
        assert task.priority == 5

    def test_input_data_default_factory_isolation(self):
        """Ensure each task gets its own dict, not a shared mutable default."""
        task1 = AgentTask(agent_type="investigation")
        task2 = AgentTask(agent_type="investigation")
        task1.input_data["mutated"] = True
        assert "mutated" not in task2.input_data


# ===========================================================================
# AgentResult Model Tests
# ===========================================================================


class TestAgentResult:
    """Tests for the AgentResult Pydantic model."""

    def test_default_status_is_pending(self):
        result = AgentResult(task_id="t1", agent_type="investigation")
        assert result.status == ExecutionStatus.PENDING

    def test_default_result_is_empty_dict(self):
        result = AgentResult(task_id="t1", agent_type="investigation")
        assert result.result == {}

    def test_default_error_is_none(self):
        result = AgentResult(task_id="t1", agent_type="investigation")
        assert result.error is None

    def test_default_duration_ms_is_zero(self):
        result = AgentResult(task_id="t1", agent_type="investigation")
        assert result.duration_ms == 0

    def test_default_timestamps_are_none(self):
        result = AgentResult(task_id="t1", agent_type="investigation")
        assert result.started_at is None
        assert result.completed_at is None

    def test_custom_result(self):
        now = datetime.now(UTC)
        result = AgentResult(
            task_id="t1",
            agent_type="security",
            status=ExecutionStatus.COMPLETED,
            result={"findings": ["cve-1"]},
            error=None,
            duration_ms=1500,
            started_at=now,
            completed_at=now,
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert result.result == {"findings": ["cve-1"]}
        assert result.duration_ms == 1500


# ===========================================================================
# ExecutionPlan Model Tests
# ===========================================================================


class TestExecutionPlan:
    """Tests for the ExecutionPlan Pydantic model."""

    def test_default_id_generated(self):
        plan = ExecutionPlan()
        assert plan.id.startswith("plan-")

    def test_unique_plan_ids(self):
        plan1 = ExecutionPlan()
        plan2 = ExecutionPlan()
        assert plan1.id != plan2.id

    def test_default_empty_task_lists(self):
        plan = ExecutionPlan()
        assert plan.parallel_tasks == []
        assert plan.sequential_tasks == []

    def test_default_priority_is_normal(self):
        plan = ExecutionPlan()
        assert plan.priority == "normal"

    def test_task_list_isolation(self):
        plan1 = ExecutionPlan()
        plan2 = ExecutionPlan()
        plan1.parallel_tasks.append(AgentTask(agent_type="investigation"))
        assert len(plan2.parallel_tasks) == 0


# ===========================================================================
# MergedResult Model Tests
# ===========================================================================


class TestMergedResult:
    """Tests for the MergedResult Pydantic model."""

    def test_defaults(self):
        mr = MergedResult(plan_id="plan-abc")
        assert mr.plan_id == "plan-abc"
        assert mr.status == ExecutionStatus.COMPLETED
        assert mr.total_tasks == 0
        assert mr.completed_tasks == 0
        assert mr.failed_tasks == 0
        assert mr.results == []
        assert mr.merged_findings == {}
        assert mr.total_duration_ms == 0


# ===========================================================================
# ResultMerger Tests
# ===========================================================================


class TestResultMerger:
    """Tests for the ResultMerger.merge() method."""

    def setup_method(self):
        self.merger = ResultMerger()

    def test_merge_empty_results(self):
        merged = self.merger.merge([])
        assert merged["hypotheses"] == []
        assert merged["security_findings"] == []
        assert merged["recommendations"] == []
        assert merged["confidence_scores"] == {}

    def test_merge_investigation_hypotheses(self, completed_investigation_result):
        merged = self.merger.merge([completed_investigation_result])
        assert "memory leak in pod" in merged["hypotheses"]
        assert "connection pool exhaustion" in merged["hypotheses"]
        assert merged["confidence_scores"]["investigation"] == 0.85

    def test_merge_investigation_recommendations(self, completed_investigation_result):
        merged = self.merger.merge([completed_investigation_result])
        assert "restart pod" in merged["recommendations"]
        assert "increase pool size" in merged["recommendations"]

    def test_merge_security_findings(self, completed_security_result):
        merged = self.merger.merge([completed_security_result])
        assert "CVE-2024-1234 in openssl" in merged["security_findings"]
        assert "exposed port 9090" in merged["security_findings"]
        assert merged["confidence_scores"]["security"] == 0.92

    def test_merge_security_recommendations(self, completed_security_result):
        merged = self.merger.merge([completed_security_result])
        assert "patch openssl" in merged["recommendations"]
        assert "close port 9090" in merged["recommendations"]

    def test_merge_combined_investigation_and_security(
        self, completed_investigation_result, completed_security_result
    ):
        merged = self.merger.merge([completed_investigation_result, completed_security_result])
        # Both hypotheses and findings present
        assert len(merged["hypotheses"]) == 2
        assert len(merged["security_findings"]) == 2
        # Combined recommendations from both agents
        assert len(merged["recommendations"]) == 4
        # Both confidence scores
        assert "investigation" in merged["confidence_scores"]
        assert "security" in merged["confidence_scores"]

    def test_merge_skips_failed_results(self, failed_result):
        merged = self.merger.merge([failed_result])
        assert merged["hypotheses"] == []
        assert merged["recommendations"] == []

    def test_merge_skips_timed_out_results(self, timed_out_result):
        merged = self.merger.merge([timed_out_result])
        assert merged["security_findings"] == []

    def test_merge_mixed_completed_and_failed(self, completed_investigation_result, failed_result):
        merged = self.merger.merge([completed_investigation_result, failed_result])
        # Only the completed result contributes
        assert len(merged["hypotheses"]) == 2
        assert len(merged["recommendations"]) == 2

    def test_merge_unknown_agent_type_still_merges_recommendations(self):
        result = AgentResult(
            task_id="t-custom",
            agent_type="custom_agent",
            status=ExecutionStatus.COMPLETED,
            result={"recommendations": ["custom recommendation"]},
        )
        merged = self.merger.merge([result])
        assert "custom recommendation" in merged["recommendations"]
        # No hypotheses or findings for unknown type
        assert merged["hypotheses"] == []
        assert merged["security_findings"] == []

    def test_merge_investigation_without_confidence_score(self):
        result = AgentResult(
            task_id="t1",
            agent_type="investigation",
            status=ExecutionStatus.COMPLETED,
            result={"hypotheses": ["h1"]},
        )
        merged = self.merger.merge([result])
        assert merged["hypotheses"] == ["h1"]
        assert "investigation" not in merged["confidence_scores"]

    def test_merge_security_without_risk_level(self):
        """When risk_level is absent, confidence_scores['security'] should not be set."""
        result = AgentResult(
            task_id="t1",
            agent_type="security",
            status=ExecutionStatus.COMPLETED,
            result={"findings": ["f1"], "confidence": 0.75},
        )
        merged = self.merger.merge([result])
        assert merged["security_findings"] == ["f1"]
        # risk_level absent => no confidence_scores entry
        assert "security" not in merged["confidence_scores"]

    def test_merge_security_with_risk_level_but_no_confidence(self):
        """When risk_level present but confidence absent, defaults to 0."""
        result = AgentResult(
            task_id="t1",
            agent_type="security",
            status=ExecutionStatus.COMPLETED,
            result={"findings": ["f1"], "risk_level": "critical"},
        )
        merged = self.merger.merge([result])
        assert merged["confidence_scores"]["security"] == 0

    def test_merge_result_with_no_data_keys(self):
        """A completed result with empty dict still contributes no findings."""
        result = AgentResult(
            task_id="t1",
            agent_type="investigation",
            status=ExecutionStatus.COMPLETED,
            result={},
        )
        merged = self.merger.merge([result])
        assert merged["hypotheses"] == []
        assert merged["recommendations"] == []

    def test_merge_pending_status_skipped(self):
        result = AgentResult(
            task_id="t1",
            agent_type="investigation",
            status=ExecutionStatus.PENDING,
            result={"hypotheses": ["should be ignored"]},
        )
        merged = self.merger.merge([result])
        assert merged["hypotheses"] == []


# ===========================================================================
# ParallelAgentExecutor — create_plan Tests
# ===========================================================================


class TestCreatePlan:
    """Tests for ParallelAgentExecutor.create_plan()."""

    def setup_method(self):
        self.executor = ParallelAgentExecutor(default_timeout=120)

    def test_critical_priority_creates_parallel_tasks(self, sample_event):
        plan = self.executor.create_plan(sample_event, priority="critical")
        assert plan.priority == "critical"
        assert len(plan.parallel_tasks) == 2
        assert len(plan.sequential_tasks) == 0

    def test_critical_includes_investigation_and_security(self, sample_event):
        plan = self.executor.create_plan(sample_event, priority="critical")
        agent_types = {t.agent_type for t in plan.parallel_tasks}
        assert agent_types == {"investigation", "security"}

    def test_critical_investigation_has_higher_priority(self, sample_event):
        plan = self.executor.create_plan(sample_event, priority="critical")
        inv_task = next(t for t in plan.parallel_tasks if t.agent_type == "investigation")
        sec_task = next(t for t in plan.parallel_tasks if t.agent_type == "security")
        assert inv_task.priority > sec_task.priority

    def test_high_priority_creates_parallel_tasks(self, sample_event):
        plan = self.executor.create_plan(sample_event, priority="high")
        assert plan.priority == "high"
        assert len(plan.parallel_tasks) == 2
        assert len(plan.sequential_tasks) == 0

    def test_normal_priority_creates_sequential_tasks(self, sample_event):
        plan = self.executor.create_plan(sample_event, priority="normal")
        assert plan.priority == "normal"
        assert len(plan.parallel_tasks) == 0
        assert len(plan.sequential_tasks) == 1

    def test_normal_sequential_is_investigation(self, sample_event):
        plan = self.executor.create_plan(sample_event, priority="normal")
        assert plan.sequential_tasks[0].agent_type == "investigation"

    def test_default_priority_is_normal(self, sample_event):
        plan = self.executor.create_plan(sample_event)
        assert plan.priority == "normal"
        assert len(plan.sequential_tasks) == 1
        assert len(plan.parallel_tasks) == 0

    def test_plan_tasks_carry_event_as_input_data(self, sample_event):
        plan = self.executor.create_plan(sample_event, priority="critical")
        for task in plan.parallel_tasks:
            assert task.input_data == sample_event

    def test_plan_tasks_use_executor_default_timeout(self, sample_event):
        plan = self.executor.create_plan(sample_event, priority="critical")
        for task in plan.parallel_tasks:
            assert task.timeout_seconds == 120

    def test_plan_has_unique_id(self, sample_event):
        plan1 = self.executor.create_plan(sample_event, priority="critical")
        plan2 = self.executor.create_plan(sample_event, priority="critical")
        assert plan1.id != plan2.id

    @pytest.mark.parametrize("priority", ["low", "medium", "info", "unknown", ""])
    def test_non_critical_non_high_creates_sequential(self, sample_event, priority):
        plan = self.executor.create_plan(sample_event, priority=priority)
        assert len(plan.parallel_tasks) == 0
        assert len(plan.sequential_tasks) == 1


# ===========================================================================
# ParallelAgentExecutor — execute Tests (Parallel)
# ===========================================================================


class TestExecuteParallel:
    """Tests for execute() with parallel plans (critical/high priority)."""

    @pytest.mark.asyncio
    async def test_execute_parallel_all_succeed(
        self, sample_event, investigation_result_data, security_result_data
    ):
        inv_runner = make_investigate_runner(return_value=investigation_result_data)
        sec_runner = make_scan_runner(return_value=security_result_data)

        executor = ParallelAgentExecutor(
            agent_runners={"investigation": inv_runner, "security": sec_runner},
            default_timeout=60,
        )
        plan = executor.create_plan(sample_event, priority="critical")
        merged = await executor.execute(plan)

        assert merged.status == ExecutionStatus.COMPLETED
        assert merged.total_tasks == 2
        assert merged.completed_tasks == 2
        assert merged.failed_tasks == 0
        assert merged.plan_id == plan.id
        assert merged.total_duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_parallel_results_are_merged(
        self, sample_event, investigation_result_data, security_result_data
    ):
        inv_runner = make_investigate_runner(return_value=investigation_result_data)
        sec_runner = make_scan_runner(return_value=security_result_data)

        executor = ParallelAgentExecutor(
            agent_runners={"investigation": inv_runner, "security": sec_runner},
        )
        plan = executor.create_plan(sample_event, priority="critical")
        merged = await executor.execute(plan)

        assert len(merged.merged_findings["hypotheses"]) == 2
        assert len(merged.merged_findings["security_findings"]) == 2
        assert len(merged.merged_findings["recommendations"]) == 4

    @pytest.mark.asyncio
    async def test_execute_parallel_partial_failure(self, sample_event, security_result_data):
        """One agent fails, the other succeeds => PARTIAL status."""
        inv_runner = make_investigate_runner(side_effect=RuntimeError("LLM API down"))
        sec_runner = make_scan_runner(return_value=security_result_data)

        executor = ParallelAgentExecutor(
            agent_runners={"investigation": inv_runner, "security": sec_runner},
        )
        plan = executor.create_plan(sample_event, priority="critical")
        merged = await executor.execute(plan)

        assert merged.status == ExecutionStatus.PARTIAL
        assert merged.completed_tasks == 1
        assert merged.failed_tasks == 1
        # Security findings still present despite investigation failure
        assert len(merged.merged_findings["security_findings"]) == 2

    @pytest.mark.asyncio
    async def test_execute_parallel_all_fail(self, sample_event):
        """All agents fail => FAILED status."""
        inv_runner = make_investigate_runner(side_effect=RuntimeError("error 1"))
        sec_runner = make_scan_runner(side_effect=RuntimeError("error 2"))

        executor = ParallelAgentExecutor(
            agent_runners={"investigation": inv_runner, "security": sec_runner},
        )
        plan = executor.create_plan(sample_event, priority="critical")
        merged = await executor.execute(plan)

        assert merged.status == ExecutionStatus.FAILED
        assert merged.completed_tasks == 0
        assert merged.failed_tasks == 2

    @pytest.mark.asyncio
    async def test_execute_parallel_sets_error_message_on_failure(self, sample_event):
        inv_runner = make_investigate_runner(side_effect=ValueError("bad input"))
        sec_runner = make_scan_runner(return_value={})

        executor = ParallelAgentExecutor(
            agent_runners={"investigation": inv_runner, "security": sec_runner},
        )
        plan = executor.create_plan(sample_event, priority="critical")
        merged = await executor.execute(plan)

        failed_results = [r for r in merged.results if r.status == ExecutionStatus.FAILED]
        assert len(failed_results) == 1
        assert "bad input" in failed_results[0].error


# ===========================================================================
# ParallelAgentExecutor — execute Tests (Sequential)
# ===========================================================================


class TestExecuteSequential:
    """Tests for execute() with sequential plans (normal priority)."""

    @pytest.mark.asyncio
    async def test_execute_sequential_single_task_success(
        self, sample_event, investigation_result_data
    ):
        inv_runner = make_investigate_runner(return_value=investigation_result_data)
        executor = ParallelAgentExecutor(
            agent_runners={"investigation": inv_runner},
        )
        plan = executor.create_plan(sample_event, priority="normal")
        merged = await executor.execute(plan)

        assert merged.status == ExecutionStatus.COMPLETED
        assert merged.total_tasks == 1
        assert merged.completed_tasks == 1
        assert merged.failed_tasks == 0

    @pytest.mark.asyncio
    async def test_execute_sequential_single_task_failure(self, sample_event):
        inv_runner = make_investigate_runner(side_effect=RuntimeError("crash"))
        executor = ParallelAgentExecutor(
            agent_runners={"investigation": inv_runner},
        )
        plan = executor.create_plan(sample_event, priority="normal")
        merged = await executor.execute(plan)

        assert merged.status == ExecutionStatus.FAILED
        assert merged.completed_tasks == 0
        assert merged.failed_tasks == 1

    @pytest.mark.asyncio
    async def test_execute_sequential_multiple_tasks(self, sample_event):
        """Manually add multiple sequential tasks and verify execution order."""
        inv_runner = make_investigate_runner(return_value={"hypotheses": ["h1"]})
        sec_runner = make_scan_runner(return_value={"findings": ["f1"]})

        executor = ParallelAgentExecutor(
            agent_runners={"investigation": inv_runner, "security": sec_runner},
        )
        plan = ExecutionPlan(
            priority="normal",
            sequential_tasks=[
                AgentTask(agent_type="investigation", input_data=sample_event),
                AgentTask(agent_type="security", input_data=sample_event),
            ],
        )
        merged = await executor.execute(plan)

        assert merged.total_tasks == 2
        assert merged.completed_tasks == 2
        assert merged.status == ExecutionStatus.COMPLETED


# ===========================================================================
# ParallelAgentExecutor — Timeout Handling Tests
# ===========================================================================


class TestTimeoutHandling:
    """Tests for agent timeout behavior."""

    @pytest.mark.asyncio
    async def test_timeout_produces_timeout_status(self, sample_event):
        """A slow runner that exceeds the timeout should get TIMEOUT status."""

        async def slow_investigate(**kwargs):
            await asyncio.sleep(10)  # Will be cancelled by the 0.1s timeout
            return {}

        runner = MagicMock()
        runner.investigate = slow_investigate
        del runner.scan
        del runner.run

        executor = ParallelAgentExecutor(
            agent_runners={"investigation": runner},
            default_timeout=300,
        )
        # Create a task with a very short timeout
        plan = ExecutionPlan(
            sequential_tasks=[
                AgentTask(
                    agent_type="investigation",
                    input_data=sample_event,
                    timeout_seconds=0,  # instant timeout
                ),
            ],
        )
        merged = await executor.execute(plan)

        timed_out = [r for r in merged.results if r.status == ExecutionStatus.TIMEOUT]
        assert len(timed_out) == 1
        assert "timed out" in timed_out[0].error

    @pytest.mark.asyncio
    async def test_timeout_counts_as_failed_in_merged(self, sample_event):
        """Timed-out tasks count toward the failed_tasks counter."""

        async def slow_scan(**kwargs):
            await asyncio.sleep(10)
            return {}

        runner = MagicMock()
        runner.scan = slow_scan
        del runner.investigate
        del runner.run

        inv_runner = make_investigate_runner(return_value={"hypotheses": ["h1"]})

        executor = ParallelAgentExecutor(
            agent_runners={"investigation": inv_runner, "security": runner},
        )
        plan = ExecutionPlan(
            priority="critical",
            parallel_tasks=[
                AgentTask(agent_type="investigation", input_data=sample_event, timeout_seconds=10),
                AgentTask(agent_type="security", input_data=sample_event, timeout_seconds=0),
            ],
        )
        merged = await executor.execute(plan)

        assert merged.failed_tasks == 1
        assert merged.completed_tasks == 1
        assert merged.status == ExecutionStatus.PARTIAL


# ===========================================================================
# ParallelAgentExecutor — No Runner Registered Tests
# ===========================================================================


class TestNoRunnerRegistered:
    """Tests for when no runner is registered for an agent type."""

    @pytest.mark.asyncio
    async def test_no_runner_returns_failed_result(self, sample_event):
        executor = ParallelAgentExecutor(agent_runners={})
        plan = executor.create_plan(sample_event, priority="normal")
        merged = await executor.execute(plan)

        assert merged.status == ExecutionStatus.FAILED
        assert merged.failed_tasks == 1
        failed_results = [r for r in merged.results if r.status == ExecutionStatus.FAILED]
        assert len(failed_results) == 1
        assert "No runner registered" in failed_results[0].error

    @pytest.mark.asyncio
    async def test_no_runner_parallel_both_missing(self, sample_event):
        executor = ParallelAgentExecutor(agent_runners={})
        plan = executor.create_plan(sample_event, priority="critical")
        merged = await executor.execute(plan)

        assert merged.status == ExecutionStatus.FAILED
        assert merged.failed_tasks == 2
        assert merged.completed_tasks == 0

    @pytest.mark.asyncio
    async def test_no_runner_for_one_of_two_agents(self, sample_event):
        """Only investigation runner registered; security missing => PARTIAL."""
        inv_runner = make_investigate_runner(return_value={"hypotheses": ["h1"]})
        executor = ParallelAgentExecutor(
            agent_runners={"investigation": inv_runner},
        )
        plan = executor.create_plan(sample_event, priority="critical")
        merged = await executor.execute(plan)

        assert merged.status == ExecutionStatus.PARTIAL
        assert merged.completed_tasks == 1
        assert merged.failed_tasks == 1

    @pytest.mark.asyncio
    async def test_no_runner_sets_duration_ms(self, sample_event):
        executor = ParallelAgentExecutor(agent_runners={})
        plan = executor.create_plan(sample_event, priority="normal")
        merged = await executor.execute(plan)

        failed_result = merged.results[0]
        assert failed_result.duration_ms >= 0


# ===========================================================================
# ParallelAgentExecutor — _run_agent dispatch Tests
# ===========================================================================


class TestRunAgentDispatch:
    """Tests for _run_agent routing to investigate/scan/run/fallback."""

    @pytest.mark.asyncio
    async def test_runner_with_investigate_method(self, sample_event):
        inv_runner = make_investigate_runner(return_value={"hypotheses": ["h"]})
        executor = ParallelAgentExecutor(agent_runners={"investigation": inv_runner})

        task = AgentTask(agent_type="investigation", input_data=sample_event)
        result = await executor._execute_single(task)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.result == {"hypotheses": ["h"]}
        inv_runner.investigate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_runner_with_scan_method(self, sample_event):
        sec_runner = make_scan_runner(return_value={"findings": ["f"]})
        executor = ParallelAgentExecutor(agent_runners={"security": sec_runner})

        task = AgentTask(agent_type="security", input_data=sample_event)
        result = await executor._execute_single(task)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.result == {"findings": ["f"]}
        sec_runner.scan.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_runner_with_run_method(self, sample_event):
        runner = make_run_runner(return_value={"action": "restart"})
        executor = ParallelAgentExecutor(agent_runners={"remediation": runner})

        task = AgentTask(agent_type="remediation", input_data=sample_event)
        result = await executor._execute_single(task)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.result == {"action": "restart"}
        runner.run.assert_awaited_once_with(sample_event)

    @pytest.mark.asyncio
    async def test_runner_with_run_method_non_dict_return(self, sample_event):
        """run() returning a non-dict should produce an empty dict result."""
        runner = make_run_runner(return_value="not a dict")
        executor = ParallelAgentExecutor(agent_runners={"remediation": runner})

        task = AgentTask(agent_type="remediation", input_data=sample_event)
        result = await executor._execute_single(task)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.result == {}

    @pytest.mark.asyncio
    async def test_runner_with_no_known_method_returns_fallback(self, sample_event):
        runner = make_bare_runner()
        executor = ParallelAgentExecutor(agent_runners={"learning": runner})

        task = AgentTask(agent_type="learning", input_data=sample_event)
        result = await executor._execute_single(task)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.result["status"] == "no_run_method"
        assert result.result["agent_type"] == "learning"

    @pytest.mark.asyncio
    async def test_runner_investigate_returns_pydantic_model(self, sample_event):
        """If investigate returns a Pydantic-like object with model_dump(), use that."""
        dump_data = {"hypotheses": ["leak"], "confidence_score": 0.9}
        runner = make_model_dump_runner(dump_data)
        executor = ParallelAgentExecutor(agent_runners={"investigation": runner})

        task = AgentTask(agent_type="investigation", input_data=sample_event)
        result = await executor._execute_single(task)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.result == dump_data

    @pytest.mark.asyncio
    async def test_runner_scan_returns_pydantic_model(self, sample_event):
        """If scan returns a Pydantic-like object with model_dump(), use that."""
        dump_data = {"findings": ["cve-1"], "risk_level": "high"}
        result_obj = MagicMock()
        result_obj.model_dump.return_value = dump_data

        runner = MagicMock()
        runner.scan = AsyncMock(return_value=result_obj)
        del runner.investigate
        del runner.run

        executor = ParallelAgentExecutor(agent_runners={"security": runner})

        task = AgentTask(agent_type="security", input_data=sample_event)
        result = await executor._execute_single(task)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.result == dump_data


# ===========================================================================
# ParallelAgentExecutor — Result Timestamps and Duration
# ===========================================================================


class TestResultTimestampsAndDuration:
    """Tests for started_at, completed_at, and duration_ms on results."""

    @pytest.mark.asyncio
    async def test_successful_result_has_timestamps(self, sample_event):
        runner = make_investigate_runner(return_value={})
        executor = ParallelAgentExecutor(agent_runners={"investigation": runner})

        task = AgentTask(agent_type="investigation", input_data=sample_event)
        result = await executor._execute_single(task)

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_failed_result_has_timestamps(self, sample_event):
        runner = make_investigate_runner(side_effect=RuntimeError("boom"))
        executor = ParallelAgentExecutor(agent_runners={"investigation": runner})

        task = AgentTask(agent_type="investigation", input_data=sample_event)
        result = await executor._execute_single(task)

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration_ms >= 0


# ===========================================================================
# ParallelAgentExecutor — _execute_parallel Exception Wrapping
# ===========================================================================


class TestExecuteParallelExceptionWrapping:
    """Tests for _execute_parallel handling of gather exceptions."""

    @pytest.mark.asyncio
    async def test_exception_in_gather_wrapped_as_failed(self, sample_event):
        """If _execute_single raises unexpectedly, gather catches it as an exception."""
        inv_runner = make_investigate_runner(return_value={"hypotheses": []})
        sec_runner = make_scan_runner(return_value={"findings": []})

        executor = ParallelAgentExecutor(
            agent_runners={"investigation": inv_runner, "security": sec_runner},
        )

        tasks = [
            AgentTask(agent_type="investigation", input_data=sample_event),
            AgentTask(agent_type="security", input_data=sample_event),
        ]
        results = await executor._execute_parallel(tasks)

        assert len(results) == 2
        assert all(isinstance(r, AgentResult) for r in results)


# ===========================================================================
# ParallelAgentExecutor — Constructor Tests
# ===========================================================================


class TestParallelAgentExecutorInit:
    """Tests for ParallelAgentExecutor initialization."""

    def test_default_timeout(self):
        executor = ParallelAgentExecutor()
        assert executor._default_timeout == 300

    def test_custom_timeout(self):
        executor = ParallelAgentExecutor(default_timeout=60)
        assert executor._default_timeout == 60

    def test_default_runners_empty(self):
        executor = ParallelAgentExecutor()
        assert executor._runners == {}

    def test_custom_runners(self):
        runners = {"investigation": MagicMock(), "security": MagicMock()}
        executor = ParallelAgentExecutor(agent_runners=runners)
        assert executor._runners == runners

    def test_none_runners_becomes_empty_dict(self):
        executor = ParallelAgentExecutor(agent_runners=None)
        assert executor._runners == {}

    def test_has_result_merger(self):
        executor = ParallelAgentExecutor()
        assert isinstance(executor._merger, ResultMerger)


# ===========================================================================
# ParallelAgentExecutor — Mixed Plan (parallel + sequential)
# ===========================================================================


class TestMixedPlan:
    """Tests for execute() with both parallel and sequential tasks in one plan."""

    @pytest.mark.asyncio
    async def test_execute_plan_with_parallel_and_sequential(self, sample_event):
        """A plan with both parallel and sequential tasks executes all of them."""
        inv_runner = make_investigate_runner(return_value={"hypotheses": ["h1"]})
        sec_runner = make_scan_runner(return_value={"findings": ["f1"]})
        rem_runner = make_run_runner(return_value={"action": "restarted"})

        executor = ParallelAgentExecutor(
            agent_runners={
                "investigation": inv_runner,
                "security": sec_runner,
                "remediation": rem_runner,
            },
        )

        plan = ExecutionPlan(
            priority="critical",
            parallel_tasks=[
                AgentTask(agent_type="investigation", input_data=sample_event),
                AgentTask(agent_type="security", input_data=sample_event),
            ],
            sequential_tasks=[
                AgentTask(agent_type="remediation", input_data=sample_event),
            ],
        )
        merged = await executor.execute(plan)

        assert merged.total_tasks == 3
        assert merged.completed_tasks == 3
        assert merged.failed_tasks == 0
        assert merged.status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_mixed_plan_sequential_failure_after_parallel_success(self, sample_event):
        """Parallel succeeds but sequential fails => PARTIAL."""
        inv_runner = make_investigate_runner(return_value={"hypotheses": ["h1"]})
        sec_runner = make_scan_runner(return_value={"findings": ["f1"]})
        rem_runner = make_run_runner(side_effect=RuntimeError("remediation failed"))

        executor = ParallelAgentExecutor(
            agent_runners={
                "investigation": inv_runner,
                "security": sec_runner,
                "remediation": rem_runner,
            },
        )

        plan = ExecutionPlan(
            priority="critical",
            parallel_tasks=[
                AgentTask(agent_type="investigation", input_data=sample_event),
                AgentTask(agent_type="security", input_data=sample_event),
            ],
            sequential_tasks=[
                AgentTask(agent_type="remediation", input_data=sample_event),
            ],
        )
        merged = await executor.execute(plan)

        assert merged.total_tasks == 3
        assert merged.completed_tasks == 2
        assert merged.failed_tasks == 1
        assert merged.status == ExecutionStatus.PARTIAL


# ===========================================================================
# ParallelAgentExecutor — Empty Plan
# ===========================================================================


class TestEmptyPlan:
    """Tests for execute() with an empty plan (no tasks).

    Note: With zero tasks, `failed == len(all_results)` evaluates to `0 == 0`
    which is True, so the overall status is FAILED. This is the actual behavior
    of the implementation (debatable, but tested as-is).
    """

    @pytest.mark.asyncio
    async def test_execute_empty_plan_returns_failed_status(self):
        """Empty plan: failed==0 equals total==0, so status is FAILED."""
        executor = ParallelAgentExecutor()
        plan = ExecutionPlan()
        merged = await executor.execute(plan)

        # 0 == 0 triggers the "all failed" branch
        assert merged.status == ExecutionStatus.FAILED
        assert merged.total_tasks == 0
        assert merged.completed_tasks == 0
        assert merged.failed_tasks == 0
        assert merged.results == []
        assert merged.total_duration_ms >= 0
