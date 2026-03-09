"""LangGraph workflow definition for the ChatOps Agent."""

import structlog
from langgraph.graph import END, StateGraph

from shieldops.agents.chatops.models import (
    ChatOpsApprovalStatus,
    ChatOpsExecutionStatus,
    ChatOpsState,
)
from shieldops.agents.chatops.nodes import (
    deliver_response,
    execute_action,
    format_denial_response,
    format_error_response,
    format_response,
    parse_command,
    queue_for_approval,
    route_to_agent,
    validate_permissions,
)
from shieldops.agents.tracing import traced_node

logger = structlog.get_logger()


def after_validate_permissions(state: ChatOpsState) -> str:
    """Route based on policy evaluation result.

    - Denied → format_denial_response
    - Requires approval → queue_for_approval
    - Allowed → route_to_agent
    """
    if state.approval_status == ChatOpsApprovalStatus.DENIED:
        return "format_denial_response"
    if state.approval_status == ChatOpsApprovalStatus.PENDING:
        return "queue_for_approval"
    return "route_to_agent"


def after_execute_action(state: ChatOpsState) -> str:
    """Route based on execution result.

    - Failed → format_error_response
    - Success → format_response
    """
    if state.execution_status == ChatOpsExecutionStatus.FAILED:
        return "format_error_response"
    return "format_response"


def create_chatops_graph() -> StateGraph[ChatOpsState]:
    """Build the ChatOps Agent LangGraph workflow.

    Workflow:
        parse_command → validate_permissions
            → [conditional: route_to_agent | format_denial_response | queue_for_approval]
            → route_to_agent → execute_action
                → [conditional: format_response | format_error_response]
            → deliver_response
    """
    graph = StateGraph(ChatOpsState)

    _agent = "chatops"

    # Add nodes (wrapped with OTEL tracing spans)
    graph.add_node(
        "parse_command",
        traced_node("chatops.parse_command", _agent)(parse_command),
    )
    graph.add_node(
        "validate_permissions",
        traced_node("chatops.validate_permissions", _agent)(validate_permissions),
    )
    graph.add_node(
        "route_to_agent",
        traced_node("chatops.route_to_agent", _agent)(route_to_agent),
    )
    graph.add_node(
        "execute_action",
        traced_node("chatops.execute_action", _agent)(execute_action),
    )
    graph.add_node(
        "format_response",
        traced_node("chatops.format_response", _agent)(format_response),
    )
    graph.add_node(
        "format_denial_response",
        traced_node("chatops.format_denial_response", _agent)(format_denial_response),
    )
    graph.add_node(
        "queue_for_approval",
        traced_node("chatops.queue_for_approval", _agent)(queue_for_approval),
    )
    graph.add_node(
        "format_error_response",
        traced_node("chatops.format_error_response", _agent)(format_error_response),
    )
    graph.add_node(
        "deliver_response",
        traced_node("chatops.deliver_response", _agent)(deliver_response),
    )

    # Define edges
    graph.set_entry_point("parse_command")
    graph.add_edge("parse_command", "validate_permissions")

    # Conditional: after permission check
    graph.add_conditional_edges(
        "validate_permissions",
        after_validate_permissions,
        {
            "route_to_agent": "route_to_agent",
            "format_denial_response": "format_denial_response",
            "queue_for_approval": "queue_for_approval",
        },
    )

    # Normal flow
    graph.add_edge("route_to_agent", "execute_action")

    # Conditional: after execution
    graph.add_conditional_edges(
        "execute_action",
        after_execute_action,
        {
            "format_response": "format_response",
            "format_error_response": "format_error_response",
        },
    )

    # All response paths lead to delivery
    graph.add_edge("format_response", "deliver_response")
    graph.add_edge("format_denial_response", "deliver_response")
    graph.add_edge("queue_for_approval", "deliver_response")
    graph.add_edge("format_error_response", "deliver_response")

    # Terminal
    graph.add_edge("deliver_response", END)

    return graph
