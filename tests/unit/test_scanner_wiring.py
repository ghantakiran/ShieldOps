"""Tests for security scanner wiring into API lifespan.

Covers:
- When scanner settings are disabled (default), scanners list stays empty
- When scanner settings are enabled, SecurityRunner receives them
- Each scanner type is independently opt-in
- Scanner init failures are non-fatal
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.config.settings import settings
from shieldops.connectors.base import ConnectorRouter
from shieldops.observability.factory import ObservabilitySources


def _make_mock_infra() -> tuple[ObservabilitySources, MagicMock, MagicMock]:
    """Create reusable mock infrastructure objects."""
    mock_sources = ObservabilitySources(
        log_sources=[AsyncMock()],
        metric_sources=[AsyncMock()],
        trace_sources=[AsyncMock()],
    )
    mock_router = MagicMock(spec=ConnectorRouter)
    mock_policy = MagicMock()
    mock_policy.close = AsyncMock()
    return mock_sources, mock_router, mock_policy


class TestScannerWiringDefaults:
    """Scanners are NOT loaded when settings are disabled."""

    @pytest.mark.asyncio
    async def test_scanners_empty_by_default(self) -> None:
        """With default settings all scanner flags are False,
        so SecurityRunner.security_scanners should be None."""
        sources, router, policy = _make_mock_infra()

        with (
            patch(
                "shieldops.api.app.create_observability_sources",
                return_value=sources,
            ),
            patch(
                "shieldops.api.app.create_connector_router",
                return_value=router,
            ),
            patch("shieldops.api.app.InvestigationRunner"),
            patch(
                "shieldops.api.app.PolicyEngine",
                return_value=policy,
            ),
            patch("shieldops.api.app.ApprovalWorkflow"),
            patch("shieldops.api.app.RemediationRunner"),
            patch(
                "shieldops.api.app.SecurityRunner",
            ) as mock_sec_cls,
        ):
            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                mock_sec_cls.assert_called_once()
                kw = mock_sec_cls.call_args.kwargs
                # Empty list becomes None via `or None`
                assert kw["security_scanners"] is None


class TestScannerWiringEnabled:
    """Each scanner is loaded when its flag is True."""

    @pytest.mark.asyncio
    async def test_iac_scanner_wired(self) -> None:
        """IaCScanner appears in security_scanners."""
        sources, router, policy = _make_mock_infra()
        mock_iac = MagicMock()

        with (
            patch(
                "shieldops.api.app.create_observability_sources",
                return_value=sources,
            ),
            patch(
                "shieldops.api.app.create_connector_router",
                return_value=router,
            ),
            patch("shieldops.api.app.InvestigationRunner"),
            patch(
                "shieldops.api.app.PolicyEngine",
                return_value=policy,
            ),
            patch("shieldops.api.app.ApprovalWorkflow"),
            patch("shieldops.api.app.RemediationRunner"),
            patch(
                "shieldops.api.app.SecurityRunner",
            ) as mock_sec_cls,
            patch.object(settings, "iac_scanner_enabled", True),
            patch(
                "shieldops.integrations.scanners.iac_scanner.IaCScanner",
                return_value=mock_iac,
            ),
        ):
            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                kw = mock_sec_cls.call_args.kwargs
                scanners = kw["security_scanners"]
                assert scanners is not None
                assert mock_iac in scanners
                assert len(scanners) == 1

    @pytest.mark.asyncio
    async def test_git_scanners_wired(self) -> None:
        """GitSecretScanner + GitDependencyScanner both appear."""
        sources, router, policy = _make_mock_infra()
        mock_secret = MagicMock()
        mock_dep = MagicMock()

        with (
            patch(
                "shieldops.api.app.create_observability_sources",
                return_value=sources,
            ),
            patch(
                "shieldops.api.app.create_connector_router",
                return_value=router,
            ),
            patch("shieldops.api.app.InvestigationRunner"),
            patch(
                "shieldops.api.app.PolicyEngine",
                return_value=policy,
            ),
            patch("shieldops.api.app.ApprovalWorkflow"),
            patch("shieldops.api.app.RemediationRunner"),
            patch(
                "shieldops.api.app.SecurityRunner",
            ) as mock_sec_cls,
            patch.object(settings, "git_scanner_enabled", True),
            patch(
                "shieldops.integrations.scanners.git_scanner.GitSecretScanner",
                return_value=mock_secret,
            ),
            patch(
                "shieldops.integrations.scanners.git_scanner.GitDependencyScanner",
                return_value=mock_dep,
            ),
        ):
            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                kw = mock_sec_cls.call_args.kwargs
                scanners = kw["security_scanners"]
                assert scanners is not None
                assert mock_secret in scanners
                assert mock_dep in scanners
                assert len(scanners) == 2

    @pytest.mark.asyncio
    async def test_k8s_scanner_wired(self) -> None:
        """K8sSecurityScanner appears with connector_router."""
        sources, router, policy = _make_mock_infra()
        mock_k8s = MagicMock()

        with (
            patch(
                "shieldops.api.app.create_observability_sources",
                return_value=sources,
            ),
            patch(
                "shieldops.api.app.create_connector_router",
                return_value=router,
            ),
            patch("shieldops.api.app.InvestigationRunner"),
            patch(
                "shieldops.api.app.PolicyEngine",
                return_value=policy,
            ),
            patch("shieldops.api.app.ApprovalWorkflow"),
            patch("shieldops.api.app.RemediationRunner"),
            patch(
                "shieldops.api.app.SecurityRunner",
            ) as mock_sec_cls,
            patch.object(settings, "k8s_scanner_enabled", True),
            patch(
                "shieldops.integrations.scanners.k8s_security.K8sSecurityScanner",
                return_value=mock_k8s,
            ),
        ):
            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                kw = mock_sec_cls.call_args.kwargs
                scanners = kw["security_scanners"]
                assert scanners is not None
                assert mock_k8s in scanners
                assert len(scanners) == 1

    @pytest.mark.asyncio
    async def test_network_scanner_wired(self) -> None:
        """NetworkSecurityScanner appears with connector_router."""
        sources, router, policy = _make_mock_infra()
        mock_net = MagicMock()

        with (
            patch(
                "shieldops.api.app.create_observability_sources",
                return_value=sources,
            ),
            patch(
                "shieldops.api.app.create_connector_router",
                return_value=router,
            ),
            patch("shieldops.api.app.InvestigationRunner"),
            patch(
                "shieldops.api.app.PolicyEngine",
                return_value=policy,
            ),
            patch("shieldops.api.app.ApprovalWorkflow"),
            patch("shieldops.api.app.RemediationRunner"),
            patch(
                "shieldops.api.app.SecurityRunner",
            ) as mock_sec_cls,
            patch.object(settings, "network_scanner_enabled", True),
            patch(
                "shieldops.integrations.scanners.network_scanner.NetworkSecurityScanner",
                return_value=mock_net,
            ),
        ):
            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                kw = mock_sec_cls.call_args.kwargs
                scanners = kw["security_scanners"]
                assert scanners is not None
                assert mock_net in scanners
                assert len(scanners) == 1

    @pytest.mark.asyncio
    async def test_all_scanners_wired(self) -> None:
        """All 5 scanner instances appear when every flag is on."""
        sources, router, policy = _make_mock_infra()
        mock_iac = MagicMock()
        mock_secret = MagicMock()
        mock_dep = MagicMock()
        mock_k8s = MagicMock()
        mock_net = MagicMock()

        with (
            patch(
                "shieldops.api.app.create_observability_sources",
                return_value=sources,
            ),
            patch(
                "shieldops.api.app.create_connector_router",
                return_value=router,
            ),
            patch("shieldops.api.app.InvestigationRunner"),
            patch(
                "shieldops.api.app.PolicyEngine",
                return_value=policy,
            ),
            patch("shieldops.api.app.ApprovalWorkflow"),
            patch("shieldops.api.app.RemediationRunner"),
            patch(
                "shieldops.api.app.SecurityRunner",
            ) as mock_sec_cls,
            patch.object(settings, "iac_scanner_enabled", True),
            patch.object(settings, "git_scanner_enabled", True),
            patch.object(settings, "k8s_scanner_enabled", True),
            patch.object(settings, "network_scanner_enabled", True),
            patch(
                "shieldops.integrations.scanners.iac_scanner.IaCScanner",
                return_value=mock_iac,
            ),
            patch(
                "shieldops.integrations.scanners.git_scanner.GitSecretScanner",
                return_value=mock_secret,
            ),
            patch(
                "shieldops.integrations.scanners.git_scanner.GitDependencyScanner",
                return_value=mock_dep,
            ),
            patch(
                "shieldops.integrations.scanners.k8s_security.K8sSecurityScanner",
                return_value=mock_k8s,
            ),
            patch(
                "shieldops.integrations.scanners.network_scanner.NetworkSecurityScanner",
                return_value=mock_net,
            ),
        ):
            from shieldops.api.app import create_app

            app = create_app()
            async with app.router.lifespan_context(app):
                kw = mock_sec_cls.call_args.kwargs
                scanners = kw["security_scanners"]
                assert scanners is not None
                assert len(scanners) == 5
                assert mock_iac in scanners
                assert mock_secret in scanners
                assert mock_dep in scanners
                assert mock_k8s in scanners
                assert mock_net in scanners


class TestScannerWiringErrorHandling:
    """Scanner init failures are non-fatal."""

    @pytest.mark.asyncio
    async def test_iac_scanner_init_error_non_fatal(self) -> None:
        """If IaCScanner() raises, startup continues and the
        scanner is simply skipped."""
        sources, router, policy = _make_mock_infra()

        with (
            patch(
                "shieldops.api.app.create_observability_sources",
                return_value=sources,
            ),
            patch(
                "shieldops.api.app.create_connector_router",
                return_value=router,
            ),
            patch("shieldops.api.app.InvestigationRunner"),
            patch(
                "shieldops.api.app.PolicyEngine",
                return_value=policy,
            ),
            patch("shieldops.api.app.ApprovalWorkflow"),
            patch("shieldops.api.app.RemediationRunner"),
            patch(
                "shieldops.api.app.SecurityRunner",
            ) as mock_sec_cls,
            patch.object(settings, "iac_scanner_enabled", True),
            patch(
                "shieldops.integrations.scanners.iac_scanner.IaCScanner",
                side_effect=RuntimeError("checkov missing"),
            ),
        ):
            from shieldops.api.app import create_app

            app = create_app()
            # Startup should NOT raise
            async with app.router.lifespan_context(app):
                kw = mock_sec_cls.call_args.kwargs
                # Scanner list stays empty -> None
                assert kw["security_scanners"] is None
