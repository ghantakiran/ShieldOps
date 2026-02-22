"""LangGraph workflow definition for the Prediction Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.prediction.models import PredictionState
from shieldops.agents.prediction.nodes import (
    assess_risk,
    collect_baselines,
    correlate_changes,
    detect_trends,
    generate_predictions,
)


def should_generate(state: PredictionState) -> str:
    """Only generate predictions if risk is non-trivial."""
    if state.error:
        return END
    if state.risk_score > 0.1 or state.trend_anomalies:
        return "generate_predictions"
    return END


def create_prediction_graph() -> StateGraph[PredictionState]:
    """Build the Prediction Agent LangGraph workflow.

    Workflow:
        collect_baselines → detect_trends → correlate_changes
        → assess_risk → [conditional: generate_predictions OR end]
    """
    graph = StateGraph(PredictionState)

    graph.add_node("collect_baselines", collect_baselines)
    graph.add_node("detect_trends", detect_trends)
    graph.add_node("correlate_changes", correlate_changes)
    graph.add_node("assess_risk", assess_risk)
    graph.add_node("generate_predictions", generate_predictions)

    graph.set_entry_point("collect_baselines")
    graph.add_edge("collect_baselines", "detect_trends")
    graph.add_edge("detect_trends", "correlate_changes")
    graph.add_edge("correlate_changes", "assess_risk")
    graph.add_conditional_edges(
        "assess_risk",
        should_generate,
        {
            "generate_predictions": "generate_predictions",
            END: END,
        },
    )
    graph.add_edge("generate_predictions", END)

    return graph
