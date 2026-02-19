"""Tests for SecurityRunner, CostRunner, and LearningRunner wiring into API lifespan.

Covers:
- Each runner constructed with correct args
- Each route module's _runner is set
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.connectors.base import ConnectorRouter
from shieldops.observability.factory import ObservabilitySources


def _enter_infra_patches(stack: ExitStack, mock_router: MagicMock) -> None:
    """Enter the common infrastructure patches on the given ExitStack."""
    mock_policy = MagicMock()
    mock_policy.close = AsyncMock()
    stack.enter_context(
        patch("shieldops.api.app.create_observability_sources", return_value=ObservabilitySources())
    )
    stack.enter_context(
        patch("shieldops.api.app.create_connector_router", return_value=mock_router)
    )
    stack.enter_context(patch("shieldops.api.app.InvestigationRunner"))
    stack.enter_context(patch("shieldops.api.app.PolicyEngine", return_value=mock_policy))
    stack.enter_context(patch("shieldops.api.app.ApprovalWorkflow"))
    stack.enter_context(patch("shieldops.api.app.RemediationRunner"))


class TestSecurityRunnerWiring:
    @pytest.mark.asyncio
    async def test_security_runner_receives_connector_router(self) -> None:
        mock_router = MagicMock(spec=ConnectorRouter)

        with ExitStack() as stack:
            _enter_infra_patches(stack, mock_router)
            mock_sec_cls = stack.enter_context(patch("shieldops.api.app.SecurityRunner"))
            stack.enter_context(patch("shieldops.api.app.CostRunner"))
            stack.enter_context(patch("shieldops.api.app.LearningRunner"))

            from shieldops.api.app import create_app
            from shieldops.api.routes import security

            app = create_app()
            async with app.router.lifespan_context(app):
                mock_sec_cls.assert_called_once()
                call_kwargs = mock_sec_cls.call_args[1]
                assert call_kwargs["connector_router"] is mock_router
                assert "policy_engine" in call_kwargs
                assert "approval_workflow" in call_kwargs
                assert "repository" in call_kwargs
                assert security._runner is mock_sec_cls.return_value


class TestCostRunnerWiring:
    @pytest.mark.asyncio
    async def test_cost_runner_receives_connector_router(self) -> None:
        mock_router = MagicMock(spec=ConnectorRouter)

        with ExitStack() as stack:
            _enter_infra_patches(stack, mock_router)
            stack.enter_context(patch("shieldops.api.app.SecurityRunner"))
            mock_cost_cls = stack.enter_context(patch("shieldops.api.app.CostRunner"))
            stack.enter_context(patch("shieldops.api.app.LearningRunner"))

            from shieldops.api.app import create_app
            from shieldops.api.routes import cost

            app = create_app()
            async with app.router.lifespan_context(app):
                mock_cost_cls.assert_called_once_with(
                    connector_router=mock_router, billing_sources=None
                )
                assert cost._runner is mock_cost_cls.return_value


class TestLearningRunnerWiring:
    @pytest.mark.asyncio
    async def test_learning_runner_constructed_with_no_args(self) -> None:
        mock_router = MagicMock(spec=ConnectorRouter)

        with ExitStack() as stack:
            _enter_infra_patches(stack, mock_router)
            stack.enter_context(patch("shieldops.api.app.SecurityRunner"))
            stack.enter_context(patch("shieldops.api.app.CostRunner"))
            mock_learn_cls = stack.enter_context(patch("shieldops.api.app.LearningRunner"))

            from shieldops.api.app import create_app
            from shieldops.api.routes import learning

            app = create_app()
            async with app.router.lifespan_context(app):
                mock_learn_cls.assert_called_once()
                call_kwargs = mock_learn_cls.call_args[1]
                assert "repository" in call_kwargs
                assert "playbook_loader" in call_kwargs
                assert learning._runner is mock_learn_cls.return_value
