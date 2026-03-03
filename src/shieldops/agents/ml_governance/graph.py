"""LangGraph workflow definition for the ML Governance Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.ml_governance.models import MLGovernanceState
from shieldops.agents.ml_governance.nodes import (
    assess_risk,
    audit_models,
    evaluate_fairness,
    finalize_evaluation,
    plan_actions,
)
from shieldops.agents.tracing import traced_node


def should_evaluate(state: MLGovernanceState) -> str:
    """Check if fairness evaluation is needed based on audit results."""
    if state.error:
        return "finalize_evaluation"
    if state.audit_count > 0:
        return "evaluate_fairness"
    return "finalize_evaluation"


def should_act(state: MLGovernanceState) -> str:
    """Check if action planning is needed based on critical findings."""
    if state.critical_count > 0:
        return "plan_actions"
    return "finalize_evaluation"


def create_ml_governance_graph() -> StateGraph[MLGovernanceState]:
    """Build the ML Governance Agent LangGraph workflow.

    Workflow:
        audit_models -> [has_audits? -> evaluate_fairness -> assess_risk]
            -> [critical? -> plan_actions]
            -> finalize_evaluation
    """
    graph = StateGraph(MLGovernanceState)

    _agent = "ml_governance"
    graph.add_node(
        "audit_models",
        traced_node("ml_governance.audit_models", _agent)(audit_models),
    )
    graph.add_node(
        "evaluate_fairness",
        traced_node("ml_governance.evaluate_fairness", _agent)(evaluate_fairness),
    )
    graph.add_node(
        "assess_risk",
        traced_node("ml_governance.assess_risk", _agent)(assess_risk),
    )
    graph.add_node(
        "plan_actions",
        traced_node("ml_governance.plan_actions", _agent)(plan_actions),
    )
    graph.add_node(
        "finalize_evaluation",
        traced_node("ml_governance.finalize_evaluation", _agent)(finalize_evaluation),
    )

    # Define edges
    graph.set_entry_point("audit_models")
    graph.add_conditional_edges(
        "audit_models",
        should_evaluate,
        {"evaluate_fairness": "evaluate_fairness", "finalize_evaluation": "finalize_evaluation"},
    )
    graph.add_edge("evaluate_fairness", "assess_risk")
    graph.add_conditional_edges(
        "assess_risk",
        should_act,
        {"plan_actions": "plan_actions", "finalize_evaluation": "finalize_evaluation"},
    )
    graph.add_edge("plan_actions", "finalize_evaluation")
    graph.add_edge("finalize_evaluation", END)

    return graph
