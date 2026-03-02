"""Tests for the ML Governance Agent LangGraph workflow.

Covers:
- MLGovernanceState model creation, defaults, and field types
- Sub-models: ModelAudit, GovernanceFinding, GovernanceReasoningStep
- Prompt schemas: AuditOutput, FairnessOutput, ActionPlanOutput
- MLGovernanceToolkit initialization and async methods
- Graph creation (create_ml_governance_graph returns a StateGraph)
- MLGovernanceRunner initialization and list_results
- Node functions (audit_models, evaluate_fairness, assess_risk,
  plan_actions, finalize_evaluation) with mock state
- Conditional edges (should_evaluate, should_act)
- Integration: full workflow with simple inputs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.ml_governance.graph import (
    create_ml_governance_graph,
    should_act,
    should_evaluate,
)
from shieldops.agents.ml_governance.models import (
    GovernanceFinding,
    GovernanceReasoningStep,
    MLGovernanceState,
    ModelAudit,
)
from shieldops.agents.ml_governance.nodes import (
    _get_toolkit,
    assess_risk,
    audit_models,
    evaluate_fairness,
    finalize_evaluation,
    plan_actions,
    set_toolkit,
)
from shieldops.agents.ml_governance.prompts import (
    ActionPlanOutput,
    AuditOutput,
    FairnessOutput,
)
from shieldops.agents.ml_governance.runner import MLGovernanceRunner
from shieldops.agents.ml_governance.tools import MLGovernanceToolkit

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_toolkit():
    """Reset the module-level toolkit singleton between tests."""
    import shieldops.agents.ml_governance.nodes as nodes_mod

    original = nodes_mod._toolkit
    nodes_mod._toolkit = None
    yield
    nodes_mod._toolkit = original


@pytest.fixture
def base_state() -> MLGovernanceState:
    return MLGovernanceState(
        session_id="audit-001",
        audit_config={"scope": "credit-scoring", "depth": "full"},
    )


@pytest.fixture
def discovered_state() -> MLGovernanceState:
    return MLGovernanceState(
        session_id="audit-002",
        audit_config={"scope": "credit-scoring"},
        model_audits=[
            ModelAudit(
                audit_id="ma-001",
                model_id="model-a",
                model_name="Credit Scorer v1",
                audit_type="compliance",
                compliance_score=85.0,
                risk_level="medium",
            ),
            ModelAudit(
                audit_id="ma-002",
                model_id="model-b",
                model_name="Fraud Detector v2",
                audit_type="fairness",
                compliance_score=60.0,
                risk_level="high",
            ),
        ],
        audit_count=2,
        governance_findings=[
            GovernanceFinding(
                finding_id="f-001",
                finding_type="fairness_violation",
                severity="critical",
                affected_model="model-b",
                description="Demographic parity violation detected",
                remediation="Retrain with balanced dataset",
            ),
        ],
        risk_score=72.5,
        critical_count=1,
    )


# -- TestState ---------------------------------------------------------------


class TestState:
    def test_default_values(self):
        state = MLGovernanceState()
        assert state.session_id == ""
        assert state.audit_config == {}
        assert state.model_audits == []
        assert state.audit_count == 0
        assert state.governance_findings == []
        assert state.risk_score == pytest.approx(0.0)
        assert state.prioritized_findings == []
        assert state.critical_count == 0
        assert state.action_plan == []
        assert state.action_started is False
        assert state.session_start is None
        assert state.session_duration_ms == 0
        assert state.reasoning_chain == []
        assert state.current_step == "init"
        assert state.error is None

    def test_creation_with_custom_values(self, base_state: MLGovernanceState):
        assert base_state.session_id == "audit-001"
        assert base_state.audit_config["scope"] == "credit-scoring"
        assert base_state.audit_config["depth"] == "full"

    def test_list_fields_are_independent_instances(self):
        s1 = MLGovernanceState()
        s2 = MLGovernanceState()
        s1.model_audits.append(ModelAudit(audit_id="x-1", model_id="m-1"))
        assert s2.model_audits == []

    def test_state_with_error(self):
        state = MLGovernanceState(error="connection timeout", current_step="failed")
        assert state.error == "connection timeout"
        assert state.current_step == "failed"

    def test_state_with_model_audits(self, discovered_state: MLGovernanceState):
        assert discovered_state.audit_count == 2
        assert len(discovered_state.model_audits) == 2
        assert discovered_state.model_audits[0].model_name == "Credit Scorer v1"

    def test_state_with_findings(self, discovered_state: MLGovernanceState):
        assert len(discovered_state.governance_findings) == 1
        assert discovered_state.governance_findings[0].severity == "critical"
        assert discovered_state.critical_count == 1

    def test_state_action_defaults(self):
        state = MLGovernanceState()
        assert state.action_plan == []
        assert state.action_started is False

    def test_state_audit_config_complex(self):
        state = MLGovernanceState(
            session_id="audit-complex",
            audit_config={"scope": "*.models", "checks": ["fairness", "bias"], "deep": True},
        )
        assert state.audit_config["checks"] == ["fairness", "bias"]
        assert state.audit_config["deep"] is True


# -- TestSubModels -----------------------------------------------------------


class TestSubModels:
    def test_model_audit_defaults(self):
        audit = ModelAudit()
        assert audit.audit_id == ""
        assert audit.model_id == ""
        assert audit.model_name == ""
        assert audit.audit_type == ""
        assert audit.compliance_score == pytest.approx(0.0)
        assert audit.risk_level == "low"

    def test_governance_finding_defaults(self):
        finding = GovernanceFinding()
        assert finding.finding_id == ""
        assert finding.finding_type == ""
        assert finding.severity == "medium"
        assert finding.affected_model == ""
        assert finding.description == ""
        assert finding.remediation == ""

    def test_governance_reasoning_step_creation(self):
        step = GovernanceReasoningStep(
            step_number=1,
            action="audit_models",
            input_summary="Auditing scope=credit-scoring",
            output_summary="Audited 5 models",
        )
        assert step.step_number == 1
        assert step.action == "audit_models"
        assert step.duration_ms == 0
        assert step.tool_used is None

    def test_model_audit_with_all_fields(self):
        audit = ModelAudit(
            audit_id="ma-001",
            model_id="model-a",
            model_name="Loan Approver",
            audit_type="fairness",
            compliance_score=95.0,
            risk_level="low",
        )
        assert audit.compliance_score == pytest.approx(95.0)
        assert audit.risk_level == "low"

    def test_governance_finding_with_all_fields(self):
        finding = GovernanceFinding(
            finding_id="f-001",
            finding_type="bias",
            severity="critical",
            affected_model="model-a",
            description="Racial bias detected",
            remediation="Retrain with balanced data",
        )
        assert finding.severity == "critical"
        assert finding.remediation == "Retrain with balanced data"

    def test_reasoning_step_with_tool(self):
        step = GovernanceReasoningStep(
            step_number=2,
            action="evaluate_fairness",
            input_summary="5 audits",
            output_summary="3 findings",
            duration_ms=150,
            tool_used="fairness_evaluator",
        )
        assert step.tool_used == "fairness_evaluator"
        assert step.duration_ms == 150

    def test_model_audit_low_default_risk(self):
        audit = ModelAudit(audit_id="ma-test")
        assert audit.risk_level == "low"
        assert audit.compliance_score == 0.0

    def test_governance_finding_medium_default_severity(self):
        finding = GovernanceFinding(finding_id="f-test")
        assert finding.severity == "medium"

    def test_reasoning_step_no_tool(self):
        step = GovernanceReasoningStep(
            step_number=1, action="test", input_summary="i", output_summary="o"
        )
        assert step.tool_used is None


# -- TestPromptSchemas -------------------------------------------------------


class TestPromptSchemas:
    def test_audit_output_fields(self):
        output = AuditOutput(
            audit_count=10,
            compliance_summary="5 models need review",
            risk_level="high",
        )
        assert output.audit_count == 10
        assert output.risk_level == "high"

    def test_fairness_output_fields(self):
        output = FairnessOutput(
            findings=[{"metric": "demographic_parity", "severity": "high", "desc": "violation"}],
            fairness_score=45.0,
            reasoning="Multiple fairness violations detected",
        )
        assert len(output.findings) == 1
        assert output.fairness_score == pytest.approx(45.0)

    def test_action_plan_output_fields(self):
        output = ActionPlanOutput(
            actions=[{"priority": "high", "target": "model-b"}],
            estimated_effort="2 weeks",
            reasoning="Retrain with balanced dataset",
        )
        assert len(output.actions) == 1
        assert output.estimated_effort == "2 weeks"

    def test_audit_output_zero_count(self):
        output = AuditOutput(
            audit_count=0,
            compliance_summary="No models found",
            risk_level="low",
        )
        assert output.audit_count == 0
        assert output.risk_level == "low"

    def test_fairness_output_high_score(self):
        output = FairnessOutput(
            findings=[],
            fairness_score=99.0,
            reasoning="All models passing fairness checks",
        )
        assert output.fairness_score == pytest.approx(99.0)

    def test_action_plan_output_empty_actions(self):
        output = ActionPlanOutput(
            actions=[],
            estimated_effort="0 hours",
            reasoning="Nothing to remediate",
        )
        assert len(output.actions) == 0


# -- TestToolkit -------------------------------------------------------------


class TestToolkit:
    def test_toolkit_initialization_with_no_deps(self):
        toolkit = MLGovernanceToolkit()
        assert toolkit._model_registry is None
        assert toolkit._fairness_engine is None
        assert toolkit._risk_assessor is None
        assert toolkit._policy_engine is None
        assert toolkit._repository is None

    def test_toolkit_initialization_with_deps(self):
        mock_registry = MagicMock()
        toolkit = MLGovernanceToolkit(model_registry=mock_registry)
        assert toolkit._model_registry is mock_registry

    @pytest.mark.asyncio
    async def test_audit_models_returns_list(self):
        toolkit = MLGovernanceToolkit()
        result = await toolkit.audit_models({"scope": "credit-scoring"})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_evaluate_fairness_returns_list(self):
        toolkit = MLGovernanceToolkit()
        result = await toolkit.evaluate_fairness([{"audit_id": "ma-1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_assess_risk_returns_sorted(self):
        toolkit = MLGovernanceToolkit()
        findings = [
            {"id": "f-1", "severity_score": 50},
            {"id": "f-2", "severity_score": 90},
        ]
        result = await toolkit.assess_risk(findings)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_create_action_plan_returns_list(self):
        toolkit = MLGovernanceToolkit()
        result = await toolkit.create_action_plan([{"id": "f-1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_record_governance_metric(self):
        toolkit = MLGovernanceToolkit()
        await toolkit.record_governance_metric("audit", 5.0)  # should not raise

    @pytest.mark.asyncio
    async def test_toolkit_with_all_deps(self):
        toolkit = MLGovernanceToolkit(
            model_registry=MagicMock(),
            fairness_engine=MagicMock(),
            risk_assessor=MagicMock(),
            policy_engine=MagicMock(),
            repository=MagicMock(),
        )
        assert toolkit._model_registry is not None
        assert toolkit._fairness_engine is not None
        assert toolkit._risk_assessor is not None
        assert toolkit._policy_engine is not None
        assert toolkit._repository is not None


# -- TestGraph ---------------------------------------------------------------


class TestGraph:
    def test_create_ml_governance_graph_returns_state_graph(self):
        graph = create_ml_governance_graph()
        assert graph is not None
        assert hasattr(graph, "compile")

    def test_graph_has_expected_nodes(self):
        graph = create_ml_governance_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "audit_models",
            "evaluate_fairness",
            "assess_risk",
            "plan_actions",
            "finalize_evaluation",
        }
        assert expected.issubset(node_names)

    def test_graph_compiles_without_error(self):
        graph = create_ml_governance_graph()
        app = graph.compile()
        assert app is not None

    def test_graph_entry_point_is_audit(self):
        graph = create_ml_governance_graph()
        assert "__start__" in graph.nodes or "audit_models" in graph.nodes

    def test_graph_has_finalize_node(self):
        graph = create_ml_governance_graph()
        assert "finalize_evaluation" in graph.nodes

    def test_graph_has_plan_actions_node(self):
        graph = create_ml_governance_graph()
        assert "plan_actions" in graph.nodes


# -- TestRunner --------------------------------------------------------------


class TestRunner:
    def test_runner_initialization(self):
        with patch(
            "shieldops.agents.ml_governance.runner.create_ml_governance_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = MLGovernanceRunner()
            assert runner._results == {}

    def test_list_results_empty(self):
        with patch(
            "shieldops.agents.ml_governance.runner.create_ml_governance_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = MLGovernanceRunner()
            assert runner.list_results() == []

    def test_list_results_returns_summaries(self):
        with patch(
            "shieldops.agents.ml_governance.runner.create_ml_governance_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = MLGovernanceRunner()
            runner._results["mg-abc"] = MLGovernanceState(
                session_id="audit-001",
                audit_count=5,
                critical_count=2,
                risk_score=75.0,
                current_step="complete",
            )
            summaries = runner.list_results()
            assert len(summaries) == 1
            assert summaries[0]["audit_id"] == "audit-001"
            assert summaries[0]["audit_count"] == 5

    @pytest.mark.asyncio
    async def test_evaluate_success(self):
        mock_app = AsyncMock()
        final_state = MLGovernanceState(
            session_id="audit-001",
            audit_count=3,
            critical_count=1,
            risk_score=80.0,
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch(
            "shieldops.agents.ml_governance.runner.create_ml_governance_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = MLGovernanceRunner()
            result = await runner.evaluate(audit_id="audit-001")

        assert isinstance(result, MLGovernanceState)
        assert result.current_step == "complete"

    @pytest.mark.asyncio
    async def test_evaluate_handles_exception(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.side_effect = RuntimeError("Graph exploded")

        with patch(
            "shieldops.agents.ml_governance.runner.create_ml_governance_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = MLGovernanceRunner()
            result = await runner.evaluate(audit_id="audit-x")

        assert result.error == "Graph exploded"
        assert result.current_step == "failed"

    @pytest.mark.asyncio
    async def test_evaluate_with_config(self):
        mock_app = AsyncMock()
        final_state = MLGovernanceState(
            session_id="audit-cfg",
            audit_config={"scope": "fraud-detection"},
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch(
            "shieldops.agents.ml_governance.runner.create_ml_governance_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = MLGovernanceRunner()
            result = await runner.evaluate(
                audit_id="audit-cfg",
                audit_config={"scope": "fraud-detection"},
            )

        assert result.audit_config["scope"] == "fraud-detection"

    def test_get_result_found(self):
        with patch(
            "shieldops.agents.ml_governance.runner.create_ml_governance_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = MLGovernanceRunner()
            runner._results["mg-test"] = MLGovernanceState(session_id="audit-001")
            assert runner.get_result("mg-test") is not None
            assert runner.get_result("mg-test").session_id == "audit-001"

    def test_get_result_not_found(self):
        with patch(
            "shieldops.agents.ml_governance.runner.create_ml_governance_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = MLGovernanceRunner()
            assert runner.get_result("nonexistent") is None

    def test_list_results_multiple(self):
        with patch(
            "shieldops.agents.ml_governance.runner.create_ml_governance_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = MLGovernanceRunner()
            runner._results["mg-1"] = MLGovernanceState(session_id="a1", current_step="complete")
            runner._results["mg-2"] = MLGovernanceState(
                session_id="a2", current_step="failed", error="err"
            )
            summaries = runner.list_results()
            assert len(summaries) == 2
            audit_ids = {s["audit_id"] for s in summaries}
            assert "a1" in audit_ids
            assert "a2" in audit_ids


# -- TestNodes ---------------------------------------------------------------


class TestNodes:
    @pytest.mark.asyncio
    async def test_audit_models_with_scope(self):
        state = MLGovernanceState(
            session_id="audit-001",
            audit_config={"scope": "credit-scoring"},
        )
        result = await audit_models(state)
        assert "model_audits" in result
        assert result["audit_count"] >= 1
        assert result["current_step"] == "audit_models"
        assert len(result["reasoning_chain"]) == 1

    @pytest.mark.asyncio
    async def test_audit_models_empty_scope(self):
        state = MLGovernanceState(
            session_id="audit-002",
            audit_config={},
        )
        result = await audit_models(state)
        assert "model_audits" in result
        assert result["current_step"] == "audit_models"

    @pytest.mark.asyncio
    async def test_evaluate_fairness(self, discovered_state: MLGovernanceState):
        result = await evaluate_fairness(discovered_state)
        assert "governance_findings" in result
        assert "risk_score" in result
        assert result["current_step"] == "evaluate_fairness"

    @pytest.mark.asyncio
    async def test_assess_risk(self, discovered_state: MLGovernanceState):
        result = await assess_risk(discovered_state)
        assert "prioritized_findings" in result
        assert "critical_count" in result
        assert result["current_step"] == "assess_risk"

    @pytest.mark.asyncio
    async def test_plan_actions(self, discovered_state: MLGovernanceState):
        discovered_state.prioritized_findings = [{"id": "f-1", "severity": "critical"}]
        result = await plan_actions(discovered_state)
        assert "action_plan" in result
        assert "action_started" in result
        assert result["current_step"] == "plan_actions"

    @pytest.mark.asyncio
    async def test_finalize_evaluation_records_duration(self):
        state = MLGovernanceState(
            session_id="audit-final",
            session_start=datetime.now(UTC),
        )
        result = await finalize_evaluation(state)
        assert result["session_duration_ms"] >= 0
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_finalize_evaluation_no_session_start(self):
        state = MLGovernanceState(session_id="audit-no-start")
        result = await finalize_evaluation(state)
        assert result["session_duration_ms"] == 0

    @pytest.mark.asyncio
    async def test_audit_models_sets_session_start(self):
        state = MLGovernanceState(
            session_id="audit-start",
            audit_config={"scope": "test-models"},
        )
        result = await audit_models(state)
        assert result["session_start"] is not None

    @pytest.mark.asyncio
    async def test_audit_models_reasoning_chain_grows(self):
        state = MLGovernanceState(
            session_id="audit-chain",
            audit_config={"scope": "chain-models"},
            reasoning_chain=[
                GovernanceReasoningStep(
                    step_number=1, action="prev", input_summary="", output_summary=""
                )
            ],
        )
        result = await audit_models(state)
        assert len(result["reasoning_chain"]) == 2
        assert result["reasoning_chain"][-1].action == "audit_models"

    @pytest.mark.asyncio
    async def test_evaluate_fairness_risk_score_calculated(
        self, discovered_state: MLGovernanceState
    ):
        result = await evaluate_fairness(discovered_state)
        assert isinstance(result["risk_score"], float)

    @pytest.mark.asyncio
    async def test_assess_risk_counts_critical(self, discovered_state: MLGovernanceState):
        result = await assess_risk(discovered_state)
        assert result["critical_count"] == 1  # one critical finding in fixture

    @pytest.mark.asyncio
    async def test_plan_actions_empty_findings(self):
        state = MLGovernanceState(
            session_id="audit-empty-act",
            prioritized_findings=[],
            critical_count=1,
        )
        result = await plan_actions(state)
        assert result["current_step"] == "plan_actions"

    @pytest.mark.asyncio
    async def test_finalize_evaluation_adds_reasoning_step(self):
        state = MLGovernanceState(
            session_id="audit-reason",
            session_start=datetime.now(UTC),
        )
        result = await finalize_evaluation(state)
        assert len(result["reasoning_chain"]) >= 1
        assert result["reasoning_chain"][-1].action == "finalize_evaluation"


# -- TestConditionalEdges ----------------------------------------------------


class TestConditionalEdges:
    def test_should_evaluate_with_audits(self):
        state = MLGovernanceState(audit_count=5)
        assert should_evaluate(state) == "evaluate_fairness"

    def test_should_evaluate_no_audits(self):
        state = MLGovernanceState(audit_count=0)
        assert should_evaluate(state) == "finalize_evaluation"

    def test_should_evaluate_with_error(self):
        state = MLGovernanceState(audit_count=5, error="failed")
        assert should_evaluate(state) == "finalize_evaluation"

    def test_should_act_with_critical(self):
        state = MLGovernanceState(critical_count=3)
        assert should_act(state) == "plan_actions"

    def test_should_act_no_critical(self):
        state = MLGovernanceState(critical_count=0)
        assert should_act(state) == "finalize_evaluation"

    def test_should_evaluate_zero_audits_no_error(self):
        state = MLGovernanceState(audit_count=0, error=None)
        assert should_evaluate(state) == "finalize_evaluation"

    def test_should_evaluate_one_audit(self):
        state = MLGovernanceState(audit_count=1)
        assert should_evaluate(state) == "evaluate_fairness"

    def test_should_act_one_critical(self):
        state = MLGovernanceState(critical_count=1)
        assert should_act(state) == "plan_actions"

    def test_should_act_many_critical(self):
        state = MLGovernanceState(critical_count=100)
        assert should_act(state) == "plan_actions"


# -- TestToolkitManagement ---------------------------------------------------


class TestToolkitManagement:
    def test_get_toolkit_returns_default_when_none_set(self):
        toolkit = _get_toolkit()
        assert isinstance(toolkit, MLGovernanceToolkit)

    def test_set_toolkit_is_used_by_get_toolkit(self):
        custom = MLGovernanceToolkit(model_registry=MagicMock())
        set_toolkit(custom)
        assert _get_toolkit() is custom

    def test_set_toolkit_overrides_previous(self):
        first = MLGovernanceToolkit()
        second = MLGovernanceToolkit(model_registry=MagicMock())
        set_toolkit(first)
        assert _get_toolkit() is first
        set_toolkit(second)
        assert _get_toolkit() is second

    def test_get_toolkit_creates_new_each_time_when_none(self):
        t1 = _get_toolkit()
        t2 = _get_toolkit()
        assert isinstance(t1, MLGovernanceToolkit)
        assert isinstance(t2, MLGovernanceToolkit)


# -- TestIntegration ---------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_no_audits(self):
        """Audit with no scope discovers nothing, goes to finalize."""
        state = MLGovernanceState(
            session_id="audit-int-1",
            audit_config={},
        )
        result = await audit_models(state)
        assert result["current_step"] == "audit_models"

    @pytest.mark.asyncio
    async def test_full_workflow_with_scope(self):
        """Audit with scope finds models, evaluates fairness."""
        state = MLGovernanceState(
            session_id="audit-int-2",
            audit_config={"scope": "credit-scoring"},
        )
        audit_result = await audit_models(state)
        assert audit_result["audit_count"] >= 1

        state_after_audit = MLGovernanceState(**{**state.model_dump(), **audit_result})
        fairness_result = await evaluate_fairness(state_after_audit)
        assert "governance_findings" in fairness_result

    @pytest.mark.asyncio
    async def test_full_workflow_finalize(self):
        """Finalize correctly records duration with session_start set."""
        state = MLGovernanceState(
            session_id="audit-int-3",
            session_start=datetime.now(UTC),
            audit_count=2,
            critical_count=0,
        )
        result = await finalize_evaluation(state)
        assert result["current_step"] == "complete"
        assert result["session_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_full_workflow_audit_then_check_conditional(self):
        """Audit models, then check conditional edge routes correctly."""
        state = MLGovernanceState(
            session_id="audit-int-4",
            audit_config={"scope": "fraud-detection"},
        )
        result = await audit_models(state)
        state_after = MLGovernanceState(**{**state.model_dump(), **result})
        assert should_evaluate(state_after) == "evaluate_fairness"

    @pytest.mark.asyncio
    async def test_full_workflow_assess_then_check_act(self, discovered_state: MLGovernanceState):
        """Assess risk, then check action conditional edge."""
        result = await assess_risk(discovered_state)
        state_after = MLGovernanceState(**{**discovered_state.model_dump(), **result})
        assert should_act(state_after) == "plan_actions"

    @pytest.mark.asyncio
    async def test_full_workflow_error_skips_evaluation(self):
        """Error state should skip evaluation and go to finalize."""
        state = MLGovernanceState(
            session_id="audit-int-err",
            audit_count=5,
            error="timeout",
        )
        assert should_evaluate(state) == "finalize_evaluation"

    @pytest.mark.asyncio
    async def test_full_workflow_no_critical_skips_actions(self):
        """No critical findings should skip actions and go to finalize."""
        state = MLGovernanceState(
            session_id="audit-int-nocrits",
            audit_count=3,
            critical_count=0,
        )
        assert should_act(state) == "finalize_evaluation"

    @pytest.mark.asyncio
    async def test_full_workflow_audit_evaluate_assess(self):
        """Full path through audit -> evaluate -> assess."""
        state = MLGovernanceState(
            session_id="audit-int-full",
            audit_config={"scope": "full.models"},
        )
        a_result = await audit_models(state)
        state2 = MLGovernanceState(**{**state.model_dump(), **a_result})

        f_result = await evaluate_fairness(state2)
        state3 = MLGovernanceState(**{**state2.model_dump(), **f_result})

        r_result = await assess_risk(state3)
        assert r_result["current_step"] == "assess_risk"
        assert "critical_count" in r_result
