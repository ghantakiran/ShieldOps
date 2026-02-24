"""Deployment Approval Gate — multi-stage deployment approval gates."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"
    EXPIRED = "expired"


class GateType(StrEnum):
    MANUAL_REVIEW = "manual_review"
    AUTOMATED_CHECK = "automated_check"
    SECURITY_SCAN = "security_scan"
    LOAD_TEST = "load_test"
    CANARY_VALIDATION = "canary_validation"


class ApprovalLevel(StrEnum):
    TEAM_LEAD = "team_lead"
    ENGINEERING_MANAGER = "engineering_manager"
    SRE_ON_CALL = "sre_on_call"
    SECURITY_TEAM = "security_team"
    VP_ENGINEERING = "vp_engineering"


# --- Models ---


class DeploymentGate(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    deployment_id: str = ""
    service_name: str = ""
    gate_type: GateType = GateType.MANUAL_REVIEW
    status: GateStatus = GateStatus.PENDING
    approval_level: ApprovalLevel = ApprovalLevel.TEAM_LEAD
    approver: str = ""
    reason: str = ""
    pre_checks: list[str] = Field(
        default_factory=list,
    )
    expires_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class GateDecision(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    gate_id: str = ""
    decision: str = ""
    decided_by: str = ""
    rationale: str = ""
    decided_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class GateReport(BaseModel):
    total_gates: int = 0
    total_decisions: int = 0
    approval_rate_pct: float = 0.0
    avg_wait_hours: float = 0.0
    by_status: dict[str, int] = Field(
        default_factory=dict,
    )
    by_type: dict[str, int] = Field(
        default_factory=dict,
    )
    slow_gates: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(
        default_factory=time.time,
    )


# --- Gate Manager ---


class DeploymentApprovalGate:
    """Manage multi-stage deployment approval gates."""

    def __init__(
        self,
        max_gates: int = 100000,
        gate_expiry_hours: float = 24,
    ) -> None:
        self._max_gates = max_gates
        self._gate_expiry_hours = gate_expiry_hours
        self._items: list[DeploymentGate] = []
        self._decisions: list[GateDecision] = []
        logger.info(
            "deployment_gate.initialized",
            max_gates=max_gates,
            gate_expiry_hours=gate_expiry_hours,
        )

    # -- create --

    def create_gate(
        self,
        deployment_id: str,
        service_name: str = "",
        gate_type: GateType = GateType.MANUAL_REVIEW,
        approval_level: ApprovalLevel = (ApprovalLevel.TEAM_LEAD),
        reason: str = "",
        pre_checks: list[str] | None = None,
        **kw: Any,
    ) -> DeploymentGate:
        """Create a new deployment gate."""
        now = time.time()
        expires = now + (self._gate_expiry_hours * 3600)
        gate = DeploymentGate(
            deployment_id=deployment_id,
            service_name=service_name,
            gate_type=gate_type,
            approval_level=approval_level,
            reason=reason,
            pre_checks=pre_checks or [],
            expires_at=expires,
            **kw,
        )
        self._items.append(gate)
        if len(self._items) > self._max_gates:
            self._items = self._items[-self._max_gates :]
        logger.info(
            "deployment_gate.created",
            gate_id=gate.id,
            deployment_id=deployment_id,
        )
        return gate

    # -- get / list --

    def get_gate(
        self,
        gate_id: str,
    ) -> DeploymentGate | None:
        """Get a single gate by ID."""
        for item in self._items:
            if item.id == gate_id:
                return item
        return None

    def list_gates(
        self,
        deployment_id: str | None = None,
        status: GateStatus | None = None,
        limit: int = 50,
    ) -> list[DeploymentGate]:
        """List gates with optional filters."""
        results = list(self._items)
        if deployment_id is not None:
            results = [g for g in results if g.deployment_id == deployment_id]
        if status is not None:
            results = [g for g in results if g.status == status]
        return results[-limit:]

    # -- domain operations --

    def approve_gate(
        self,
        gate_id: str,
        approver: str,
        rationale: str = "",
    ) -> DeploymentGate | None:
        """Approve a pending gate."""
        gate = self.get_gate(gate_id)
        if gate is None:
            return None
        if gate.status != GateStatus.PENDING:
            return gate
        gate.status = GateStatus.APPROVED
        gate.approver = approver
        decision = GateDecision(
            gate_id=gate_id,
            decision="approved",
            decided_by=approver,
            rationale=rationale,
            decided_at=time.time(),
        )
        self._decisions.append(decision)
        logger.info(
            "deployment_gate.approved",
            gate_id=gate_id,
            approver=approver,
        )
        return gate

    def reject_gate(
        self,
        gate_id: str,
        approver: str,
        rationale: str = "",
    ) -> DeploymentGate | None:
        """Reject a pending gate."""
        gate = self.get_gate(gate_id)
        if gate is None:
            return None
        if gate.status != GateStatus.PENDING:
            return gate
        gate.status = GateStatus.REJECTED
        gate.approver = approver
        gate.reason = rationale
        decision = GateDecision(
            gate_id=gate_id,
            decision="rejected",
            decided_by=approver,
            rationale=rationale,
            decided_at=time.time(),
        )
        self._decisions.append(decision)
        logger.info(
            "deployment_gate.rejected",
            gate_id=gate_id,
            approver=approver,
        )
        return gate

    def evaluate_auto_approval(
        self,
        gate_id: str,
    ) -> DeploymentGate | None:
        """Evaluate if a gate qualifies for auto-approval."""
        gate = self.get_gate(gate_id)
        if gate is None:
            return None
        if gate.status != GateStatus.PENDING:
            return gate
        # Auto-approve automated checks with passing
        # pre-checks
        can_auto = gate.gate_type == GateType.AUTOMATED_CHECK and len(gate.pre_checks) > 0
        if can_auto:
            gate.status = GateStatus.AUTO_APPROVED
            gate.approver = "system"
            decision = GateDecision(
                gate_id=gate_id,
                decision="auto_approved",
                decided_by="system",
                rationale="Pre-checks passed",
                decided_at=time.time(),
            )
            self._decisions.append(decision)
            logger.info(
                "deployment_gate.auto_approved",
                gate_id=gate_id,
            )
        return gate

    def check_gate_expiry(
        self,
    ) -> list[DeploymentGate]:
        """Check and expire gates past their expiry."""
        now = time.time()
        expired: list[DeploymentGate] = []
        for gate in self._items:
            if gate.status == GateStatus.PENDING and gate.expires_at > 0 and now > gate.expires_at:
                gate.status = GateStatus.EXPIRED
                expired.append(gate)
                logger.info(
                    "deployment_gate.expired",
                    gate_id=gate.id,
                )
        return expired

    def calculate_approval_velocity(
        self,
    ) -> dict[str, Any]:
        """Calculate how fast gates get approved."""
        decided = [d for d in self._decisions if d.decided_at > 0]
        if not decided:
            return {
                "avg_wait_hours": 0.0,
                "total_decisions": 0,
                "fastest_hours": 0.0,
                "slowest_hours": 0.0,
            }
        waits: list[float] = []
        for d in decided:
            gate = self.get_gate(d.gate_id)
            if gate:
                wait = (d.decided_at - gate.created_at) / 3600
                waits.append(max(0.0, wait))
        avg = round(sum(waits) / len(waits), 2) if waits else 0.0
        return {
            "avg_wait_hours": avg,
            "total_decisions": len(decided),
            "fastest_hours": (round(min(waits), 2) if waits else 0.0),
            "slowest_hours": (round(max(waits), 2) if waits else 0.0),
        }

    # -- report --

    def generate_gate_report(self) -> GateReport:
        """Generate a comprehensive gate report."""
        by_status: dict[str, int] = {}
        for g in self._items:
            key = g.status.value
            by_status[key] = by_status.get(key, 0) + 1
        by_type: dict[str, int] = {}
        for g in self._items:
            key = g.gate_type.value
            by_type[key] = by_type.get(key, 0) + 1
        approved = sum(
            1
            for g in self._items
            if g.status
            in (
                GateStatus.APPROVED,
                GateStatus.AUTO_APPROVED,
            )
        )
        total = len(self._items)
        rate = round(approved / total * 100, 2) if total else 0.0
        velocity = self.calculate_approval_velocity()
        # Identify slow gates (> 2x avg wait)
        avg_wait = velocity["avg_wait_hours"]
        slow: list[str] = []
        for d in self._decisions:
            gate = self.get_gate(d.gate_id)
            if gate and d.decided_at > 0:
                wait = (d.decided_at - gate.created_at) / 3600
                if avg_wait > 0 and wait > avg_wait * 2:
                    slow.append(gate.id)
        recs = self._build_recommendations(
            by_status,
            rate,
            velocity,
        )
        return GateReport(
            total_gates=total,
            total_decisions=len(self._decisions),
            approval_rate_pct=rate,
            avg_wait_hours=velocity["avg_wait_hours"],
            by_status=by_status,
            by_type=by_type,
            slow_gates=slow,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all gates and decisions."""
        count = len(self._items)
        self._items.clear()
        self._decisions.clear()
        logger.info(
            "deployment_gate.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        status_dist: dict[str, int] = {}
        for g in self._items:
            key = g.status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_gates": len(self._items),
            "total_decisions": len(self._decisions),
            "gate_expiry_hours": (self._gate_expiry_hours),
            "status_distribution": status_dist,
        }

    # -- internal helpers --

    def _build_recommendations(
        self,
        by_status: dict[str, int],
        approval_rate: float,
        velocity: dict[str, Any],
    ) -> list[str]:
        recs: list[str] = []
        pending = by_status.get("pending", 0)
        expired = by_status.get("expired", 0)
        if pending > 10:
            recs.append(f"{pending} gates pending - review backlog")
        if expired > 0:
            recs.append(f"{expired} gate(s) expired - check SLAs")
        avg = velocity.get("avg_wait_hours", 0)
        if avg > 4:
            recs.append("Average wait exceeds 4 hours - consider auto-approval")
        if not recs:
            recs.append("Gate approval process operating normally")
        return recs
