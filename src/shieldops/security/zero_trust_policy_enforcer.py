"""Zero Trust Policy Enforcer — enforce zero trust policies across all access requests."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AccessDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    CHALLENGE = "challenge"
    STEP_UP = "step_up"


class DevicePosture(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"
    DEGRADED = "degraded"


class TrustLevel(StrEnum):
    ZERO = "zero"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FULL = "full"


class ViolationType(StrEnum):
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DEVICE_NON_COMPLIANT = "device_non_compliant"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    POLICY_BYPASS = "policy_bypass"
    SEGMENTATION_BREACH = "segmentation_breach"


# --- Models ---


class AccessRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    resource: str = ""
    decision: AccessDecision = AccessDecision.DENY
    device_posture: DevicePosture = DevicePosture.UNKNOWN
    trust_score: float = 0.0
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    violation_type: ViolationType = ViolationType.UNAUTHORIZED_ACCESS
    user_id: str = ""
    resource: str = ""
    severity: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ZeroTrustReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_requests: int = 0
    total_violations: int = 0
    avg_trust_score: float = 0.0
    by_decision: dict[str, int] = Field(default_factory=dict)
    by_posture: dict[str, int] = Field(default_factory=dict)
    by_violation_type: dict[str, int] = Field(default_factory=dict)
    top_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ZeroTrustPolicyEnforcer:
    """Enforce zero trust policies across all access requests."""

    def __init__(
        self,
        max_records: int = 200000,
        trust_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._trust_threshold = trust_threshold
        self._requests: list[AccessRequest] = []
        self._violations: list[PolicyViolation] = []
        logger.info(
            "zero_trust_policy_enforcer.initialized",
            max_records=max_records,
            trust_threshold=trust_threshold,
        )

    def evaluate_access_request(
        self,
        user_id: str,
        resource: str,
        trust_score: float = 0.0,
        risk_score: float = 0.0,
        device_posture: DevicePosture = DevicePosture.UNKNOWN,
        service: str = "",
        team: str = "",
    ) -> AccessRequest:
        """Evaluate an access request and render a decision."""
        if trust_score >= self._trust_threshold and device_posture == DevicePosture.COMPLIANT:
            decision = AccessDecision.ALLOW
        elif trust_score >= self._trust_threshold * 0.6:
            decision = AccessDecision.STEP_UP
        elif device_posture == DevicePosture.NON_COMPLIANT:
            decision = AccessDecision.DENY
        else:
            decision = AccessDecision.CHALLENGE
        request = AccessRequest(
            user_id=user_id,
            resource=resource,
            decision=decision,
            device_posture=device_posture,
            trust_score=trust_score,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._requests.append(request)
        if len(self._requests) > self._max_records:
            self._requests = self._requests[-self._max_records :]
        logger.info(
            "zero_trust_policy_enforcer.request_evaluated",
            request_id=request.id,
            decision=decision.value,
        )
        return request

    def enforce_microsegmentation(
        self,
        source_service: str,
        target_service: str,
        allowed_pairs: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Check whether communication between services is allowed."""
        allowed = allowed_pairs or []
        is_allowed = (source_service, target_service) in allowed
        if not is_allowed:
            self._violations.append(
                PolicyViolation(
                    violation_type=ViolationType.SEGMENTATION_BREACH,
                    description=f"{source_service} -> {target_service} not allowed",
                )
            )
        return {
            "source": source_service,
            "target": target_service,
            "allowed": is_allowed,
        }

    def validate_device_posture(
        self,
        device_id: str,
        os_patched: bool = False,
        encryption_enabled: bool = False,
        antivirus_active: bool = False,
    ) -> dict[str, Any]:
        """Validate device posture based on security attributes."""
        checks = [os_patched, encryption_enabled, antivirus_active]
        passed = sum(checks)
        if passed == len(checks):
            posture = DevicePosture.COMPLIANT
        elif passed >= 1:
            posture = DevicePosture.DEGRADED
        else:
            posture = DevicePosture.NON_COMPLIANT
        return {
            "device_id": device_id,
            "posture": posture.value,
            "checks_passed": passed,
            "checks_total": len(checks),
        }

    def score_trust_level(self, user_id: str) -> dict[str, Any]:
        """Compute trust level for a user based on recent access history."""
        user_requests = [r for r in self._requests if r.user_id == user_id]
        if not user_requests:
            return {"user_id": user_id, "trust_level": TrustLevel.ZERO.value, "avg_score": 0.0}
        scores = [r.trust_score for r in user_requests]
        avg = round(sum(scores) / len(scores), 2)
        if avg >= 80:
            level = TrustLevel.HIGH
        elif avg >= 60:
            level = TrustLevel.MEDIUM
        elif avg >= 30:
            level = TrustLevel.LOW
        else:
            level = TrustLevel.ZERO
        return {"user_id": user_id, "trust_level": level.value, "avg_score": avg}

    def get_policy_violations(
        self,
        violation_type: ViolationType | None = None,
        limit: int = 50,
    ) -> list[PolicyViolation]:
        """List recorded policy violations."""
        results = list(self._violations)
        if violation_type is not None:
            results = [v for v in results if v.violation_type == violation_type]
        return results[-limit:]

    def generate_report(self) -> ZeroTrustReport:
        """Generate a zero trust posture report."""
        by_decision: dict[str, int] = {}
        by_posture: dict[str, int] = {}
        for r in self._requests:
            by_decision[r.decision.value] = by_decision.get(r.decision.value, 0) + 1
            by_posture[r.device_posture.value] = by_posture.get(r.device_posture.value, 0) + 1
        by_vtype: dict[str, int] = {}
        for v in self._violations:
            by_vtype[v.violation_type.value] = by_vtype.get(v.violation_type.value, 0) + 1
        scores = [r.trust_score for r in self._requests]
        avg_trust = round(sum(scores) / len(scores), 2) if scores else 0.0
        issues = [v.description for v in self._violations[-5:]]
        recs: list[str] = []
        if self._violations:
            recs.append(f"{len(self._violations)} policy violation(s) detected")
        if avg_trust < self._trust_threshold:
            recs.append(f"Avg trust {avg_trust} below threshold ({self._trust_threshold})")
        if not recs:
            recs.append("Zero trust posture within healthy range")
        return ZeroTrustReport(
            total_requests=len(self._requests),
            total_violations=len(self._violations),
            avg_trust_score=avg_trust,
            by_decision=by_decision,
            by_posture=by_posture,
            by_violation_type=by_vtype,
            top_issues=issues,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        return {
            "total_requests": len(self._requests),
            "total_violations": len(self._violations),
            "trust_threshold": self._trust_threshold,
            "unique_users": len({r.user_id for r in self._requests}),
            "unique_resources": len({r.resource for r in self._requests}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._requests.clear()
        self._violations.clear()
        logger.info("zero_trust_policy_enforcer.cleared")
        return {"status": "cleared"}
