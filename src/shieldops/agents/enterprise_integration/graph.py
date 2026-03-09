"""LangGraph workflow definition for the Enterprise Integration Agent."""

from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from shieldops.agents.enterprise_integration.models import (
    IntegrationState,
    IntegrationStatus,
)
from shieldops.agents.enterprise_integration.nodes import (
    analyze_sync_history,
    apply_fixes,
    check_health,
    diagnose_issues,
    generate_recommendations,
    load_config,
)
from shieldops.agents.tracing import traced_node

logger = structlog.get_logger()


def _route_after_health(state: IntegrationState) -> str:
    """Route based on health status after initial health check."""
    if state.error:
        return "generate_recommendations"

    if state.health is None:
        return "generate_recommendations"

    if state.health.status in (IntegrationStatus.CONNECTED,):
        return "analyze_sync_history"

    # Degraded, disconnected, error, configuring → diagnose
    return "diagnose_issues"


def _route_after_diagnosis(state: IntegrationState) -> str:
    """Route based on diagnosis: auto-fixable or manual intervention."""
    if not state.diagnostics:
        return "generate_recommendations"

    # Check if any diagnostic recommendation suggests an automatable fix
    auto_fix_keywords = {"rotat", "reconnect", "restart", "retry", "refresh"}
    for diag in state.diagnostics:
        recommendation_lower = diag.recommendation.lower()
        if any(kw in recommendation_lower for kw in auto_fix_keywords):
            return "apply_fixes"

    return "generate_recommendations"


async def check_health_again(state: IntegrationState) -> dict[str, Any]:
    """Re-check health after applying fixes to verify recovery."""
    from datetime import UTC, datetime

    from shieldops.agents.enterprise_integration.models import ReasoningStep
    from shieldops.agents.enterprise_integration.nodes import _get_toolkit

    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "integration_recheck_health",
        integration_id=state.integration_id,
    )

    health = await toolkit.check_health(state.integration_id)

    status_changed = False
    if state.health is not None and state.health.status != health.status:
        status_changed = True

    processing_duration_ms = 0
    if state.action_start:
        processing_duration_ms = int(
            (datetime.now(UTC) - state.action_start).total_seconds() * 1000
        )

    output_summary = (
        f"Post-fix status: {health.status} "
        f"(was {state.health.status if state.health else 'unknown'}). "
        f"Latency: {health.latency_ms:.0f}ms"
    )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="check_health_again",
        input_summary=f"Re-checking health after fixes for {state.integration_id}",
        output_summary=output_summary,
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="health_check",
    )

    return {
        "health": health,
        "status_changed": status_changed,
        "processing_duration_ms": processing_duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }


def create_integration_graph() -> StateGraph[IntegrationState]:
    """Build the Enterprise Integration Agent LangGraph workflow.

    Workflow:
        load_config → check_health → [conditional]
          if healthy → analyze_sync_history → generate_recommendations → END
          if degraded/error → diagnose_issues → [conditional]
            if auto_fixable → apply_fixes → check_health_again → END
            if manual → generate_recommendations → END
    """
    graph = StateGraph(IntegrationState)

    _agent = "enterprise_integration"

    # Add nodes (wrapped with OTEL tracing spans)
    graph.add_node(
        "load_config",
        traced_node("enterprise_integration.load_config", _agent)(load_config),
    )
    graph.add_node(
        "check_health",
        traced_node("enterprise_integration.check_health", _agent)(check_health),
    )
    graph.add_node(
        "analyze_sync_history",
        traced_node("enterprise_integration.analyze_sync_history", _agent)(analyze_sync_history),
    )
    graph.add_node(
        "diagnose_issues",
        traced_node("enterprise_integration.diagnose_issues", _agent)(diagnose_issues),
    )
    graph.add_node(
        "apply_fixes",
        traced_node("enterprise_integration.apply_fixes", _agent)(apply_fixes),
    )
    graph.add_node(
        "check_health_again",
        traced_node("enterprise_integration.check_health_again", _agent)(check_health_again),
    )
    graph.add_node(
        "generate_recommendations",
        traced_node("enterprise_integration.generate_recommendations", _agent)(
            generate_recommendations
        ),
    )

    # Define edges
    graph.set_entry_point("load_config")
    graph.add_edge("load_config", "check_health")

    # After health check: healthy → sync analysis, degraded → diagnose
    graph.add_conditional_edges(
        "check_health",
        _route_after_health,
        {
            "analyze_sync_history": "analyze_sync_history",
            "diagnose_issues": "diagnose_issues",
            "generate_recommendations": "generate_recommendations",
        },
    )

    # Healthy path
    graph.add_edge("analyze_sync_history", "generate_recommendations")

    # Degraded path: after diagnosis decide auto-fix vs manual
    graph.add_conditional_edges(
        "diagnose_issues",
        _route_after_diagnosis,
        {
            "apply_fixes": "apply_fixes",
            "generate_recommendations": "generate_recommendations",
        },
    )

    # After applying fixes, re-check health
    graph.add_edge("apply_fixes", "check_health_again")
    graph.add_edge("check_health_again", END)

    # Recommendations → END
    graph.add_edge("generate_recommendations", END)

    return graph
