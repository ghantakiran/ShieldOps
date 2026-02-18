"""Tests for the orchestration supervisor module."""

import pytest

from shieldops.orchestration.supervisor import Supervisor, SupervisorTask, TaskType


class TestTaskType:
    """Tests for TaskType enum."""

    def test_enum_values(self):
        assert TaskType.INVESTIGATE == "investigate"
        assert TaskType.REMEDIATE == "remediate"
        assert TaskType.SECURITY_SCAN == "security_scan"
        assert TaskType.LEARN == "learn"

    def test_enum_members(self):
        assert len(TaskType) == 4


class TestSupervisorTask:
    """Tests for SupervisorTask model."""

    def test_defaults(self):
        task = SupervisorTask(id="t-1", task_type=TaskType.INVESTIGATE)
        assert task.status == "pending"
        assert task.agent_id is None
        assert task.input_data == {}
        assert task.completed_at is None
        assert task.result is None
        assert task.error is None
        assert task.created_at is not None

    def test_with_input_data(self):
        task = SupervisorTask(
            id="t-2",
            task_type=TaskType.REMEDIATE,
            input_data={"action": "restart_pod"},
        )
        assert task.input_data["action"] == "restart_pod"


class TestSupervisor:
    """Tests for Supervisor orchestrator."""

    @pytest.mark.asyncio
    async def test_handle_alert_event(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "alert", "severity": "critical"})
        assert task.task_type == TaskType.INVESTIGATE
        assert task.input_data["type"] == "alert"
        assert task.id in supervisor._active_tasks

    @pytest.mark.asyncio
    async def test_handle_incident_event(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "incident"})
        assert task.task_type == TaskType.INVESTIGATE

    @pytest.mark.asyncio
    async def test_handle_remediation_request(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "remediation_request"})
        assert task.task_type == TaskType.REMEDIATE

    @pytest.mark.asyncio
    async def test_handle_auto_heal(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "auto_heal"})
        assert task.task_type == TaskType.REMEDIATE

    @pytest.mark.asyncio
    async def test_handle_cve_alert(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "cve_alert"})
        assert task.task_type == TaskType.SECURITY_SCAN

    @pytest.mark.asyncio
    async def test_handle_compliance_drift(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "compliance_drift"})
        assert task.task_type == TaskType.SECURITY_SCAN

    @pytest.mark.asyncio
    async def test_handle_credential_expiry(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "credential_expiry"})
        assert task.task_type == TaskType.SECURITY_SCAN

    @pytest.mark.asyncio
    async def test_handle_feedback_event(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "feedback"})
        assert task.task_type == TaskType.LEARN

    @pytest.mark.asyncio
    async def test_handle_incident_resolved(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "incident_resolved"})
        assert task.task_type == TaskType.LEARN

    @pytest.mark.asyncio
    async def test_handle_unknown_event_defaults_to_investigate(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "something_unknown"})
        assert task.task_type == TaskType.INVESTIGATE

    @pytest.mark.asyncio
    async def test_chain_investigation_to_remediation_high_confidence(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "alert"})
        task.status = "completed"
        task.result = {"confidence_score": 0.9, "recommended_action": "restart_pod"}

        remediation = await supervisor.chain_investigation_to_remediation(task.id)
        assert remediation is not None
        assert remediation.task_type == TaskType.REMEDIATE
        assert remediation.input_data["investigation_id"] == task.id
        assert remediation.input_data["action"] == "restart_pod"
        assert remediation.id in supervisor._active_tasks

    @pytest.mark.asyncio
    async def test_chain_investigation_low_confidence_returns_none(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "alert"})
        task.status = "completed"
        task.result = {"confidence_score": 0.5, "recommended_action": "restart_pod"}

        remediation = await supervisor.chain_investigation_to_remediation(task.id)
        assert remediation is None

    @pytest.mark.asyncio
    async def test_chain_investigation_no_action_returns_none(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "alert"})
        task.status = "completed"
        task.result = {"confidence_score": 0.95}

        remediation = await supervisor.chain_investigation_to_remediation(task.id)
        assert remediation is None

    @pytest.mark.asyncio
    async def test_chain_investigation_no_result_returns_none(self):
        supervisor = Supervisor()
        task = await supervisor.handle_event({"type": "alert"})
        # task.result is None by default

        remediation = await supervisor.chain_investigation_to_remediation(task.id)
        assert remediation is None

    @pytest.mark.asyncio
    async def test_chain_investigation_unknown_task_returns_none(self):
        supervisor = Supervisor()
        remediation = await supervisor.chain_investigation_to_remediation("nonexistent")
        assert remediation is None
