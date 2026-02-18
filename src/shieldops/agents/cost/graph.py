"""LangGraph workflow definition for the Cost Agent.

Workflow:
    gather_costs → detect_anomalies
    → [if not anomaly_only] recommend_optimizations
    → synthesize_savings → END
"""

import structlog
from langgraph.graph import END, StateGraph

from shieldops.agents.cost.models import CostAnalysisState
from shieldops.agents.cost.nodes import (
    detect_anomalies,
    gather_costs,
    recommend_optimizations,
    synthesize_savings,
)

logger = structlog.get_logger()


def should_recommend_optimizations(state: CostAnalysisState) -> str:
    """Skip optimization analysis if scan type is anomaly_only."""
    if state.analysis_type == "anomaly_only":
        return "synthesize_savings"
    if state.error:
        return "synthesize_savings"
    return "recommend_optimizations"


def should_detect_anomalies(state: CostAnalysisState) -> str:
    """Skip anomaly detection if scan type is optimization_only or savings_only."""
    if state.analysis_type in ("optimization_only", "savings_only"):
        return (
            "recommend_optimizations"
            if state.analysis_type == "optimization_only"
            else "synthesize_savings"
        )
    if state.error:
        return "synthesize_savings"
    return "detect_anomalies"


def create_cost_graph() -> StateGraph:
    """Build the Cost Agent LangGraph workflow."""
    graph = StateGraph(CostAnalysisState)

    # Add nodes
    graph.add_node("gather_costs", gather_costs)
    graph.add_node("detect_anomalies", detect_anomalies)
    graph.add_node("recommend_optimizations", recommend_optimizations)
    graph.add_node("synthesize_savings", synthesize_savings)

    # Entry point
    graph.set_entry_point("gather_costs")

    # Conditional: gather → anomalies or skip
    graph.add_conditional_edges(
        "gather_costs",
        should_detect_anomalies,
        {
            "detect_anomalies": "detect_anomalies",
            "recommend_optimizations": "recommend_optimizations",
            "synthesize_savings": "synthesize_savings",
        },
    )

    # Conditional: anomalies → optimizations or skip to synthesis
    graph.add_conditional_edges(
        "detect_anomalies",
        should_recommend_optimizations,
        {
            "recommend_optimizations": "recommend_optimizations",
            "synthesize_savings": "synthesize_savings",
        },
    )

    # Optimizations → synthesis
    graph.add_edge("recommend_optimizations", "synthesize_savings")

    # Synthesis → END
    graph.add_edge("synthesize_savings", END)

    return graph
