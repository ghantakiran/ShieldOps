"""Remediation Agent runner — entry point for executing remediations.

Takes a RemediationAction, constructs the LangGraph, runs it end-to-end,
and returns the completed remediation state.
"""

from datetime import datetime, timezone
from uuid import uuid4

import structlog

from shieldops.agents.remediation.graph import create_remediation_graph
from shieldops.agents.remediation.models import RemediationState
from shieldops.agents.remediation.nodes import set_toolkit
from shieldops.agents.remediation.tools import RemediationToolkit
from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import AlertContext, RemediationAction
from shieldops.policy.approval.workflow import ApprovalWorkflow
from shieldops.policy.opa.client import PolicyEngine

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

        # In-memory store of completed remediations
        self._remediations: dict[str, RemediationState] = {}

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
                initial_state.model_dump(),
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
                    (datetime.now(timezone.utc) - final_state.remediation_start).total_seconds()
                    * 1000
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
            return error_state

    def get_remediation(self, remediation_id: str) -> RemediationState | None:
        """Retrieve a completed remediation by ID."""
        return self._remediations.get(remediation_id)

    def list_remediations(self) -> list[dict]:
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
