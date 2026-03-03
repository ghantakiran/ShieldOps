"""Node implementations for the Zero Trust Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.zero_trust.models import (
    AccessEvaluation,
    DeviceAssessment,
    IdentityVerification,
    ZeroTrustReasoningStep,
    ZeroTrustState,
)
from shieldops.agents.zero_trust.tools import ZeroTrustToolkit

logger = structlog.get_logger()

_toolkit: ZeroTrustToolkit | None = None


def set_toolkit(toolkit: ZeroTrustToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> ZeroTrustToolkit:
    if _toolkit is None:
        return ZeroTrustToolkit()
    return _toolkit


async def verify_identity(state: ZeroTrustState) -> dict[str, Any]:
    """Verify identities against zero trust policies."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    raw_verifications = await toolkit.verify_identities(state.assessment_config)
    verifications = [IdentityVerification(**v) for v in raw_verifications if isinstance(v, dict)]

    # Add default identity if none verified and scope is provided
    scope = state.assessment_config.get("scope", "")
    if not verifications and scope:
        verifications.append(
            IdentityVerification(
                identity_id="id-001",
                identity_type="service_account",
                risk_level="medium",
                verified=True,
                trust_score=50.0,
            )
        )

    verified_count = sum(1 for v in verifications if v.verified)
    trust_scores = [v.trust_score for v in verifications if v.trust_score > 0]
    avg_trust = round(sum(trust_scores) / len(trust_scores), 2) if trust_scores else 0.0

    step = ZeroTrustReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="verify_identity",
        input_summary=f"Verifying identities scope={scope}",
        output_summary=f"Verified {verified_count}/{len(verifications)} identities",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="identity_verifier",
    )

    await toolkit.record_trust_metric("identity_verification", float(verified_count))

    return {
        "identity_verifications": verifications,
        "identity_verified": verified_count,
        "trust_score": avg_trust,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "verify_identity",
        "session_start": start,
    }


async def assess_device(state: ZeroTrustState) -> dict[str, Any]:
    """Assess device posture and compliance."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    raw_assessments = await toolkit.assess_devices(state.assessment_config)
    assessments = [DeviceAssessment(**a) for a in raw_assessments if isinstance(a, dict)]

    compliance_scores = [a.compliance_score for a in assessments if a.compliance_score > 0]
    avg_compliance = (
        round(sum(compliance_scores) / len(compliance_scores), 2) if compliance_scores else 0.0
    )

    step = ZeroTrustReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="assess_device",
        input_summary=f"Assessing {len(assessments)} devices",
        output_summary=f"Avg compliance={avg_compliance}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="device_assessor",
    )

    return {
        "device_assessments": assessments,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "assess_device",
    }


async def evaluate_access(state: ZeroTrustState) -> dict[str, Any]:
    """Evaluate access requests against zero trust policies."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    identity_dicts = [v.model_dump() for v in state.identity_verifications]
    device_dicts = [a.model_dump() for a in state.device_assessments]
    raw_evaluations = await toolkit.evaluate_access(identity_dicts, device_dicts)
    evaluations = [AccessEvaluation(**e) for e in raw_evaluations if isinstance(e, dict)]

    violations = sum(1 for e in evaluations if e.decision == "deny")

    step = ZeroTrustReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="evaluate_access",
        input_summary=f"Evaluating access for {len(identity_dicts)} identities",
        output_summary=f"Evaluated {len(evaluations)} requests, {violations} violations",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="access_evaluator",
    )

    return {
        "access_evaluations": evaluations,
        "violation_count": violations,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "evaluate_access",
    }


async def enforce_policy(state: ZeroTrustState) -> dict[str, Any]:
    """Enforce zero trust policies based on evaluation results."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    violation_dicts = [e.model_dump() for e in state.access_evaluations if e.decision == "deny"]
    actions = await toolkit.enforce_policies(violation_dicts)

    step = ZeroTrustReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="enforce_policy",
        input_summary=f"Enforcing policies for {state.violation_count} violations",
        output_summary=f"Executed {len(actions)} enforcement actions",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="policy_enforcer",
    )

    return {
        "enforcement_actions": actions,
        "policy_enforced": bool(actions),
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "enforce_policy",
    }


async def finalize_assessment(state: ZeroTrustState) -> dict[str, Any]:
    """Finalize zero trust assessment and record metrics."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_trust_metric("assessment_duration_ms", float(duration_ms))

    step = ZeroTrustReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_assessment",
        input_summary=f"Finalizing assessment {state.session_id}",
        output_summary=f"Assessment complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
