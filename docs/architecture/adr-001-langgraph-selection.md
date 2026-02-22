# ADR-001: LangGraph as Agent Orchestration Framework

**Status:** Accepted
**Date:** 2026-02-17
**Decision Makers:** Founding Team

## Context
We need an AI agent orchestration framework to build our multi-agent SRE platform. Key requirements:
- Cyclic workflows (investigate → remediate → validate → retry/escalate)
- Persistent state across multi-step operations
- Deterministic control flow for safety-critical infrastructure operations
- Production-grade reliability with error recovery
- Transparent decision tracing for enterprise audit requirements

## Options Considered

### Option 1: LangGraph (Selected)
- Graph-based workflow with explicit state machines
- Native cyclic patterns, conditional branching
- Persistent state via checkpointing
- LangSmith integration for tracing
- Used by Klarna, Replit in production

### Option 2: CrewAI
- Role-based multi-agent system
- Sequential task execution paradigm
- Easier initial setup
- Poor fit for non-linear infrastructure workflows
- Limited state management

### Option 3: AutoGen
- Conversational multi-agent paradigm
- Good for collaborative reasoning
- Poor fit for deterministic infrastructure execution
- Limited production deployment evidence
- Higher unpredictability in agent interactions

### Option 4: OpenAI Swarm (Agents SDK)
- Lightweight, function-based routing
- Good for simple handoffs
- Lacks persistent state management
- OpenAI vendor lock-in
- Not suitable for complex multi-step workflows

## Decision
**LangGraph** for the following reasons:

1. **Workflow-Reality Match:** SRE operations are graph-shaped (not linear, not conversational)
2. **State Persistence:** Critical for multi-step remediations spanning minutes/hours
3. **Deterministic Control:** Conditional edges ensure predictable behavior for safety-critical ops
4. **Audit Trail:** Graph traces provide explainable decision chains for compliance
5. **Error Recovery:** Built-in retry, checkpoint, and fallback mechanisms

## Trade-offs Accepted
- **Steeper learning curve** — mitigated by hiring senior engineers
- **Higher compute cost** (~60% more than stateless alternatives) — offset by value delivered
- **LangChain ecosystem dependency** — acceptable given active development and MIT license

## Consequences
- All agent workflows defined as LangGraph `StateGraph` instances
- Agent state schemas use Pydantic models (type-safe, serializable)
- LangSmith required for production tracing and monitoring
- Team must learn LangGraph graph patterns (training budget allocated)

## References
- LangGraph docs: https://python.langchain.com/docs/langgraph
- Comparison analysis: Galileo AI framework comparison (2025)
- Production evidence: Klarna case study, Replit deployment
