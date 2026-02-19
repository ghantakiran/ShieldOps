"""Unit tests for OPA compliance mapping policy rules.

Since OPA is not available in unit tests, we verify:
1. The OPA input built by PolicyEngine has correct fields for compliance.
2. PolicyDecision correctly carries compliance-related OPA responses.
3. Different action types produce expected input for compliance matching.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.models.base import Environment, RemediationAction, RiskLevel
from shieldops.policy.opa.client import PolicyEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_action(
    action_type: str,
    environment: Environment = Environment.PRODUCTION,
    risk_level: RiskLevel = RiskLevel.LOW,
    action_id: str = "act-comp-001",
) -> RemediationAction:
    return RemediationAction(
        id=action_id,
        action_type=action_type,
        target_resource="default/nginx",
        environment=environment,
        risk_level=risk_level,
        description="compliance test action",
    )


def _mock_opa_response(result: bool | dict) -> MagicMock:
    """Build a mock httpx response with the given OPA result."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": result}
    mock_response.raise_for_status = MagicMock()
    return mock_response


def _extract_input(engine: PolicyEngine) -> dict:
    """Extract the OPA input dict from the most recent engine._client.post call."""
    call_args = engine._client.post.call_args
    json_payload = call_args.kwargs.get(
        "json", call_args.args[1] if len(call_args.args) > 1 else {}
    )
    return json_payload["input"]


# ---------------------------------------------------------------------------
# TestComplianceControlMapping
# ---------------------------------------------------------------------------


class TestComplianceControlMapping:
    """Verify the OPA input data contains correct fields so the compliance.rego
    rules can match the expected control IDs for each action type."""

    @pytest.mark.asyncio
    async def test_mutating_action_sends_correct_input(self):
        """A mutating action like restart_pod should produce input that the Rego
        rule for SOC2-CC8.1 (change management) can match on."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(True))

        action = _make_action("restart_pod")
        await engine.evaluate(action, agent_id="test-agent")

        opa_input = _extract_input(engine)
        # The action is NOT read-only, so SOC2-CC8.1 would apply in Rego
        assert opa_input["action"] == "restart_pod"
        assert opa_input["action"] not in {
            "query_logs",
            "query_metrics",
            "query_traces",
            "get_health",
            "list_resources",
            "get_events",
            "check_compliance",
        }

    @pytest.mark.asyncio
    async def test_read_only_action_excluded_from_change_management(self):
        """Read-only actions like query_logs should NOT trigger SOC2-CC8.1."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(True))

        action = _make_action("query_logs")
        await engine.evaluate(action, agent_id="test-agent")

        opa_input = _extract_input(engine)
        assert opa_input["action"] == "query_logs"
        # This action IS in the read_only_actions set, so SOC2-CC8.1 would NOT apply
        assert opa_input["action"] in {
            "query_logs",
            "query_metrics",
            "query_traces",
            "get_health",
            "list_resources",
            "get_events",
            "check_compliance",
        }

    @pytest.mark.asyncio
    async def test_patching_action_maps_to_pci_dss_62(self):
        """Patching actions should map to PCI-DSS-6.2 in the Rego rules."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(True))

        for action_type in ("patch_package", "update_service", "apply_security_patch"):
            action = _make_action(action_type)
            await engine.evaluate(action, agent_id="test-agent")
            opa_input = _extract_input(engine)
            assert opa_input["action"] == action_type

    @pytest.mark.asyncio
    async def test_credential_action_maps_to_hipaa(self):
        """Credential actions should map to HIPAA-164.312a in the Rego rules."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(True))

        for action_type in ("rotate_credentials", "revoke_access", "update_iam_policy"):
            action = _make_action(action_type)
            await engine.evaluate(action, agent_id="test-agent")
            opa_input = _extract_input(engine)
            assert opa_input["action"] == action_type

    @pytest.mark.asyncio
    async def test_k8s_pod_action_maps_to_cis_52(self):
        """Kubernetes pod-level actions should map to CIS-5.2."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(True))

        for action_type in ("restart_pod", "scale_horizontal", "drain_node", "rollback_deployment"):
            action = _make_action(action_type)
            await engine.evaluate(action, agent_id="test-agent")
            opa_input = _extract_input(engine)
            assert opa_input["action"] == action_type

    @pytest.mark.asyncio
    async def test_all_actions_include_environment_and_context(self):
        """Every action input must include environment and context for compliance evaluation."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(True))

        action = _make_action("force_new_deployment", environment=Environment.STAGING)
        await engine.evaluate(
            action,
            agent_id="test-agent",
            context={"audit_enabled": True, "mfa_verified": True},
        )

        opa_input = _extract_input(engine)
        assert opa_input["environment"] == "staging"
        assert opa_input["context"]["audit_enabled"] is True
        assert opa_input["context"]["mfa_verified"] is True


