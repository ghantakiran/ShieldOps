"""Unit tests for OPA team scoping: input construction and deny scenarios."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.models.base import Environment, RemediationAction, RiskLevel
from shieldops.policy.opa.client import PolicyEngine


def _make_action(**overrides) -> RemediationAction:
    """Helper to build a RemediationAction with sensible defaults."""
    defaults = {
        "id": "act-team-001",
        "action_type": "restart_pod",
        "target_resource": "default/nginx",
        "environment": Environment.DEVELOPMENT,
        "risk_level": RiskLevel.LOW,
        "description": "test action",
        "parameters": {},
    }
    defaults.update(overrides)
    return RemediationAction(**defaults)


def _engine_with_mock_response(response_json: dict) -> PolicyEngine:
    """Create a PolicyEngine whose HTTP client returns *response_json*."""
    engine = PolicyEngine(opa_url="http://opa:8181")
    engine._client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()
    engine._client.post = AsyncMock(return_value=mock_response)
    return engine


def _extract_input(engine: PolicyEngine) -> dict:
    """Pull out the 'input' dict from the most recent POST call."""
    call_args = engine._client.post.call_args
    payload = call_args.kwargs.get("json", call_args.args[1] if len(call_args.args) > 1 else {})
    return payload["input"]


# ---------------------------------------------------------------------------
# TestTeamScopingInput — verify that PolicyEngine builds the OPA input
# with the correct 'team' and 'resource_labels' fields.
# ---------------------------------------------------------------------------


class TestTeamScopingInput:
    """Verify team and resource_labels are correctly populated in OPA input."""

    @pytest.mark.asyncio
    async def test_team_from_parameters(self):
        """team in action.parameters should appear in OPA input."""
        engine = _engine_with_mock_response({"result": True})
        action = _make_action(parameters={"team": "backend"})

        await engine.evaluate(action, agent_id="agent-1")

        input_data = _extract_input(engine)
        assert input_data["team"] == "backend"

    @pytest.mark.asyncio
    async def test_team_from_context(self):
        """team in context (but not parameters) should appear in OPA input."""
        engine = _engine_with_mock_response({"result": True})
        action = _make_action(parameters={})

        await engine.evaluate(action, agent_id="agent-1", context={"team": "frontend"})

        input_data = _extract_input(engine)
        assert input_data["team"] == "frontend"

    @pytest.mark.asyncio
    async def test_team_parameter_overrides_context(self):
        """parameters.team takes precedence over context.team."""
        engine = _engine_with_mock_response({"result": True})
        action = _make_action(parameters={"team": "backend"})

        await engine.evaluate(action, agent_id="agent-1", context={"team": "frontend"})

        input_data = _extract_input(engine)
        assert input_data["team"] == "backend"

    @pytest.mark.asyncio
    async def test_no_team(self):
        """When neither parameters nor context has team, input.team is None."""
        engine = _engine_with_mock_response({"result": True})
        action = _make_action(parameters={})

        await engine.evaluate(action, agent_id="agent-1")

        input_data = _extract_input(engine)
        assert input_data["team"] is None

    @pytest.mark.asyncio
    async def test_resource_labels_from_parameters(self):
        """resource_labels in parameters should appear in OPA input."""
        engine = _engine_with_mock_response({"result": True})
        labels = {"team": "backend", "scope": "production_database"}
        action = _make_action(parameters={"resource_labels": labels})

        await engine.evaluate(action, agent_id="agent-1")

        input_data = _extract_input(engine)
        assert input_data["resource_labels"] == labels

    @pytest.mark.asyncio
    async def test_resource_labels_from_context(self):
        """resource_labels in context (but not parameters) should be used."""
        engine = _engine_with_mock_response({"result": True})
        labels = {"team": "frontend", "scope": "staging"}
        action = _make_action(parameters={})

        await engine.evaluate(action, agent_id="agent-1", context={"resource_labels": labels})

        input_data = _extract_input(engine)
        assert input_data["resource_labels"] == labels

    @pytest.mark.asyncio
    async def test_empty_resource_labels(self):
        """When neither source has resource_labels, default is {}."""
        engine = _engine_with_mock_response({"result": True})
        action = _make_action(parameters={})

        await engine.evaluate(action, agent_id="agent-1")

        input_data = _extract_input(engine)
        assert input_data["resource_labels"] == {}


# ---------------------------------------------------------------------------
# TestTeamScopingDenyScenarios — verify PolicyEngine correctly interprets
# deny responses from OPA for team-related rules.
# ---------------------------------------------------------------------------


class TestTeamScopingDenyScenarios:
    """Verify that team-related OPA deny responses are handled correctly."""

    @pytest.mark.asyncio
    async def test_team_mismatch_denied(self):
        """OPA denies team mismatch; PolicyDecision should reflect the reason."""
        reason = "Team 'frontend' cannot modify resources owned by team 'backend'"
        engine = _engine_with_mock_response({"result": False, "reasons": [reason]})
        action = _make_action(
            parameters={"team": "frontend", "resource_labels": {"team": "backend"}},
        )

        result = await engine.evaluate(action, agent_id="agent-1")

        assert result.denied is True
        assert result.allowed is False
        assert reason in result.reasons

    @pytest.mark.asyncio
    async def test_team_match_allowed(self):
        """When teams match, OPA allows the action."""
        engine = _engine_with_mock_response({"result": True})
        action = _make_action(
            parameters={"team": "backend", "resource_labels": {"team": "backend"}},
        )

        result = await engine.evaluate(action, agent_id="agent-1")

        assert result.allowed is True
        assert result.denied is False

    @pytest.mark.asyncio
    async def test_team_rate_limit_denied(self):
        """OPA denies for team rate limit; reason mentions rate limit."""
        reason = (
            "Team 'backend' rate limit exceeded: 11 actions this hour, limit is 10 for production"
        )
        engine = _engine_with_mock_response({"result": False, "reasons": [reason]})
        action = _make_action(
            environment=Environment.PRODUCTION,
            parameters={"team": "backend"},
        )

        result = await engine.evaluate(
            action,
            agent_id="agent-1",
            context={"team_actions_this_hour": 11},
        )

        assert result.denied is True
        assert "rate limit" in result.reasons[0].lower()
