"""Tests for SupervisorRunner wiring into API lifespan.

Covers:
- agent_runners dict has all specialist keys (including SOC agents)
- SupervisorRunner receives the dict
- supervisor._runner is set
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.connectors.base import ConnectorRouter
from shieldops.observability.factory import ObservabilitySources


class TestSupervisorWiring:
    @pytest.mark.asyncio
    async def test_supervisor_receives_all_agent_runners(self) -> None:
        mock_router = MagicMock(spec=ConnectorRouter)
        mock_policy = MagicMock()
        mock_policy.close = AsyncMock()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "shieldops.api.app.create_observability_sources",
                    return_value=ObservabilitySources(),
                )
            )
            stack.enter_context(
                patch("shieldops.api.app.create_connector_router", return_value=mock_router)
            )

            mock_inv = stack.enter_context(patch("shieldops.api.app.InvestigationRunner"))
            stack.enter_context(patch("shieldops.api.app.PolicyEngine", return_value=mock_policy))
            stack.enter_context(patch("shieldops.api.app.ApprovalWorkflow"))
            mock_rem = stack.enter_context(patch("shieldops.api.app.RemediationRunner"))
            mock_sec = stack.enter_context(patch("shieldops.api.app.SecurityRunner"))
            mock_cost = stack.enter_context(patch("shieldops.api.app.CostRunner"))
            mock_learn = stack.enter_context(patch("shieldops.api.app.LearningRunner"))
            mock_soc = stack.enter_context(patch("shieldops.api.app.SOCAnalystRunner"))
            mock_sup_cls = stack.enter_context(patch("shieldops.api.app.SupervisorRunner"))

            from shieldops.api.app import create_app
            from shieldops.api.routes import supervisor

            app = create_app()
            async with app.router.lifespan_context(app):
                # SupervisorRunner was called exactly once
                mock_sup_cls.assert_called_once()

                # Extract the agent_runners kwarg
                call_kwargs = mock_sup_cls.call_args.kwargs
                runners = call_kwargs["agent_runners"]

                # All specialist keys present (including SOC agents)
                assert "investigation" in runners
                assert "remediation" in runners
                assert "security" in runners
                assert "cost" in runners
                assert "learning" in runners
                assert "soc_analyst" in runners

                # Each value is the return_value of the corresponding mock class
                assert runners["investigation"] is mock_inv.return_value
                assert runners["remediation"] is mock_rem.return_value
                assert runners["security"] is mock_sec.return_value
                assert runners["cost"] is mock_cost.return_value
                assert runners["learning"] is mock_learn.return_value
                assert runners["soc_analyst"] is mock_soc.return_value

                # Runner injected into route module
                assert supervisor._runner is mock_sup_cls.return_value
