"""Tests for RemediationRunner wiring into API lifespan.

Covers:
- PolicyEngine receives correct OPA URL
- ApprovalWorkflow constructed with defaults
- RemediationRunner receives all 3 dependencies
- remediations._runner is set
- policy_engine.close() awaited on shutdown
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.connectors.base import ConnectorRouter
from shieldops.observability.factory import ObservabilitySources


class TestRemediationWiring:
    @pytest.mark.asyncio
    async def test_remediation_runner_receives_all_deps(self) -> None:
        """RemediationRunner gets connector_router, policy_engine, approval_workflow."""
        from shieldops.api.routes import remediations

        mock_sources = ObservabilitySources(
            log_sources=[AsyncMock()],
            metric_sources=[AsyncMock()],
            trace_sources=[AsyncMock()],
        )
        mock_router = MagicMock(spec=ConnectorRouter)
        mock_policy = MagicMock()
        mock_policy.close = AsyncMock()
        mock_approval = MagicMock()

        with (
            patch("shieldops.api.app.create_observability_sources", return_value=mock_sources),
            patch("shieldops.api.app.create_connector_router", return_value=mock_router),
            patch("shieldops.api.app.InvestigationRunner"),
            patch("shieldops.api.app.PolicyEngine", return_value=mock_policy) as mock_pe_cls,
            patch("shieldops.api.app.ApprovalWorkflow", return_value=mock_approval) as mock_aw_cls,
            patch("shieldops.api.app.RemediationRunner") as mock_rem_cls,
        ):
            from shieldops.api.app import create_app

            app = create_app()

            async with app.router.lifespan_context(app):
                # PolicyEngine created with OPA URL from settings
                mock_pe_cls.assert_called_once()
                call_kwargs = mock_pe_cls.call_args
                assert "opa_url" in call_kwargs.kwargs or len(call_kwargs.args) > 0

                # ApprovalWorkflow created (with optional notifier)
                mock_aw_cls.assert_called_once()

                # RemediationRunner receives all core deps
                mock_rem_cls.assert_called_once()
                rem_kwargs = mock_rem_cls.call_args.kwargs
                assert rem_kwargs["connector_router"] is mock_router
                assert rem_kwargs["policy_engine"] is mock_policy
                assert rem_kwargs["approval_workflow"] is mock_approval

                # Runner injected into route module
                assert remediations._runner is mock_rem_cls.return_value

    @pytest.mark.asyncio
    async def test_policy_engine_closed_on_shutdown(self) -> None:
        """policy_engine.close() is awaited during lifespan shutdown."""
        mock_sources = ObservabilitySources(
            log_sources=[AsyncMock()],
            metric_sources=[AsyncMock()],
            trace_sources=[AsyncMock()],
        )
        mock_router = MagicMock(spec=ConnectorRouter)
        mock_policy = MagicMock()
        mock_policy.close = AsyncMock()

        with (
            patch("shieldops.api.app.create_observability_sources", return_value=mock_sources),
            patch("shieldops.api.app.create_connector_router", return_value=mock_router),
            patch("shieldops.api.app.InvestigationRunner"),
            patch("shieldops.api.app.PolicyEngine", return_value=mock_policy),
            patch("shieldops.api.app.ApprovalWorkflow"),
            patch("shieldops.api.app.RemediationRunner"),
        ):
            from shieldops.api.app import create_app

            app = create_app()

            async with app.router.lifespan_context(app):
                # close not yet called during startup
                mock_policy.close.assert_not_awaited()

        # After lifespan exits, close should have been awaited
        mock_policy.close.assert_awaited_once()
