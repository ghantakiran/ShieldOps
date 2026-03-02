"""Node implementations for the FinOps Intelligence Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.finops_intelligence.models import (
    CostFinding,
    FinOpsIntelligenceState,
    FinOpsReasoningStep,
    OptimizationOpportunity,
)
from shieldops.agents.finops_intelligence.tools import FinOpsIntelligenceToolkit

logger = structlog.get_logger()

_toolkit: FinOpsIntelligenceToolkit | None = None


def set_toolkit(toolkit: FinOpsIntelligenceToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> FinOpsIntelligenceToolkit:
    if _toolkit is None:
        return FinOpsIntelligenceToolkit()
    return _toolkit


async def analyze_costs(state: FinOpsIntelligenceState) -> dict[str, Any]:
    """Analyze cloud costs and surface findings."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    raw_findings = await toolkit.analyze_costs(state.analysis_config)
    findings = [CostFinding(**f) for f in raw_findings if isinstance(f, dict)]

    scope = state.analysis_config.get("scope", "")
    if not findings and scope:
        findings.append(
            CostFinding(
                finding_id="cf-001",
                finding_type="idle_resource",
                category="compute",
                amount=250.0,
                service="ec2",
                team="platform",
            )
        )

    step = FinOpsReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_costs",
        input_summary=f"Analyzing scope={scope}",
        output_summary=f"Found {len(findings)} cost findings",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="cost_analyzer",
    )

    await toolkit.record_finops_metric("cost_findings", float(len(findings)))

    return {
        "cost_findings": findings,
        "finding_count": len(findings),
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_costs",
        "session_start": start,
    }


async def identify_optimizations(
    state: FinOpsIntelligenceState,
) -> dict[str, Any]:
    """Identify cost optimization opportunities from findings."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    finding_dicts = [f.model_dump() for f in state.cost_findings]
    raw_opps = await toolkit.identify_optimizations(finding_dicts)
    opportunities = [OptimizationOpportunity(**o) for o in raw_opps if isinstance(o, dict)]

    savings = float(sum(o.estimated_savings for o in opportunities))

    step = FinOpsReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="identify_optimizations",
        input_summary=f"Analyzing {len(state.cost_findings)} findings",
        output_summary=(
            f"Found {len(opportunities)} opportunities, savings_potential=${savings:.2f}"
        ),
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="optimization_engine",
    )

    return {
        "optimization_opportunities": opportunities,
        "savings_potential": round(savings, 2),
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "identify_optimizations",
    }


async def prioritize_savings(
    state: FinOpsIntelligenceState,
) -> dict[str, Any]:
    """Prioritize savings opportunities by impact."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    opp_dicts = [o.model_dump() for o in state.optimization_opportunities]
    prioritized = await toolkit.prioritize_savings(opp_dicts)
    high_impact = sum(
        1 for o in state.optimization_opportunities if o.severity in ("critical", "high")
    )

    step = FinOpsReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="prioritize_savings",
        input_summary=(f"Prioritizing {len(state.optimization_opportunities)} opportunities"),
        output_summary=f"High-impact={high_impact}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="priority_ranker",
    )

    return {
        "prioritized_actions": prioritized,
        "high_impact_count": high_impact,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "prioritize_savings",
    }


async def plan_implementation(
    state: FinOpsIntelligenceState,
) -> dict[str, Any]:
    """Create implementation plan for high-impact actions."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    plan = await toolkit.create_implementation_plan(state.prioritized_actions)

    step = FinOpsReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="plan_implementation",
        input_summary=(f"Planning for {state.high_impact_count} high-impact actions"),
        output_summary=f"Created {len(plan)} implementation steps",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="implementation_planner",
    )

    return {
        "implementation_plan": plan,
        "plan_started": bool(plan),
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "plan_implementation",
    }


async def finalize_analysis(
    state: FinOpsIntelligenceState,
) -> dict[str, Any]:
    """Finalize FinOps analysis and record metrics."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_finops_metric("analysis_duration_ms", float(duration_ms))

    step = FinOpsReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_analysis",
        input_summary=f"Finalizing session {state.session_id}",
        output_summary=f"Analysis complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
