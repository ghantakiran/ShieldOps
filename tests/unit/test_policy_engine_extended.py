"""Extended unit tests for the policy engine: RollbackManager, ApprovalWorkflow,
RemediationRunner rollback methods, and wired API endpoints.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import (
    ActionResult,
    ApprovalStatus,
    Environment,
    ExecutionStatus,
    HealthStatus,
    RemediationAction,
    RiskLevel,
    Snapshot,
)
from shieldops.policy.approval.workflow import ApprovalRequest, ApprovalWorkflow
from shieldops.policy.rollback.manager import RollbackManager

# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _make_snapshot(sid: str = "snap-1", resource_id: str = "pod/api") -> Snapshot:
    return Snapshot(
        id=sid,
        resource_id=resource_id,
        snapshot_type="k8s_resource",
        state={"replicas": 2},
        created_at=datetime.now(UTC),
    )


def _make_action(risk: RiskLevel = RiskLevel.HIGH) -> RemediationAction:
    return RemediationAction(
        id="act-test",
        action_type="restart_pod",
        target_resource="pod/api",
        environment=Environment.PRODUCTION,
        risk_level=risk,
        description="Restart API pod",
    )


def _make_connector(
    *,
    rollback_result: ActionResult | None = None,
    health: HealthStatus | None = None,
    rollback_error: Exception | None = None,
    health_error: Exception | None = None,
) -> MagicMock:
    connector = MagicMock()
    if rollback_error:
        connector.rollback = AsyncMock(side_effect=rollback_error)
    else:
        connector.rollback = AsyncMock(
            return_value=rollback_result
            or ActionResult(
                action_id="rollback-snap-1",
                status=ExecutionStatus.SUCCESS,
                message="Rolled back",
                started_at=datetime.now(UTC),
            )
        )
    if health_error:
        connector.get_health = AsyncMock(side_effect=health_error)
    else:
        connector.get_health = AsyncMock(
            return_value=health
            or HealthStatus(
                resource_id="pod/api",
                healthy=True,
                status="running",
                last_checked=datetime.now(UTC),
            )
        )
    return connector


def _make_router(connector: MagicMock | None = None) -> ConnectorRouter:
    router = ConnectorRouter()
    c = connector or _make_connector()
    c.provider = "kubernetes"
    router.register(c)
    return router


# ────────────────────────────────────────────────────────────────────
# TestRollbackManager
# ────────────────────────────────────────────────────────────────────


class TestRollbackManager:
    @pytest.mark.asyncio
    async def test_execute_success(self):
        manager = RollbackManager(connector_router=_make_router())
        result = await manager.execute_rollback(_make_snapshot(), reason="bad deploy")
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_failure_never_raises(self):
        connector = _make_connector(rollback_error=RuntimeError("network error"))
        manager = RollbackManager(connector_router=_make_router(connector))
        result = await manager.execute_rollback(_make_snapshot(), reason="retry")
        assert result.status == ExecutionStatus.FAILED
        assert "network error" in result.message

    @pytest.mark.asyncio
    async def test_no_router_returns_failed(self):
        manager = RollbackManager(connector_router=None)
        result = await manager.execute_rollback(_make_snapshot())
        assert result.status == ExecutionStatus.FAILED
        assert "No connector router" in result.message

    @pytest.mark.asyncio
    async def test_writes_audit(self):
        repo = MagicMock()
        repo.append_audit_log = AsyncMock()
        manager = RollbackManager(connector_router=_make_router(), repository=repo)
        await manager.execute_rollback(_make_snapshot(), reason="test")
        repo.append_audit_log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_crash(self):
        repo = MagicMock()
        repo.append_audit_log = AsyncMock(side_effect=RuntimeError("db down"))
        manager = RollbackManager(connector_router=_make_router(), repository=repo)
        result = await manager.execute_rollback(_make_snapshot(), reason="test")
        # Rollback itself succeeds; audit failure is swallowed
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_validate_healthy(self):
        manager = RollbackManager(connector_router=_make_router())
        assert await manager.validate_rollback("pod/api") is True

    @pytest.mark.asyncio
    async def test_validate_unhealthy(self):
        health = HealthStatus(
            resource_id="pod/api",
            healthy=False,
            status="crash_loop",
            last_checked=datetime.now(UTC),
        )
        connector = _make_connector(health=health)
        manager = RollbackManager(connector_router=_make_router(connector))
        assert await manager.validate_rollback("pod/api") is False

    @pytest.mark.asyncio
    async def test_validate_error_returns_false(self):
        connector = _make_connector(health_error=RuntimeError("timeout"))
        manager = RollbackManager(connector_router=_make_router(connector))
        assert await manager.validate_rollback("pod/api") is False

    @pytest.mark.asyncio
    async def test_validate_no_router_returns_false(self):
        manager = RollbackManager(connector_router=None)
        assert await manager.validate_rollback("pod/api") is False


# ────────────────────────────────────────────────────────────────────
# TestApprovalWorkflowUnit
# ────────────────────────────────────────────────────────────────────


class TestApprovalWorkflowUnit:
    def test_requires_approval_high(self):
        wf = ApprovalWorkflow()
        assert wf.requires_approval(RiskLevel.HIGH) is True

    def test_requires_approval_critical(self):
        wf = ApprovalWorkflow()
        assert wf.requires_approval(RiskLevel.CRITICAL) is True

    def test_no_approval_low(self):
        wf = ApprovalWorkflow()
        assert wf.requires_approval(RiskLevel.LOW) is False

    def test_no_approval_medium(self):
        wf = ApprovalWorkflow()
        assert wf.requires_approval(RiskLevel.MEDIUM) is False

    def test_required_approvals_critical_is_two(self):
        wf = ApprovalWorkflow()
        assert wf.required_approvals(RiskLevel.CRITICAL) == 2

    def test_required_approvals_high_is_one(self):
        wf = ApprovalWorkflow()
        assert wf.required_approvals(RiskLevel.HIGH) == 1

    def test_approve_updates_request(self):
        wf = ApprovalWorkflow()
        req = ApprovalRequest("req-1", _make_action(), "agent-1", "needs approval")
        wf._pending["req-1"] = req
        wf.approve("req-1", "alice")
        assert "alice" in req.approvals

    def test_deny_updates_request(self):
        wf = ApprovalWorkflow()
        req = ApprovalRequest("req-1", _make_action(), "agent-1", "needs approval")
        wf._pending["req-1"] = req
        wf.deny("req-1", "bob", "too risky")
        assert "bob" in req.denials

    def test_approve_noop_on_nonexistent(self):
        wf = ApprovalWorkflow()
        wf.approve("nonexistent", "alice")  # should not raise

    def test_deny_noop_on_nonexistent(self):
        wf = ApprovalWorkflow()
        wf.deny("nonexistent", "bob")  # should not raise

    @pytest.mark.asyncio
    async def test_request_approval_approved(self):
        wf = ApprovalWorkflow(timeout_seconds=5)
        req = ApprovalRequest("req-1", _make_action(), "agent-1", "needs approval")

        async def approve_after_delay():
            await asyncio.sleep(0.1)
            wf.approve("req-1", "alice")

        task = asyncio.create_task(approve_after_delay())
        result = await wf.request_approval(req)
        await task
        assert result == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_request_approval_denied(self):
        wf = ApprovalWorkflow(timeout_seconds=5)
        req = ApprovalRequest("req-1", _make_action(), "agent-1", "needs approval")

        async def deny_after_delay():
            await asyncio.sleep(0.1)
            wf.deny("req-1", "bob", "nope")

        task = asyncio.create_task(deny_after_delay())
        result = await wf.request_approval(req)
        await task
        assert result == ApprovalStatus.DENIED

    @pytest.mark.asyncio
    async def test_request_approval_timeout(self):
        wf = ApprovalWorkflow(timeout_seconds=0.2)
        req = ApprovalRequest("req-1", _make_action(), "agent-1", "needs approval")
        result = await wf.request_approval(req)
        assert result == ApprovalStatus.ESCALATED

    @pytest.mark.asyncio
    async def test_four_eyes_critical(self):
        wf = ApprovalWorkflow(timeout_seconds=5)
        action = _make_action(risk=RiskLevel.CRITICAL)
        req = ApprovalRequest(
            "req-1", action, "agent-1", "critical change",
            required_approvals=wf.required_approvals(RiskLevel.CRITICAL),
        )

        async def approve_twice():
            await asyncio.sleep(0.1)
            wf.approve("req-1", "alice")
            await asyncio.sleep(0.1)
            wf.approve("req-1", "bob")

        task = asyncio.create_task(approve_twice())
        result = await wf.request_approval(req)
        await task
        assert result == ApprovalStatus.APPROVED
        assert len(req.approvals) == 2


# ────────────────────────────────────────────────────────────────────
# TestRunnerRollbackMethods
# ────────────────────────────────────────────────────────────────────


class TestRunnerRollbackMethods:
    def _make_runner(self, *, with_workflow: bool = True):
        from shieldops.agents.remediation.runner import RemediationRunner

        workflow = ApprovalWorkflow() if with_workflow else None
        router = _make_router()
        runner = RemediationRunner(
            connector_router=router,
            approval_workflow=workflow,
        )
        return runner

    def test_get_approval_workflow_returns_workflow(self):
        runner = self._make_runner(with_workflow=True)
        assert runner.get_approval_workflow() is not None

    def test_get_approval_workflow_none(self):
        runner = self._make_runner(with_workflow=False)
        assert runner.get_approval_workflow() is None

    @pytest.mark.asyncio
    async def test_rollback_success_updates_state(self):
        runner = self._make_runner()
        # Manually insert a remediation state with a snapshot
        from shieldops.agents.remediation.models import RemediationState

        state = RemediationState(
            remediation_id="rem-test",
            action=_make_action(),
            snapshot=_make_snapshot(),
            current_step="completed",
        )
        runner._remediations["rem-test"] = state

        result = await runner.rollback("rem-test", reason="bad deploy")
        assert result.status == ExecutionStatus.SUCCESS
        assert state.rollback_result is not None
        assert state.current_step == "rolled_back"

    @pytest.mark.asyncio
    async def test_rollback_not_found(self):
        runner = self._make_runner()
        result = await runner.rollback("nonexistent")
        assert result.status == ExecutionStatus.FAILED
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_rollback_no_snapshot(self):
        runner = self._make_runner()
        from shieldops.agents.remediation.models import RemediationState

        state = RemediationState(
            remediation_id="rem-nosnapshot",
            action=_make_action(),
            snapshot=None,
            current_step="completed",
        )
        runner._remediations["rem-nosnapshot"] = state

        result = await runner.rollback("rem-nosnapshot")
        assert result.status == ExecutionStatus.FAILED
        assert "no snapshot" in result.message.lower()


# ────────────────────────────────────────────────────────────────────
# TestWiredApproveAPI
# ────────────────────────────────────────────────────────────────────


class TestWiredApproveAPI:
    """Test the wired approve/deny/rollback endpoints via httpx + FastAPI TestClient."""

    @pytest.fixture
    def _setup_app(self):
        """Create a minimal FastAPI app with remediations router and auth overrides."""
        from fastapi import FastAPI

        from shieldops.api.auth.dependencies import get_current_user, require_role
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import remediations as rem_module

        app = FastAPI()
        app.include_router(rem_module.router, prefix="/api/v1")

        # Override auth to always return an admin user
        admin_user = UserResponse(
            id="test-admin",
            email="admin@test.com",
            name="Test Admin",
            role=UserRole.ADMIN,
            is_active=True,
        )

        async def _fake_user():
            return admin_user

        # Override both the base dependency and all role-check dependencies
        app.dependency_overrides[get_current_user] = _fake_user
        for role_combo in [
            (UserRole.ADMIN, UserRole.OPERATOR),
        ]:
            app.dependency_overrides[require_role(*role_combo)] = _fake_user

        return app, rem_module

    @pytest.fixture
    def _runner_with_state(self):
        """Create a RemediationRunner with a pre-populated remediation state."""
        from shieldops.agents.remediation.models import RemediationState
        from shieldops.agents.remediation.runner import RemediationRunner

        workflow = ApprovalWorkflow()
        router = _make_router()
        runner = RemediationRunner(
            connector_router=router,
            approval_workflow=workflow,
        )

        # State with approval_request_id and snapshot
        state = RemediationState(
            remediation_id="rem-api-test",
            action=_make_action(),
            approval_request_id="req-api-1",
            snapshot=_make_snapshot(),
            current_step="waiting_approval",
        )
        runner._remediations["rem-api-test"] = state

        # Register the approval request in the workflow
        req = ApprovalRequest("req-api-1", _make_action(), "agent-1", "needs approval")
        workflow._pending["req-api-1"] = req

        return runner, workflow

    @pytest.mark.asyncio
    async def test_approve_calls_workflow(self, _setup_app, _runner_with_state):
        app, rem_module = _setup_app
        runner, workflow = _runner_with_state
        rem_module.set_runner(runner)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/remediations/rem-api-test/approve",
                json={"approver": "alice"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "approved"
        # Verify the workflow was actually called
        assert "alice" in workflow._pending["req-api-1"].approvals

    @pytest.mark.asyncio
    async def test_approve_400_no_approval_request_id(self, _setup_app):
        app, rem_module = _setup_app
        from shieldops.agents.remediation.models import RemediationState
        from shieldops.agents.remediation.runner import RemediationRunner

        runner = RemediationRunner(
            connector_router=_make_router(),
            approval_workflow=ApprovalWorkflow(),
        )
        # State without approval_request_id
        state = RemediationState(
            remediation_id="rem-noapproval",
            action=_make_action(),
            current_step="completed",
        )
        runner._remediations["rem-noapproval"] = state
        rem_module.set_runner(runner)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/remediations/rem-noapproval/approve",
                json={"approver": "alice"},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_approve_404_not_found(self, _setup_app):
        app, rem_module = _setup_app
        from shieldops.agents.remediation.runner import RemediationRunner

        runner = RemediationRunner(connector_router=_make_router())
        rem_module.set_runner(runner)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/remediations/nonexistent/approve",
                json={"approver": "alice"},
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_deny_calls_workflow(self, _setup_app, _runner_with_state):
        app, rem_module = _setup_app
        runner, workflow = _runner_with_state
        rem_module.set_runner(runner)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/remediations/rem-api-test/deny",
                json={"approver": "bob", "reason": "too risky"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "denied"
        assert "bob" in workflow._pending["req-api-1"].denials

    @pytest.mark.asyncio
    async def test_deny_400_no_approval_request_id(self, _setup_app):
        app, rem_module = _setup_app
        from shieldops.agents.remediation.models import RemediationState
        from shieldops.agents.remediation.runner import RemediationRunner

        runner = RemediationRunner(
            connector_router=_make_router(),
            approval_workflow=ApprovalWorkflow(),
        )
        state = RemediationState(
            remediation_id="rem-nodeny",
            action=_make_action(),
            current_step="completed",
        )
        runner._remediations["rem-nodeny"] = state
        rem_module.set_runner(runner)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/remediations/rem-nodeny/deny",
                json={"approver": "bob"},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rollback_executes(self, _setup_app, _runner_with_state):
        app, rem_module = _setup_app
        runner, _ = _runner_with_state
        rem_module.set_runner(runner)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/remediations/rem-api-test/rollback",
                json={"reason": "bad deploy"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "rollback_initiated"
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_rollback_400_no_snapshot(self, _setup_app):
        app, rem_module = _setup_app
        from shieldops.agents.remediation.models import RemediationState
        from shieldops.agents.remediation.runner import RemediationRunner

        runner = RemediationRunner(connector_router=_make_router())
        state = RemediationState(
            remediation_id="rem-nosnap",
            action=_make_action(),
            current_step="completed",
        )
        runner._remediations["rem-nosnap"] = state
        rem_module.set_runner(runner)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/remediations/rem-nosnap/rollback",
                json={"reason": "test"},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rollback_404_not_found(self, _setup_app):
        app, rem_module = _setup_app
        from shieldops.agents.remediation.runner import RemediationRunner

        runner = RemediationRunner(connector_router=_make_router())
        rem_module.set_runner(runner)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/remediations/nonexistent/rollback",
                json={"reason": "test"},
            )
        assert resp.status_code == 404
