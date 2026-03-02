"""Node implementations for the Threat Hunter Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.threat_hunter.models import (
    ReasoningStep,
    ThreatHunterState,
)
from shieldops.agents.threat_hunter.tools import ThreatHunterToolkit

logger = structlog.get_logger()

_toolkit: ThreatHunterToolkit | None = None


def set_toolkit(toolkit: ThreatHunterToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> ThreatHunterToolkit:
    if _toolkit is None:
        return ThreatHunterToolkit()
    return _toolkit


async def generate_hypothesis(state: ThreatHunterState) -> dict[str, Any]:
    """Generate or refine a threat hunting hypothesis."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    context = {
        "hypothesis": state.hypothesis,
        "hunt_scope": state.hunt_scope,
    }
    result = await toolkit.generate_hypothesis(context)

    hypothesis = result.get("hypothesis") or state.hypothesis
    data_sources = result.get("data_sources", []) or state.data_sources

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="generate_hypothesis",
        input_summary=f"Hypothesis: {state.hypothesis[:80] if state.hypothesis else 'none'}",
        output_summary=f"Refined hypothesis, {len(data_sources)} data sources identified",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="threat_intel",
    )

    return {
        "hypothesis": hypothesis,
        "data_sources": data_sources,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "generate_hypothesis",
        "session_start": start,
    }


async def define_scope(state: ThreatHunterState) -> dict[str, Any]:
    """Define the hunt scope based on the hypothesis and available data sources."""
    start = datetime.now(UTC)

    # Build scope from hypothesis and data sources
    scope = dict(state.hunt_scope)
    if not scope.get("time_range"):
        scope["time_range"] = "7d"
    if not scope.get("environments"):
        scope["environments"] = ["production"]
    scope["data_sources"] = state.data_sources

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="define_scope",
        input_summary=f"Defining scope for {len(state.data_sources)} data sources",
        output_summary=f"Scope: time_range={scope.get('time_range')}, "
        f"envs={scope.get('environments')}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "hunt_scope": scope,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "define_scope",
    }


async def collect_data(state: ThreatHunterState) -> dict[str, Any]:
    """Validate data source availability and prepare collection parameters."""
    start = datetime.now(UTC)

    available_sources = []
    for source in state.data_sources:
        # In production, this would verify connectivity and data freshness
        available_sources.append(source)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="collect_data",
        input_summary=f"Validating {len(state.data_sources)} data sources",
        output_summary=f"{len(available_sources)} sources available for hunting",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "data_sources": available_sources,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "collect_data",
    }


async def sweep_iocs(state: ThreatHunterState) -> dict[str, Any]:
    """Sweep the environment for indicators of compromise."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    # Extract indicators from hypothesis context
    indicators = state.hunt_scope.get("indicators", [])
    results = await toolkit.sweep_iocs(state.hunt_scope, indicators)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="sweep_iocs",
        input_summary=f"Sweeping {len(indicators)} indicators across scope",
        output_summary=f"Found {len(results)} IOC matches",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="ioc_scanner",
    )

    return {
        "ioc_sweep_results": results,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "sweep_iocs",
    }


async def analyze_behavior(state: ThreatHunterState) -> dict[str, Any]:
    """Analyze behavioral deviations from baseline."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    baseline_id = state.hunt_scope.get("baseline_id", "default")
    findings = await toolkit.analyze_behavior(state.hunt_scope, baseline_id)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_behavior",
        input_summary=f"Analyzing behavior against baseline={baseline_id}",
        output_summary=f"Found {len(findings)} behavioral deviations",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="behavior_analyzer",
    )

    return {
        "behavioral_findings": findings,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_behavior",
    }


async def check_mitre(state: ThreatHunterState) -> dict[str, Any]:
    """Check MITRE ATT&CK technique coverage and detection gaps."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    techniques = state.hunt_scope.get("mitre_techniques", [])
    coverage = await toolkit.check_mitre_coverage(techniques)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="check_mitre",
        input_summary=f"Checking coverage for {len(techniques)} MITRE techniques",
        output_summary=f"Found {len(coverage)} coverage findings",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="mitre_mapper",
    )

    return {
        "mitre_findings": coverage,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "check_mitre",
    }


async def correlate_findings(state: ThreatHunterState) -> dict[str, Any]:
    """Correlate findings across IOC sweeps, behavioral analysis, and MITRE coverage."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    all_findings: list[dict[str, Any]] = [
        *[{"type": "ioc", **f} for f in state.ioc_sweep_results],
        *[{"type": "behavioral", **f} for f in state.behavioral_findings],
        *[{"type": "mitre", **f} for f in state.mitre_findings],
    ]

    correlated = await toolkit.correlate_findings(all_findings)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="correlate_findings",
        input_summary=f"Correlating {len(all_findings)} findings across sources",
        output_summary=f"Produced {len(correlated)} correlated finding groups",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="signal_correlator",
    )

    return {
        "correlated_findings": correlated,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "correlate_findings",
    }


