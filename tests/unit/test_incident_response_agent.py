"""Tests for the Incident Response Agent LangGraph workflow.

Covers:
- IncidentResponseState model creation, defaults, and field types
- Sub-models: ContainmentAction, EradicationStep, RecoveryTask, ResponseReasoningStep
- Prompt schemas: AssessmentOutput, ContainmentPlanOutput, RecoveryPlanOutput
- IncidentResponseToolkit initialization and async methods
- Graph creation (create_incident_response_graph returns a StateGraph)
- IncidentResponseRunner initialization and list_results
- Node functions with mock state
- Conditional edges (should_contain, should_validate)
- Integration: full workflow with simple inputs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.incident_response.graph import (
    create_incident_response_graph,
    should_contain,
    should_validate,
)
from shieldops.agents.incident_response.models import (
    ContainmentAction,
    EradicationStep,
    IncidentResponseState,
    RecoveryTask,
    ResponseReasoningStep,
)
from shieldops.agents.incident_response.nodes import (
    _get_toolkit,
    assess_incident,
    execute_containment,
    finalize_response,
    plan_containment,
    plan_eradication,
    plan_recovery,
    set_toolkit,
    validate_response,
)
from shieldops.agents.incident_response.prompts import (
    AssessmentOutput,
    ContainmentPlanOutput,
    RecoveryPlanOutput,
)
from shieldops.agents.incident_response.runner import IncidentResponseRunner
from shieldops.agents.incident_response.tools import IncidentResponseToolkit

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_toolkit():
    """Reset the module-level toolkit singleton between tests."""
    import shieldops.agents.incident_response.nodes as nodes_mod

    original = nodes_mod._toolkit
    nodes_mod._toolkit = None
    yield
    nodes_mod._toolkit = original


@pytest.fixture
def base_state() -> IncidentResponseState:
    return IncidentResponseState(
        incident_id="inc-001",
        incident_data={"severity": "high", "type": "malware", "affected_host": "host-1"},
    )


@pytest.fixture
def assessed_state() -> IncidentResponseState:
    return IncidentResponseState(
        incident_id="inc-002",
        incident_data={
            "severity": "critical",
            "type": "ransomware",
            "affected_host": "host-2",
            "malware_detected": True,
            "malware_process": "evil.exe",
            "affected_services": ["web-app", "api-svc"],
        },
        severity="critical",
        assessment_score=95.0,
        incident_type="ransomware",
    )


# -- TestState ---------------------------------------------------------------


class TestState:
    def test_default_values(self):
        state = IncidentResponseState()
        assert state.incident_id == ""
        assert state.incident_data == {}
        assert state.severity == "medium"
        assert state.assessment_score == pytest.approx(0.0)
        assert state.incident_type == ""
        assert state.containment_actions == []
        assert state.containment_complete is False
        assert state.eradication_steps == []
        assert state.eradication_complete is False
        assert state.recovery_tasks == []
        assert state.recovery_complete is False
        assert state.validation_passed is False
        assert state.validation_results == {}
        assert state.session_start is None
        assert state.session_duration_ms == 0
        assert state.reasoning_chain == []
        assert state.current_step == "init"
        assert state.error is None

    def test_creation_with_custom_values(self, base_state: IncidentResponseState):
        assert base_state.incident_id == "inc-001"
        assert base_state.incident_data["severity"] == "high"
        assert base_state.incident_data["type"] == "malware"

    def test_list_fields_are_independent(self):
        s1 = IncidentResponseState()
        s2 = IncidentResponseState()
        s1.containment_actions.append(ContainmentAction(action_id="c-1"))
        assert s2.containment_actions == []

    def test_state_with_error(self):
        state = IncidentResponseState(error="timeout", current_step="failed")
        assert state.error == "timeout"
        assert state.current_step == "failed"


# -- TestSubModels -----------------------------------------------------------


class TestSubModels:
    def test_containment_action_defaults(self):
        action = ContainmentAction()
        assert action.action_id == ""
        assert action.action_type == ""
        assert action.target == ""
        assert action.status == "pending"
        assert action.risk_level == "medium"
        assert action.automated is False
        assert action.result == {}

    def test_eradication_step_defaults(self):
        step = EradicationStep()
        assert step.step_id == ""
        assert step.step_type == ""
        assert step.target == ""
        assert step.status == "pending"
        assert step.description == ""

    def test_recovery_task_defaults(self):
        task = RecoveryTask()
        assert task.task_id == ""
        assert task.task_type == ""
        assert task.service == ""
        assert task.status == "pending"
        assert task.priority == "medium"
        assert task.estimated_duration_min == 0

    def test_reasoning_step_creation(self):
        step = ResponseReasoningStep(
            step_number=1,
            action="assess_incident",
            input_summary="Incident inc-001",
            output_summary="Assessed",
        )
        assert step.step_number == 1
        assert step.action == "assess_incident"
        assert step.duration_ms == 0
        assert step.tool_used is None

    def test_containment_action_with_all_fields(self):
        action = ContainmentAction(
            action_id="c-001",
            action_type="network_isolation",
            target="host-1",
            status="completed",
            risk_level="high",
            automated=True,
            result={"status": "ok"},
        )
        assert action.automated is True
        assert action.result["status"] == "ok"

    def test_recovery_task_with_all_fields(self):
        task = RecoveryTask(
            task_id="r-001",
            task_type="service_restart",
            service="web-app",
            status="completed",
            priority="critical",
            estimated_duration_min=30,
        )
        assert task.estimated_duration_min == 30


# -- TestPromptSchemas -------------------------------------------------------


class TestPromptSchemas:
    def test_assessment_output_fields(self):
        output = AssessmentOutput(
            severity="critical",
            assessment_score=95.0,
            incident_type="ransomware",
            reasoning="Active ransomware detected",
        )
        assert output.assessment_score == pytest.approx(95.0)
        assert output.severity == "critical"

    def test_containment_plan_output_fields(self):
        output = ContainmentPlanOutput(
            actions=[{"type": "isolate", "target": "host-1"}],
            auto_executable=True,
            reasoning="Host shows active threat",
        )
        assert len(output.actions) == 1
        assert output.auto_executable is True

    def test_recovery_plan_output_fields(self):
        output = RecoveryPlanOutput(
            tasks=[{"type": "restart", "service": "web-app"}],
            estimated_duration_min=45,
            reasoning="Services need restart after containment",
        )
        assert len(output.tasks) == 1
        assert output.estimated_duration_min == 45


# -- TestToolkit -------------------------------------------------------------


class TestToolkit:
    def test_toolkit_initialization_with_no_deps(self):
        toolkit = IncidentResponseToolkit()
        assert toolkit._containment_engine is None
        assert toolkit._eradication_planner is None
        assert toolkit._recovery_orchestrator is None

    def test_toolkit_initialization_with_deps(self):
        mock_engine = MagicMock()
        toolkit = IncidentResponseToolkit(containment_engine=mock_engine)
        assert toolkit._containment_engine is mock_engine

    @pytest.mark.asyncio
    async def test_assess_incident_returns_expected_keys(self):
        toolkit = IncidentResponseToolkit()
        result = await toolkit.assess_incident({"type": "malware"})
        assert "severity" in result
        assert "assessment_score" in result
        assert "incident_type" in result

    @pytest.mark.asyncio
    async def test_execute_containment_returns_status(self):
        toolkit = IncidentResponseToolkit()
        result = await toolkit.execute_containment("network_isolation", "host-1")
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_plan_eradication_returns_list(self):
        toolkit = IncidentResponseToolkit()
        result = await toolkit.plan_eradication("malware")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_execute_recovery_returns_status(self):
        toolkit = IncidentResponseToolkit()
        result = await toolkit.execute_recovery("web-app", "service_restart")
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_validate_recovery_returns_passed(self):
        toolkit = IncidentResponseToolkit()
        result = await toolkit.validate_recovery("inc-001")
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_record_response_metric(self):
        toolkit = IncidentResponseToolkit()
        await toolkit.record_response_metric("assessment", 85.0)


# -- TestGraph ---------------------------------------------------------------


class TestGraph:
    def test_create_graph_returns_state_graph(self):
        graph = create_incident_response_graph()
        assert graph is not None
        assert hasattr(graph, "compile")

    def test_graph_has_expected_nodes(self):
        graph = create_incident_response_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "assess_incident",
            "plan_containment",
            "execute_containment",
            "plan_eradication",
            "plan_recovery",
            "validate_response",
            "finalize_response",
        }
        assert expected.issubset(node_names)

    def test_graph_compiles_without_error(self):
        graph = create_incident_response_graph()
        app = graph.compile()
        assert app is not None


# -- TestRunner --------------------------------------------------------------


class TestRunner:
    def test_runner_initialization(self):
        with patch(
            "shieldops.agents.incident_response.runner.create_incident_response_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = IncidentResponseRunner()
            assert runner._results == {}

    def test_list_results_empty(self):
        with patch(
            "shieldops.agents.incident_response.runner.create_incident_response_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = IncidentResponseRunner()
            assert runner.list_results() == []

    def test_list_results_returns_summaries(self):
        with patch(
            "shieldops.agents.incident_response.runner.create_incident_response_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = IncidentResponseRunner()
            runner._results["ir-abc"] = IncidentResponseState(
                incident_id="inc-001",
                severity="high",
                assessment_score=80.0,
                current_step="complete",
            )
            summaries = runner.list_results()
            assert len(summaries) == 1
            assert summaries[0]["incident_id"] == "inc-001"
            assert summaries[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_respond_success(self):
        mock_app = AsyncMock()
        final_state = IncidentResponseState(
            incident_id="inc-001",
            severity="high",
            assessment_score=80.0,
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch(
            "shieldops.agents.incident_response.runner.create_incident_response_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = IncidentResponseRunner()
            result = await runner.respond(incident_id="inc-001")

        assert isinstance(result, IncidentResponseState)
        assert result.current_step == "complete"

    @pytest.mark.asyncio
    async def test_respond_handles_exception(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.side_effect = RuntimeError("Graph exploded")

        with patch(
            "shieldops.agents.incident_response.runner.create_incident_response_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = IncidentResponseRunner()
            result = await runner.respond(incident_id="inc-x")

        assert result.error == "Graph exploded"
        assert result.current_step == "failed"


# -- TestNodes ---------------------------------------------------------------


class TestNodes:
    @pytest.mark.asyncio
    async def test_assess_incident_critical(self):
        state = IncidentResponseState(
            incident_id="inc-crit",
            incident_data={"severity": "critical", "type": "ransomware"},
        )
        result = await assess_incident(state)
        assert result["assessment_score"] == pytest.approx(95.0)
        assert result["severity"] == "critical"
        assert result["incident_type"] == "ransomware"
        assert result["current_step"] == "assess_incident"
        assert len(result["reasoning_chain"]) == 1

    @pytest.mark.asyncio
    async def test_assess_incident_high(self):
        state = IncidentResponseState(
            incident_id="inc-high",
            incident_data={"severity": "high", "type": "malware"},
        )
        result = await assess_incident(state)
        assert result["assessment_score"] == pytest.approx(80.0)
        assert result["severity"] == "high"

    @pytest.mark.asyncio
    async def test_assess_incident_low(self):
        state = IncidentResponseState(
            incident_id="inc-low",
            incident_data={"severity": "low", "type": "policy_violation"},
        )
        result = await assess_incident(state)
        assert result["assessment_score"] == pytest.approx(25.0)
        assert result["incident_type"] == "policy_violation"

    @pytest.mark.asyncio
    async def test_plan_containment_high_score(self, assessed_state: IncidentResponseState):
        result = await plan_containment(assessed_state)
        assert len(result["containment_actions"]) >= 1
        assert result["current_step"] == "plan_containment"

    @pytest.mark.asyncio
    async def test_plan_containment_low_score(self):
        state = IncidentResponseState(
            incident_id="inc-low",
            assessment_score=30.0,
            severity="low",
        )
        result = await plan_containment(state)
        assert len(result["containment_actions"]) == 0

    @pytest.mark.asyncio
    async def test_execute_containment_auto(self):
        state = IncidentResponseState(
            incident_id="inc-auto",
            containment_actions=[
                ContainmentAction(
                    action_id="c-1",
                    action_type="process_kill",
                    target="evil.exe",
                    automated=True,
                ),
            ],
        )
        result = await execute_containment(state)
        assert result["containment_complete"] is True
        assert result["current_step"] == "execute_containment"

    @pytest.mark.asyncio
    async def test_plan_eradication(self, assessed_state: IncidentResponseState):
        result = await plan_eradication(assessed_state)
        assert len(result["eradication_steps"]) >= 1
        assert result["eradication_complete"] is True

    @pytest.mark.asyncio
    async def test_plan_recovery_with_services(self, assessed_state: IncidentResponseState):
        result = await plan_recovery(assessed_state)
        assert len(result["recovery_tasks"]) >= 2
        assert result["current_step"] == "plan_recovery"

    @pytest.mark.asyncio
    async def test_plan_recovery_no_services(self):
        state = IncidentResponseState(incident_id="inc-none", severity="low")
        result = await plan_recovery(state)
        assert len(result["recovery_tasks"]) == 1
        assert result["recovery_tasks"][0].task_type == "health_check"

    @pytest.mark.asyncio
    async def test_validate_response(self):
        state = IncidentResponseState(incident_id="inc-val")
        result = await validate_response(state)
        assert result["validation_passed"] is True
        assert result["recovery_complete"] is True

    @pytest.mark.asyncio
    async def test_finalize_response(self):
        state = IncidentResponseState(
            incident_id="inc-fin",
            session_start=datetime.now(UTC),
        )
        result = await finalize_response(state)
        assert result["current_step"] == "complete"
        assert result["session_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_finalize_no_session_start(self):
        state = IncidentResponseState(incident_id="inc-no-start")
        result = await finalize_response(state)
        assert result["session_duration_ms"] == 0


# -- TestConditionalEdges ----------------------------------------------------


class TestConditionalEdges:
    def test_should_contain_high_score(self):
        state = IncidentResponseState(assessment_score=80.0)
        assert should_contain(state) == "plan_containment"

    def test_should_contain_exact_threshold(self):
        state = IncidentResponseState(assessment_score=50.0)
        assert should_contain(state) == "plan_containment"

    def test_should_contain_low_score(self):
        state = IncidentResponseState(assessment_score=30.0)
        assert should_contain(state) == "plan_recovery"

    def test_should_contain_error(self):
        state = IncidentResponseState(error="failed")
        assert should_contain(state) == "finalize_response"

    def test_should_validate_with_tasks(self):
        state = IncidentResponseState(
            recovery_tasks=[RecoveryTask(task_id="r-1")],
        )
        assert should_validate(state) == "validate_response"

    def test_should_validate_no_tasks(self):
        state = IncidentResponseState()
        assert should_validate(state) == "finalize_response"


# -- TestToolkitManagement ---------------------------------------------------


class TestToolkitManagement:
    def test_get_toolkit_returns_default_when_none_set(self):
        toolkit = _get_toolkit()
        assert isinstance(toolkit, IncidentResponseToolkit)

    def test_set_toolkit_is_used_by_get_toolkit(self):
        custom = IncidentResponseToolkit(containment_engine=MagicMock())
        set_toolkit(custom)
        assert _get_toolkit() is custom


# -- TestIntegration ---------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_low_severity(self):
        """Low-severity alert goes through triage with low score."""
        state = IncidentResponseState(
            incident_id="inc-int-1",
            incident_data={"severity": "low", "type": "policy_violation"},
        )
        result = await assess_incident(state)
        assert result["assessment_score"] == pytest.approx(25.0)
        assert (
            should_contain(IncidentResponseState(**{**state.model_dump(), **result}))
            == "plan_recovery"
        )

    @pytest.mark.asyncio
    async def test_full_workflow_high_severity_path(self):
        """High-severity incident goes through assess -> containment -> eradication -> recovery."""
        state = IncidentResponseState(
            incident_id="inc-int-2",
            incident_data={
                "severity": "high",
                "type": "malware",
                "affected_host": "host-99",
                "affected_services": ["web-app"],
            },
        )
        assess_result = await assess_incident(state)
        assert assess_result["assessment_score"] == pytest.approx(80.0)

        state_after_assess = IncidentResponseState(**{**state.model_dump(), **assess_result})
        assert should_contain(state_after_assess) == "plan_containment"

        contain_result = await plan_containment(state_after_assess)
        assert len(contain_result["containment_actions"]) >= 1

        state_after_contain = IncidentResponseState(
            **{**state_after_assess.model_dump(), **contain_result}
        )
        exec_result = await execute_containment(state_after_contain)
        assert exec_result["current_step"] == "execute_containment"

    @pytest.mark.asyncio
    async def test_full_workflow_critical_with_malware(self):
        """Critical ransomware incident generates containment with malware kill."""
        state = IncidentResponseState(
            incident_id="inc-int-3",
            incident_data={
                "severity": "critical",
                "type": "ransomware",
                "affected_host": "host-3",
                "malware_detected": True,
                "malware_process": "evil.exe",
                "affected_services": ["api-svc", "db-svc"],
            },
        )
        assess_result = await assess_incident(state)
        assert assess_result["assessment_score"] == pytest.approx(95.0)

        state_after_assess = IncidentResponseState(**{**state.model_dump(), **assess_result})
        contain_result = await plan_containment(state_after_assess)
        # Critical severity with malware should produce 2 actions:
        # network_isolation + process_kill
        assert len(contain_result["containment_actions"]) == 2
        action_types = [a.action_type for a in contain_result["containment_actions"]]
        assert "network_isolation" in action_types
        assert "process_kill" in action_types
        # Critical severity means network_isolation is NOT automated (severity == "critical")
        net_action = [
            a for a in contain_result["containment_actions"] if a.action_type == "network_isolation"
        ][0]
        assert net_action.automated is False
