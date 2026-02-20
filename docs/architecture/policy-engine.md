# Policy Engine

Every agent action in ShieldOps must pass through the Policy Engine before execution.
The engine uses [Open Policy Agent (OPA)](https://www.openpolicyagent.org/) to evaluate
Rego policies, ensuring that agents operate within defined safety boundaries.

---

## How It Works

```
Agent prepares action
        |
        v
PolicyEngine.evaluate(action)
        |
        v
HTTP POST to OPA /v1/data/shieldops/allow
        |
        v
OPA evaluates Rego policies
        |
        +-- allowed=true  --> proceed to execution
        +-- allowed=false --> action denied, reason returned
        +-- OPA unreachable --> fail closed (deny)
```

The policy engine is implemented in `src/shieldops/policy/opa/client.py`.

---

## Default Policies

ShieldOps ships with default OPA policies in `playbooks/policies/shieldops.rego`.
These policies implement:

### Read-Only Actions (always allowed)

```rego
read_only_actions := {
    "query_logs",
    "query_metrics",
    "query_traces",
    "get_health",
    "list_resources",
    "get_events",
    "check_compliance",
}
```

### Environment-Based Permissions

| Risk Level | Development | Staging | Production |
|------------|-------------|---------|------------|
| Low | Allowed | Allowed | Allowed (safe actions only) |
| Medium | Allowed | Allowed | Allowed (safe actions only) |
| High | Allowed | Allowed | Requires approval |
| Critical | Allowed | Allowed | Requires approval |

### Forbidden Actions (hard deny)

These actions are never allowed regardless of environment or approval:

```rego
forbidden_actions := {
    "delete_database",
    "drop_table",
    "delete_namespace",
    "modify_iam_root",
    "disable_logging",
    "disable_monitoring",
    "stop_instance",
}
```

### Blast Radius Limits

Maximum resources affected per action:

| Environment | Limit |
|-------------|-------|
| Development | 50 |
| Staging | 20 |
| Production | 5 |

### Rate Limiting

Maximum actions per hour per environment:

| Environment | Limit |
|-------------|-------|
| Development | 100 |
| Staging | 50 |
| Production | 20 |

### Change Freeze Windows

Production changes are blocked during freeze windows (default: weekends UTC).
This can be overridden with `context.override_freeze`.

---

## Policy Input Schema

The policy engine sends the following input to OPA for evaluation:

```json
{
  "input": {
    "action": "restart_pod",
    "target_resource": "web-server-01",
    "environment": "production",
    "risk_level": "medium",
    "parameters": {},
    "agent_id": "inv-abc123",
    "team": "platform",
    "resource_labels": {},
    "context": {
      "actions_this_hour": 5,
      "actions_this_minute": 1,
      "team_actions_this_hour": 3
    }
  }
}
```

---

## Risk Classification

The policy engine classifies risk based on action type and environment:

```python
# Destructive actions are always CRITICAL
destructive_actions = {"drain_node", "delete_namespace", "modify_network_policy", "modify_iam_policy"}

# High-impact actions
high_impact_actions = {"rollback_deployment", "rotate_credentials", "scale_down"}
```

| Action Category | Dev | Staging | Production |
|----------------|-----|---------|------------|
| Destructive | CRITICAL | CRITICAL | CRITICAL |
| High-impact | LOW | MEDIUM | HIGH |
| Other | LOW | LOW | MEDIUM |

---

## Fail-Closed Design

The policy engine defaults to **deny** in all failure scenarios:

- OPA server unreachable: deny
- HTTP error from OPA: deny
- Circuit breaker open (5+ consecutive failures): deny with recovery info
- Unexpected exception: deny

This ensures that agent actions are never executed without policy evaluation.

---

## Circuit Breaker

The OPA client uses a circuit breaker to handle repeated failures gracefully:

- **Failure threshold:** 5 consecutive failures
- **Recovery timeout:** 30 seconds
- When open, requests fail immediately with a descriptive message

---

## Customizing Policies

### Adding a New Policy Rule

Create a new `.rego` file in `playbooks/policies/` or extend `shieldops.rego`:

```rego
# Allow specific actions for a named team
allow if {
    input.team == "sre-oncall"
    input.environment == "production"
    input.action in {"restart_pod", "scale_horizontal"}
}
```

### Loading Custom Policies

OPA loads policies from the `playbooks/policies/` directory. In Docker Compose,
this directory is mounted as a volume. In Kubernetes, policies are loaded via
ConfigMap (see [Helm Chart](../deployment/helm.md)).

### Testing Policies

Use the OPA CLI to test policies locally:

```bash
# Evaluate a policy with sample input
opa eval -d playbooks/policies/ -i test-input.json "data.shieldops.allow"

# Run Rego unit tests
opa test playbooks/policies/
```