async def assess_threat(state: ThreatHunterState) -> dict[str, Any]:
    """Assess whether a confirmed threat exists based on correlated findings."""
    start = datetime.now(UTC)

    total_findings = (
        len(state.ioc_sweep_results) + len(state.behavioral_findings) + len(state.mitre_findings)
    )
    correlated_count = len(state.correlated_findings)

    # Determine threat presence based on findings
    threat_found = correlated_count > 0 or total_findings >= 3

    # Determine severity
    if correlated_count >= 3:
        severity = "critical"
        confidence = 0.9
    elif correlated_count >= 1:
        severity = "high"
        confidence = 0.75
    elif total_findings >= 3:
        severity = "medium"
        confidence = 0.5
    else:
        severity = "low"
        confidence = 0.3
        threat_found = False

    assessment = {
        "threat_found": threat_found,
        "severity": severity,
        "confidence": confidence,
        "total_findings": total_findings,
        "correlated_count": correlated_count,
        "summary": f"Hunt assessment: threat_found={threat_found}, "
        f"severity={severity}, findings={total_findings}, "
        f"correlated={correlated_count}",
    }

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="assess_threat",
        input_summary=f"Assessing {total_findings} findings, {correlated_count} correlated",
        output_summary=f"Threat found={threat_found}, severity={severity}, confidence={confidence}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="llm",
    )

    return {
        "threat_assessment": assessment,
        "threat_found": threat_found,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "assess_threat",
    }


async def recommend_response(state: ThreatHunterState) -> dict[str, Any]:
    """Generate response recommendations for confirmed threats."""
    start = datetime.now(UTC)

    recommendations: list[dict[str, Any]] = []
    severity = state.threat_assessment.get("severity", "low")

    if severity in ("critical", "high"):
        recommendations.append(
            {
                "action": "escalate_to_ir",
                "priority": "immediate",
                "description": "Escalate to incident response team for immediate investigation",
            }
        )
        recommendations.append(
            {
                "action": "isolate_affected_assets",
                "priority": "high",
                "description": "Isolate affected assets to contain potential spread",
            }
        )
    if severity == "critical":
        recommendations.append(
            {
                "action": "activate_war_room",
                "priority": "immediate",
                "description": "Activate war room for coordinated response",
            }
        )

    if state.ioc_sweep_results:
        recommendations.append(
            {
                "action": "block_iocs",
                "priority": "high",
                "description": "Block confirmed IOCs at perimeter and endpoint controls",
            }
        )

    if state.behavioral_findings:
        recommendations.append(
            {
                "action": "enhance_monitoring",
                "priority": "medium",
                "description": "Increase monitoring granularity for affected systems",
            }
        )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="recommend_response",
        input_summary=f"Generating response for severity={severity}",
        output_summary=f"Generated {len(recommendations)} response recommendations",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="policy_engine",
    )

    return {
        "response_recommendations": recommendations,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "recommend_response",
    }


async def track_effectiveness(state: ThreatHunterState) -> dict[str, Any]:
    """Track hunt effectiveness and record final metrics."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    total_findings = (
        len(state.ioc_sweep_results) + len(state.behavioral_findings) + len(state.mitre_findings)
    )

    # Compute effectiveness score (0-1)
    if state.threat_found:
        effectiveness = min(1.0, 0.5 + (len(state.correlated_findings) * 0.1))
    elif total_findings > 0:
        effectiveness = min(0.5, total_findings * 0.1)
    else:
        effectiveness = 0.1  # baseline: no findings but hunt completed

    outcome = {
        "threat_found": state.threat_found,
        "total_findings": total_findings,
        "correlated_count": len(state.correlated_findings),
        "recommendations": len(state.response_recommendations),
        "effectiveness_score": effectiveness,
        "duration_ms": duration_ms,
    }

    await toolkit.track_effectiveness(state.hypothesis_id, outcome)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="track_effectiveness",
        input_summary=f"Tracking effectiveness for hunt {state.hypothesis_id}",
        output_summary=f"Effectiveness={effectiveness:.2f}, duration={duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="hunt_metrics",
    )

    return {
        "effectiveness_score": effectiveness,
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
