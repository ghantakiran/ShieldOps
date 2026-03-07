"""Workflow engine — manages workflow definitions and async execution."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.orchestration.models import (
    AgentType,
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Workflow step definitions for built-in workflows
# ---------------------------------------------------------------------------

_INCIDENT_RESPONSE_STEPS: list[dict[str, Any]] = [
    {
        "agent_type": AgentType.INVESTIGATION,
        "action": "investigate",
    },
    {
        "agent_type": AgentType.INVESTIGATION,
        "action": "recommend",
    },
    {
        "agent_type": AgentType.REMEDIATION,
        "action": "remediate",
        "condition": "investigation_confidence_gt_0_7",
    },
    {
        "agent_type": AgentType.INVESTIGATION,
        "action": "verify",
    },
    {
        "agent_type": AgentType.LEARNING,
        "action": "notify",
    },
]

_SECURITY_SCAN_STEPS: list[dict[str, Any]] = [
    {"agent_type": AgentType.SECURITY, "action": "scan_cve"},
    {"agent_type": AgentType.SECURITY, "action": "scan_secrets"},
    {"agent_type": AgentType.SECURITY, "action": "scan_certs"},
    {"agent_type": AgentType.SECURITY, "action": "aggregate"},
    {"agent_type": AgentType.LEARNING, "action": "notify"},
]

_PROACTIVE_CHECK_STEPS: list[dict[str, Any]] = [
    {"agent_type": AgentType.INVESTIGATION, "action": "check_resources"},
    {"agent_type": AgentType.SECURITY, "action": "check_certificates"},
    {"agent_type": AgentType.INVESTIGATION, "action": "check_slos"},
    {"agent_type": AgentType.LEARNING, "action": "report"},
]

BUILTIN_WORKFLOWS: dict[str, list[dict[str, Any]]] = {
    "incident_response": _INCIDENT_RESPONSE_STEPS,
    "security_scan": _SECURITY_SCAN_STEPS,
    "proactive_check": _PROACTIVE_CHECK_STEPS,
}


class WorkflowEngine:
    """Manages workflow definitions and executes them step-by-step."""

    def __init__(
        self,
        agent_runners: dict[str, Any] | None = None,
    ) -> None:
        self._runners: dict[str, Any] = agent_runners or {}
        self._custom_workflows: dict[str, list[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def register_workflow(
        self,
        name: str,
        steps: list[dict[str, Any]],
    ) -> None:
        """Register a custom workflow definition."""
        self._custom_workflows[name] = steps
        logger.info("workflow_registered", workflow_name=name)

    def list_workflows(self) -> list[str]:
        """Return names of all available workflows."""
        return sorted(set(BUILTIN_WORKFLOWS) | set(self._custom_workflows))

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute_workflow(
        self,
        workflow_name: str,
        trigger: str,
        params: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Execute a named workflow and return the completed run."""
        step_defs = self._custom_workflows.get(
            workflow_name,
            BUILTIN_WORKFLOWS.get(workflow_name),
        )
        if step_defs is None:
            raise ValueError(f"Unknown workflow: {workflow_name}")

        run = WorkflowRun(
            workflow_name=workflow_name,
            trigger=trigger,
            metadata=params or {},
        )
        run.status = WorkflowStatus.RUNNING
        run.steps = self._build_steps(step_defs, params)

        logger.info(
            "workflow_started",
            run_id=run.run_id,
            workflow=workflow_name,
            trigger=trigger,
            step_count=len(run.steps),
        )

        accumulated: dict[str, Any] = dict(params or {})

        for step in run.steps:
            if run.status == WorkflowStatus.CANCELLED:
                break

            # Evaluate conditions
            if not self._evaluate_condition(step, accumulated):
                step.status = WorkflowStatus.COMPLETED
                step.result = {"skipped": True, "reason": "condition_not_met"}
                logger.info(
                    "workflow_step_skipped",
                    run_id=run.run_id,
                    step_id=step.step_id,
                    action=step.action,
                )
                continue

            step.status = WorkflowStatus.RUNNING
            step.started_at = datetime.now(UTC)

            try:
                result = await self._execute_step(step, accumulated)
                step.status = WorkflowStatus.COMPLETED
                step.result = result
                step.completed_at = datetime.now(UTC)
                accumulated[step.action] = result

                logger.info(
                    "workflow_step_completed",
                    run_id=run.run_id,
                    step_id=step.step_id,
                    action=step.action,
                    agent_type=step.agent_type,
                )

            except Exception as exc:
                step.status = WorkflowStatus.FAILED
                step.error = str(exc)
                step.completed_at = datetime.now(UTC)
                run.status = WorkflowStatus.FAILED
                run.completed_at = datetime.now(UTC)

                logger.error(
                    "workflow_step_failed",
                    run_id=run.run_id,
                    step_id=step.step_id,
                    action=step.action,
                    error=str(exc),
                )
                return run

        if run.status != WorkflowStatus.CANCELLED:
            run.status = WorkflowStatus.COMPLETED
        run.completed_at = datetime.now(UTC)

        logger.info(
            "workflow_completed",
            run_id=run.run_id,
            workflow=workflow_name,
            status=run.status,
        )
        return run

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_steps(
        step_defs: list[dict[str, Any]],
        params: dict[str, Any] | None,
    ) -> list[WorkflowStep]:
        """Construct WorkflowStep instances from definitions."""
        steps: list[WorkflowStep] = []
        for defn in step_defs:
            merged_params = dict(params or {})
            merged_params.update(defn.get("parameters", {}))
            step = WorkflowStep(
                agent_type=AgentType(defn["agent_type"]),
                action=defn["action"],
                parameters=merged_params,
            )
            # Stash condition for later evaluation
            if "condition" in defn:
                step.parameters["_condition"] = defn["condition"]
            steps.append(step)
        return steps

    @staticmethod
    def _evaluate_condition(
        step: WorkflowStep,
        accumulated: dict[str, Any],
    ) -> bool:
        """Evaluate whether a conditional step should execute."""
        condition = step.parameters.pop("_condition", None)
        if condition is None:
            return True

        if condition == "investigation_confidence_gt_0_7":
            investigate_result = accumulated.get("investigate", {})
            confidence = investigate_result.get(
                "confidence", investigate_result.get("confidence_score", 0)
            )
            return float(confidence) > 0.7

        # Unknown conditions default to True
        return True

    async def _execute_step(
        self,
        step: WorkflowStep,
        accumulated: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch a single step to the appropriate agent runner."""
        runner = self._runners.get(step.agent_type)
        if runner is None:
            logger.warning(
                "no_runner_for_agent",
                agent_type=step.agent_type,
                action=step.action,
            )
            return {"status": "no_runner", "agent_type": step.agent_type}

        method = getattr(runner, step.action, None)
        if method is None:
            method = getattr(runner, "run", None)

        if method is None:
            return {
                "status": "no_method",
                "agent_type": step.agent_type,
                "action": step.action,
            }

        result = await method(**step.parameters, _accumulated=accumulated)
        if hasattr(result, "model_dump"):
            return dict(result.model_dump())
        return result if isinstance(result, dict) else {"result": result}
