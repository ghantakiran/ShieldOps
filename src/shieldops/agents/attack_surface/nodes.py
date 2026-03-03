"""Node implementations for the Attack Surface Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.attack_surface.models import (
    AttackSurfaceState,
    DiscoveredAsset,
    ExposureFinding,
    SurfaceReasoningStep,
)
from shieldops.agents.attack_surface.tools import AttackSurfaceToolkit

logger = structlog.get_logger()

_toolkit: AttackSurfaceToolkit | None = None


def set_toolkit(toolkit: AttackSurfaceToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> AttackSurfaceToolkit:
    if _toolkit is None:
        return AttackSurfaceToolkit()
    return _toolkit


async def discover_assets(state: AttackSurfaceState) -> dict[str, Any]:
    """Discover external-facing assets."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    raw_assets = await toolkit.discover_assets(state.scan_config)
    assets = [DiscoveredAsset(**a) for a in raw_assets if isinstance(a, dict)]

    # Add default asset if none discovered
    scope = state.scan_config.get("scope", "")
    if not assets and scope:
        assets.append(
            DiscoveredAsset(
                asset_id="a-001",
                asset_type="domain",
                hostname=scope,
                exposure_level="medium",
                risk_score=50.0,
            )
        )

    step = SurfaceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="discover_assets",
        input_summary=f"Scanning scope={scope}",
        output_summary=f"Discovered {len(assets)} assets",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="asset_discovery",
    )

    await toolkit.record_surface_metric("discovery", float(len(assets)))

    return {
        "discovered_assets": assets,
        "asset_count": len(assets),
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "discover_assets",
        "session_start": start,
    }


async def analyze_exposures(state: AttackSurfaceState) -> dict[str, Any]:
    """Analyze discovered assets for security exposures."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    asset_dicts = [a.model_dump() for a in state.discovered_assets]
    raw_findings = await toolkit.scan_exposures(asset_dicts)
    findings = [ExposureFinding(**f) for f in raw_findings if isinstance(f, dict)]

    risk_scores = [a.risk_score for a in state.discovered_assets]
    avg_risk = round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0

    step = SurfaceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_exposures",
        input_summary=f"Analyzing {len(state.discovered_assets)} assets",
        output_summary=f"Found {len(findings)} exposures, avg risk={avg_risk}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="exposure_scanner",
    )

    return {
        "exposure_findings": findings,
        "risk_score": avg_risk,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_exposures",
    }


async def prioritize_findings(state: AttackSurfaceState) -> dict[str, Any]:
    """Prioritize exposure findings by risk."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    finding_dicts = [f.model_dump() for f in state.exposure_findings]
    prioritized = await toolkit.prioritize_findings(finding_dicts)
    critical = sum(1 for f in state.exposure_findings if f.severity in ("critical", "high"))

    step = SurfaceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="prioritize_findings",
        input_summary=f"Prioritizing {len(state.exposure_findings)} findings",
        output_summary=f"Critical/high={critical}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="priority_ranker",
    )

    return {
        "prioritized_findings": prioritized,
        "critical_count": critical,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "prioritize_findings",
    }


async def plan_remediation(state: AttackSurfaceState) -> dict[str, Any]:
    """Plan remediation for exposure findings."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    plan = await toolkit.create_remediation_plan(state.prioritized_findings)

    step = SurfaceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="plan_remediation",
        input_summary=f"Planning remediation for {state.critical_count} critical findings",
        output_summary=f"Created {len(plan)} remediation actions",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="remediation_planner",
    )

    return {
        "remediation_plan": plan,
        "remediation_started": bool(plan),
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "plan_remediation",
    }


async def finalize_scan(state: AttackSurfaceState) -> dict[str, Any]:
    """Finalize attack surface scan and record metrics."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_surface_metric("scan_duration_ms", float(duration_ms))

    step = SurfaceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_scan",
        input_summary=f"Finalizing scan {state.scan_id}",
        output_summary=f"Scan complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
