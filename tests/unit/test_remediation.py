"""Comprehensive tests for the Remediation Agent.

Tests cover:
- RemediationToolkit (tools.py)
- Node functions (nodes.py)
- Graph construction and routing (graph.py)
- RemediationRunner (runner.py)
- API endpoints (routes/remediations.py)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.remediation.models import (
    PolicyResult,
    RemediationState,
    RemediationStep,
    ValidationCheck,
)
from shieldops.agents.remediation.prompts import (
    RiskAssessmentResult,
    ValidationAssessmentResult,
)
from shieldops.agents.remediation.tools import RemediationToolkit
from shieldops.models.base import (
    ActionResult,
    AlertContext,
    ApprovalStatus,
    Environment,
    ExecutionStatus,
    HealthStatus,
    RemediationAction,
    RiskLevel,
    Snapshot,
)
from shieldops.policy.approval.workflow import ApprovalWorkflow
from shieldops.policy.opa.client import PolicyDecision, PolicyEngine


# --- Fixtures ---


@pytest.fixture
def action():
    return RemediationAction(
        id="act-test-001",
        action_type="restart_pod",
        target_resource="default/api-server",
        environment=Environment.PRODUCTION,
        risk_level=RiskLevel.MEDIUM,
        parameters={"grace_period": 30},
        description="Restart crash-looping pod",
    )


@pytest.fixture
def high_risk_action():
    return RemediationAction(
        id="act-test-002",
        action_type="rollback_deployment",
        target_resource="default/api-server",
        environment=Environment.PRODUCTION,
        risk_level=RiskLevel.HIGH,
        parameters={"revision": 3},
        description="Rollback deployment to revision 3",
    )


@pytest.fixture
def alert_context():
    return AlertContext(
        alert_id="alert-test-001",
        alert_name="KubePodCrashLooping",
        severity="critical",
        source="prometheus",
        resource_id="default/api-server",
        triggered_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def remediation_state(action):
    return RemediationState(
        remediation_id="rem-test-001",
        action=action,
        remediation_start=datetime.now(timezone.utc),
    )


@pytest.fixture
def state_after_policy(remediation_state):
    """State after policy evaluation passed."""
    remediation_state.policy_result = PolicyResult(
        allowed=True,
        reasons=["Action allowed by default policy"],
        evaluated_at=datetime.now(timezone.utc),
    )
    remediation_state.reasoning_chain = [
        RemediationStep(
            step_number=1, action="evaluate_policy",
            input_summary="restart_pod", output_summary="ALLOWED",
            duration_ms=10, tool_used="opa",
        ),
    ]
    return remediation_state


@pytest.fixture
def state_after_risk(state_after_policy):
    """State after risk assessment."""
    state_after_policy.assessed_risk = RiskLevel.MEDIUM
    state_after_policy.reasoning_chain.append(
        RemediationStep(
            step_number=2, action="assess_risk",
            input_summary="Assessing risk", output_summary="Risk: medium",
            duration_ms=100, tool_used="policy_engine + llm",
        ),
    )
    return state_after_policy


@pytest.fixture
def state_after_snapshot(state_after_risk):
    """State after snapshot creation."""
    state_after_risk.snapshot = Snapshot(
        id="snap-test-001",
        resource_id="default/api-server",
        snapshot_type="k8s_resource",
        state={"kind": "Pod", "metadata": {"name": "api-server"}},
        created_at=datetime.now(timezone.utc),
    )
    state_after_risk.reasoning_chain.append(
        RemediationStep(
            step_number=3, action="create_snapshot",
            input_summary="Capturing state", output_summary="Snapshot created",
            duration_ms=50, tool_used="infra_connector",
        ),
    )
    return state_after_risk


@pytest.fixture
def state_after_execution(state_after_snapshot):
    """State after successful execution."""
    state_after_snapshot.execution_result = ActionResult(
        action_id="act-test-001",
        status=ExecutionStatus.SUCCESS,
        message="Pod restarted successfully",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    state_after_snapshot.reasoning_chain.append(
        RemediationStep(
            step_number=4, action="execute_action",
            input_summary="Executing restart_pod",
            output_summary="Action succeeded",
            duration_ms=200, tool_used="infra_connector",
        ),
    )
    return state_after_snapshot


@pytest.fixture
def mock_policy_engine():
    engine = MagicMock(spec=PolicyEngine)
    engine.evaluate = AsyncMock(
        return_value=PolicyDecision(allowed=True, reasons=["Allowed by default"])
    )
    engine.classify_risk = MagicMock(return_value=RiskLevel.MEDIUM)
    return engine


@pytest.fixture
def mock_approval_workflow():
    workflow = MagicMock(spec=ApprovalWorkflow)
    workflow.requires_approval = MagicMock(return_value=False)
    workflow.required_approvals = MagicMock(return_value=1)
    workflow.request_approval = AsyncMock(return_value=ApprovalStatus.APPROVED)
    return workflow


@pytest.fixture
def mock_connector_router():
    router = MagicMock()
    connector = AsyncMock()
    connector.create_snapshot = AsyncMock(return_value=Snapshot(
        id="snap-mock-001",
        resource_id="default/api-server",
        snapshot_type="k8s_resource",
        state={"kind": "Pod"},
        created_at=datetime.now(timezone.utc),
    ))
    connector.execute_action = AsyncMock(return_value=ActionResult(
        action_id="act-test-001",
        status=ExecutionStatus.SUCCESS,
        message="Pod restarted",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    ))
    connector.get_health = AsyncMock(return_value=HealthStatus(
        resource_id="default/api-server",
        healthy=True,
        status="Running",
        last_checked=datetime.now(timezone.utc),
    ))
    connector.rollback = AsyncMock(return_value=ActionResult(
        action_id="rollback-snap-mock-001",
        status=ExecutionStatus.SUCCESS,
        message="Rolled back",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    ))
    router.get = MagicMock(return_value=connector)
    return router


# ============================================================================
# RemediationToolkit tests
# ============================================================================


class TestRemediationToolkit:
    @pytest.mark.asyncio
    async def test_evaluate_policy(self, mock_policy_engine, action):
        toolkit = RemediationToolkit(policy_engine=mock_policy_engine)
        decision = await toolkit.evaluate_policy(action)
        assert decision.allowed is True
        mock_policy_engine.evaluate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_policy_no_engine(self, action):
        toolkit = RemediationToolkit()
        decision = await toolkit.evaluate_policy(action)
        assert decision.allowed is True  # Default allow when no engine

    def test_classify_risk(self, mock_policy_engine):
        toolkit = RemediationToolkit(policy_engine=mock_policy_engine)
        risk = toolkit.classify_risk("restart_pod", "production")
        assert risk == RiskLevel.MEDIUM

    def test_classify_risk_no_engine(self):
        toolkit = RemediationToolkit()
        risk = toolkit.classify_risk("restart_pod", "production")
        assert risk == RiskLevel.MEDIUM

    def test_requires_approval_false(self, mock_approval_workflow):
        toolkit = RemediationToolkit(approval_workflow=mock_approval_workflow)
        assert toolkit.requires_approval(RiskLevel.LOW) is False

    def test_requires_approval_no_workflow(self):
        toolkit = RemediationToolkit()
        assert toolkit.requires_approval(RiskLevel.HIGH) is False

    @pytest.mark.asyncio
    async def test_request_approval(self, mock_approval_workflow, action):
        from shieldops.policy.approval.workflow import ApprovalRequest

        toolkit = RemediationToolkit(approval_workflow=mock_approval_workflow)
        request = ApprovalRequest(
            request_id="apr-test",
            action=action,
            agent_id="test",
            reason="test",
        )
        status = await toolkit.request_approval(request)
        assert status == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_request_approval_no_workflow(self, action):
        from shieldops.policy.approval.workflow import ApprovalRequest

        toolkit = RemediationToolkit()
        request = ApprovalRequest(
            request_id="apr-test",
            action=action,
            agent_id="test",
            reason="test",
        )
        status = await toolkit.request_approval(request)
        assert status == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_create_snapshot(self, mock_connector_router):
        toolkit = RemediationToolkit(connector_router=mock_connector_router)
        snapshot = await toolkit.create_snapshot("default/api-server")
        assert snapshot is not None
        assert snapshot.id == "snap-mock-001"

    @pytest.mark.asyncio
    async def test_create_snapshot_no_router(self):
        toolkit = RemediationToolkit()
        snapshot = await toolkit.create_snapshot("default/api-server")
        assert snapshot is None

    @pytest.mark.asyncio
    async def test_execute_action(self, mock_connector_router, action):
        toolkit = RemediationToolkit(connector_router=mock_connector_router)
        result = await toolkit.execute_action(action)
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_action_no_router(self, action):
        toolkit = RemediationToolkit()
        result = await toolkit.execute_action(action)
        assert result.status == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_validate_health(self, mock_connector_router):
        toolkit = RemediationToolkit(connector_router=mock_connector_router)
        health = await toolkit.validate_health("default/api-server")
        assert health is not None
        assert health.healthy is True

    @pytest.mark.asyncio
    async def test_validate_health_no_router(self):
        toolkit = RemediationToolkit()
        health = await toolkit.validate_health("default/api-server")
        assert health is None

    @pytest.mark.asyncio
    async def test_rollback(self, mock_connector_router):
        toolkit = RemediationToolkit(connector_router=mock_connector_router)
        result = await toolkit.rollback("snap-test-001")
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_rollback_no_router(self):
        toolkit = RemediationToolkit()
        result = await toolkit.rollback("snap-test-001")
        assert result.status == ExecutionStatus.FAILED


# ============================================================================
# Node tests
# ============================================================================


class TestEvaluatePolicyNode:
    @pytest.mark.asyncio
    async def test_policy_allowed(self, remediation_state, mock_policy_engine):
        from shieldops.agents.remediation.nodes import evaluate_policy, set_toolkit

        toolkit = RemediationToolkit(policy_engine=mock_policy_engine)
        set_toolkit(toolkit)

        result = await evaluate_policy(remediation_state)

        assert result["policy_result"].allowed is True
        assert result["current_step"] == "evaluate_policy"
        assert len(result["reasoning_chain"]) == 1

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_policy_denied(self, remediation_state):
        from shieldops.agents.remediation.nodes import evaluate_policy, set_toolkit

        engine = MagicMock(spec=PolicyEngine)
        engine.evaluate = AsyncMock(
            return_value=PolicyDecision(allowed=False, reasons=["Blocked by change freeze"])
        )
        toolkit = RemediationToolkit(policy_engine=engine)
        set_toolkit(toolkit)

        result = await evaluate_policy(remediation_state)

        assert result["policy_result"].allowed is False
        assert "DENIED" in result["reasoning_chain"][0].output_summary

        set_toolkit(None)


class TestAssessRiskNode:
    @pytest.mark.asyncio
    async def test_assess_risk_with_llm(self, state_after_policy, mock_policy_engine):
        from shieldops.agents.remediation.nodes import assess_risk, set_toolkit

        toolkit = RemediationToolkit(policy_engine=mock_policy_engine)
        set_toolkit(toolkit)

        mock_result = RiskAssessmentResult(
            risk_level="medium",
            reasoning=["Pod restart is low impact"],
            blast_radius="single_pod",
            reversible=True,
            precautions=["Ensure replacement pod starts"],
        )

        with patch(
            "shieldops.agents.remediation.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await assess_risk(state_after_policy)

        assert result["assessed_risk"] == RiskLevel.MEDIUM
        assert result["current_step"] == "assess_risk"

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_assess_risk_llm_escalates(self, state_after_policy, mock_policy_engine):
        """LLM sees higher risk → uses the higher of baseline and LLM risk."""
        from shieldops.agents.remediation.nodes import assess_risk, set_toolkit

        toolkit = RemediationToolkit(policy_engine=mock_policy_engine)
        set_toolkit(toolkit)

        mock_result = RiskAssessmentResult(
            risk_level="high",
            reasoning=["Production deployment with active traffic"],
            blast_radius="deployment",
            reversible=True,
            precautions=["Drain connections first"],
        )

        with patch(
            "shieldops.agents.remediation.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await assess_risk(state_after_policy)

        assert result["assessed_risk"] == RiskLevel.HIGH  # Escalated from MEDIUM

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_assess_risk_llm_failure(self, state_after_policy, mock_policy_engine):
        from shieldops.agents.remediation.nodes import assess_risk, set_toolkit

        toolkit = RemediationToolkit(policy_engine=mock_policy_engine)
        set_toolkit(toolkit)

        with patch(
            "shieldops.agents.remediation.nodes.llm_structured",
            new_callable=AsyncMock,
            side_effect=Exception("LLM unavailable"),
        ):
            result = await assess_risk(state_after_policy)

        # Falls back to baseline risk
        assert result["assessed_risk"] == RiskLevel.MEDIUM

        set_toolkit(None)


class TestRequestApprovalNode:
    @pytest.mark.asyncio
    async def test_approval_granted(self, state_after_risk, mock_approval_workflow):
        from shieldops.agents.remediation.nodes import request_approval, set_toolkit

        mock_approval_workflow.request_approval = AsyncMock(
            return_value=ApprovalStatus.APPROVED
        )
        toolkit = RemediationToolkit(approval_workflow=mock_approval_workflow)
        set_toolkit(toolkit)

        state_after_risk.assessed_risk = RiskLevel.HIGH
        result = await request_approval(state_after_risk)

        assert result["approval_status"] == ApprovalStatus.APPROVED
        assert result["approval_request_id"] is not None

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_approval_denied(self, state_after_risk):
        from shieldops.agents.remediation.nodes import request_approval, set_toolkit

        workflow = MagicMock(spec=ApprovalWorkflow)
        workflow.request_approval = AsyncMock(return_value=ApprovalStatus.DENIED)
        toolkit = RemediationToolkit(approval_workflow=workflow)
        set_toolkit(toolkit)

        state_after_risk.assessed_risk = RiskLevel.HIGH
        result = await request_approval(state_after_risk)

        assert result["approval_status"] == ApprovalStatus.DENIED

        set_toolkit(None)


class TestCreateSnapshotNode:
    @pytest.mark.asyncio
    async def test_snapshot_created(self, state_after_risk, mock_connector_router):
        from shieldops.agents.remediation.nodes import create_snapshot, set_toolkit

        toolkit = RemediationToolkit(connector_router=mock_connector_router)
        set_toolkit(toolkit)

        result = await create_snapshot(state_after_risk)

        assert result["snapshot"] is not None
        assert result["snapshot"].id == "snap-mock-001"

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_snapshot_failed(self, state_after_risk):
        from shieldops.agents.remediation.nodes import create_snapshot, set_toolkit

        toolkit = RemediationToolkit()
        set_toolkit(toolkit)

        result = await create_snapshot(state_after_risk)

        assert result["snapshot"] is None
        assert "failed" in result["reasoning_chain"][-1].output_summary.lower()

        set_toolkit(None)


class TestExecuteActionNode:
    @pytest.mark.asyncio
    async def test_execution_success(self, state_after_snapshot, mock_connector_router):
        from shieldops.agents.remediation.nodes import execute_action, set_toolkit

        toolkit = RemediationToolkit(connector_router=mock_connector_router)
        set_toolkit(toolkit)

        result = await execute_action(state_after_snapshot)

        assert result["execution_result"].status == ExecutionStatus.SUCCESS
        assert result["current_step"] == "execute_action"

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_execution_failure(self, state_after_snapshot):
        from shieldops.agents.remediation.nodes import execute_action, set_toolkit

        toolkit = RemediationToolkit()  # No connector
        set_toolkit(toolkit)

        result = await execute_action(state_after_snapshot)

        assert result["execution_result"].status == ExecutionStatus.FAILED

        set_toolkit(None)


class TestValidateHealthNode:
    @pytest.mark.asyncio
    async def test_validation_healthy(self, state_after_execution, mock_connector_router):
        from shieldops.agents.remediation.nodes import set_toolkit, validate_health

        toolkit = RemediationToolkit(connector_router=mock_connector_router)
        set_toolkit(toolkit)

        mock_result = ValidationAssessmentResult(
            overall_healthy=True,
            summary="System healthy after restart",
            concerns=[],
            recommendation="proceed",
        )

        with patch(
            "shieldops.agents.remediation.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await validate_health(state_after_execution)

        assert result["validation_passed"] is True
        assert len(result["validation_checks"]) >= 1

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_validation_unhealthy(self, state_after_execution):
        from shieldops.agents.remediation.nodes import set_toolkit, validate_health

        router = MagicMock()
        connector = AsyncMock()
        connector.get_health = AsyncMock(return_value=HealthStatus(
            resource_id="default/api-server",
            healthy=False,
            status="CrashLoopBackOff",
            message="Still crashing",
            last_checked=datetime.now(timezone.utc),
        ))
        router.get = MagicMock(return_value=connector)

        toolkit = RemediationToolkit(connector_router=router)
        set_toolkit(toolkit)

        mock_result = ValidationAssessmentResult(
            overall_healthy=False,
            summary="System still unhealthy",
            concerns=["Pod still crash-looping"],
            recommendation="rollback",
        )

        with patch(
            "shieldops.agents.remediation.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await validate_health(state_after_execution)

        assert result["validation_passed"] is False

        set_toolkit(None)


class TestPerformRollbackNode:
    @pytest.mark.asyncio
    async def test_rollback_with_snapshot(self, state_after_execution, mock_connector_router):
        from shieldops.agents.remediation.nodes import perform_rollback, set_toolkit

        toolkit = RemediationToolkit(connector_router=mock_connector_router)
        set_toolkit(toolkit)

        result = await perform_rollback(state_after_execution)

        assert result["rollback_result"] is not None
        assert result["rollback_result"].status == ExecutionStatus.SUCCESS
        assert result["current_step"] == "rolled_back"

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_rollback_no_snapshot(self, state_after_risk):
        from shieldops.agents.remediation.nodes import perform_rollback, set_toolkit

        toolkit = RemediationToolkit()
        set_toolkit(toolkit)

        # No snapshot on this state
        result = await perform_rollback(state_after_risk)

        assert result["rollback_result"] is None
        assert "manual intervention" in result["reasoning_chain"][-1].output_summary.lower()

        set_toolkit(None)


# ============================================================================
# Graph routing tests
# ============================================================================


class TestGraphRouting:
    def test_policy_gate_allowed(self, state_after_policy):
        from shieldops.agents.remediation.graph import policy_gate

        assert policy_gate(state_after_policy) == "assess_risk"

    def test_policy_gate_denied(self, remediation_state):
        from shieldops.agents.remediation.graph import policy_gate

        remediation_state.policy_result = PolicyResult(allowed=False, reasons=["Blocked"])
        assert policy_gate(remediation_state) == "__end__"

    def test_policy_gate_no_result(self, remediation_state):
        from shieldops.agents.remediation.graph import policy_gate

        assert policy_gate(remediation_state) == "__end__"

    def test_approval_gate_low_risk(self, state_after_risk):
        from shieldops.agents.remediation.graph import approval_gate

        state_after_risk.assessed_risk = RiskLevel.LOW
        assert approval_gate(state_after_risk) == "create_snapshot"

    def test_approval_decision_approved(self, state_after_risk):
        from shieldops.agents.remediation.graph import approval_decision

        state_after_risk.approval_status = ApprovalStatus.APPROVED
        assert approval_decision(state_after_risk) == "create_snapshot"

    def test_approval_decision_denied(self, state_after_risk):
        from shieldops.agents.remediation.graph import approval_decision

        state_after_risk.approval_status = ApprovalStatus.DENIED
        assert approval_decision(state_after_risk) == "__end__"

    def test_execution_gate_success(self, state_after_execution):
        from shieldops.agents.remediation.graph import execution_gate

        assert execution_gate(state_after_execution) == "validate_health"

    def test_execution_gate_failure(self, state_after_snapshot):
        from shieldops.agents.remediation.graph import execution_gate

        state_after_snapshot.execution_result = ActionResult(
            action_id="test",
            status=ExecutionStatus.FAILED,
            message="Failed",
            started_at=datetime.now(timezone.utc),
        )
        assert execution_gate(state_after_snapshot) == "perform_rollback"

    def test_validation_gate_healthy(self, state_after_execution):
        from shieldops.agents.remediation.graph import validation_gate

        state_after_execution.validation_passed = True
        assert validation_gate(state_after_execution) == "__end__"

    def test_validation_gate_unhealthy(self, state_after_execution):
        from shieldops.agents.remediation.graph import validation_gate

        state_after_execution.validation_passed = False
        assert validation_gate(state_after_execution) == "perform_rollback"

    def test_validation_gate_uncertain(self, state_after_execution):
        from shieldops.agents.remediation.graph import validation_gate

        state_after_execution.validation_passed = None
        assert validation_gate(state_after_execution) == "__end__"


class TestGraphConstruction:
    def test_create_remediation_graph(self):
        from shieldops.agents.remediation.graph import create_remediation_graph

        graph = create_remediation_graph()
        compiled = graph.compile()
        assert compiled is not None


# ============================================================================
# Runner tests
# ============================================================================


class TestRemediationRunner:
    def test_runner_init(self):
        from shieldops.agents.remediation.runner import RemediationRunner

        runner = RemediationRunner()
        assert runner._remediations == {}

    @pytest.mark.asyncio
    async def test_remediate_returns_state(self, action, alert_context):
        from shieldops.agents.remediation.runner import RemediationRunner

        runner = RemediationRunner()

        mock_state = RemediationState(
            remediation_id="rem-mock",
            action=action,
            alert_context=alert_context,
            current_step="validate_health",
            validation_passed=True,
            remediation_start=datetime.now(timezone.utc),
        )
        runner._app = AsyncMock()
        runner._app.ainvoke = AsyncMock(return_value=mock_state.model_dump())

        result = await runner.remediate(action, alert_context)

        assert result.action.action_type == "restart_pod"
        assert len(runner._remediations) == 1

    @pytest.mark.asyncio
    async def test_remediate_handles_error(self, action):
        from shieldops.agents.remediation.runner import RemediationRunner

        runner = RemediationRunner()
        runner._app = AsyncMock()
        runner._app.ainvoke = AsyncMock(side_effect=RuntimeError("Graph exploded"))

        result = await runner.remediate(action)

        assert result.error == "Graph exploded"
        assert result.current_step == "failed"

    def test_list_remediations_empty(self):
        from shieldops.agents.remediation.runner import RemediationRunner

        runner = RemediationRunner()
        assert runner.list_remediations() == []

    def test_get_remediation_not_found(self):
        from shieldops.agents.remediation.runner import RemediationRunner

        runner = RemediationRunner()
        assert runner.get_remediation("nonexistent") is None


# ============================================================================
# API endpoint tests
# ============================================================================


class TestRemediationAPI:
    @pytest.fixture
    def mock_runner(self, action, alert_context):
        from shieldops.agents.remediation.runner import RemediationRunner

        runner = MagicMock(spec=RemediationRunner)
        runner.list_remediations.return_value = [
            {
                "remediation_id": "rem-abc123",
                "action_type": "restart_pod",
                "target_resource": "default/api-server",
                "environment": "production",
                "risk_level": "medium",
                "status": "validate_health",
                "validation_passed": True,
                "duration_ms": 3000,
                "error": None,
            },
        ]

        state = RemediationState(
            remediation_id="rem-abc123",
            action=action,
            current_step="validate_health",
            validation_passed=True,
            snapshot=Snapshot(
                id="snap-001",
                resource_id="default/api-server",
                snapshot_type="k8s_resource",
                state={},
                created_at=datetime.now(timezone.utc),
            ),
        )
        runner.get_remediation.return_value = state
        runner.remediate = AsyncMock(return_value=state)
        return runner

    @pytest.fixture
    async def client(self, mock_runner):
        from httpx import ASGITransport, AsyncClient

        from shieldops.api.app import create_app
        from shieldops.api.routes.remediations import set_runner

        set_runner(mock_runner)
        app = create_app()

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole

        def _mock_admin_user():
            return UserResponse(
                id="test-admin", email="admin@test.com", name="Test Admin",
                role=UserRole.ADMIN, is_active=True,
            )

        app.dependency_overrides[get_current_user] = _mock_admin_user

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

        set_runner(None)

    @pytest.mark.asyncio
    async def test_list_remediations(self, client):
        response = await client.get("/api/v1/remediations")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["remediations"][0]["remediation_id"] == "rem-abc123"

    @pytest.mark.asyncio
    async def test_list_remediations_filter_env(self, client):
        response = await client.get("/api/v1/remediations?environment=production")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_list_remediations_filter_no_match(self, client):
        response = await client.get("/api/v1/remediations?environment=staging")
        assert response.status_code == 200
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_get_remediation_found(self, client):
        response = await client.get("/api/v1/remediations/rem-abc123")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_remediation_not_found(self, client, mock_runner):
        mock_runner.get_remediation.return_value = None
        response = await client.get("/api/v1/remediations/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_remediation_async(self, client):
        response = await client.post(
            "/api/v1/remediations",
            json={
                "action_type": "restart_pod",
                "target_resource": "default/web-server",
                "environment": "production",
                "risk_level": "low",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["action_type"] == "restart_pod"

    @pytest.mark.asyncio
    async def test_trigger_remediation_sync(self, client):
        response = await client.post(
            "/api/v1/remediations/sync",
            json={
                "action_type": "scale_horizontal",
                "target_resource": "default/api-server",
                "environment": "production",
                "risk_level": "medium",
                "parameters": {"replicas": 5},
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_approve_remediation(self, client):
        response = await client.post(
            "/api/v1/remediations/rem-abc123/approve",
            json={"approver": "admin@example.com"},
        )
        assert response.status_code == 200
        assert response.json()["action"] == "approved"

    @pytest.mark.asyncio
    async def test_deny_remediation(self, client):
        response = await client.post(
            "/api/v1/remediations/rem-abc123/deny",
            json={"approver": "admin@example.com", "reason": "Too risky"},
        )
        assert response.status_code == 200
        assert response.json()["action"] == "denied"

    @pytest.mark.asyncio
    async def test_rollback_remediation(self, client):
        response = await client.post("/api/v1/remediations/rem-abc123/rollback")
        assert response.status_code == 200
        assert response.json()["action"] == "rollback_initiated"

    @pytest.mark.asyncio
    async def test_rollback_no_snapshot(self, client, mock_runner):
        from shieldops.agents.remediation.models import RemediationState

        state = RemediationState(
            remediation_id="rem-no-snap",
            action=RemediationAction(
                id="act-1", action_type="restart_pod",
                target_resource="default/pod",
                environment=Environment.PRODUCTION,
                risk_level=RiskLevel.LOW,
                description="test",
            ),
        )
        mock_runner.get_remediation.return_value = state
        response = await client.post("/api/v1/remediations/rem-no-snap/rollback")
        assert response.status_code == 400


# ============================================================================
# Remediation models tests
# ============================================================================


class TestRemediationModels:
    def test_policy_result(self):
        result = PolicyResult(allowed=True, reasons=["OK"])
        assert result.allowed is True

    def test_validation_check(self):
        check = ValidationCheck(
            check_name="resource_health",
            passed=True,
            message="Pod is Running",
        )
        assert check.passed is True

    def test_remediation_step(self):
        step = RemediationStep(
            step_number=1,
            action="evaluate_policy",
            input_summary="restart_pod",
            output_summary="ALLOWED",
            duration_ms=10,
        )
        assert step.tool_used is None

    def test_remediation_state_defaults(self, action):
        state = RemediationState(action=action)
        assert state.remediation_id == ""
        assert state.policy_result is None
        assert state.assessed_risk is None
        assert state.approval_status is None
        assert state.snapshot is None
        assert state.execution_result is None
        assert state.validation_checks == []
        assert state.validation_passed is None
        assert state.rollback_result is None
        assert state.current_step == "init"
        assert state.error is None
