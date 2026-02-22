# PRD-001: Investigation Agent

**Status:** Implemented
**Author:** ShieldOps Team
**Date:** 2026-02-17
**Priority:** P0 (MVP)

## Problem Statement
SRE teams spend 60-70% of incident response time on manual root cause analysis — querying logs, correlating metrics, tracing dependencies across services. With alert volumes exceeding 50/day in mid-size companies, human investigation capacity is the primary bottleneck in MTTR reduction.

## Objective
Build an autonomous Investigation Agent that performs root cause analysis when alerts trigger, producing a ranked hypothesis with evidence and confidence scores — reducing time-to-diagnosis from hours to minutes.

## Target Persona
- **Primary:** On-call SRE engineer (receives 2am pages, needs fast triage)
- **Secondary:** VP Engineering (wants MTTR metrics improvement)
- **Tertiary:** Security team (needs incident forensics trail)

## User Stories

### US-1: Automated Alert Triage
**As** an on-call SRE, **I want** the agent to automatically investigate when an alert fires **so that** I receive a root cause hypothesis before I even open my laptop.

**Acceptance Criteria:**
- Agent triggers within 30 seconds of alert receipt
- Queries relevant logs, metrics, and traces from connected observability tools
- Produces structured hypothesis with: root cause, confidence score (0-1), evidence chain, affected services
- If confidence > 0.85, recommends specific remediation action
- If confidence < 0.5, escalates to human with investigation summary

### US-2: Multi-Source Correlation
**As** an SRE, **I want** the agent to correlate data across Splunk, Prometheus, and Kubernetes events **so that** I get a unified view instead of querying 5 different tools.

**Acceptance Criteria:**
- Agent queries 3+ observability sources per investigation
- Correlates events by timestamp, service name, and trace ID
- Identifies dependency chains (Service A → Service B → Database C)
- Presents timeline of events leading to incident

### US-3: Historical Pattern Matching
**As** an SRE, **I want** the agent to compare current incidents against historical patterns **so that** known issues are resolved instantly.

**Acceptance Criteria:**
- Agent maintains index of past incidents and resolutions
- Matches current alert signature against historical patterns
- If match found (>0.9 similarity), suggests previous resolution
- Tracks pattern match accuracy over time

## Technical Design

### LangGraph Workflow
```
[Alert Received] → [Context Gathering] → [Log Analysis] → [Metric Analysis]
       ↓                                         ↓                ↓
[Trace Analysis] → [Correlation Engine] → [Hypothesis Generation]
       ↓                                         ↓
[Confidence Scoring] → [>0.85: Recommend Action] / [<0.5: Escalate] / [0.5-0.85: Request Approval]
```

### State Schema
```python
class InvestigationState(BaseModel):
    alert_id: str
    alert_context: AlertContext
    log_findings: list[LogFinding]
    metric_anomalies: list[MetricAnomaly]
    trace_analysis: TraceResult | None
    correlated_events: list[CorrelatedEvent]
    hypotheses: list[Hypothesis]
    confidence_score: float
    recommended_action: RemediationAction | None
    investigation_duration_ms: int
    reasoning_chain: list[ReasoningStep]
```

### Tools Required
- `query_logs(source, query, time_range)` — Query Splunk/ELK/CloudWatch
- `query_metrics(source, metric_name, labels, time_range)` — Query Prometheus/Datadog/CloudWatch
- `query_traces(trace_id)` — Query Jaeger/Zipkin/X-Ray
- `get_k8s_events(namespace, resource)` — Kubernetes event stream
- `get_deployment_history(service, time_range)` — Recent deployments
- `search_incidents(query)` — Historical incident database
- `get_service_topology(service)` — Dependency map

### OPA Policies
- Agent can only read data (no write operations)
- Rate limit: max 100 queries per investigation
- Time limit: max 10 minutes per investigation
- Data access: limited to customer's own tenancy

## Success Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to Hypothesis | < 5 minutes | Median across all investigations |
| Hypothesis Accuracy | > 70% | Validated by human SRE feedback |
| Alert-to-Resolution | 50% reduction in MTTR | Before/after comparison |
| False Positive Rate | < 15% | Incorrect root cause identifications |
| Coverage | 80% of common alert types | Alert types with playbooks |

## MVP Scope (Phase 1)
- AWS + Kubernetes environments only
- Splunk + Prometheus integrations
- 10 pre-built investigation playbooks (pod crashes, high latency, disk full, OOM kills, certificate expiry, DNS failures, connection pool exhaustion, API rate limiting, deployment rollback triggers, health check failures)
- Basic historical pattern matching

## Out of Scope (Phase 1)
- GCP/Azure (Phase 2)
- Datadog/New Relic integrations (Phase 2)
- Custom playbook builder UI (Phase 2)
- Multi-tenant investigation sharing (Phase 3)

## Dependencies
- Observability Ingestion Layer must be operational
- Kubernetes connector must support event streaming
- Historical incident database schema defined
- OPA policy engine deployed and configured

## Timeline
- **Week 1-2:** Core LangGraph workflow + state management
- **Week 3-4:** Observability tool integrations (Splunk, Prometheus)
- **Week 5-6:** Hypothesis generation + confidence scoring
- **Week 7-8:** Historical pattern matching + testing
- **Week 9-10:** Shadow mode testing with design partners
