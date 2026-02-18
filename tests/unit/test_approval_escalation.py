"""Tests for approval timeout escalation and notifier."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from shieldops.models.base import ApprovalStatus, Environment, RemediationAction, RiskLevel
from shieldops.policy.approval.notifier import ApprovalNotifier
from shieldops.policy.approval.workflow import ApprovalRequest, ApprovalWorkflow

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def action():
    return RemediationAction(
        id="act-esc-001",
        action_type="rollback_deployment",
        target_resource="default/api-server",
        environment=Environment.PRODUCTION,
        risk_level=RiskLevel.HIGH,
        parameters={"revision": 3},
        description="Rollback deployment",
    )


@pytest.fixture
def approval_req(action):
    return ApprovalRequest(
        request_id="req-esc-001",
        action=action,
        agent_id="agent-test",
        reason="High risk action requires approval",
        required_approvals=1,
    )


@pytest.fixture
def mock_notifier():
    notifier = AsyncMock(spec=ApprovalNotifier)
    notifier.enabled = True
    return notifier


# ── ApprovalWorkflow Escalation ──────────────────────────────────


class TestApprovalEscalation:
    @pytest.mark.asyncio
    async def test_primary_approval_no_escalation(self, approval_req):
        """Approval within timeout skips escalation entirely."""
        workflow = ApprovalWorkflow(
            timeout_seconds=5,
            escalation_targets=["@sre-manager", "@vp-eng"],
        )

        async def _approve():
            await asyncio.sleep(0.1)
            workflow.approve(approval_req.request_id, "sre-lead")

        asyncio.create_task(_approve())
        result = await workflow.request_approval(approval_req)

        assert result == ApprovalStatus.APPROVED
        assert approval_req.status == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_primary_denial_no_escalation(self, approval_req):
        """Denial within timeout stops immediately."""
        workflow = ApprovalWorkflow(
            timeout_seconds=5,
            escalation_targets=["@sre-manager"],
        )

        async def _deny():
            await asyncio.sleep(0.1)
            workflow.deny(approval_req.request_id, "sre-lead", "Too risky")

        asyncio.create_task(_deny())
        result = await workflow.request_approval(approval_req)

        assert result == ApprovalStatus.DENIED
        assert approval_req.status == ApprovalStatus.DENIED

    @pytest.mark.asyncio
    async def test_primary_timeout_triggers_escalation(self, approval_req, mock_notifier):
        """Primary timeout sends escalation to first target."""
        workflow = ApprovalWorkflow(
            timeout_seconds=1,
            escalation_timeout_seconds=2,
            escalation_targets=["@sre-manager"],
            notifier=mock_notifier,
        )

        async def _approve_on_escalation():
            await asyncio.sleep(1.5)
            workflow.approve(approval_req.request_id, "sre-manager")

        asyncio.create_task(_approve_on_escalation())
        result = await workflow.request_approval(approval_req)

        assert result == ApprovalStatus.APPROVED
        mock_notifier.send_request.assert_awaited_once()
        mock_notifier.send_escalation.assert_awaited_once_with(approval_req, "@sre-manager")
        mock_notifier.send_resolution.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_all_escalation_targets_exhausted(self, approval_req, mock_notifier):
        """When all escalation targets timeout, returns ESCALATED."""
        workflow = ApprovalWorkflow(
            timeout_seconds=1,
            escalation_timeout_seconds=1,
            escalation_targets=["@sre-manager", "@vp-eng"],
            notifier=mock_notifier,
        )

        result = await workflow.request_approval(approval_req)

        assert result == ApprovalStatus.ESCALATED
        assert approval_req.status == ApprovalStatus.ESCALATED
        assert mock_notifier.send_escalation.await_count == 2

    @pytest.mark.asyncio
    async def test_no_escalation_targets_returns_escalated(self, approval_req):
        """Without escalation targets, timeout returns ESCALATED immediately."""
        workflow = ApprovalWorkflow(
            timeout_seconds=1,
            escalation_targets=[],
        )

        result = await workflow.request_approval(approval_req)

        assert result == ApprovalStatus.ESCALATED

    @pytest.mark.asyncio
    async def test_second_escalation_target_approves(self, approval_req, mock_notifier):
        """Second escalation target can approve when first times out."""
        workflow = ApprovalWorkflow(
            timeout_seconds=1,
            escalation_timeout_seconds=2,
            escalation_targets=["@sre-manager", "@vp-eng"],
            notifier=mock_notifier,
        )

        async def _approve_late():
            # primary timeout=1s, first escalation timeout=2s → second escalation starts ~3s
            await asyncio.sleep(3.5)
            workflow.approve(approval_req.request_id, "vp-eng")

        asyncio.create_task(_approve_late())
        result = await workflow.request_approval(approval_req)

        assert result == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_notifier_none_preserves_behavior(self, approval_req):
        """When notifier is None, behavior is poll-only (backward compatible)."""
        workflow = ApprovalWorkflow(
            timeout_seconds=1,
            notifier=None,
        )

        result = await workflow.request_approval(approval_req)

        assert result == ApprovalStatus.ESCALATED


# ── ApprovalNotifier ─────────────────────────────────────────────


class TestApprovalNotifier:
    def test_notifier_disabled_when_no_token(self):
        notifier = ApprovalNotifier(slack_bot_token="", slack_channel="#test")
        assert notifier.enabled is False

    def test_notifier_enabled_with_token(self):
        notifier = ApprovalNotifier(slack_bot_token="xoxb-test", slack_channel="#test")
        assert notifier.enabled is True

    @pytest.mark.asyncio
    async def test_send_request_noop_when_disabled(self, approval_req):
        notifier = ApprovalNotifier(slack_bot_token="")
        await notifier.send_request(approval_req)

    @pytest.mark.asyncio
    async def test_send_escalation_noop_when_disabled(self, approval_req):
        notifier = ApprovalNotifier(slack_bot_token="")
        await notifier.send_escalation(approval_req, "@sre-manager")

    @pytest.mark.asyncio
    async def test_send_resolution_noop_when_disabled(self, approval_req):
        notifier = ApprovalNotifier(slack_bot_token="")
        await notifier.send_resolution(approval_req, ApprovalStatus.APPROVED)

    @pytest.mark.asyncio
    async def test_send_request_posts_to_slack(self, approval_req):
        notifier = ApprovalNotifier(
            slack_bot_token="xoxb-test-token",
            slack_channel="#approvals",
        )

        with patch("shieldops.policy.approval.notifier.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = AsyncMock(
                json=lambda: {"ok": True, "ts": "1234.5678"}
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_request(approval_req)

            mock_client.post.assert_awaited_once()
            call_kwargs = mock_client.post.call_args
            assert "chat.postMessage" in call_kwargs[0][0]
            body = call_kwargs[1]["json"]
            assert body["channel"] == "#approvals"
            assert "Approval Required" in body["text"]
            assert approval_req.request_id in body["text"]

    @pytest.mark.asyncio
    async def test_send_escalation_posts_to_target_channel(self, approval_req):
        notifier = ApprovalNotifier(
            slack_bot_token="xoxb-test-token",
            slack_channel="#approvals",
        )

        with patch("shieldops.policy.approval.notifier.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = AsyncMock(
                json=lambda: {"ok": True, "ts": "1234.5678"}
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_escalation(approval_req, "@sre-manager")

            body = mock_client.post.call_args[1]["json"]
            assert body["channel"] == "@sre-manager"
            assert "Escalation" in body["text"]

    @pytest.mark.asyncio
    async def test_send_request_handles_slack_error(self, approval_req):
        notifier = ApprovalNotifier(
            slack_bot_token="xoxb-test-token",
            slack_channel="#approvals",
        )

        with patch("shieldops.policy.approval.notifier.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = AsyncMock(
                json=lambda: {"ok": False, "error": "channel_not_found"}
            )
            mock_client_cls.return_value = mock_client

            await notifier.send_request(approval_req)

    @pytest.mark.asyncio
    async def test_send_request_handles_network_error(self, approval_req):
        notifier = ApprovalNotifier(
            slack_bot_token="xoxb-test-token",
            slack_channel="#approvals",
        )

        with patch("shieldops.policy.approval.notifier.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.side_effect = Exception("Connection refused")
            mock_client_cls.return_value = mock_client

            await notifier.send_request(approval_req)


# ── Workflow + Notifier Integration ──────────────────────────────


class TestWorkflowWithNotifier:
    @pytest.mark.asyncio
    async def test_approval_sends_request_and_resolution(self, action, mock_notifier):
        """Full flow: send_request on start, send_resolution on approval."""
        workflow = ApprovalWorkflow(
            timeout_seconds=5,
            notifier=mock_notifier,
        )
        req = ApprovalRequest(
            request_id="req-int-001",
            action=action,
            agent_id="agent-test",
            reason="Test",
        )

        async def _approve():
            await asyncio.sleep(0.1)
            workflow.approve(req.request_id, "sre-lead")

        asyncio.create_task(_approve())
        result = await workflow.request_approval(req)

        assert result == ApprovalStatus.APPROVED
        mock_notifier.send_request.assert_awaited_once_with(req)
        mock_notifier.send_resolution.assert_awaited_once()
        resolution_call = mock_notifier.send_resolution.call_args
        assert resolution_call[0][1] == ApprovalStatus.APPROVED


# ── Backward Compatibility ───────────────────────────────────────


class TestBackwardCompatibility:
    def test_workflow_init_without_new_params(self):
        """Workflow still works with original constructor signature."""
        workflow = ApprovalWorkflow(timeout_seconds=300, escalation_timeout_seconds=600)
        assert workflow._notifier is None
        assert workflow._escalation_targets == []

    def test_requires_approval_unchanged(self):
        workflow = ApprovalWorkflow()
        assert workflow.requires_approval(RiskLevel.LOW) is False
        assert workflow.requires_approval(RiskLevel.MEDIUM) is False
        assert workflow.requires_approval(RiskLevel.HIGH) is True
        assert workflow.requires_approval(RiskLevel.CRITICAL) is True

    def test_required_approvals_unchanged(self):
        workflow = ApprovalWorkflow()
        assert workflow.required_approvals(RiskLevel.HIGH) == 1
        assert workflow.required_approvals(RiskLevel.CRITICAL) == 2
