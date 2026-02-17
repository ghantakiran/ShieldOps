# ADR-003: Agent Safety Model (Defense in Depth)

**Status:** Accepted
**Date:** 2026-02-17

## Context
Autonomous agents executing infrastructure changes carry inherent risk. Current AI agents have ~55% task completion rates. A failed agent action in production could cause outages. Enterprise customers demand safety guarantees.

## Decision
Implement a **five-layer defense-in-depth safety model**:

### Layer 1: Policy Gate (OPA)
Every agent action evaluated against Rego policies before execution.
- Blast radius limits
- Environment-specific permissions
- Change freeze windows
- Rate limiting

### Layer 2: Risk Classification
Actions classified as Low/Medium/High/Critical with corresponding approval requirements.
- Low: autonomous in dev, notify in prod
- Medium: autonomous in dev, approval in prod
- High: approval in all environments
- Critical: two-person approval in all environments

### Layer 3: Snapshot & Rollback
Infrastructure state captured before every write operation.
- Kubernetes: resource YAML snapshots
- AWS: resource state via APIs
- Linux: config file backups
- One-click rollback via dashboard or API

### Layer 4: Validation Loop
Post-action validation confirms success before moving to next step.
- Health checks on affected services
- Metric comparison (before vs. after)
- Error rate monitoring for 5 minutes post-change
- Automatic rollback if validation fails

### Layer 5: Human Escalation
Graceful degradation from autonomous to human-assisted to manual.
- Confidence < 0.5: escalate immediately
- Confidence 0.5-0.85: request human approval
- Confidence > 0.85: execute autonomously (subject to policy)
- Any failure: escalate with full context

## Reliability Math
Single-step reliability: 95%
Without safety layers: 20-step workflow = 36% success rate
With checkpoint+retry: Each checkpoint independently restartable
Effective reliability target: > 99% for end-to-end workflows

## Consequences
- Every action takes ~200ms longer (policy evaluation + snapshot)
- Storage costs for snapshots (estimated $0.50/customer/month)
- Agents must implement `validate()` and `rollback()` for every action type
- Audit trail storage grows linearly with agent activity
