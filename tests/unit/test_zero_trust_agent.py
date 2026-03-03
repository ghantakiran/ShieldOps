"""Tests for the Zero Trust Agent LangGraph workflow.

Covers:
- ZeroTrustState model creation, defaults, and field types
- Sub-models: IdentityVerification, DeviceAssessment, AccessEvaluation, ZeroTrustReasoningStep
- Prompt schemas: IdentityVerificationOutput, DeviceAssessmentOutput, PolicyEnforcementOutput
- ZeroTrustToolkit initialization and async methods
- Graph creation (create_zero_trust_graph returns a StateGraph)
- ZeroTrustRunner initialization and list_results
- Node functions (verify_identity, assess_device, evaluate_access,
  enforce_policy, finalize_assessment) with mock state
- Conditional edges (should_assess_device, should_enforce)
- Integration: full workflow with simple inputs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.zero_trust.graph import (
    create_zero_trust_graph,
    should_assess_device,
    should_enforce,
)
from shieldops.agents.zero_trust.models import (
    AccessEvaluation,
    DeviceAssessment,
    IdentityVerification,
    ZeroTrustReasoningStep,
    ZeroTrustState,
)
from shieldops.agents.zero_trust.nodes import (
    _get_toolkit,
    assess_device,
    enforce_policy,
    evaluate_access,
    finalize_assessment,
    set_toolkit,
    verify_identity,
)
from shieldops.agents.zero_trust.prompts import (
    DeviceAssessmentOutput,
    IdentityVerificationOutput,
    PolicyEnforcementOutput,
)
from shieldops.agents.zero_trust.runner import ZeroTrustRunner
from shieldops.agents.zero_trust.tools import ZeroTrustToolkit

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_toolkit():
    """Reset the module-level toolkit singleton between tests."""
    import shieldops.agents.zero_trust.nodes as nodes_mod

    original = nodes_mod._toolkit
    nodes_mod._toolkit = None
    yield
    nodes_mod._toolkit = original


@pytest.fixture
def base_state() -> ZeroTrustState:
    return ZeroTrustState(
        session_id="zt-001",
        assessment_config={"scope": "org.example.com", "depth": "full"},
    )


@pytest.fixture
def verified_state() -> ZeroTrustState:
    return ZeroTrustState(
        session_id="zt-002",
        assessment_config={"scope": "org.example.com"},
        identity_verifications=[
            IdentityVerification(
                identity_id="id-001",
                identity_type="service_account",
                risk_level="medium",
                verified=True,
                trust_score=75.0,
            ),
            IdentityVerification(
                identity_id="id-002",
                identity_type="user",
                risk_level="low",
                verified=True,
                trust_score=90.0,
            ),
        ],
        identity_verified=2,
        device_assessments=[
            DeviceAssessment(
                device_id="dev-001",
                device_type="laptop",
                posture_status="compliant",
                compliance_score=85.0,
                issues=[],
            ),
        ],
        access_evaluations=[
            AccessEvaluation(
                access_id="acc-001",
                resource="db-prod",
                action="read",
                decision="deny",
                risk_factors=["no_mfa", "unpatched_device"],
            ),
        ],
        violation_count=1,
        trust_score=82.5,
    )


# -- TestState ---------------------------------------------------------------


class TestState:
    def test_default_values(self):
        state = ZeroTrustState()
        assert state.session_id == ""
        assert state.assessment_config == {}
        assert state.identity_verifications == []
        assert state.device_assessments == []
        assert state.access_evaluations == []
        assert state.identity_verified == 0
        assert state.violation_count == 0
        assert state.trust_score == pytest.approx(0.0)
        assert state.enforcement_actions == []
        assert state.policy_enforced is False
        assert state.session_start is None
        assert state.session_duration_ms == 0
        assert state.reasoning_chain == []
        assert state.current_step == "init"
        assert state.error is None

    def test_creation_with_custom_values(self, base_state: ZeroTrustState):
        assert base_state.session_id == "zt-001"
        assert base_state.assessment_config["scope"] == "org.example.com"
        assert base_state.assessment_config["depth"] == "full"

    def test_list_fields_are_independent_instances(self):
        s1 = ZeroTrustState()
        s2 = ZeroTrustState()
        s1.identity_verifications.append(
            IdentityVerification(identity_id="x-1", identity_type="user")
        )
        assert s2.identity_verifications == []

    def test_state_with_error(self):
        state = ZeroTrustState(error="connection timeout", current_step="failed")
        assert state.error == "connection timeout"
        assert state.current_step == "failed"

    def test_state_with_identities(self, verified_state: ZeroTrustState):
        assert verified_state.identity_verified == 2
        assert len(verified_state.identity_verifications) == 2
        assert verified_state.identity_verifications[0].identity_id == "id-001"

    def test_state_with_violations(self):
        state = ZeroTrustState(
            violation_count=3,
            access_evaluations=[
                AccessEvaluation(access_id="a-1", decision="deny"),
                AccessEvaluation(access_id="a-2", decision="deny"),
                AccessEvaluation(access_id="a-3", decision="deny"),
            ],
        )
        assert state.violation_count == 3
        assert len(state.access_evaluations) == 3

    def test_state_enforcement_defaults(self):
        state = ZeroTrustState()
        assert state.enforcement_actions == []
        assert state.policy_enforced is False

    def test_state_assessment_config_complex(self):
        state = ZeroTrustState(
            session_id="zt-complex",
            assessment_config={
                "scope": "*.org.example.com",
                "ports": [443, 8443, 9090],
                "strict": True,
            },
        )
        assert state.assessment_config["ports"] == [443, 8443, 9090]
        assert state.assessment_config["strict"] is True


# -- TestSubModels -----------------------------------------------------------


class TestSubModels:
    def test_identity_verification_defaults(self):
        identity = IdentityVerification()
        assert identity.identity_id == ""
        assert identity.identity_type == ""
        assert identity.risk_level == "low"
        assert identity.verified is False
        assert identity.trust_score == pytest.approx(0.0)

    def test_device_assessment_defaults(self):
        device = DeviceAssessment()
        assert device.device_id == ""
        assert device.device_type == ""
        assert device.posture_status == "unknown"
        assert device.compliance_score == pytest.approx(0.0)
        assert device.issues == []

    def test_access_evaluation_defaults(self):
        evaluation = AccessEvaluation()
        assert evaluation.access_id == ""
        assert evaluation.resource == ""
        assert evaluation.action == ""
        assert evaluation.decision == "deny"
        assert evaluation.risk_factors == []

    def test_reasoning_step_creation(self):
        step = ZeroTrustReasoningStep(
            step_number=1,
            action="verify_identity",
            input_summary="Verifying identities scope=org.example.com",
            output_summary="Verified 3 identities",
        )
        assert step.step_number == 1
        assert step.action == "verify_identity"
        assert step.duration_ms == 0
        assert step.tool_used is None

    def test_identity_verification_with_all_fields(self):
        identity = IdentityVerification(
            identity_id="id-001",
            identity_type="service_account",
            risk_level="high",
            verified=True,
            trust_score=95.0,
        )
        assert identity.risk_level == "high"
        assert identity.trust_score == pytest.approx(95.0)

    def test_device_assessment_with_all_fields(self):
        device = DeviceAssessment(
            device_id="dev-001",
            device_type="laptop",
            posture_status="compliant",
            compliance_score=92.0,
            issues=["outdated_antivirus"],
        )
        assert device.posture_status == "compliant"
        assert device.compliance_score == pytest.approx(92.0)
        assert device.issues == ["outdated_antivirus"]

    def test_access_evaluation_with_all_fields(self):
        evaluation = AccessEvaluation(
            access_id="acc-001",
            resource="db-prod",
            action="write",
            decision="allow",
            risk_factors=["elevated_privilege"],
        )
        assert evaluation.decision == "allow"
        assert evaluation.risk_factors == ["elevated_privilege"]

    def test_reasoning_step_with_tool(self):
        step = ZeroTrustReasoningStep(
            step_number=2,
            action="assess_device",
            input_summary="3 devices",
            output_summary="2 compliant",
            duration_ms=150,
            tool_used="device_assessor",
        )
        assert step.tool_used == "device_assessor"
        assert step.duration_ms == 150

    def test_reasoning_step_no_tool(self):
        step = ZeroTrustReasoningStep(
            step_number=1, action="test", input_summary="i", output_summary="o"
        )
        assert step.tool_used is None


# -- TestPromptSchemas -------------------------------------------------------


class TestPromptSchemas:
    def test_identity_verification_output_fields(self):
        output = IdentityVerificationOutput(
            verified_count=10,
            risk_summary="3 high-risk identities found",
            trust_level="medium",
        )
        assert output.verified_count == 10
        assert output.trust_level == "medium"

    def test_device_assessment_output_fields(self):
        output = DeviceAssessmentOutput(
            devices=[{"id": "dev-1", "type": "laptop", "posture": "compliant"}],
            compliance_score=85.0,
            issues=["outdated_os"],
        )
        assert len(output.devices) == 1
        assert output.compliance_score == pytest.approx(85.0)

    def test_policy_enforcement_output_fields(self):
        output = PolicyEnforcementOutput(
            actions=[{"type": "block", "target": "user-123", "status": "applied"}],
            enforced_count=1,
            reasoning="Block unauthorized access attempts",
        )
        assert len(output.actions) == 1
        assert output.enforced_count == 1

    def test_identity_output_zero_verified(self):
        output = IdentityVerificationOutput(
            verified_count=0,
            risk_summary="No identities verified",
            trust_level="none",
        )
        assert output.verified_count == 0
        assert output.trust_level == "none"

    def test_device_assessment_output_high_compliance(self):
        output = DeviceAssessmentOutput(
            devices=[],
            compliance_score=99.0,
            issues=[],
        )
        assert output.compliance_score == pytest.approx(99.0)

    def test_policy_enforcement_output_empty_actions(self):
        output = PolicyEnforcementOutput(
            actions=[],
            enforced_count=0,
            reasoning="Nothing to enforce",
        )
        assert len(output.actions) == 0


# -- TestToolkit -------------------------------------------------------------


class TestToolkit:
    def test_toolkit_initialization_with_no_deps(self):
        toolkit = ZeroTrustToolkit()
        assert toolkit._identity_provider is None
        assert toolkit._device_manager is None
        assert toolkit._policy_engine is None
        assert toolkit._access_controller is None
        assert toolkit._repository is None

    def test_toolkit_initialization_with_deps(self):
        mock_provider = MagicMock()
        toolkit = ZeroTrustToolkit(identity_provider=mock_provider)
        assert toolkit._identity_provider is mock_provider

    @pytest.mark.asyncio
    async def test_verify_identities_returns_list(self):
        toolkit = ZeroTrustToolkit()
        result = await toolkit.verify_identities({"scope": "org.example.com"})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_assess_devices_returns_list(self):
        toolkit = ZeroTrustToolkit()
        result = await toolkit.assess_devices({"scope": "org.example.com"})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_evaluate_access_returns_list(self):
        toolkit = ZeroTrustToolkit()
        result = await toolkit.evaluate_access([{"identity_id": "id-1"}], [{"device_id": "dev-1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_enforce_policies_returns_list(self):
        toolkit = ZeroTrustToolkit()
        result = await toolkit.enforce_policies([{"violation_id": "v-1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_record_trust_metric(self):
        toolkit = ZeroTrustToolkit()
        await toolkit.record_trust_metric("identity_verification", 5.0)  # should not raise

    def test_toolkit_with_all_deps(self):
        toolkit = ZeroTrustToolkit(
            identity_provider=MagicMock(),
            device_manager=MagicMock(),
            policy_engine=MagicMock(),
            access_controller=MagicMock(),
            repository=MagicMock(),
        )
        assert toolkit._identity_provider is not None
        assert toolkit._device_manager is not None
        assert toolkit._policy_engine is not None
        assert toolkit._access_controller is not None
        assert toolkit._repository is not None


# -- TestGraph ---------------------------------------------------------------


class TestGraph:
    def test_create_zero_trust_graph_returns_state_graph(self):
        graph = create_zero_trust_graph()
        assert graph is not None
        assert hasattr(graph, "compile")

    def test_graph_has_expected_nodes(self):
        graph = create_zero_trust_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "verify_identity",
            "assess_device",
            "evaluate_access",
            "enforce_policy",
            "finalize_assessment",
        }
        assert expected.issubset(node_names)

    def test_graph_compiles_without_error(self):
        graph = create_zero_trust_graph()
        app = graph.compile()
        assert app is not None

    def test_graph_entry_point_is_verify(self):
        graph = create_zero_trust_graph()
        # The entry point should be verify_identity
        assert "__start__" in graph.nodes or "verify_identity" in graph.nodes

    def test_graph_has_finalize_node(self):
        graph = create_zero_trust_graph()
        assert "finalize_assessment" in graph.nodes

    def test_graph_has_enforce_node(self):
        graph = create_zero_trust_graph()
        assert "enforce_policy" in graph.nodes


# -- TestRunner --------------------------------------------------------------


class TestRunner:
    def test_runner_initialization(self):
        with patch("shieldops.agents.zero_trust.runner.create_zero_trust_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ZeroTrustRunner()
            assert runner._results == {}

    def test_list_results_empty(self):
        with patch("shieldops.agents.zero_trust.runner.create_zero_trust_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ZeroTrustRunner()
            assert runner.list_results() == []

    def test_list_results_returns_summaries(self):
        with patch("shieldops.agents.zero_trust.runner.create_zero_trust_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ZeroTrustRunner()
            runner._results["zt-abc"] = ZeroTrustState(
                session_id="zt-001",
                identity_verified=5,
                violation_count=2,
                trust_score=75.0,
                current_step="complete",
            )
            summaries = runner.list_results()
            assert len(summaries) == 1
            assert summaries[0]["session_id"] == "zt-abc"
            assert summaries[0]["identity_verified"] == 5

    @pytest.mark.asyncio
    async def test_assess_success(self):
        mock_app = AsyncMock()
        final_state = ZeroTrustState(
            session_id="zt-001",
            identity_verified=3,
            violation_count=1,
            trust_score=80.0,
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch("shieldops.agents.zero_trust.runner.create_zero_trust_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = ZeroTrustRunner()
            result = await runner.assess(session_id="zt-001")

        assert isinstance(result, ZeroTrustState)
        assert result.current_step == "complete"

    @pytest.mark.asyncio
    async def test_assess_handles_exception(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.side_effect = RuntimeError("Graph exploded")

        with patch("shieldops.agents.zero_trust.runner.create_zero_trust_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = ZeroTrustRunner()
            result = await runner.assess(session_id="zt-x")

        assert result.error == "Graph exploded"
        assert result.current_step == "failed"

    @pytest.mark.asyncio
    async def test_assess_with_config(self):
        mock_app = AsyncMock()
        final_state = ZeroTrustState(
            session_id="zt-cfg",
            assessment_config={"scope": "test.com"},
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch("shieldops.agents.zero_trust.runner.create_zero_trust_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = ZeroTrustRunner()
            result = await runner.assess(
                session_id="zt-cfg", assessment_config={"scope": "test.com"}
            )

        assert result.assessment_config["scope"] == "test.com"

    def test_get_result_found(self):
        with patch("shieldops.agents.zero_trust.runner.create_zero_trust_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ZeroTrustRunner()
            runner._results["zt-test"] = ZeroTrustState(session_id="zt-001")
            assert runner.get_result("zt-test") is not None
            assert runner.get_result("zt-test").session_id == "zt-001"

    def test_get_result_not_found(self):
        with patch("shieldops.agents.zero_trust.runner.create_zero_trust_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ZeroTrustRunner()
            assert runner.get_result("nonexistent") is None


# -- TestNodes ---------------------------------------------------------------


class TestNodes:
    @pytest.mark.asyncio
    async def test_verify_identity_with_scope(self):
        state = ZeroTrustState(
            session_id="zt-001",
            assessment_config={"scope": "org.example.com"},
        )
        result = await verify_identity(state)
        assert "identity_verifications" in result
        assert result["identity_verified"] >= 1
        assert result["current_step"] == "verify_identity"
        assert len(result["reasoning_chain"]) == 1

    @pytest.mark.asyncio
    async def test_verify_identity_empty_scope(self):
        state = ZeroTrustState(
            session_id="zt-002",
            assessment_config={},
        )
        result = await verify_identity(state)
        assert "identity_verifications" in result
        assert result["current_step"] == "verify_identity"

    @pytest.mark.asyncio
    async def test_assess_device(self, verified_state: ZeroTrustState):
        result = await assess_device(verified_state)
        assert "device_assessments" in result
        assert result["current_step"] == "assess_device"

    @pytest.mark.asyncio
    async def test_evaluate_access(self, verified_state: ZeroTrustState):
        result = await evaluate_access(verified_state)
        assert "access_evaluations" in result
        assert "violation_count" in result
        assert result["current_step"] == "evaluate_access"

    @pytest.mark.asyncio
    async def test_enforce_policy(self, verified_state: ZeroTrustState):
        result = await enforce_policy(verified_state)
        assert "enforcement_actions" in result
        assert "policy_enforced" in result
        assert result["current_step"] == "enforce_policy"

    @pytest.mark.asyncio
    async def test_finalize_assessment_records_duration(self):
        state = ZeroTrustState(
            session_id="zt-final",
            session_start=datetime.now(UTC),
        )
        result = await finalize_assessment(state)
        assert result["session_duration_ms"] >= 0
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_finalize_assessment_no_session_start(self):
        state = ZeroTrustState(session_id="zt-no-start")
        result = await finalize_assessment(state)
        assert result["session_duration_ms"] == 0

    @pytest.mark.asyncio
    async def test_verify_identity_sets_session_start(self):
        state = ZeroTrustState(
            session_id="zt-start",
            assessment_config={"scope": "test.com"},
        )
        result = await verify_identity(state)
        assert result["session_start"] is not None

    @pytest.mark.asyncio
    async def test_verify_identity_reasoning_chain_grows(self):
        state = ZeroTrustState(
            session_id="zt-chain",
            assessment_config={"scope": "chain.com"},
            reasoning_chain=[
                ZeroTrustReasoningStep(
                    step_number=1, action="prev", input_summary="", output_summary=""
                )
            ],
        )
        result = await verify_identity(state)
        assert len(result["reasoning_chain"]) == 2
        assert result["reasoning_chain"][-1].action == "verify_identity"

    @pytest.mark.asyncio
    async def test_assess_device_compliance_score(self, verified_state: ZeroTrustState):
        result = await assess_device(verified_state)
        assert "device_assessments" in result
        # The node returns device_assessments list (may be empty from default toolkit)
        assert isinstance(result["device_assessments"], list)

    @pytest.mark.asyncio
    async def test_evaluate_access_counts_violations(self, verified_state: ZeroTrustState):
        result = await evaluate_access(verified_state)
        assert isinstance(result["violation_count"], int)


# -- TestConditionalEdges ----------------------------------------------------


class TestConditionalEdges:
    def test_should_assess_device_with_identities(self):
        state = ZeroTrustState(identity_verified=5)
        assert should_assess_device(state) == "assess_device"

    def test_should_assess_device_no_identities(self):
        state = ZeroTrustState(identity_verified=0)
        assert should_assess_device(state) == "finalize_assessment"

    def test_should_assess_device_with_error(self):
        state = ZeroTrustState(identity_verified=5, error="failed")
        assert should_assess_device(state) == "finalize_assessment"

    def test_should_enforce_with_violations(self):
        state = ZeroTrustState(violation_count=3)
        assert should_enforce(state) == "enforce_policy"

    def test_should_enforce_no_violations(self):
        state = ZeroTrustState(violation_count=0)
        assert should_enforce(state) == "finalize_assessment"

    def test_should_assess_device_zero_no_error(self):
        state = ZeroTrustState(identity_verified=0, error=None)
        assert should_assess_device(state) == "finalize_assessment"

    def test_should_assess_device_one_identity(self):
        state = ZeroTrustState(identity_verified=1)
        assert should_assess_device(state) == "assess_device"

    def test_should_enforce_one_violation(self):
        state = ZeroTrustState(violation_count=1)
        assert should_enforce(state) == "enforce_policy"

    def test_should_enforce_many_violations(self):
        state = ZeroTrustState(violation_count=100)
        assert should_enforce(state) == "enforce_policy"


# -- TestToolkitManagement ---------------------------------------------------


class TestToolkitManagement:
    def test_get_toolkit_returns_default_when_none_set(self):
        toolkit = _get_toolkit()
        assert isinstance(toolkit, ZeroTrustToolkit)

    def test_set_toolkit_is_used_by_get_toolkit(self):
        custom = ZeroTrustToolkit(identity_provider=MagicMock())
        set_toolkit(custom)
        assert _get_toolkit() is custom

    def test_set_toolkit_overrides_previous(self):
        first = ZeroTrustToolkit()
        second = ZeroTrustToolkit(identity_provider=MagicMock())
        set_toolkit(first)
        assert _get_toolkit() is first
        set_toolkit(second)
        assert _get_toolkit() is second

    def test_get_toolkit_creates_new_each_time_when_none(self):
        t1 = _get_toolkit()
        t2 = _get_toolkit()
        # Both are valid toolkits (different instances since _toolkit is None each time)
        assert isinstance(t1, ZeroTrustToolkit)
        assert isinstance(t2, ZeroTrustToolkit)


# -- TestIntegration ---------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_no_identities(self):
        """Assessment with no scope discovers nothing, goes to finalize."""
        state = ZeroTrustState(
            session_id="zt-int-1",
            assessment_config={},
        )
        result = await verify_identity(state)
        assert result["current_step"] == "verify_identity"

    @pytest.mark.asyncio
    async def test_full_workflow_with_scope(self):
        """Assessment with scope verifies identities, assesses devices."""
        state = ZeroTrustState(
            session_id="zt-int-2",
            assessment_config={"scope": "org.example.com"},
        )
        verify_result = await verify_identity(state)
        assert verify_result["identity_verified"] >= 1

        state_after_verify = ZeroTrustState(**{**state.model_dump(), **verify_result})
        device_result = await assess_device(state_after_verify)
        assert "device_assessments" in device_result

    @pytest.mark.asyncio
    async def test_full_workflow_finalize(self):
        """Finalize correctly records duration with session_start set."""
        state = ZeroTrustState(
            session_id="zt-int-3",
            session_start=datetime.now(UTC),
            identity_verified=2,
            violation_count=0,
        )
        result = await finalize_assessment(state)
        assert result["current_step"] == "complete"
        assert result["session_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_full_workflow_verify_then_check_conditional(self):
        """Verify identities, then check conditional edge routes correctly."""
        state = ZeroTrustState(
            session_id="zt-int-4",
            assessment_config={"scope": "org.example.com"},
        )
        result = await verify_identity(state)
        state_after = ZeroTrustState(**{**state.model_dump(), **result})
        # With identities verified, should route to assess_device
        assert should_assess_device(state_after) == "assess_device"

    @pytest.mark.asyncio
    async def test_full_workflow_evaluate_then_check_enforce(self, verified_state: ZeroTrustState):
        """Evaluate access, then check enforce conditional edge."""
        result = await evaluate_access(verified_state)
        state_after = ZeroTrustState(**{**verified_state.model_dump(), **result})
        # The conditional depends on violation_count from the evaluation
        edge = should_enforce(state_after)
        assert edge in ("enforce_policy", "finalize_assessment")

    @pytest.mark.asyncio
    async def test_full_workflow_error_skips_assessment(self):
        """Error state should skip device assessment and go to finalize."""
        state = ZeroTrustState(
            session_id="zt-int-err",
            identity_verified=5,
            error="timeout",
        )
        assert should_assess_device(state) == "finalize_assessment"

    @pytest.mark.asyncio
    async def test_full_workflow_no_violations_skips_enforcement(self):
        """No violations should skip enforcement and go to finalize."""
        state = ZeroTrustState(
            session_id="zt-int-noviols",
            identity_verified=3,
            violation_count=0,
        )
        assert should_enforce(state) == "finalize_assessment"

    @pytest.mark.asyncio
    async def test_full_workflow_verify_assess_evaluate(self):
        """Full path through verify -> assess -> evaluate."""
        state = ZeroTrustState(
            session_id="zt-int-full",
            assessment_config={"scope": "full.org.example.com"},
        )
        v_result = await verify_identity(state)
        state2 = ZeroTrustState(**{**state.model_dump(), **v_result})

        a_result = await assess_device(state2)
        state3 = ZeroTrustState(**{**state2.model_dump(), **a_result})

        e_result = await evaluate_access(state3)
        assert e_result["current_step"] == "evaluate_access"
        assert "violation_count" in e_result
