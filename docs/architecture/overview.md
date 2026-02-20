# Architecture Overview

ShieldOps is a four-layer platform designed to give autonomous AI agents the ability
to investigate incidents, remediate infrastructure issues, and enforce security policies
across any cloud or on-premise environment.

---

## Four-Layer Architecture

```
+-----------------------------------------------------+
|  Layer 4: Policy & Safety                            |
|  OPA policies . Approval workflows . Rollback        |
|  Compliance reporting . Blast-radius limits          |
+-----------------------------------------------------+
|  Layer 3: Agent Orchestration (LangGraph)            |
|  Investigation . Remediation . Security . Learning   |
|  Cost . Supervisor (multi-agent coordination)        |
+-----------------------------------------------------+
|  Layer 2: Observability Ingestion                    |
|  OpenTelemetry . Splunk . Datadog . Prometheus       |
|  Vendor-neutral telemetry . No rip-and-replace       |
+-----------------------------------------------------+
|  Layer 1: Multi-Environment Connectors               |
|  AWS . GCP . Azure . Kubernetes . Linux (SSH)        |
|  Unified interface . Write once, deploy anywhere     |
+-----------------------------------------------------+
```

### Layer 1: Multi-Environment Connectors

All infrastructure operations go through a `ConnectorRouter` that dispatches to
provider-specific implementations (AWS, GCP, Azure, Kubernetes, Linux). Agents never
call cloud APIs directly.

See: [Connector Layer](connectors.md)

### Layer 2: Observability Ingestion

A vendor-neutral telemetry layer supports Prometheus, Splunk, Datadog, and native
OpenTelemetry. Sources are registered at startup based on configuration -- no code
changes required to add a new observability backend.

### Layer 3: Agent Orchestration

Six agent types run as LangGraph `StateGraph` workflows:

| Agent | Purpose |
|-------|---------|
| [Investigation](../agents/investigation.md) | Root cause analysis from alerts, logs, metrics, traces |
| [Remediation](../agents/remediation.md) | Policy-gated infrastructure execution |
| [Security](../agents/security.md) | CVE patching, credential rotation, compliance |
| [Learning](../agents/learning.md) | Playbook refinement from historical outcomes |
| Cost | Cloud cost analysis and optimization |
| [Supervisor](../agents/supervisor.md) | Multi-agent orchestration and escalation |

See: [Agent System](agents.md)

### Layer 4: Policy & Safety

Every agent action is evaluated against OPA (Open Policy Agent) Rego policies
before execution. A five-layer defense-in-depth model prevents unsafe changes.

See: [Policy Engine](policy-engine.md), [Safety Model](safety-model.md)

---

## Architecture Decision Records

The following ADRs document key technical decisions:

### ADR-001: LangGraph as Agent Framework

**Decision:** Use LangGraph for agent orchestration.

**Rationale:**

- SRE operations are graph-shaped (not linear or conversational)
- Persistent state via checkpointing supports multi-step remediations
- Conditional edges ensure deterministic, predictable behavior
- Graph traces provide explainable decision chains for compliance
- Built-in retry, checkpoint, and fallback mechanisms

**Alternatives rejected:** CrewAI (linear paradigm), AutoGen (conversational, not
deterministic), OpenAI Swarm (no persistent state, vendor lock-in).

### ADR-002: Protocol-Based Multi-Cloud Abstraction

**Decision:** Use an abstract `InfraConnector` interface with a `ConnectorRouter`.

**Rationale:**

- Agents write infrastructure logic once; connectors handle provider differences
- Each new cloud requires only a connector implementation, no agent changes
- Testing uses mock connectors -- no cloud resources needed for unit tests
- Latency budgets: read < 200ms, write < 2s, snapshot < 10s

**Alternatives rejected:** Terraform-only (too slow for real-time), per-cloud agent
implementations (doesn't scale).

### ADR-003: Five-Layer Safety Model

**Decision:** Implement defense-in-depth with five safety layers.

**Rationale:**

- Single-step reliability of 95% means a 20-step workflow has only 36% success
- Checkpointing makes each step independently restartable
- Fail-closed policy evaluation prevents unsafe actions during OPA outages
- Snapshot-before-write enables one-click rollback

See: [Safety Model](safety-model.md)

---

## Data Flow

```
Alert (Kafka/API)
    |
    v
Supervisor Agent
    |
    +--> Investigation Agent
    |         |
    |         +--> Connector (get_events, get_health)
    |         +--> Observability (query_logs, query_metrics, query_traces)
    |         +--> LLM (hypothesis generation)
    |         |
    |         v
    |    Investigation Result (confidence, hypotheses)
    |
    +--> Remediation Agent (if confidence > 0.85)
    |         |
    |         +--> Policy Engine (OPA evaluate)
    |         +--> Approval Workflow (if high/critical risk)
    |         +--> Connector (create_snapshot, execute_action)
    |         +--> Connector (validate_health)
    |         +--> Connector (rollback if validation fails)
    |
    +--> Learning Agent (post-incident)
              |
              +--> Repository (fetch outcomes)
              +--> LLM (pattern analysis, playbook recommendations)
              +--> Playbook Store (updates)
```

---

## Key Dependencies

| Component | Purpose | Connection |
|-----------|---------|------------|
| PostgreSQL | Agent state, investigations, remediations, audit trail | `SHIELDOPS_DATABASE_URL` |
| Redis | Rate limiting, token revocation, job scheduling, caching | `SHIELDOPS_REDIS_URL` |
| Kafka | Alert event streaming, agent event bus | `SHIELDOPS_KAFKA_BROKERS` |
| OPA | Policy evaluation for all agent actions | `SHIELDOPS_OPA_ENDPOINT` |
| Anthropic Claude | Primary LLM for agent reasoning | `SHIELDOPS_ANTHROPIC_API_KEY` |

---

## Project Structure

```
src/shieldops/
  agents/                  # Agent implementations
    investigation/         #   graph.py, nodes.py, models.py, runner.py
    remediation/           #   graph.py, nodes.py, models.py, runner.py
    security/              #   graph.py, nodes.py, models.py, runner.py
    learning/              #   graph.py, nodes.py, models.py, runner.py
    supervisor/            #   graph.py, nodes.py, models.py, runner.py
    cost/                  #   graph.py, nodes.py, models.py, runner.py
    registry.py            #   Agent fleet registry
    tracing.py             #   OpenTelemetry span wrappers
  connectors/              # Multi-cloud connectors
    base.py                #   InfraConnector ABC + ConnectorRouter
    factory.py             #   Connector registration from settings
    kubernetes/            #   Kubernetes implementation
    aws/                   #   AWS implementation
    gcp/                   #   GCP implementation
    azure/                 #   Azure implementation
    linux/                 #   SSH/Ansible implementation
  policy/                  # Safety & governance
    opa/client.py          #   OPA policy evaluation
    approval/workflow.py   #   Human-in-the-loop approvals
    rollback/manager.py    #   Rollback orchestration
  api/                     # FastAPI application
    app.py                 #   App factory, lifespan, middleware
    auth/                  #   JWT auth, OIDC, RBAC
    routes/                #   REST endpoints per resource
    middleware/             #   Rate limiting, security headers, metrics
    ws/                    #   WebSocket routes and connection manager
  config/settings.py       # Pydantic Settings (all env vars)
  models/base.py           # Shared Pydantic models
```
