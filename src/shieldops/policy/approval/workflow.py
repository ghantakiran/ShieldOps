"""Human-in-the-loop approval workflow for high-risk agent actions."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from shieldops.models.base import ApprovalStatus, RemediationAction, RiskLevel

if TYPE_CHECKING:
    from shieldops.policy.approval.notifier import ApprovalNotifier

logger = structlog.get_logger()


class ApprovalRequest:
    """A pending approval request for an agent action."""

    def __init__(
        self,
        request_id: str,
        action: RemediationAction,
        agent_id: str,
        reason: str,
        required_approvals: int = 1,
    ) -> None:
        self.request_id = request_id
        self.action = action
        self.agent_id = agent_id
        self.reason = reason
        self.required_approvals = required_approvals
        self.status = ApprovalStatus.PENDING
        self.approvals: list[str] = []
        self.denials: list[str] = []
        self.created_at = datetime.now(UTC)

    @property
    def is_approved(self) -> bool:
        return len(self.approvals) >= self.required_approvals

    @property
    def is_denied(self) -> bool:
        return len(self.denials) > 0


class ApprovalWorkflow:
    """Manages human approval workflows for agent actions.

    Routes approval requests to Slack/Teams, tracks responses,
    handles timeouts and escalation.
    """

    def __init__(
        self,
        timeout_seconds: int = 300,
        escalation_timeout_seconds: int = 600,
        escalation_targets: list[str] | None = None,
        notifier: ApprovalNotifier | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._escalation_timeout = escalation_timeout_seconds
        self._escalation_targets = escalation_targets or []
        self._notifier = notifier
        self._pending: dict[str, ApprovalRequest] = {}

    def requires_approval(self, risk_level: RiskLevel) -> bool:
        """Determine if an action requires human approval based on risk level."""
        return risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def required_approvals(self, risk_level: RiskLevel) -> int:
        """Number of approvals required based on risk level."""
        if risk_level == RiskLevel.CRITICAL:
            return 2  # Four-eyes principle
        return 1

    async def request_approval(self, request: ApprovalRequest) -> ApprovalStatus:
        """Submit an approval request and wait for response.

        Sends notification to configured channel (Slack/Teams),
        waits for approval/denial, handles timeout and escalation.
        """
        self._pending[request.request_id] = request

        logger.info(
            "approval_requested",
            request_id=request.request_id,
            action=request.action.action_type,
            risk_level=request.action.risk_level.value,
            required_approvals=request.required_approvals,
        )

        # Notify via Slack if notifier is configured
        if self._notifier:
            await self._notifier.send_request(request)

        # Wait for primary response with timeout
        try:
            result = await asyncio.wait_for(
                self._wait_for_decision(request),
                timeout=self._timeout,
            )
            if self._notifier:
                await self._notifier.send_resolution(request, result)
            return result
        except TimeoutError:
            logger.warning(
                "approval_primary_timeout",
                request_id=request.request_id,
            )

        # Primary timed out — try escalation chain
        if self._escalation_targets:
            result = await self._run_escalation_chain(request)
            if self._notifier:
                await self._notifier.send_resolution(request, result)
            return result

        # No escalation targets — mark as escalated
        request.status = ApprovalStatus.ESCALATED
        if self._notifier:
            await self._notifier.send_resolution(request, ApprovalStatus.ESCALATED)
        return ApprovalStatus.ESCALATED

    async def _run_escalation_chain(self, request: ApprovalRequest) -> ApprovalStatus:
        """Walk the escalation chain, notifying each target in sequence."""
        for target in self._escalation_targets:
            logger.info(
                "approval_escalating",
                request_id=request.request_id,
                target=target,
            )

            if self._notifier:
                await self._notifier.send_escalation(request, target)

            try:
                result = await asyncio.wait_for(
                    self._wait_for_decision(request),
                    timeout=self._escalation_timeout,
                )
                return result
            except TimeoutError:
                logger.warning(
                    "approval_escalation_timeout",
                    request_id=request.request_id,
                    target=target,
                )
                continue

        # All escalation targets exhausted
        request.status = ApprovalStatus.ESCALATED
        return ApprovalStatus.ESCALATED

    async def _wait_for_decision(self, request: ApprovalRequest) -> ApprovalStatus:
        """Poll for approval decision."""
        while True:
            if request.is_approved:
                request.status = ApprovalStatus.APPROVED
                return ApprovalStatus.APPROVED
            if request.is_denied:
                request.status = ApprovalStatus.DENIED
                return ApprovalStatus.DENIED
            await asyncio.sleep(1)

    def approve(self, request_id: str, approver: str) -> None:
        """Record an approval for a pending request."""
        if request_id in self._pending:
            self._pending[request_id].approvals.append(approver)
            logger.info("approval_granted", request_id=request_id, approver=approver)

    def deny(self, request_id: str, denier: str, reason: str = "") -> None:
        """Record a denial for a pending request."""
        if request_id in self._pending:
            self._pending[request_id].denials.append(denier)
            logger.info("approval_denied", request_id=request_id, denier=denier, reason=reason)
