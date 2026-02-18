"""Human-in-the-loop approval workflow for high-risk agent actions."""

import asyncio
from datetime import datetime, timezone

import structlog

from shieldops.models.base import ApprovalStatus, RemediationAction, RiskLevel

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
        self.created_at = datetime.now(timezone.utc)

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
    ) -> None:
        self._timeout = timeout_seconds
        self._escalation_timeout = escalation_timeout_seconds
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

        # TODO: Send Slack/Teams notification with approve/deny buttons

        # Wait for response with timeout
        try:
            result = await asyncio.wait_for(
                self._wait_for_decision(request),
                timeout=self._timeout,
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(
                "approval_timeout",
                request_id=request.request_id,
            )
            request.status = ApprovalStatus.TIMEOUT
            # TODO: Escalate to next responder
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
