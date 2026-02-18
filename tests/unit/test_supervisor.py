"""Comprehensive tests for the Supervisor Agent."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from shieldops.agents.supervisor.graph import (
    after_chain,
    create_supervisor_graph,
    should_chain_or_escalate,
)
from shieldops.agents.supervisor.models import (
    ChainedWorkflow,
    DelegatedTask,
    EscalationRecord,
    EventClassification,
    SupervisorState,
    SupervisorStep,
    TaskStatus,
    TaskType,
)
from shieldops.agents.supervisor.nodes import (
    classify_event,
    dispatch_to_agent,
    escalate,
    evaluate_result,
    finalize,
    set_toolkit,
)
from shieldops.agents.supervisor.runner import SupervisorRunner
from shieldops.agents.supervisor.tools import SupervisorToolkit

# ===========================================================================
# Toolkit Tests
# ===========================================================================


class TestSupervisorToolkit:
    """Tests for SupervisorToolkit."""

    def test_classify_alert(self):
        toolkit = SupervisorToolkit()
        result = toolkit.classify_event_rules({"type": "alert", "severity": "critical"})
        assert result["task_type"] == "investigate"
        assert result["priority"] == "high"
        assert result["confidence"] == 1.0

    def test_classify_incident(self):
        toolkit = SupervisorToolkit()
        result = toolkit.classify_event_rules({"type": "incident"})
        assert result["task_type"] == "investigate"
        assert result["priority"] == "critical"

    def test_classify_cve_alert(self):
        toolkit = SupervisorToolkit()
        result = toolkit.classify_event_rules({"type": "cve_alert"})
        assert result["task_type"] == "security_scan"

    def test_classify_cost_anomaly(self):
        toolkit = SupervisorToolkit()
        result = toolkit.classify_event_rules({"type": "cost_anomaly"})
        assert result["task_type"] == "cost_analysis"

    def test_classify_feedback(self):
        toolkit = SupervisorToolkit()
        result = toolkit.classify_event_rules({"type": "feedback"})
        assert result["task_type"] == "learn"

    def test_classify_unknown_event(self):
        toolkit = SupervisorToolkit()
        result = toolkit.classify_event_rules({"type": "something_new"})
        assert result["task_type"] == "investigate"
        assert result["confidence"] == 0.6

    @pytest.mark.asyncio
    async def test_dispatch_task_no_runner(self):
        toolkit = SupervisorToolkit()
        task = await toolkit.dispatch_task(TaskType.INVESTIGATE, {"type": "alert"})
        assert task.status == TaskStatus.COMPLETED
        assert task.result["simulated"] is True

    @pytest.mark.asyncio
    async def test_dispatch_task_with_runner(self):
        runner = AsyncMock()
        runner.run.return_value = {"confidence_score": 0.9, "recommended_action": "restart_pod"}
        toolkit = SupervisorToolkit(agent_runners={"investigation": runner})
        task = await toolkit.dispatch_task(TaskType.INVESTIGATE, {"type": "alert"})
        assert task.status == TaskStatus.COMPLETED
        assert task.result["confidence_score"] == 0.9

    @pytest.mark.asyncio
    async def test_dispatch_task_runner_failure(self):
        runner = AsyncMock()
        runner.run.side_effect = RuntimeError("agent crashed")
        toolkit = SupervisorToolkit(agent_runners={"investigation": runner})
        task = await toolkit.dispatch_task(TaskType.INVESTIGATE, {"type": "alert"})
        assert task.status == TaskStatus.FAILED
        assert "agent crashed" in task.error

    @pytest.mark.asyncio
    async def test_send_escalation_no_channel(self):
        toolkit = SupervisorToolkit()
        result = await toolkit.send_escalation("slack", "test message")
        assert result["delivered"] is True
        assert result["simulated"] is True

    @pytest.mark.asyncio
    async def test_send_escalation_with_channel(self):
        channel = AsyncMock()
        channel.send.return_value = {"delivered": True, "message_id": "123"}
        toolkit = SupervisorToolkit(notification_channels={"slack": channel})
        result = await toolkit.send_escalation("slack", "test message")
        assert result["delivered"] is True
        channel.send.assert_awaited_once()

    def test_evaluate_chain_investigation_high_confidence(self):
        toolkit = SupervisorToolkit()
        task = DelegatedTask(
            task_id="t1",
            task_type=TaskType.INVESTIGATE,
            agent_name="investigation",
            status=TaskStatus.COMPLETED,
            result={"confidence_score": 0.9, "recommended_action": "restart_pod"},
        )
        result = toolkit.evaluate_chain_rules(task)
        assert result["should_chain"] is True
        assert result["chain_task_type"] == "remediate"

    def test_evaluate_chain_investigation_low_confidence(self):
        toolkit = SupervisorToolkit()
        task = DelegatedTask(
            task_id="t1",
            task_type=TaskType.INVESTIGATE,
            agent_name="investigation",
            status=TaskStatus.COMPLETED,
            result={"confidence_score": 0.5, "recommended_action": "restart_pod"},
        )
        result = toolkit.evaluate_chain_rules(task)
        assert result["should_chain"] is False

    def test_evaluate_chain_remediation_triggers_learn(self):
        toolkit = SupervisorToolkit()
        task = DelegatedTask(
            task_id="t1",
            task_type=TaskType.REMEDIATE,
            agent_name="remediation",
            status=TaskStatus.COMPLETED,
            result={"status": "success"},
        )
        result = toolkit.evaluate_chain_rules(task)
        assert result["should_chain"] is True
        assert result["chain_task_type"] == "learn"

    def test_evaluate_chain_failed_task(self):
        toolkit = SupervisorToolkit()
        task = DelegatedTask(
            task_id="t1",
            task_type=TaskType.INVESTIGATE,
            agent_name="investigation",
            status=TaskStatus.FAILED,
            error="crashed",
        )
        result = toolkit.evaluate_chain_rules(task)
        assert result["should_chain"] is False

    def test_evaluate_escalation_failed_critical(self):
        toolkit = SupervisorToolkit()
        task = DelegatedTask(
            task_id="t1",
            task_type=TaskType.INVESTIGATE,
            agent_name="investigation",
            status=TaskStatus.FAILED,
            error="timeout",
        )
        result = toolkit.evaluate_escalation_rules(task, {"priority": "critical"})
        assert result["needs_escalation"] is True
        assert result["channel"] == "pagerduty"

    def test_evaluate_escalation_low_confidence(self):
        toolkit = SupervisorToolkit()
        task = DelegatedTask(
            task_id="t1",
            task_type=TaskType.INVESTIGATE,
            agent_name="investigation",
            status=TaskStatus.COMPLETED,
            result={},
        )
        result = toolkit.evaluate_escalation_rules(
            task, {"priority": "critical", "confidence": 0.3}
        )
        assert result["needs_escalation"] is True

    def test_evaluate_escalation_not_needed(self):
        toolkit = SupervisorToolkit()
        task = DelegatedTask(
            task_id="t1",
            task_type=TaskType.INVESTIGATE,
            agent_name="investigation",
            status=TaskStatus.COMPLETED,
            result={},
        )
        result = toolkit.evaluate_escalation_rules(task, {"priority": "medium", "confidence": 0.9})
        assert result["needs_escalation"] is False


# ===========================================================================
# Node Tests
# ===========================================================================


class TestClassifyEventNode:
    """Tests for classify_event node."""

    @pytest.mark.asyncio
    async def test_classify_known_event(self):
        toolkit = SupervisorToolkit()
        set_toolkit(toolkit)

        state = SupervisorState(
            session_id="test-001", event={"type": "alert", "severity": "critical"}
        )
        result = await classify_event(state)

        assert result["classification"] is not None
        assert result["classification"].task_type == TaskType.INVESTIGATE
        assert result["current_step"] == "classify_event"

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_classify_unknown_event_uses_llm(self):
        toolkit = SupervisorToolkit()
        set_toolkit(toolkit)

        state = SupervisorState(session_id="test-002", event={"type": "unknown_event"})

        with patch(
            "shieldops.agents.supervisor.nodes.llm_structured", side_effect=RuntimeError("skip")
        ):
            result = await classify_event(state)

        # Falls back to rule-based classification
        assert result["classification"].task_type == TaskType.INVESTIGATE
        assert result["classification"].confidence == 0.6

        set_toolkit(None)


class TestDispatchToAgentNode:
    """Tests for dispatch_to_agent node."""

    @pytest.mark.asyncio
    async def test_dispatch_success(self):
        toolkit = SupervisorToolkit()
        set_toolkit(toolkit)

        state = SupervisorState(
            session_id="test-003",
            classification=EventClassification(
                event_type="alert", task_type=TaskType.INVESTIGATE, priority="high"
            ),
            reasoning_chain=[],
        )
        result = await dispatch_to_agent(state)

        assert result["active_task"] is not None
        assert result["active_task"].agent_name == "investigation"
        assert len(result["delegated_tasks"]) == 1

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_dispatch_no_classification(self):
        toolkit = SupervisorToolkit()
        set_toolkit(toolkit)

        state = SupervisorState(session_id="test-004", classification=None)
        result = await dispatch_to_agent(state)

        assert result["error"] is not None

        set_toolkit(None)


class TestEvaluateResultNode:
    """Tests for evaluate_result node."""

    @pytest.mark.asyncio
    async def test_evaluate_completed_task(self):
        toolkit = SupervisorToolkit()
        set_toolkit(toolkit)

        state = SupervisorState(
            session_id="test-005",
            active_task=DelegatedTask(
                task_id="t1",
                task_type=TaskType.INVESTIGATE,
                agent_name="investigation",
                status=TaskStatus.COMPLETED,
                result={"confidence_score": 0.9, "recommended_action": "restart_pod"},
            ),
            classification=EventClassification(
                event_type="alert", task_type=TaskType.INVESTIGATE, priority="high"
            ),
            reasoning_chain=[],
        )

        with patch(
            "shieldops.agents.supervisor.nodes.llm_structured", side_effect=RuntimeError("skip")
        ):
            result = await evaluate_result(state)

        assert result["should_chain"] is True
        assert result["current_step"] == "evaluate_result"

        set_toolkit(None)


class TestEscalateNode:
    """Tests for escalate node."""

    @pytest.mark.asyncio
    async def test_escalate_failed_task(self):
        toolkit = SupervisorToolkit()
        set_toolkit(toolkit)

        state = SupervisorState(
            session_id="test-006",
            active_task=DelegatedTask(
                task_id="t1",
                task_type=TaskType.INVESTIGATE,
                agent_name="investigation",
                status=TaskStatus.FAILED,
                error="timeout",
            ),
            classification=EventClassification(
                event_type="alert", task_type=TaskType.INVESTIGATE, priority="critical"
            ),
            reasoning_chain=[],
        )
        result = await escalate(state)

        assert len(result["escalations"]) == 1
        assert result["escalations"][0].reason is not None

        set_toolkit(None)


class TestFinalizeNode:
    """Tests for finalize node."""

    @pytest.mark.asyncio
    async def test_finalize(self):
        state = SupervisorState(
            session_id="test-007",
            session_start=datetime.now(UTC) - timedelta(seconds=2),
            delegated_tasks=[
                DelegatedTask(
                    task_id="t1", task_type=TaskType.INVESTIGATE, agent_name="investigation"
                )
            ],
            reasoning_chain=[],
        )
        result = await finalize(state)

        assert result["current_step"] == "complete"
        assert result["session_duration_ms"] > 0


# ===========================================================================
# Graph Routing Tests
# ===========================================================================


class TestGraphRouting:
    """Tests for conditional routing functions."""

    def test_should_chain(self):
        state = SupervisorState(should_chain=True, chain_task_type=TaskType.REMEDIATE)
        assert should_chain_or_escalate(state) == "chain_followup"

    def test_should_escalate(self):
        state = SupervisorState(needs_escalation=True)
        assert should_chain_or_escalate(state) == "escalate"

    def test_should_finalize(self):
        state = SupervisorState()
        assert should_chain_or_escalate(state) == "finalize"

    def test_should_finalize_on_error(self):
        state = SupervisorState(should_chain=True, error="broken")
        assert should_chain_or_escalate(state) == "finalize"

    def test_chain_then_escalate(self):
        state = SupervisorState(should_chain=True, needs_escalation=True)
        # Chain takes priority, then after_chain checks escalation
        assert should_chain_or_escalate(state) == "chain_followup"

    def test_after_chain_escalate(self):
        state = SupervisorState(needs_escalation=True)
        assert after_chain(state) == "escalate"

    def test_after_chain_finalize(self):
        state = SupervisorState(needs_escalation=False)
        assert after_chain(state) == "finalize"


class TestGraphConstruction:
    """Tests for graph construction."""

    def test_create_supervisor_graph(self):
        graph = create_supervisor_graph()
        compiled = graph.compile()
        assert compiled is not None


# ===========================================================================
# Runner Tests
# ===========================================================================


class TestSupervisorRunner:
    """Tests for SupervisorRunner."""

    def test_runner_init(self):
        runner = SupervisorRunner()
        assert runner.list_sessions() == []

    @pytest.mark.asyncio
    async def test_handle_event_returns_state(self):
        runner = SupervisorRunner()

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(
                return_value=SupervisorState(
                    session_id="sup-test",
                    current_step="complete",
                    session_start=datetime.now(UTC),
                    delegated_tasks=[
                        DelegatedTask(
                            task_id="t1", task_type=TaskType.INVESTIGATE, agent_name="investigation"
                        ),
                    ],
                ).model_dump()
            )

            result = await runner.handle_event({"type": "alert"})

        assert result.current_step == "complete"
        assert len(runner.list_sessions()) == 1

    @pytest.mark.asyncio
    async def test_handle_event_error(self):
        runner = SupervisorRunner()

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(side_effect=RuntimeError("graph failed"))
            result = await runner.handle_event({"type": "alert"})

        assert result.current_step == "failed"
        assert result.error == "graph failed"

    def test_list_sessions_empty(self):
        runner = SupervisorRunner()
        assert runner.list_sessions() == []

    def test_get_session_not_found(self):
        runner = SupervisorRunner()
        assert runner.get_session("nonexistent") is None


# ===========================================================================
# API Tests
# ===========================================================================


class TestSupervisorAPI:
    """Tests for supervisor API endpoints."""

    def _make_app(self):
        from shieldops.api.routes import supervisor as supervisor_module

        runner = SupervisorRunner()
        supervisor_module.set_runner(runner)

        from shieldops.api.app import create_app
        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole

        app = create_app()

        def _mock_admin_user():
            return UserResponse(
                id="test-admin",
                email="admin@test.com",
                name="Test Admin",
                role=UserRole.ADMIN,
                is_active=True,
            )

        app.dependency_overrides[get_current_user] = _mock_admin_user

        return TestClient(app), runner

    def test_list_sessions(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/supervisor/sessions")
        assert resp.status_code == 200
        assert resp.json()["sessions"] == []

    def test_get_session_not_found(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/supervisor/sessions/nonexistent")
        assert resp.status_code == 404

    def test_get_session_found(self):
        client, runner = self._make_app()
        state = SupervisorState(
            session_id="sup-123",
            event={"type": "alert"},
            current_step="complete",
        )
        runner._sessions["sup-123"] = state

        resp = client.get("/api/v1/supervisor/sessions/sup-123")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "sup-123"

    def test_submit_event_async(self):
        client, _ = self._make_app()
        resp = client.post(
            "/api/v1/supervisor/events",
            json={
                "type": "alert",
                "severity": "critical",
                "source": "prometheus",
            },
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"

    def test_submit_event_sync(self):
        client, runner = self._make_app()

        async def mock_handle(**kwargs):
            return SupervisorState(
                session_id="sup-sync",
                event=kwargs.get("event", {}),
                current_step="complete",
            )

        runner.handle_event = mock_handle

        resp = client.post(
            "/api/v1/supervisor/events/sync",
            json={
                "type": "incident",
                "severity": "critical",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["current_step"] == "complete"

    def test_get_session_tasks(self):
        client, runner = self._make_app()
        state = SupervisorState(
            session_id="sup-tasks",
            event={"type": "alert"},
            delegated_tasks=[
                DelegatedTask(
                    task_id="t1", task_type=TaskType.INVESTIGATE, agent_name="investigation"
                ),
                DelegatedTask(task_id="t2", task_type=TaskType.REMEDIATE, agent_name="remediation"),
            ],
        )
        runner._sessions["sup-tasks"] = state

        resp = client.get("/api/v1/supervisor/sessions/sup-tasks/tasks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_get_session_tasks_not_found(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/supervisor/sessions/nope/tasks")
        assert resp.status_code == 404

    def test_get_session_escalations(self):
        client, runner = self._make_app()
        state = SupervisorState(
            session_id="sup-esc",
            event={"type": "alert"},
            escalations=[
                EscalationRecord(escalation_id="esc-1", reason="agent failed", channel="slack"),
            ],
        )
        runner._sessions["sup-esc"] = state

        resp = client.get("/api/v1/supervisor/sessions/sup-esc/escalations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_get_session_escalations_not_found(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/supervisor/sessions/nope/escalations")
        assert resp.status_code == 404


# ===========================================================================
# Model Tests
# ===========================================================================


class TestSupervisorModels:
    """Tests for supervisor data models."""

    def test_event_classification(self):
        ec = EventClassification(
            event_type="alert",
            task_type=TaskType.INVESTIGATE,
            priority="critical",
            confidence=0.95,
        )
        assert ec.task_type == TaskType.INVESTIGATE

    def test_delegated_task(self):
        task = DelegatedTask(
            task_id="t1",
            task_type=TaskType.REMEDIATE,
            agent_name="remediation",
            status=TaskStatus.COMPLETED,
        )
        assert task.status == TaskStatus.COMPLETED

    def test_escalation_record(self):
        esc = EscalationRecord(
            escalation_id="esc-1",
            reason="agent failed",
            channel="pagerduty",
        )
        assert esc.acknowledged is False

    def test_chained_workflow(self):
        chain = ChainedWorkflow(
            source_task_id="t1",
            source_task_type=TaskType.INVESTIGATE,
            chained_task_id="t2",
            chained_task_type=TaskType.REMEDIATE,
        )
        assert chain.chained_task_type == TaskType.REMEDIATE

    def test_supervisor_step(self):
        step = SupervisorStep(
            step_number=1,
            action="classify_event",
            input_summary="test",
            output_summary="test",
        )
        assert step.step_number == 1

    def test_supervisor_state_defaults(self):
        state = SupervisorState()
        assert state.delegated_tasks == []
        assert state.escalations == []
        assert state.chained_workflows == []
        assert state.current_step == "pending"
        assert state.should_chain is False
        assert state.needs_escalation is False
