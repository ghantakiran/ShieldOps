"""LangGraph workflow definition for the Automation Orchestrator Agent."""

import structlog
from langgraph.graph import END, StateGraph

from shieldops.agents.automation_orchestrator.models import AutomationState
from shieldops.agents.automation_orchestrator.nodes import (
    check_policy,
    evaluate_trigger,
    execute_actions,
    plan_execution,
    queue_for_approval,
    send_denial_notification,
    send_notifications,
    summarize_execution,
)
from shieldops.agents.tracing import traced_node

logger = structlog.get_logger()


def should_continue_after_trigger(state: AutomationState) -> str:
    """Route after trigger evaluation.

    If the trigger did not match or was blocked by cooldown/concurrency,
    end immediately. Otherwise proceed to policy check.
    """
    if state.error:
        return END
    if not state.policy_allowed:
        return END
    return "check_policy"


def should_continue_after_policy(state: AutomationState) -> str:
    """Route after policy evaluation.

    - If denied → send denial notification
    - If requires approval → queue for approval
    - If allowed → plan execution
    """
    if not state.policy_allowed:
        return "send_denial_notification"
    if state.requires_approval:
        return "queue_for_approval"
    return "plan_execution"


def should_continue_after_plan(state: AutomationState) -> str:
    """Route after execution planning.

    If the plan says not to execute (e.g., LLM determined actions are
    inappropriate), send notifications and end. Otherwise execute.
    """
    if state.overall_status == "denied":
        return "send_notifications"
    return "execute_actions"


def create_automation_graph() -> StateGraph[AutomationState]:
    """Build the Automation Orchestrator LangGraph workflow.

    Workflow:
        evaluate_trigger → [conditional]
          if not matched → END
          if matched → check_policy → [conditional]
            if denied → send_denial_notification → END
            if requires_approval → queue_for_approval → END
            if allowed → plan_execution → [conditional]
              if plan rejects → send_notifications → END
              if plan approves → execute_actions → summarize_execution
                → send_notifications → END
    """
    graph = StateGraph(AutomationState)

    _agent = "automation_orchestrator"

    # Add nodes (wrapped with OTEL tracing spans)
    graph.add_node(
        "evaluate_trigger",
        traced_node("automation.evaluate_trigger", _agent)(evaluate_trigger),
    )
    graph.add_node(
        "check_policy",
        traced_node("automation.check_policy", _agent)(check_policy),
    )
    graph.add_node(
        "plan_execution",
        traced_node("automation.plan_execution", _agent)(plan_execution),
    )
    graph.add_node(
        "execute_actions",
        traced_node("automation.execute_actions", _agent)(execute_actions),
    )
    graph.add_node(
        "summarize_execution",
        traced_node("automation.summarize_execution", _agent)(summarize_execution),
    )
    graph.add_node(
        "send_notifications",
        traced_node("automation.send_notifications", _agent)(send_notifications),
    )
    graph.add_node(
        "send_denial_notification",
        traced_node("automation.send_denial_notification", _agent)(send_denial_notification),
    )
    graph.add_node(
        "queue_for_approval",
        traced_node("automation.queue_for_approval", _agent)(queue_for_approval),
    )

    # Define edges
    graph.set_entry_point("evaluate_trigger")

    graph.add_conditional_edges(
        "evaluate_trigger",
        should_continue_after_trigger,
        {
            "check_policy": "check_policy",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "check_policy",
        should_continue_after_policy,
        {
            "send_denial_notification": "send_denial_notification",
            "queue_for_approval": "queue_for_approval",
            "plan_execution": "plan_execution",
        },
    )

    graph.add_conditional_edges(
        "plan_execution",
        should_continue_after_plan,
        {
            "send_notifications": "send_notifications",
            "execute_actions": "execute_actions",
        },
    )

    graph.add_edge("execute_actions", "summarize_execution")
    graph.add_edge("summarize_execution", "send_notifications")
    graph.add_edge("send_notifications", END)
    graph.add_edge("send_denial_notification", END)
    graph.add_edge("queue_for_approval", END)

    return graph
