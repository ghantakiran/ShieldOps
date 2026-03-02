"""Node implementations for the ML Governance Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.ml_governance.models import (
    GovernanceFinding,
    GovernanceReasoningStep,
    MLGovernanceState,
    ModelAudit,
)
from shieldops.agents.ml_governance.tools import MLGovernanceToolkit

logger = structlog.get_logger()

_toolkit: MLGovernanceToolkit | None = None


def set_toolkit(toolkit: MLGovernanceToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> MLGovernanceToolkit:
    if _toolkit is None:
        return MLGovernanceToolkit()
    return _toolkit


async def audit_models(state: MLGovernanceState) -> dict[str, Any]:
    """Audit ML models for governance compliance."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    raw_audits = await toolkit.audit_models(state.audit_config)
    audits = [ModelAudit(**a) for a in raw_audits if isinstance(a, dict)]

    # Add default audit if none found
    scope = state.audit_config.get("scope", "")
    if not audits and scope:
        audits.append(
            ModelAudit(
                audit_id="ma-001",
                model_id=scope,
                model_name=scope,
                audit_type="compliance",
                compliance_score=75.0,
                risk_level="medium",
            )
        )

    step = GovernanceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="audit_models",
        input_summary=f"Auditing scope={scope}",
        output_summary=f"Audited {len(audits)} models",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="model_auditor",
    )

    await toolkit.record_governance_metric("audit", float(len(audits)))

    return {
        "model_audits": audits,
        "audit_count": len(audits),
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "audit_models",
        "session_start": start,
    }


async def evaluate_fairness(state: MLGovernanceState) -> dict[str, Any]:
    """Evaluate fairness metrics for audited models."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    audit_dicts = [a.model_dump() for a in state.model_audits]
    raw_findings = await toolkit.evaluate_fairness(audit_dicts)
    findings = [GovernanceFinding(**f) for f in raw_findings if isinstance(f, dict)]

    risk_scores = [a.compliance_score for a in state.model_audits]
    avg_risk = round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0

    step = GovernanceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="evaluate_fairness",
        input_summary=f"Evaluating {len(state.model_audits)} model audits",
        output_summary=f"Found {len(findings)} findings, avg compliance={avg_risk}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="fairness_evaluator",
    )

    return {
        "governance_findings": findings,
        "risk_score": avg_risk,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "evaluate_fairness",
    }


async def assess_risk(state: MLGovernanceState) -> dict[str, Any]:
    """Assess risk from governance findings."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    finding_dicts = [f.model_dump() for f in state.governance_findings]
    prioritized = await toolkit.assess_risk(finding_dicts)
    critical = sum(1 for f in state.governance_findings if f.severity in ("critical", "high"))

    step = GovernanceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="assess_risk",
        input_summary=f"Assessing {len(state.governance_findings)} findings",
        output_summary=f"Critical/high={critical}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="risk_assessor",
    )

    return {
        "prioritized_findings": prioritized,
        "critical_count": critical,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "assess_risk",
    }


async def plan_actions(state: MLGovernanceState) -> dict[str, Any]:
    """Plan remediation actions for governance findings."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    plan = await toolkit.create_action_plan(state.prioritized_findings)

    step = GovernanceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="plan_actions",
        input_summary=f"Planning actions for {state.critical_count} critical findings",
        output_summary=f"Created {len(plan)} governance actions",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="action_planner",
    )

    return {
        "action_plan": plan,
        "action_started": bool(plan),
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "plan_actions",
    }


async def finalize_evaluation(state: MLGovernanceState) -> dict[str, Any]:
    """Finalize ML governance evaluation and record metrics."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_governance_metric("evaluation_duration_ms", float(duration_ms))

    step = GovernanceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_evaluation",
        input_summary=f"Finalizing evaluation {state.session_id}",
        output_summary=f"Evaluation complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
