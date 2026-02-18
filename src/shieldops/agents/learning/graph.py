"""LangGraph workflow definition for the Learning Agent.

Workflow:
    gather_outcomes → analyze_patterns
    → [if not pattern_only] recommend_playbooks
    → [if not playbook_only] recommend_thresholds
    → synthesize_improvements → END
"""

import structlog
from langgraph.graph import END, StateGraph

from shieldops.agents.learning.models import LearningState
from shieldops.agents.learning.nodes import (
    analyze_patterns,
    gather_outcomes,
    recommend_playbooks,
    recommend_thresholds,
    synthesize_improvements,
)

logger = structlog.get_logger()


def should_recommend_playbooks(state: LearningState) -> str:
    """Skip playbook recommendations if learning type is pattern_only or threshold_only."""
    if state.learning_type in ("pattern_only", "threshold_only"):
        return "synthesize_improvements" if state.learning_type == "pattern_only" else "recommend_thresholds"
    if state.error:
        return "synthesize_improvements"
    return "recommend_playbooks"


def should_recommend_thresholds(state: LearningState) -> str:
    """Skip threshold recommendations if learning type is pattern_only or playbook_only."""
    if state.learning_type in ("pattern_only", "playbook_only"):
        return "synthesize_improvements"
    if state.error:
        return "synthesize_improvements"
    return "recommend_thresholds"


def create_learning_graph() -> StateGraph:
    """Build the Learning Agent LangGraph workflow."""
    graph = StateGraph(LearningState)

    # Add nodes
    graph.add_node("gather_outcomes", gather_outcomes)
    graph.add_node("analyze_patterns", analyze_patterns)
    graph.add_node("recommend_playbooks", recommend_playbooks)
    graph.add_node("recommend_thresholds", recommend_thresholds)
    graph.add_node("synthesize_improvements", synthesize_improvements)

    # Entry point
    graph.set_entry_point("gather_outcomes")

    # Linear: gather → analyze patterns
    graph.add_edge("gather_outcomes", "analyze_patterns")

    # Conditional: patterns → playbooks or skip
    graph.add_conditional_edges(
        "analyze_patterns",
        should_recommend_playbooks,
        {
            "recommend_playbooks": "recommend_playbooks",
            "recommend_thresholds": "recommend_thresholds",
            "synthesize_improvements": "synthesize_improvements",
        },
    )

    # Conditional: playbooks → thresholds or skip
    graph.add_conditional_edges(
        "recommend_playbooks",
        should_recommend_thresholds,
        {
            "recommend_thresholds": "recommend_thresholds",
            "synthesize_improvements": "synthesize_improvements",
        },
    )

    # Thresholds → synthesis
    graph.add_edge("recommend_thresholds", "synthesize_improvements")

    # Synthesis → END
    graph.add_edge("synthesize_improvements", END)

    return graph