# ---------------------------------------------------------------------------
# TestComplianceViolations
# ---------------------------------------------------------------------------


class TestComplianceViolations:
    """Verify that OPA responses containing compliance violations are properly
    handled by the PolicyDecision and PolicyEngine."""

    @pytest.mark.asyncio
    async def test_denied_with_compliance_violation_reasons(self):
        """When OPA denies an action due to compliance violations, the reasons
        must be carried through to PolicyDecision."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": False,
            "reasons": [
                "Mutating action in production requires approval",
                "Audit logging must be enabled for all actions",
            ],
        }
        mock_response.raise_for_status = MagicMock()
        engine._client.post = AsyncMock(return_value=mock_response)

        action = _make_action("restart_pod")
        decision = await engine.evaluate(action, agent_id="test-agent")

        assert decision.allowed is False
        assert decision.denied is True
        assert "Mutating action in production requires approval" in decision.reasons
        assert "Audit logging must be enabled for all actions" in decision.reasons

    @pytest.mark.asyncio
    async def test_production_mutating_without_approval_sends_correct_context(self):
        """A mutating action in production without approval should send the input
        that triggers SOC2-CC8.1 violation in the Rego rules."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(False))

        action = _make_action("restart_pod", environment=Environment.PRODUCTION)
        await engine.evaluate(action, agent_id="test-agent")

        opa_input = _extract_input(engine)
        assert opa_input["environment"] == "production"
        # No approval_status in context, so Rego SOC2-CC8.1 violation rule would fire
        assert "approval_status" not in opa_input["context"]

    @pytest.mark.asyncio
    async def test_credential_action_without_mfa_sends_correct_context(self):
        """A credential action without MFA context should send input that triggers
        the HIPAA-164.312a violation rule."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(False))

        action = _make_action("rotate_credentials")
        await engine.evaluate(action, agent_id="test-agent", context={"mfa_verified": False})

        opa_input = _extract_input(engine)
        assert opa_input["action"] == "rotate_credentials"
        assert opa_input["context"]["mfa_verified"] is False


# ---------------------------------------------------------------------------
# TestComplianceSatisfied
# ---------------------------------------------------------------------------


class TestComplianceSatisfied:
    """Verify that OPA responses with satisfied compliance controls are properly
    handled, and that the correct input is sent for satisfaction rules."""

    @pytest.mark.asyncio
    async def test_approved_mutating_action_satisfies_soc2(self):
        """A mutating action with approval should send input that satisfies
        the SOC2-CC8.1 rule in Rego."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(True))

        action = _make_action("restart_pod", environment=Environment.PRODUCTION)
        await engine.evaluate(
            action, agent_id="test-agent", context={"approval_status": "approved"}
        )

        opa_input = _extract_input(engine)
        assert opa_input["context"]["approval_status"] == "approved"
        assert opa_input["environment"] == "production"

    @pytest.mark.asyncio
    async def test_non_production_satisfies_soc2_without_approval(self):
        """A mutating action in a non-production environment should satisfy
        SOC2-CC8.1 even without approval."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(True))

        action = _make_action("restart_pod", environment=Environment.DEVELOPMENT)
        result = await engine.evaluate(action, agent_id="test-agent")

        opa_input = _extract_input(engine)
        assert opa_input["environment"] == "development"
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_audit_enabled_satisfies_pci_dss_101(self):
        """When audit_enabled is true (or absent), PCI-DSS-10.1 should be satisfied."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(True))

        action = _make_action("restart_pod")
        await engine.evaluate(action, agent_id="test-agent", context={"audit_enabled": True})

        opa_input = _extract_input(engine)
        assert opa_input["context"]["audit_enabled"] is True

    @pytest.mark.asyncio
    async def test_credential_action_with_mfa_satisfies_hipaa(self):
        """A credential action with MFA verified should satisfy HIPAA-164.312a."""
        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(return_value=_mock_opa_response(True))

        action = _make_action("rotate_credentials")
        await engine.evaluate(action, agent_id="test-agent", context={"mfa_verified": True})

        opa_input = _extract_input(engine)
        assert opa_input["action"] == "rotate_credentials"
        assert opa_input["context"]["mfa_verified"] is True
