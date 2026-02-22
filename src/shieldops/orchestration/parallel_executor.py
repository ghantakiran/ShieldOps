"""Parallel agent executor — runs multiple agents concurrently for P1 incidents.

Enables the Supervisor to dispatch Investigation + Security agents in parallel,
reducing time-to-resolution for critical incidents.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PARTIAL = "partial"


class AgentTask(BaseModel):
    """A task to be executed by a specific agent."""

    task_id: str = Field(default_factory=lambda: f"ptask-{uuid4().hex[:12]}")
    agent_type: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 300
    priority: int = 0  # Higher = more important


class AgentResult(BaseModel):
    """Result from a single agent execution."""

    task_id: str
    agent_type: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionPlan(BaseModel):
    """Plan defining which agents run in parallel vs sequential."""

    id: str = Field(default_factory=lambda: f"plan-{uuid4().hex[:12]}")
    parallel_tasks: list[AgentTask] = Field(default_factory=list)
    sequential_tasks: list[AgentTask] = Field(default_factory=list)
    priority: str = "normal"  # normal, high, critical


class MergedResult(BaseModel):
    """Combined results from parallel agent execution."""

    plan_id: str
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    results: list[AgentResult] = Field(default_factory=list)
    merged_findings: dict[str, Any] = Field(default_factory=dict)
    total_duration_ms: int = 0


class ResultMerger:
    """Combines results from parallel agent executions."""

    def merge(self, results: list[AgentResult]) -> dict[str, Any]:
        """Merge findings from multiple agent results into a unified view."""
        merged: dict[str, Any] = {
            "hypotheses": [],
            "security_findings": [],
            "recommendations": [],
            "confidence_scores": {},
        }

        for result in results:
            if result.status != ExecutionStatus.COMPLETED:
                continue

            data = result.result

            # Merge investigation hypotheses
            if result.agent_type == "investigation":
                merged["hypotheses"].extend(data.get("hypotheses", []))
                if "confidence_score" in data:
                    merged["confidence_scores"]["investigation"] = data["confidence_score"]

            # Merge security findings
            elif result.agent_type == "security":
                merged["security_findings"].extend(data.get("findings", []))
                if "risk_level" in data:
                    merged["confidence_scores"]["security"] = data.get("confidence", 0)

            # Generic merge for other agent types
            merged["recommendations"].extend(data.get("recommendations", []))

        return merged


class ParallelAgentExecutor:
    """Executes multiple agents in parallel with per-agent timeouts.

    Supports partial failure: if one agent fails, others' results are still used.
    """

    def __init__(
        self,
        agent_runners: dict[str, Any] | None = None,
        default_timeout: int = 300,
    ) -> None:
        self._runners = agent_runners or {}
        self._default_timeout = default_timeout
        self._merger = ResultMerger()

    def create_plan(
        self,
        event: dict[str, Any],
        priority: str = "normal",
    ) -> ExecutionPlan:
        """Create an execution plan based on event priority.

        For critical/high priority: Investigation + Security run in parallel.
        For normal: Sequential execution as usual.
        """
        plan = ExecutionPlan(priority=priority)

        if priority in ("critical", "high"):
            # Parallel: investigation + security
            plan.parallel_tasks = [
                AgentTask(
                    agent_type="investigation",
                    input_data=event,
                    timeout_seconds=self._default_timeout,
                    priority=2,
                ),
                AgentTask(
                    agent_type="security",
                    input_data=event,
                    timeout_seconds=self._default_timeout,
                    priority=1,
                ),
            ]
        else:
            plan.sequential_tasks = [
                AgentTask(
                    agent_type="investigation",
                    input_data=event,
                    timeout_seconds=self._default_timeout,
                ),
            ]

        return plan

    async def execute(self, plan: ExecutionPlan) -> MergedResult:
        """Execute an agent plan (parallel + sequential tasks)."""
        start = datetime.now(UTC)
        all_results: list[AgentResult] = []

        # Execute parallel tasks
        if plan.parallel_tasks:
            parallel_results = await self._execute_parallel(plan.parallel_tasks)
            all_results.extend(parallel_results)

        # Execute sequential tasks
        for task in plan.sequential_tasks:
            result = await self._execute_single(task)
            all_results.append(result)

        # Merge results
        completed = sum(1 for r in all_results if r.status == ExecutionStatus.COMPLETED)
        failed = sum(
            1 for r in all_results if r.status in (ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT)
        )

        merged_findings = self._merger.merge(all_results)

        overall_status = ExecutionStatus.COMPLETED
        if failed == len(all_results):
            overall_status = ExecutionStatus.FAILED
        elif failed > 0:
            overall_status = ExecutionStatus.PARTIAL

        duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)

        return MergedResult(
            plan_id=plan.id,
            status=overall_status,
            total_tasks=len(all_results),
            completed_tasks=completed,
            failed_tasks=failed,
            results=all_results,
            merged_findings=merged_findings,
            total_duration_ms=duration_ms,
        )

    async def _execute_parallel(self, tasks: list[AgentTask]) -> list[AgentResult]:
        """Execute multiple agent tasks concurrently."""
        coros = [self._execute_single(task) for task in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        agent_results: list[AgentResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                agent_results.append(
                    AgentResult(
                        task_id=tasks[i].task_id,
                        agent_type=tasks[i].agent_type,
                        status=ExecutionStatus.FAILED,
                        error=str(result),
                    )
                )
            else:
                agent_results.append(result)  # type: ignore[arg-type]

        return agent_results

    async def _execute_single(self, task: AgentTask) -> AgentResult:
        """Execute a single agent task with timeout."""
        started_at = datetime.now(UTC)
        result = AgentResult(
            task_id=task.task_id,
            agent_type=task.agent_type,
            started_at=started_at,
        )

        runner = self._runners.get(task.agent_type)
        if runner is None:
            result.status = ExecutionStatus.FAILED
            result.error = f"No runner registered for agent type: {task.agent_type}"
            result.duration_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
            return result

        try:
            # Execute with timeout
            coro = self._run_agent(runner, task)
            agent_output = await asyncio.wait_for(coro, timeout=task.timeout_seconds)

            result.status = ExecutionStatus.COMPLETED
            result.result = agent_output if isinstance(agent_output, dict) else {}

        except TimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error = f"Agent {task.agent_type} timed out after {task.timeout_seconds}s"
            logger.warning(
                "agent_execution_timeout",
                agent_type=task.agent_type,
                timeout=task.timeout_seconds,
            )

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            logger.error(
                "agent_execution_failed",
                agent_type=task.agent_type,
                error=str(e),
            )

        result.completed_at = datetime.now(UTC)
        result.duration_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)

        logger.info(
            "agent_execution_complete",
            task_id=task.task_id,
            agent_type=task.agent_type,
            status=result.status,
            duration_ms=result.duration_ms,
        )

        return result

    async def _run_agent(self, runner: Any, task: AgentTask) -> dict[str, Any]:
        """Run an agent and return results as a dict."""
        # Agents have different run methods; try common patterns
        if hasattr(runner, "investigate"):
            result = await runner.investigate(**task.input_data)
            return dict(result.model_dump() if hasattr(result, "model_dump") else result)
        elif hasattr(runner, "scan"):
            result = await runner.scan(**task.input_data)
            return dict(result.model_dump() if hasattr(result, "model_dump") else result)
        elif hasattr(runner, "run"):
            result = await runner.run(task.input_data)
            return result if isinstance(result, dict) else {}
        else:
            return {"status": "no_run_method", "agent_type": task.agent_type}
