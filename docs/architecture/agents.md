# Agent System

ShieldOps agents are built on [LangGraph](https://python.langchain.com/docs/langgraph),
a graph-based orchestration framework that models workflows as state machines with
conditional edges, persistent checkpoints, and error recovery.

---

## Why LangGraph?

SRE operations are graph-shaped. An investigation may branch to trace analysis or skip
it; a remediation may require approval or proceed directly; a failed validation triggers
rollback. LangGraph's `StateGraph` maps naturally to these workflows.

Key advantages:

- **Cyclic workflows** -- investigate, remediate, validate, retry
- **Persistent state** -- checkpointing across multi-step operations
- **Deterministic control flow** -- conditional edges produce predictable behavior
- **Transparent tracing** -- graph traces provide auditable decision chains
- **Error recovery** -- built-in retry and fallback mechanisms

---

## Agent Types

| Agent | Module | Graph Nodes | Purpose |
|-------|--------|-------------|---------|
| Investigation | `agents/investigation/` | 8 | Root cause analysis from alerts |
| Remediation | `agents/remediation/` | 8 | Policy-gated infrastructure changes |
| Security | `agents/security/` | 14 | CVE scanning, credential rotation, compliance |
| Learning | `agents/learning/` | 5 | Playbook refinement from historical data |
| Supervisor | `agents/supervisor/` | 6 | Multi-agent orchestration and escalation |
| Cost | `agents/cost/` | Variable | Cloud cost analysis and optimization |

---

## Agent Structure

Each agent follows a consistent module structure:

```
agents/{type}/
  __init__.py
  graph.py       # StateGraph definition (nodes + edges)
  nodes.py       # Node implementations (async functions)
  models.py      # Pydantic state model
  prompts.py     # LLM system/user prompts
  tools.py       # Agent-specific tools (connector wrappers)
  runner.py      # Runner class (entry point, wires dependencies)
```

### State Model

Each agent defines a Pydantic model that serves as the graph state. LangGraph passes
this state through every node, and each node returns a partial update dict.

```python
class InvestigationState(BaseModel):
    """State carried through the investigation workflow."""
    alert_context: AlertContext
    log_findings: list[LogFinding] = []
    metric_findings: list[MetricFinding] = []
    hypotheses: list[Hypothesis] = []
    confidence_score: float = 0.0
    reasoning_chain: list[ReasoningStep] = []
    recommended_action: RemediationAction | None = None
    error: str | None = None
```

### Graph Definition

Graphs are created by `create_{type}_graph()` functions that wire nodes and edges:

```python
def create_investigation_graph() -> StateGraph[InvestigationState]:
    graph = StateGraph(InvestigationState)

    graph.add_node("gather_context", gather_context)
    graph.add_node("analyze_logs", analyze_logs)
    # ... more nodes ...

    graph.set_entry_point("gather_context")
    graph.add_edge("gather_context", "analyze_logs")
    graph.add_conditional_edges(
        "analyze_metrics",
        should_analyze_traces,
        {"analyze_traces": "analyze_traces", "correlate_findings": "correlate_findings"},
    )
    # ... more edges ...

    return graph
```

### Runner

The `Runner` class is the public API for each agent. It creates the graph, compiles it,
and provides methods like `investigate()`, `remediate()`, or `scan()`.

---

## OpenTelemetry Tracing

Every graph node is wrapped with `traced_node()` which creates an OpenTelemetry span
per node execution. This provides:

- Per-node duration metrics
- Error tracking at the node level
- Full trace waterfall visualization in Jaeger/LangSmith
- Agent type attribution

```python
graph.add_node(
    "gather_context",
    traced_node("investigation.gather_context", "investigation")(gather_context),
)
```

---

## Agent Registry

The `AgentRegistry` class tracks all deployed agent instances in PostgreSQL. On startup,
the API server auto-registers the six agent types and the registry provides:

- Agent listing with status and health
- Enable/disable individual agents
- Agent activity tracking

See: [Agents API](../api/agents.md)

---

## Detailed Agent Documentation

- [Investigation Agent](../agents/investigation.md) -- Root cause analysis
- [Remediation Agent](../agents/remediation.md) -- Infrastructure execution
- [Security Agent](../agents/security.md) -- Security posture management
- [Learning Agent](../agents/learning.md) -- Continuous improvement
- [Supervisor Agent](../agents/supervisor.md) -- Multi-agent orchestration
