"""Remediation Agent runner — entry point for executing remediations.

Takes a RemediationAction, constructs the LangGraph, runs it end-to-end,
and returns the completed remediation state.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.remediation.graph import create_remediation_graph
from shieldops.agents.remediation.models import RemediationState
from shieldops.agents.remediation.nodes import set_toolkit
from shieldops.agents.remediation.tools import RemediationToolkit
from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import (
    ActionResult,
    AlertContext,
    AuditEntry,
    ExecutionStatus,
    RemediationAction,
)
from shieldops.policy.approval.workflow import ApprovalWorkflow
from shieldops.policy.opa.client import PolicyEngine
from shieldops.policy.rollback.manager import RollbackManager

if __import__("typing").TYPE_CHECKING:
    from shieldops.db.repository import Repository

logger = structlog.get_logger()


class RemediationRunner:
    """Runs remediation agent workflows.

    Usage:
        runner = RemediationRunner(
            connector_router=router,
            policy_engine=policy,
            approval_workflow=workflow,
        )
        result = await runner.remediate(action, alert_context)
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        policy_engine: PolicyEngine | None = None,
        approval_workflow: ApprovalWorkflow | None = None,
        repository: "Repository | None" = None,
        ws_manager: "object | None" = None,
    ) -> None:
        self._toolkit = RemediationToolkit(
            connector_router=connector_router,
            policy_engine=policy_engine,
            approval_workflow=approval_workflow,
        )
        # Configure the module-level toolkit for nodes
        set_toolkit(self._toolkit)

        # Build the compiled graph
        graph = create_remediation_graph()
        self._app = graph.compile()

        # In-memory store of completed remediations (fallback when no DB)
        self._remediations: dict[str, RemediationState] = {}
        self._repository = repository
        self._ws_manager = ws_manager

        # Expose workflow and rollback manager for API routes
        self._approval_workflow = approval_workflow
        self._rollback_manager = RollbackManager(connector_router, repository)

    async def remediate(
        self,
        action: RemediationAction,
        alert_context: AlertContext | None = None,
        investigation_id: str | None = None,
    ) -> RemediationState:
        """Run a full remediation workflow for an action.

        Args:
            action: The remediation action to execute.
            alert_context: Optional alert context from the triggering investigation.
            investigation_id: Optional ID linking back to the investigation.

        Returns:
            The completed RemediationState with execution results.
        """
        remediation_id = f"rem-{uuid4().hex[:12]}"

        logger.info(
            "remediation_started",
            remediation_id=remediation_id,
            action_type=action.action_type,
            target=action.target_resource,
            environment=action.environment.value,
            risk_level=action.risk_level.value,
        )

        initial_state = RemediationState(
            remediation_id=remediation_id,
            action=action,
            alert_context=alert_context,
            investigation_id=investigation_id,
        )

        try:
            # Run the LangGraph workflow
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={
                    "metadata": {
                        "remediation_id": remediation_id,
                        "action_type": action.action_type,
                    },
                },
            )

            final_state = RemediationState.model_validate(final_state_dict)

            # Calculate total duration
            if final_state.remediation_start:
                final_state.remediation_duration_ms = int(
                    (datetime.now(UTC) - final_state.remediation_start).total_seconds() * 1000
                )

            logger.info(
                "remediation_completed",
                remediation_id=remediation_id,
                action_type=action.action_type,
                duration_ms=final_state.remediation_duration_ms,
                current_step=final_state.current_step,
                validation_passed=final_state.validation_passed,
                steps=len(final_state.reasoning_chain),
            )

            # Store result
            self._remediations[remediation_id] = final_state
            await self._persist(remediation_id, final_state)
            await self._write_audit(remediation_id, final_state)
            await self._broadcast(remediation_id, final_state)
            return final_state

        except Exception as e:
            logger.error(
                "remediation_failed",
                remediation_id=remediation_id,
                action_type=action.action_type,
                error=str(e),
            )
            # Return partial state with error
            error_state = RemediationState(
                remediation_id=remediation_id,
                action=action,
                alert_context=alert_context,
                investigation_id=investigation_id,
                error=str(e),
                current_step="failed",
            )
            self._remediations[remediation_id] = error_state
            await self._persist(remediation_id, error_state)
            await self._write_audit(remediation_id, error_state)
            return error_state

    async def _broadcast(self, remediation_id: str, state: RemediationState) -> None:
        """Broadcast progress via WebSocket if manager is available."""
        if self._ws_manager is None:
            return
        try:
            event = {
                "type": "remediation_update",
                "remediation_id": remediation_id,
                "status": state.current_step,
                "action_type": state.action.action_type,
                "validation_passed": state.validation_passed,
            }
            await self._ws_manager.broadcast("global", event)  # type: ignore[attr-defined]
            await self._ws_manager.broadcast(f"remediation:{remediation_id}", event)  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning("ws_broadcast_failed", id=remediation_id, error=str(e))

    async def _persist(self, remediation_id: str, state: RemediationState) -> None:
        """Persist to DB if repository is available."""
        if self._repository is None:
            return
        try:
            await self._repository.save_remediation(remediation_id, state)
        except Exception as e:
            logger.error("remediation_persist_failed", id=remediation_id, error=str(e))

    async def _write_audit(self, remediation_id: str, state: RemediationState) -> None:
        """Write an audit log entry for a completed remediation."""
        if self._repository is None:
            return
        try:
            outcome = ExecutionStatus.FAILED if state.error else ExecutionStatus.SUCCESS
            if state.execution_result:
                outcome = state.execution_result.status
            policy_eval = "allowed"
            if state.policy_result and not state.policy_result.allowed:
                policy_eval = "denied"

            entry = AuditEntry(
                id=f"aud-{remediation_id}",
                timestamp=datetime.now(UTC),
                agent_type="remediation",
                action=state.action.action_type,
                target_resource=state.action.target_resource,
                environment=state.action.environment,
                risk_level=state.assessed_risk or state.action.risk_level,
                policy_evaluation=policy_eval,
                approval_status=state.approval_status,
                outcome=outcome,
                reasoning=state.reasoning_chain[-1].output_summary if state.reasoning_chain else "",
                actor=f"agent:{remediation_id}",
            )
            await self._repository.append_audit_log(entry)
        except Exception as e:
            logger.error("audit_log_write_failed", id=remediation_id, error=str(e))

    def get_remediation(self, remediation_id: str) -> RemediationState | None:
        """Retrieve a completed remediation by ID."""
        return self._remediations.get(remediation_id)

    def list_remediations(self) -> list[dict[str, Any]]:
        """List all remediations with summary info."""
        return [
            {
                "remediation_id": rem_id,
                "action_type": state.action.action_type,
                "target_resource": state.action.target_resource,
                "environment": state.action.environment.value,
                "risk_level": (state.assessed_risk or state.action.risk_level).value,
                "status": state.current_step,
                "validation_passed": state.validation_passed,
                "duration_ms": state.remediation_duration_ms,
                "error": state.error,
            }
            for rem_id, state in self._remediations.items()
        ]

    def get_approval_workflow(self) -> ApprovalWorkflow | None:
        """Return the approval workflow so API routes can call approve()/deny()."""
        return self._approval_workflow

    async def rollback(self, remediation_id: str, reason: str = "") -> ActionResult:
        """Rollback a completed remediation to its pre-action snapshot.

        Returns ActionResult with FAILED status if the remediation is not found
        or has no snapshot.
        """
        now = datetime.now(UTC)
        state = self._remediations.get(remediation_id)

        if state is None:
            return ActionResult(
                action_id=f"rollback-{remediation_id}",
                status=ExecutionStatus.FAILED,
                message="Remediation not found",
                started_at=now,
            )

        if state.snapshot is None:
            return ActionResult(
                action_id=f"rollback-{remediation_id}",
                status=ExecutionStatus.FAILED,
                message="No snapshot available for rollback",
                started_at=now,
            )

        result = await self._rollback_manager.execute_rollback(
            snapshot=state.snapshot,
            reason=reason,
        )

        # Update stored state with rollback result
        state.rollback_result = result
        if result.status == ExecutionStatus.SUCCESS:
            state.current_step = "rolled_back"
        return result
