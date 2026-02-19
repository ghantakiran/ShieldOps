"""Tests for WebSocket broadcasting wiring.

Covers:
- get_ws_manager() singleton pattern
- InvestigationRunner._broadcast() with and without ws_manager
- RemediationRunner._broadcast() with and without ws_manager
- ConnectionManager.broadcast() delivery and dead-connection cleanup
- Lifespan wiring: runners receive ws_manager from get_ws_manager()
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.api.ws.manager import ConnectionManager

# ---------------------------------------------------------------------------
# Singleton: get_ws_manager()
# ---------------------------------------------------------------------------


class TestGetWsManagerSingleton:
    def setup_method(self) -> None:
        """Reset the module-level singleton before each test."""
        import shieldops.api.ws.manager as mgr_mod

        mgr_mod._default_manager = None

    def test_returns_connection_manager_instance(self) -> None:
        """get_ws_manager() should return a ConnectionManager."""
        from shieldops.api.ws.manager import get_ws_manager

        mgr = get_ws_manager()
        assert isinstance(mgr, ConnectionManager)

    def test_returns_same_instance_on_repeated_calls(self) -> None:
        """Calling get_ws_manager() twice must return the same object."""
        from shieldops.api.ws.manager import get_ws_manager

        first = get_ws_manager()
        second = get_ws_manager()
        assert first is second

    def test_reset_creates_new_instance(self) -> None:
        """After resetting _default_manager, a fresh instance is created."""
        import shieldops.api.ws.manager as mgr_mod
        from shieldops.api.ws.manager import get_ws_manager

        first = get_ws_manager()
        mgr_mod._default_manager = None
        second = get_ws_manager()
        assert first is not second


# ---------------------------------------------------------------------------
# ConnectionManager.broadcast()
# ---------------------------------------------------------------------------


class TestConnectionManagerBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_subscribers(self) -> None:
        """broadcast() should call send_json on every websocket in the channel."""
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        # Manually add sockets (bypass .connect() which calls accept())
        mgr._channels["test_channel"].add(ws1)
        mgr._channels["test_channel"].add(ws2)

        event = {"type": "test", "value": 42}
        await mgr.broadcast("test_channel", event)

        ws1.send_json.assert_awaited_once_with(event)
        ws2.send_json.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self) -> None:
        """If send_json raises, that websocket should be removed from the channel."""
        mgr = ConnectionManager()
        alive_ws = AsyncMock()
        dead_ws = AsyncMock()
        dead_ws.send_json.side_effect = RuntimeError("connection closed")

        mgr._channels["ch"].add(alive_ws)
        mgr._channels["ch"].add(dead_ws)

        await mgr.broadcast("ch", {"type": "ping"})

        # Dead socket removed
        assert dead_ws not in mgr._channels["ch"]
        # Alive socket still present
        assert alive_ws in mgr._channels["ch"]

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_channel_is_noop(self) -> None:
        """Broadcasting to a channel with no subscribers should not raise."""
        mgr = ConnectionManager()
        await mgr.broadcast("nonexistent", {"type": "noop"})
        # No error means pass

    @pytest.mark.asyncio
    async def test_broadcast_only_affects_target_channel(self) -> None:
        """Sockets in other channels must not receive the broadcast."""
        mgr = ConnectionManager()
        target_ws = AsyncMock()
        other_ws = AsyncMock()

        mgr._channels["target"].add(target_ws)
        mgr._channels["other"].add(other_ws)

        await mgr.broadcast("target", {"type": "scoped"})

        target_ws.send_json.assert_awaited_once()
        other_ws.send_json.assert_not_awaited()


# ---------------------------------------------------------------------------
# InvestigationRunner._broadcast()
# ---------------------------------------------------------------------------


class TestInvestigationRunnerBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_ws_manager(self) -> None:
        """When ws_manager is provided, _broadcast() sends to both channels."""
        from shieldops.agents.investigation.models import InvestigationState
        from shieldops.models.base import AlertContext

        mock_mgr = AsyncMock(spec=ConnectionManager)

        with patch("shieldops.agents.investigation.runner.create_investigation_graph"):
            from shieldops.agents.investigation.runner import InvestigationRunner

            runner = InvestigationRunner(ws_manager=mock_mgr)

        alert = AlertContext(
            alert_id="a1",
            alert_name="HighCPU",
            severity="critical",
            source="prometheus",
            triggered_at=datetime.now(UTC),
        )
        state = InvestigationState(
            alert_id="a1",
            alert_context=alert,
            current_step="completed",
            confidence_score=0.85,
        )

        await runner._broadcast("inv-abc123", state)

        # Should broadcast to both global and investigation-specific channels
        assert mock_mgr.broadcast.await_count == 2
        calls = mock_mgr.broadcast.await_args_list
        channels = {c.args[0] for c in calls}
        assert channels == {"global", "investigation:inv-abc123"}

        # Verify event payload structure
        event = calls[0].args[1]
        assert event["type"] == "investigation_update"
        assert event["investigation_id"] == "inv-abc123"
        assert event["status"] == "completed"
        assert event["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_broadcast_noop_without_ws_manager(self) -> None:
        """When ws_manager is None, _broadcast() must be a silent no-op."""
        from shieldops.agents.investigation.models import InvestigationState
        from shieldops.models.base import AlertContext

        with patch("shieldops.agents.investigation.runner.create_investigation_graph"):
            from shieldops.agents.investigation.runner import InvestigationRunner

            runner = InvestigationRunner(ws_manager=None)

        alert = AlertContext(
            alert_id="a1",
            alert_name="HighCPU",
            severity="warning",
            source="datadog",
            triggered_at=datetime.now(UTC),
        )
        state = InvestigationState(alert_id="a1", alert_context=alert)

        # Should not raise
        await runner._broadcast("inv-noop", state)

    @pytest.mark.asyncio
    async def test_broadcast_swallows_exceptions(self) -> None:
        """If ws_manager.broadcast raises, the error is logged, not raised."""
        from shieldops.agents.investigation.models import InvestigationState
        from shieldops.models.base import AlertContext

        mock_mgr = AsyncMock(spec=ConnectionManager)
        mock_mgr.broadcast.side_effect = RuntimeError("ws boom")

        with patch("shieldops.agents.investigation.runner.create_investigation_graph"):
            from shieldops.agents.investigation.runner import InvestigationRunner

            runner = InvestigationRunner(ws_manager=mock_mgr)

        alert = AlertContext(
            alert_id="a1",
            alert_name="NetErr",
            severity="critical",
            source="cloudwatch",
            triggered_at=datetime.now(UTC),
        )
        state = InvestigationState(alert_id="a1", alert_context=alert)

        # Must not propagate the exception
        await runner._broadcast("inv-err", state)


# ---------------------------------------------------------------------------
# RemediationRunner._broadcast()
# ---------------------------------------------------------------------------


class TestRemediationRunnerBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_ws_manager(self) -> None:
        """When ws_manager is provided, _broadcast() sends to both channels."""
        from shieldops.agents.remediation.models import RemediationState
        from shieldops.models.base import (
            Environment,
            RemediationAction,
            RiskLevel,
        )

        mock_mgr = AsyncMock(spec=ConnectionManager)

        with patch("shieldops.agents.remediation.runner.create_remediation_graph"):
            from shieldops.agents.remediation.runner import RemediationRunner

            runner = RemediationRunner(ws_manager=mock_mgr)

        action = RemediationAction(
            id="act-1",
            action_type="restart_pod",
            target_resource="web-frontend",
            environment=Environment.STAGING,
            risk_level=RiskLevel.LOW,
            description="Restart the web frontend pod",
        )
        state = RemediationState(
            remediation_id="rem-xyz789",
            action=action,
            current_step="completed",
            validation_passed=True,
        )

        await runner._broadcast("rem-xyz789", state)

        assert mock_mgr.broadcast.await_count == 2
        calls = mock_mgr.broadcast.await_args_list
        channels = {c.args[0] for c in calls}
        assert channels == {"global", "remediation:rem-xyz789"}

        event = calls[0].args[1]
        assert event["type"] == "remediation_update"
        assert event["remediation_id"] == "rem-xyz789"
        assert event["action_type"] == "restart_pod"
        assert event["validation_passed"] is True

    @pytest.mark.asyncio
    async def test_broadcast_noop_without_ws_manager(self) -> None:
        """When ws_manager is None, _broadcast() must be a silent no-op."""
        from shieldops.agents.remediation.models import RemediationState
        from shieldops.models.base import (
            Environment,
            RemediationAction,
            RiskLevel,
        )

        with patch("shieldops.agents.remediation.runner.create_remediation_graph"):
            from shieldops.agents.remediation.runner import RemediationRunner

            runner = RemediationRunner(ws_manager=None)

        action = RemediationAction(
            id="act-2",
            action_type="scale_horizontal",
            target_resource="api-service",
            environment=Environment.DEVELOPMENT,
            risk_level=RiskLevel.LOW,
            description="Scale API pods",
        )
        state = RemediationState(remediation_id="rem-noop", action=action)

        # Should not raise
        await runner._broadcast("rem-noop", state)

    @pytest.mark.asyncio
    async def test_broadcast_swallows_exceptions(self) -> None:
        """If ws_manager.broadcast raises, the error is logged, not raised."""
        from shieldops.agents.remediation.models import RemediationState
        from shieldops.models.base import (
            Environment,
            RemediationAction,
            RiskLevel,
        )

        mock_mgr = AsyncMock(spec=ConnectionManager)
        mock_mgr.broadcast.side_effect = RuntimeError("ws boom")

        with patch("shieldops.agents.remediation.runner.create_remediation_graph"):
            from shieldops.agents.remediation.runner import RemediationRunner

            runner = RemediationRunner(ws_manager=mock_mgr)

        action = RemediationAction(
            id="act-3",
            action_type="rollback_deployment",
            target_resource="payment-svc",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.HIGH,
            description="Rollback payment service",
        )
        state = RemediationState(remediation_id="rem-err", action=action)

        # Must not propagate the exception
        await runner._broadcast("rem-err", state)


# ---------------------------------------------------------------------------
# Lifespan wiring: runners receive ws_manager
# ---------------------------------------------------------------------------


class TestLifespanWsWiring:
    @pytest.mark.asyncio
    async def test_investigation_runner_receives_ws_manager(self) -> None:
        """InvestigationRunner in lifespan must get ws_manager kwarg."""
        from shieldops.connectors.base import ConnectorRouter
        from shieldops.observability.factory import ObservabilitySources

        mock_sources = ObservabilitySources(
            log_sources=[AsyncMock()],
            metric_sources=[AsyncMock()],
            trace_sources=[AsyncMock()],
        )
        mock_router = MagicMock(spec=ConnectorRouter)
        mock_policy = MagicMock()
        mock_policy.close = AsyncMock()
        mock_ws_mgr = MagicMock(spec=ConnectionManager)

        with (
            patch(
                "shieldops.api.app.create_observability_sources",
                return_value=mock_sources,
            ),
            patch(
                "shieldops.api.app.create_connector_router",
                return_value=mock_router,
            ),
            patch("shieldops.api.app.InvestigationRunner") as mock_inv_cls,
            patch(
                "shieldops.api.app.PolicyEngine",
                return_value=mock_policy,
            ),
            patch("shieldops.api.app.ApprovalWorkflow"),
            patch("shieldops.api.app.RemediationRunner"),
            patch(
                "shieldops.api.ws.manager.get_ws_manager",
                return_value=mock_ws_mgr,
            ),
        ):
            from shieldops.api.app import create_app

            test_app = create_app()

            async with test_app.router.lifespan_context(test_app):
                mock_inv_cls.assert_called_once()
                inv_kwargs = mock_inv_cls.call_args.kwargs
                assert inv_kwargs["ws_manager"] is mock_ws_mgr

    @pytest.mark.asyncio
    async def test_remediation_runner_receives_ws_manager(self) -> None:
        """RemediationRunner in lifespan must get ws_manager kwarg."""
        from shieldops.connectors.base import ConnectorRouter
        from shieldops.observability.factory import ObservabilitySources

        mock_sources = ObservabilitySources(
            log_sources=[AsyncMock()],
            metric_sources=[AsyncMock()],
            trace_sources=[AsyncMock()],
        )
        mock_router = MagicMock(spec=ConnectorRouter)
        mock_policy = MagicMock()
        mock_policy.close = AsyncMock()
        mock_ws_mgr = MagicMock(spec=ConnectionManager)

        with (
            patch(
                "shieldops.api.app.create_observability_sources",
                return_value=mock_sources,
            ),
            patch(
                "shieldops.api.app.create_connector_router",
                return_value=mock_router,
            ),
            patch("shieldops.api.app.InvestigationRunner"),
            patch(
                "shieldops.api.app.PolicyEngine",
                return_value=mock_policy,
            ),
            patch("shieldops.api.app.ApprovalWorkflow"),
            patch("shieldops.api.app.RemediationRunner") as mock_rem_cls,
            patch(
                "shieldops.api.ws.manager.get_ws_manager",
                return_value=mock_ws_mgr,
            ),
        ):
            from shieldops.api.app import create_app

            test_app = create_app()

            async with test_app.router.lifespan_context(test_app):
                mock_rem_cls.assert_called_once()
                rem_kwargs = mock_rem_cls.call_args.kwargs
                assert rem_kwargs["ws_manager"] is mock_ws_mgr
