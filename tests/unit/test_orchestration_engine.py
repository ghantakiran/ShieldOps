"""Unit tests for the orchestration engine module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.orchestration.models import (
    AgentType,
    EscalationPolicy,
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
)
from shieldops.orchestration.supervisor import (
    DEFAULT_POLICIES,
    MAX_CONCURRENT_RUNS,
    SupervisorAgent,
)
from shieldops.orchestration.workflow_engine import WorkflowEngine

# =========================================================================
# Model tests
# =========================================================================


class TestWorkflowStatus:
    """Tests for WorkflowStatus enum."""

    def test_enum_values(self) -> None:
        assert WorkflowStatus.PENDING == "pending"
        assert WorkflowStatus.RUNNING == "running"
        assert WorkflowStatus.PAUSED == "paused"
        assert WorkflowStatus.COMPLETED == "completed"
        assert WorkflowStatus.FAILED == "failed"
        assert WorkflowStatus.CANCELLED == "cancelled"

    def test_all_statuses_present(self) -> None:
        expected = {"pending", "running", "paused", "completed", "failed", "cancelled"}
        actual = {s.value for s in WorkflowStatus}
        assert actual == expected


class TestAgentType:
    """Tests for AgentType enum."""

    def test_enum_values(self) -> None:
        assert AgentType.INVESTIGATION == "investigation"
        assert AgentType.REMEDIATION == "remediation"
        assert AgentType.SECURITY == "security"
        assert AgentType.LEARNING == "learning"
        assert AgentType.SUPERVISOR == "supervisor"

    def test_all_agent_types_present(self) -> None:
        expected = {"investigation", "remediation", "security", "learning", "supervisor"}
        actual = {t.value for t in AgentType}
        assert actual == expected


class TestWorkflowStep:
    """Tests for WorkflowStep model."""

    def test_creation_with_defaults(self) -> None:
        step = WorkflowStep(
            agent_type=AgentType.INVESTIGATION,
            action="investigate",
        )
        assert step.agent_type == AgentType.INVESTIGATION
        assert step.action == "investigate"
        assert step.status == WorkflowStatus.PENDING
        assert step.parameters == {}
        assert step.started_at is None
        assert step.completed_at is None
        assert step.result is None
        assert step.error is None

    def test_step_id_auto_generated(self) -> None:
        step = WorkflowStep(agent_type=AgentType.SECURITY, action="scan")
        assert step.step_id.startswith("step-")
        assert len(step.step_id) > 5

    def test_two_steps_have_unique_ids(self) -> None:
        s1 = WorkflowStep(agent_type=AgentType.SECURITY, action="scan")
        s2 = WorkflowStep(agent_type=AgentType.SECURITY, action="scan")
        assert s1.step_id != s2.step_id

    def test_creation_with_parameters(self) -> None:
        step = WorkflowStep(
            agent_type=AgentType.REMEDIATION,
            action="restart",
            parameters={"service": "api-gateway"},
        )
        assert step.parameters == {"service": "api-gateway"}


class TestWorkflowRun:
    """Tests for WorkflowRun model."""

    def test_creation_with_defaults(self) -> None:
        run = WorkflowRun(workflow_name="incident_response", trigger="alert")
        assert run.workflow_name == "incident_response"
        assert run.trigger == "alert"
        assert run.status == WorkflowStatus.PENDING
        assert run.steps == []
        assert run.metadata == {}
        assert run.completed_at is None
        assert run.initiated_by == "system"

    def test_run_id_auto_generated(self) -> None:
        run = WorkflowRun(workflow_name="test", trigger="manual")
        assert run.run_id.startswith("wfrun-")

    def test_created_at_auto_set(self) -> None:
        run = WorkflowRun(workflow_name="test", trigger="manual")
        assert run.created_at is not None


class TestEscalationPolicy:
    """Tests for EscalationPolicy model."""

    def test_defaults(self) -> None:
        policy = EscalationPolicy(severity="medium")
        assert policy.severity == "medium"
        assert policy.auto_remediate is False
        assert policy.notify_channels == []
        assert policy.page_oncall is False
        assert policy.max_retries == 3

    def test_custom_values(self) -> None:
        policy = EscalationPolicy(
            severity="critical",
            auto_remediate=True,
            notify_channels=["slack", "pagerduty"],
            page_oncall=True,
            max_retries=1,
        )
        assert policy.auto_remediate is True
        assert policy.notify_channels == ["slack", "pagerduty"]
        assert policy.page_oncall is True
        assert policy.max_retries == 1


# =========================================================================
# WorkflowEngine tests
# =========================================================================


class TestWorkflowEngine:
    """Tests for WorkflowEngine."""

    def test_list_workflows_returns_builtins(self) -> None:
        engine = WorkflowEngine()
        workflows = engine.list_workflows()
        assert "incident_response" in workflows
        assert "security_scan" in workflows
        assert "proactive_check" in workflows

    def test_list_workflows_sorted(self) -> None:
        engine = WorkflowEngine()
        workflows = engine.list_workflows()
        assert workflows == sorted(workflows)

    def test_register_workflow_adds_custom(self) -> None:
        engine = WorkflowEngine()
        custom_steps = [{"agent_type": AgentType.LEARNING, "action": "report"}]
        engine.register_workflow("custom_wf", custom_steps)
        assert "custom_wf" in engine.list_workflows()

    def test_register_workflow_included_in_list(self) -> None:
        engine = WorkflowEngine()
        engine.register_workflow("zz_custom", [{"agent_type": "learning", "action": "x"}])
        workflows = engine.list_workflows()
        assert "zz_custom" in workflows
        # builtins still present
        assert "incident_response" in workflows

    @pytest.mark.asyncio
    async def test_execute_workflow_creates_run(self) -> None:
        runner = MagicMock()
        runner.investigate = AsyncMock(return_value={"confidence": 0.9})
        runner.recommend = AsyncMock(return_value={"action": "restart"})
        runner.verify = AsyncMock(return_value={"verified": True})

        remediation_runner = MagicMock()
        remediation_runner.remediate = AsyncMock(return_value={"success": True})

        learning_runner = MagicMock()
        learning_runner.notify = AsyncMock(return_value={"notified": True})

        engine = WorkflowEngine(
            agent_runners={
                AgentType.INVESTIGATION: runner,
                AgentType.REMEDIATION: remediation_runner,
                AgentType.LEARNING: learning_runner,
            }
        )
        run = await engine.execute_workflow("incident_response", trigger="alert")
        assert isinstance(run, WorkflowRun)
        assert run.workflow_name == "incident_response"
        assert run.run_id.startswith("wfrun-")

    @pytest.mark.asyncio
    async def test_execute_workflow_completed_on_success(self) -> None:
        runner = MagicMock()
        runner.check_resources = AsyncMock(return_value={"ok": True})
        runner.check_slos = AsyncMock(return_value={"ok": True})

        security_runner = MagicMock()
        security_runner.check_certificates = AsyncMock(return_value={"ok": True})

        learning_runner = MagicMock()
        learning_runner.report = AsyncMock(return_value={"ok": True})

        engine = WorkflowEngine(
            agent_runners={
                AgentType.INVESTIGATION: runner,
                AgentType.SECURITY: security_runner,
                AgentType.LEARNING: learning_runner,
            }
        )
        run = await engine.execute_workflow("proactive_check", trigger="scheduled")
        assert run.status == WorkflowStatus.COMPLETED
        assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_workflow_handles_step_failure(self) -> None:
        runner = MagicMock()
        runner.check_resources = AsyncMock(side_effect=RuntimeError("connection timeout"))

        engine = WorkflowEngine(agent_runners={AgentType.INVESTIGATION: runner})
        run = await engine.execute_workflow("proactive_check", trigger="manual")
        assert run.status == WorkflowStatus.FAILED
        assert run.completed_at is not None
        # First step should be failed
        failed_steps = [s for s in run.steps if s.status == WorkflowStatus.FAILED]
        assert len(failed_steps) == 1
        assert "connection timeout" in failed_steps[0].error

    @pytest.mark.asyncio
    async def test_execute_workflow_unknown_raises(self) -> None:
        engine = WorkflowEngine()
        with pytest.raises(ValueError, match="Unknown workflow"):
            await engine.execute_workflow("nonexistent_workflow", trigger="manual")

    @pytest.mark.asyncio
    async def test_execute_workflow_no_runner_returns_no_runner_result(self) -> None:
        engine = WorkflowEngine()  # no runners registered
        run = await engine.execute_workflow("proactive_check", trigger="manual")
        assert run.status == WorkflowStatus.COMPLETED
        # Steps should have no_runner result
        assert run.steps[0].result["status"] == "no_runner"

    @pytest.mark.asyncio
    async def test_execute_workflow_with_params(self) -> None:
        runner = MagicMock()
        runner.check_resources = AsyncMock(return_value={"ok": True})
        runner.check_slos = AsyncMock(return_value={"ok": True})

        security_runner = MagicMock()
        security_runner.check_certificates = AsyncMock(return_value={"ok": True})

        learning_runner = MagicMock()
        learning_runner.report = AsyncMock(return_value={"ok": True})

        engine = WorkflowEngine(
            agent_runners={
                AgentType.INVESTIGATION: runner,
                AgentType.SECURITY: security_runner,
                AgentType.LEARNING: learning_runner,
            }
        )
        run = await engine.execute_workflow(
            "proactive_check", trigger="alert", params={"namespace": "prod"}
        )
        assert run.metadata == {"namespace": "prod"}
        assert run.status == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_workflow_condition_skips_step(self) -> None:
        """When investigation confidence <= 0.7, remediation step is skipped."""
        runner = MagicMock()
        runner.investigate = AsyncMock(return_value={"confidence": 0.3})
        runner.recommend = AsyncMock(return_value={"action": "none"})
        runner.verify = AsyncMock(return_value={"verified": True})

        remediation_runner = MagicMock()
        remediation_runner.remediate = AsyncMock(return_value={"success": True})

        learning_runner = MagicMock()
        learning_runner.notify = AsyncMock(return_value={"notified": True})

        engine = WorkflowEngine(
            agent_runners={
                AgentType.INVESTIGATION: runner,
                AgentType.REMEDIATION: remediation_runner,
                AgentType.LEARNING: learning_runner,
            }
        )
        run = await engine.execute_workflow("incident_response", trigger="alert")
        assert run.status == WorkflowStatus.COMPLETED
        # remediation step should have been skipped
        remediation_steps = [s for s in run.steps if s.agent_type == AgentType.REMEDIATION]
        assert len(remediation_steps) == 1
        assert remediation_steps[0].result == {"skipped": True, "reason": "condition_not_met"}
        remediation_runner.remediate.assert_not_called()


# =========================================================================
# SupervisorAgent tests
# =========================================================================


class TestSupervisorAgent:
    """Tests for SupervisorAgent."""

    @pytest.mark.asyncio
    async def test_handle_alert_triggers_workflow_run(self) -> None:
        mock_engine = MagicMock(spec=WorkflowEngine)
        completed_run = WorkflowRun(
            workflow_name="incident_response",
            trigger="alert",
            status=WorkflowStatus.COMPLETED,
        )
        mock_engine.execute_workflow = AsyncMock(return_value=completed_run)

        supervisor = SupervisorAgent(engine=mock_engine)
        run = await supervisor.handle_alert(
            alert_name="HighCPU",
            namespace="prod",
            severity="critical",
        )
        assert isinstance(run, WorkflowRun)
        assert run.status == WorkflowStatus.COMPLETED
        mock_engine.execute_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_alert_critical_uses_incident_response(self) -> None:
        mock_engine = MagicMock(spec=WorkflowEngine)
        completed_run = WorkflowRun(
            workflow_name="incident_response",
            trigger="alert",
            status=WorkflowStatus.COMPLETED,
        )
        mock_engine.execute_workflow = AsyncMock(return_value=completed_run)

        supervisor = SupervisorAgent(engine=mock_engine)
        await supervisor.handle_alert(alert_name="HighCPU", namespace="prod", severity="critical")
        call_kwargs = mock_engine.execute_workflow.call_args
        assert call_kwargs.kwargs["workflow_name"] == "incident_response"

    @pytest.mark.asyncio
    async def test_handle_alert_high_uses_incident_response(self) -> None:
        mock_engine = MagicMock(spec=WorkflowEngine)
        completed_run = WorkflowRun(
            workflow_name="incident_response",
            trigger="alert",
            status=WorkflowStatus.COMPLETED,
        )
        mock_engine.execute_workflow = AsyncMock(return_value=completed_run)

        supervisor = SupervisorAgent(engine=mock_engine)
        await supervisor.handle_alert(alert_name="HighMem", namespace="prod", severity="high")
        call_kwargs = mock_engine.execute_workflow.call_args
        assert call_kwargs.kwargs["workflow_name"] == "incident_response"

    @pytest.mark.asyncio
    async def test_handle_alert_medium_uses_proactive_check(self) -> None:
        mock_engine = MagicMock(spec=WorkflowEngine)
        completed_run = WorkflowRun(
            workflow_name="proactive_check",
            trigger="alert",
            status=WorkflowStatus.COMPLETED,
        )
        mock_engine.execute_workflow = AsyncMock(return_value=completed_run)

        supervisor = SupervisorAgent(engine=mock_engine)
        await supervisor.handle_alert(
            alert_name="SlowQuery", namespace="staging", severity="medium"
        )
        call_kwargs = mock_engine.execute_workflow.call_args
        assert call_kwargs.kwargs["workflow_name"] == "proactive_check"

    @pytest.mark.asyncio
    async def test_handle_alert_applies_escalation_policy(self) -> None:
        mock_engine = MagicMock(spec=WorkflowEngine)
        completed_run = WorkflowRun(
            workflow_name="incident_response",
            trigger="alert",
            status=WorkflowStatus.COMPLETED,
        )
        mock_engine.execute_workflow = AsyncMock(return_value=completed_run)

        supervisor = SupervisorAgent(engine=mock_engine)
        await supervisor.handle_alert(alert_name="CritAlert", namespace="prod", severity="critical")
        call_kwargs = mock_engine.execute_workflow.call_args
        params = call_kwargs.kwargs["params"]
        # Critical policy: auto_remediate=True, notify slack+pagerduty
        assert params["auto_remediate"] is True
        assert "slack" in params["notify_channels"]
        assert "pagerduty" in params["notify_channels"]

    @pytest.mark.asyncio
    async def test_handle_alert_low_severity_policy(self) -> None:
        mock_engine = MagicMock(spec=WorkflowEngine)
        completed_run = WorkflowRun(
            workflow_name="proactive_check",
            trigger="alert",
            status=WorkflowStatus.COMPLETED,
        )
        mock_engine.execute_workflow = AsyncMock(return_value=completed_run)

        supervisor = SupervisorAgent(engine=mock_engine)
        await supervisor.handle_alert(alert_name="InfoAlert", namespace="dev", severity="low")
        call_kwargs = mock_engine.execute_workflow.call_args
        params = call_kwargs.kwargs["params"]
        assert params["auto_remediate"] is False
        assert params["notify_channels"] == ["email"]

    @pytest.mark.asyncio
    async def test_get_active_runs_returns_running_workflows(self) -> None:
        mock_engine = MagicMock(spec=WorkflowEngine)
        completed_run = WorkflowRun(
            workflow_name="incident_response",
            trigger="alert",
            status=WorkflowStatus.COMPLETED,
        )
        mock_engine.execute_workflow = AsyncMock(return_value=completed_run)

        supervisor = SupervisorAgent(engine=mock_engine)
        await supervisor.handle_alert(alert_name="Test", namespace="prod", severity="critical")
        active = await supervisor.get_active_runs()
        # The completed run is still tracked in _active_runs
        assert len(active) >= 1

    @pytest.mark.asyncio
    async def test_cancel_run_cancels_existing(self) -> None:
        mock_engine = MagicMock(spec=WorkflowEngine)
        run = WorkflowRun(
            workflow_name="incident_response",
            trigger="alert",
            status=WorkflowStatus.RUNNING,
        )
        mock_engine.execute_workflow = AsyncMock(return_value=run)

        supervisor = SupervisorAgent(engine=mock_engine)
        await supervisor.handle_alert(alert_name="Test", namespace="prod", severity="high")

        active = await supervisor.get_active_runs()
        assert len(active) > 0
        run_id = active[0].run_id

        result = await supervisor.cancel_run(run_id)
        assert result is True
        assert active[0].status == WorkflowStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_run_nonexistent_returns_false(self) -> None:
        supervisor = SupervisorAgent()
        result = await supervisor.cancel_run("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_max_concurrent_runs_limit(self) -> None:
        mock_engine = MagicMock(spec=WorkflowEngine)
        running_run = WorkflowRun(
            workflow_name="incident_response",
            trigger="alert",
            status=WorkflowStatus.RUNNING,
        )
        mock_engine.execute_workflow = AsyncMock(return_value=running_run)

        supervisor = SupervisorAgent(engine=mock_engine)

        # Fill up to the max
        for i in range(MAX_CONCURRENT_RUNS):
            run = WorkflowRun(
                workflow_name="test",
                trigger="alert",
                status=WorkflowStatus.RUNNING,
            )
            supervisor._active_runs[f"run-{i}"] = run

        with pytest.raises(RuntimeError, match="Max concurrent runs"):
            await supervisor.handle_alert(
                alert_name="Overflow",
                namespace="prod",
                severity="critical",
            )

    def test_get_policies_returns_defaults(self) -> None:
        supervisor = SupervisorAgent()
        policies = supervisor.get_policies()
        assert len(policies) == len(DEFAULT_POLICIES)
        severities = {p.severity for p in policies}
        assert severities == {"critical", "high", "medium", "low"}

    def test_get_policies_critical_values(self) -> None:
        supervisor = SupervisorAgent()
        policies = {p.severity: p for p in supervisor.get_policies()}
        critical = policies["critical"]
        assert critical.auto_remediate is True
        assert critical.page_oncall is True
        assert critical.max_retries == 1

    @pytest.mark.asyncio
    async def test_handle_alert_retries_on_failure(self) -> None:
        mock_engine = MagicMock(spec=WorkflowEngine)
        failed_run = WorkflowRun(
            workflow_name="incident_response",
            trigger="alert",
            status=WorkflowStatus.FAILED,
        )
        mock_engine.execute_workflow = AsyncMock(return_value=failed_run)

        supervisor = SupervisorAgent(engine=mock_engine)
        run = await supervisor.handle_alert(alert_name="Retry", namespace="prod", severity="medium")
        # medium policy has max_retries=3
        assert mock_engine.execute_workflow.call_count == 3
        assert run.status == WorkflowStatus.FAILED

    @pytest.mark.asyncio
    async def test_handle_alert_stops_retrying_on_success(self) -> None:
        mock_engine = MagicMock(spec=WorkflowEngine)
        failed_run = WorkflowRun(
            workflow_name="incident_response",
            trigger="alert",
            status=WorkflowStatus.FAILED,
        )
        completed_run = WorkflowRun(
            workflow_name="incident_response",
            trigger="alert",
            status=WorkflowStatus.COMPLETED,
        )
        mock_engine.execute_workflow = AsyncMock(side_effect=[failed_run, completed_run])

        supervisor = SupervisorAgent(engine=mock_engine)
        run = await supervisor.handle_alert(
            alert_name="RetrySuccess", namespace="prod", severity="high"
        )
        assert mock_engine.execute_workflow.call_count == 2
        assert run.status == WorkflowStatus.COMPLETED
