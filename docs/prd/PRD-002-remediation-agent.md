# PRD-002: Remediation Agent

**Status:** Implemented
**Author:** ShieldOps Team
**Date:** 2026-02-17
**Priority:** P0 (MVP)

## Problem Statement
Even after root cause is identified, remediation execution is manual — SREs SSH into servers, run kubectl commands, restart services, scale resources. This human execution step adds 30-60 minutes to MTTR and introduces human error risk (wrong namespace, wrong cluster, missed rollback).

## Objective
Build a Remediation Agent that executes infrastructure changes (restart, scale, patch, rollback) with policy-gated safety controls — turning investigation results into automated resolution.

## Target Persona
- **Primary:** On-call SRE (wants automated fix execution)
- **Secondary:** Platform team lead (wants consistent remediation patterns)
- **Tertiary:** CISO (needs audit trail of all infrastructure changes)

## User Stories

### US-1: Automated Pod Remediation
**As** an SRE, **I want** the agent to automatically restart crash-looping pods and validate recovery **so that** common failures resolve without human intervention.

**Acceptance Criteria:**
- Agent receives remediation request from Investigation Agent
- Validates action against OPA policies (environment, blast radius, time window)
- Creates infrastructure snapshot before executing changes
- Executes remediation (e.g., `kubectl rollout restart`)
- Validates success via health checks within 5 minutes
- If validation fails, triggers automatic rollback
- Full audit trail logged to immutable store

### US-2: Scaling Operations
**As** a platform engineer, **I want** the agent to auto-scale resources when capacity thresholds are breached **so that** we prevent cascading failures.

**Acceptance Criteria:**
- Agent detects resource pressure (CPU > 85%, memory > 90%, disk > 85%)
- Evaluates scaling options (horizontal pod scaling, node scaling, resource limit adjustment)
- Respects budget constraints (max nodes, max pods per namespace)
- Executes scaling action with rollback capability
- Reports scaling event with cost impact estimate

### US-3: Human Approval Workflow
**As** a VP Engineering, **I want** high-impact remediations to require human approval **so that** risky changes don't happen automatically.

**Acceptance Criteria:**
- Actions classified by risk level (low/medium/high/critical)
- Low-risk: autonomous execution (restart pods in dev)
- Medium-risk: notify + execute unless vetoed in 5 minutes
- High-risk: require explicit approval via Slack/Teams
- Critical: require approval from 2 people (four-eyes principle)
- Approval timeout: escalate to next responder after 10 minutes

## Technical Design

### LangGraph Workflow
```
[Remediation Request] → [Policy Evaluation (OPA)] → [Risk Assessment]
       ↓                                                    ↓
[Low Risk: Execute] → [Create Snapshot] → [Execute Action] → [Validate] → [Success/Rollback]
[Medium Risk: Notify] → [Wait 5m] → [Execute/Veto]
[High Risk: Request Approval] → [Wait 10m] → [Approved: Execute] / [Denied: Log] / [Timeout: Escalate]
```

### State Schema
```python
class RemediationState(BaseModel):
    request_id: str
    investigation_id: str
    target_environment: Environment
    action: RemediationAction
    risk_level: RiskLevel  # low, medium, high, critical
    policy_evaluation: PolicyResult
    snapshot_id: str | None
    execution_status: ExecutionStatus
    validation_result: ValidationResult | None
    rollback_available: bool
    approval_status: ApprovalStatus | None
    audit_trail: list[AuditEntry]
    duration_ms: int
```

### Remediation Actions (MVP)
| Action | Risk Level | Auto-Execute |
|--------|-----------|--------------|
| Restart pod | Low (dev), Medium (prod) | Dev: yes, Prod: approval |
| Scale horizontal (pods) | Medium | Approval in prod |
| Scale vertical (resources) | Medium | Approval in prod |
| Rollback deployment | High | Always requires approval |
| Rotate credentials | High | Always requires approval |
| Modify network policy | Critical | Requires 2 approvals |
| Drain node | Critical | Requires 2 approvals |

### OPA Policies Required
```rego
# Example: blast_radius_check
deny[msg] {
    input.action == "drain_node"
    input.environment == "production"
    count(input.affected_pods) > 50
    msg := "Cannot drain node affecting >50 pods in production"
}

# Example: time_window_check
deny[msg] {
    input.environment == "production"
    is_change_freeze_window(input.timestamp)
    not input.override_freeze
    msg := "Action blocked during change freeze window"
}
```

## Success Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Automated Resolution Rate | 40% of incidents | Incidents resolved without human |
| Remediation Accuracy | > 95% | Successful fixes / total attempts |
| Rollback Rate | < 5% | Rollbacks triggered / total remediations |
| Time to Remediation | < 10 minutes | From hypothesis to validated fix |
| Zero Security Incidents | 0 | Agent-caused security breaches |

## MVP Scope (Phase 1)
- Kubernetes pod/deployment operations (restart, scale, rollback)
- Linux service management (systemctl restart/stop/start)
- Snapshot + rollback for all actions
- Slack integration for approval workflows
- 10 pre-built remediation playbooks

## Dependencies
- Investigation Agent (provides remediation requests)
- OPA Policy Engine deployed
- Kubernetes connector with write permissions
- Slack/Teams webhook integration
- Audit logging infrastructure

## Timeline
- **Week 1-2:** Core remediation workflow + OPA integration
- **Week 3-4:** Kubernetes and Linux action executors
- **Week 5-6:** Approval workflow (Slack) + snapshot/rollback
- **Week 7-8:** Validation framework + testing
- **Week 9-10:** Shadow mode with design partners
