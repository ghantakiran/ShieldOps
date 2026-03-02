"""Node implementations for the Deception Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.deception.models import (
    DeceptionState,
    ReasoningStep,
)
from shieldops.agents.deception.tools import DeceptionToolkit

logger = structlog.get_logger()

_toolkit: DeceptionToolkit | None = None


def set_toolkit(toolkit: DeceptionToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> DeceptionToolkit:
    if _toolkit is None:
        return DeceptionToolkit()
    return _toolkit


async def deploy_assets(state: DeceptionState) -> dict[str, Any]:
    """Deploy deception assets for the campaign."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    config = {"campaign_id": state.campaign_id, "campaign_type": state.campaign_type}
    assets = await toolkit.deploy_assets(state.campaign_type, config)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="deploy_assets",
        input_summary=f"Deploying deception assets for campaign {state.campaign_id} "
        f"type={state.campaign_type}",
        output_summary=f"Deployed {len(assets)} deception assets",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="honeypot_manager",
    )

    return {
        "deployed_assets": assets,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "deploy_assets",
        "session_start": start,
    }


async def monitor_interactions(state: DeceptionState) -> dict[str, Any]:
    """Monitor deployed assets for attacker interactions."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    asset_ids = [a.get("asset_id", "") for a in state.deployed_assets]
    interactions = await toolkit.monitor_interactions(asset_ids)

    interaction_detected = len(interactions) > 0

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="monitor_interactions",
        input_summary=f"Monitoring {len(asset_ids)} deception assets",
        output_summary=f"Detected {len(interactions)} interactions, "
        f"activity={'yes' if interaction_detected else 'no'}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="interaction_monitor",
    )

    return {
        "interactions": interactions,
        "interaction_detected": interaction_detected,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "monitor_interactions",
    }


async def analyze_behavior(state: DeceptionState) -> dict[str, Any]:
    """Analyze attacker behavior from interactions."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    analysis = await toolkit.analyze_behavior(state.interactions)

    # Determine severity from sophistication
    sophistication = analysis.get("sophistication_level", "unknown")
    severity_map = {
        "apt": "critical",
        "advanced": "high",
        "intermediate": "medium",
        "script_kiddie": "low",
    }
    severity = severity_map.get(sophistication, "low")

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_behavior",
        input_summary=f"Analyzing {len(state.interactions)} interactions",
        output_summary=f"Profile: sophistication={sophistication}, severity={severity}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="behavior_analyzer",
    )

    return {
        "behavioral_analysis": analysis,
        "severity_level": severity,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_behavior",
    }


async def extract_indicators(state: DeceptionState) -> dict[str, Any]:
    """Extract IOCs from deception interactions."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    indicators = await toolkit.extract_indicators(state.interactions)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="extract_indicators",
        input_summary=f"Extracting indicators from {len(state.interactions)} interactions",
        output_summary=f"Extracted {len(indicators)} indicators",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="threat_intel",
    )

    return {
        "extracted_indicators": indicators,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "extract_indicators",
    }


async def respond_to_threat(state: DeceptionState) -> dict[str, Any]:
    """Trigger containment if severity warrants it."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    should_contain = state.severity_level in ("critical", "high")

    if should_contain:
        await toolkit.trigger_containment(state.campaign_id, state.severity_level)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="respond_to_threat",
        input_summary=f"Evaluating response for severity={state.severity_level}",
        output_summary=f"Containment triggered={should_contain}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="policy_engine",
    )

    return {
        "containment_triggered": should_contain,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "respond_to_threat",
    }


async def update_strategy(state: DeceptionState) -> dict[str, Any]:
    """Update the deception strategy based on findings."""
    start = datetime.now(UTC)

    updates: list[dict[str, Any]] = []
    if state.behavioral_analysis.get("sophistication_level") in ("advanced", "apt"):
        updates.append(
            {
                "action": "increase_complexity",
                "description": "Increase deception asset complexity to match attacker",
            }
        )
    if state.extracted_indicators:
        updates.append(
            {
                "action": "deploy_targeted_honeytokens",
                "description": f"Deploy honeytokens targeting {len(state.extracted_indicators)} "
                f"extracted indicators",
            }
        )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="update_strategy",
        input_summary=f"Updating strategy based on severity={state.severity_level}",
        output_summary=f"Generated {len(updates)} strategy updates",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="llm",
    )

    return {
        "strategy_updates": updates,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "update_strategy",
    }


async def generate_report(state: DeceptionState) -> dict[str, Any]:
    """Generate the final deception campaign report."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    report_data = await toolkit.generate_report(
        {
            "campaign_id": state.campaign_id,
            "campaign_type": state.campaign_type,
            "deployed_assets": state.deployed_assets,
            "interactions": state.interactions,
            "behavioral_analysis": state.behavioral_analysis,
            "extracted_indicators": state.extracted_indicators,
            "severity_level": state.severity_level,
            "containment_triggered": state.containment_triggered,
            "strategy_updates": state.strategy_updates,
        }
    )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="generate_report",
        input_summary=f"Generating report for campaign {state.campaign_id}",
        output_summary=f"Report status={report_data.get('status', 'unknown')}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="report_generator",
    )

    return {
        "report": report_data,
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
