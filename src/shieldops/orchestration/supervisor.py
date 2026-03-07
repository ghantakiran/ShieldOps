"""Supervisor agent — coordinates agent execution and escalation."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from shieldops.orchestration.models import (
    EscalationPolicy,
    WorkflowRun,
    WorkflowStatus,
)
from shieldops.orchestration.workflow_engine import WorkflowEngine

logger = structlog.get_logger()

MAX_CONCURRENT_RUNS = 10

# Default escalation policies keyed by severity
DEFAULT_POLICIES: dict[str, EscalationPolicy] = {
    "critical": EscalationPolicy(
        severity="critical",
        auto_remediate=True,
        notify_channels=["slack", "pagerduty"],
        page_oncall=True,
        max_retries=1,
    ),
    "high": EscalationPolicy(
        severity="high",
        auto_remediate=True,
        notify_channels=["slack"],
        page_oncall=True,
        max_retries=2,
    ),
    "medium": EscalationPolicy(
        severity="medium",
        auto_remediate=False,
        notify_channels=["slack"],
        page_oncall=False,
        max_retries=3,
    ),
    "low": EscalationPolicy(
        severity="low",
        auto_remediate=False,
        notify_channels=["email"],
        page_oncall=False,
        max_retries=3,
    ),
}


class SupervisorAgent:
    """Coordinates multi-agent workflows with escalation policies."""

    def __init__(
        self,
        engine: WorkflowEngine | None = None,
        policies: dict[str, EscalationPolicy] | None = None,
    ) -> None:
        self._engine = engine or WorkflowEngine()
        self._policies = policies or dict(DEFAULT_POLICIES)
        self._active_runs: dict[str, WorkflowRun] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Alert handling
    # ------------------------------------------------------------------

    async def handle_alert(
        self,
        alert_name: str,
        namespace: str,
        severity: str,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Entry point for alert-triggered workflows.

        Selects the appropriate workflow and escalation policy based
        on severity, then executes the workflow.
        """
        async with self._lock:
            if len(self._active_runs) >= MAX_CONCURRENT_RUNS:
                raise RuntimeError(f"Max concurrent runs ({MAX_CONCURRENT_RUNS}) reached")

        policy = self._policies.get(severity, DEFAULT_POLICIES["medium"])

        params: dict[str, Any] = {
            "alert_name": alert_name,
            "namespace": namespace,
            "severity": severity,
            "auto_remediate": policy.auto_remediate,
            "notify_channels": policy.notify_channels,
            **(metadata or {}),
        }

        logger.info(
            "supervisor_handling_alert",
            alert_name=alert_name,
            namespace=namespace,
            severity=severity,
            auto_remediate=policy.auto_remediate,
            page_oncall=policy.page_oncall,
        )

        workflow_name = self._select_workflow(severity)
        run = await self._execute_with_retries(
            workflow_name=workflow_name,
            trigger="alert",
            params=params,
            max_retries=policy.max_retries,
        )

        if policy.page_oncall and run.status == WorkflowStatus.FAILED:
            logger.warning(
                "paging_oncall",
                alert_name=alert_name,
                run_id=run.run_id,
            )

        return run

    # ------------------------------------------------------------------
    # Run management
    # ------------------------------------------------------------------

    async def get_active_runs(self) -> list[WorkflowRun]:
        """Return all currently tracked workflow runs."""
        return list(self._active_runs.values())

    async def cancel_run(self, run_id: str) -> bool:
        """Cancel an active workflow run by its ID."""
        run = self._active_runs.get(run_id)
        if run is None:
            return False
        run.status = WorkflowStatus.CANCELLED
        logger.info("workflow_run_cancelled", run_id=run_id)
        return True

    def get_policies(self) -> list[EscalationPolicy]:
        """Return all configured escalation policies."""
        return list(self._policies.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _select_workflow(severity: str) -> str:
        """Choose the workflow based on severity."""
        if severity in ("critical", "high"):
            return "incident_response"
        return "proactive_check"

    async def _execute_with_retries(
        self,
        workflow_name: str,
        trigger: str,
        params: dict[str, Any],
        max_retries: int,
    ) -> WorkflowRun:
        """Execute a workflow with retry logic on failure."""
        last_run: WorkflowRun | None = None

        for attempt in range(1, max_retries + 1):
            run = await self._engine.execute_workflow(
                workflow_name=workflow_name,
                trigger=trigger,
                params={**params, "_attempt": attempt},
            )

            async with self._lock:
                self._active_runs[run.run_id] = run

            last_run = run

            if run.status == WorkflowStatus.COMPLETED:
                logger.info(
                    "workflow_succeeded",
                    run_id=run.run_id,
                    attempt=attempt,
                )
                return run

            logger.warning(
                "workflow_attempt_failed",
                run_id=run.run_id,
                attempt=attempt,
                max_retries=max_retries,
            )

        # All retries exhausted — return last run
        assert last_run is not None  # noqa: S101
        return last_run
