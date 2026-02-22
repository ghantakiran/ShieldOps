# PRD-006: Policy & Safety Engine

**Status:** Implemented
**Author:** ShieldOps Team
**Date:** 2026-02-17
**Priority:** P0 (MVP)

## Problem Statement
Autonomous agents executing infrastructure changes without guardrails is unacceptable for enterprise customers. Every agent action must be evaluated against security policies, blast-radius limits, change windows, and compliance requirements before execution.

## Objective
Build a policy engine powered by Open Policy Agent (OPA) that evaluates every agent action against configurable rules — ensuring agents can only perform pre-approved actions within defined safety boundaries.

## Core Components

### 1. Policy Evaluation
- Every agent action passes through OPA before execution
- Policies written in Rego (OPA's policy language)
- Policies versioned and auditable (git-managed)
- Evaluation latency < 50ms (P99)

### 2. Blast Radius Controls
```rego
# Max affected resources per action
deny[msg] {
    input.affected_resources > input.environment_limits.max_blast_radius
    msg := sprintf("Action affects %d resources, limit is %d",
        [input.affected_resources, input.environment_limits.max_blast_radius])
}
```

### 3. Approval Workflows
- Slack/MS Teams integration for approval requests
- Configurable approval chains per action type + environment
- Timeout escalation (5min → next responder → manager)
- Four-eyes principle for critical actions

### 4. Rollback Framework
- Pre-action snapshots (infrastructure state capture)
- One-click rollback via dashboard or API
- Automatic rollback on validation failure
- Rollback audit trail

### 5. Compliance Mapping
- Map agent actions to compliance controls (SOC 2, PCI-DSS, HIPAA)
- Generate audit evidence automatically
- Alert on compliance drift

## Default Policies (Shipped with Product)
| Policy | Description |
|--------|-------------|
| `no_delete_data` | Agents cannot delete databases, volumes, or persistent data |
| `no_modify_iam_root` | Agents cannot modify root/admin IAM policies |
| `prod_requires_approval` | All production write actions require human approval |
| `change_freeze_window` | Block changes during configured freeze windows |
| `max_blast_radius` | Limit number of affected resources per action |
| `rate_limit_actions` | Max N actions per hour per environment |

## Success Metrics
| Metric | Target |
|--------|--------|
| Policy Evaluation Latency | < 50ms P99 |
| Policy Coverage | 100% of agent actions evaluated |
| Zero Bypass | 0 actions executed without policy check |
| False Deny Rate | < 5% (legitimate actions incorrectly blocked) |

## Timeline
- **Week 1-2:** OPA integration + base policy framework
- **Week 3-4:** Approval workflow (Slack integration)
- **Week 5-6:** Rollback framework
- **Week 7-8:** Default policy pack + testing
