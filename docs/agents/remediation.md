# Remediation Agent

The Remediation Agent executes infrastructure changes with full policy evaluation,
approval workflows, snapshotting, and automatic rollback on failure.

---

## Purpose

- Execute remediation actions (restart, scale, rollback, patch)
- Evaluate every action against OPA policies before execution
- Request human approval for high-risk operations
- Capture infrastructure state snapshots before changes
- Validate health after execution
- Automatically rollback on failure

---

## Graph Workflow

```
evaluate_policy
      |
      +-- [denied] --> END
      |
      v
resolve_playbook
      |
      v
assess_risk
      |
      +-- [high/critical risk] --> request_approval
      |                                  |
      |                          +-- [denied] --> END
      |                          |
      |                          +-- [approved] --> create_snapshot
      |
      +-- [low/medium risk] --> create_snapshot
                                       |
                                       v
                                execute_action
                                       |
                                +-- [failed] --> perform_rollback --> END
                                |
                                +-- [success] --> validate_health
                                                       |
                                                +-- [unhealthy] --> perform_rollback --> END
                                                |
                                                +-- [healthy] --> END
```

### Nodes

| Node | Description |
|------|-------------|
| `evaluate_policy` | Submit action to OPA for policy evaluation |
| `resolve_playbook` | Match action to a YAML playbook for step-by-step guidance |
| `assess_risk` | Classify risk level (low/medium/high/critical) |
| `request_approval` | Send Slack notification and wait for human approval |
| `create_snapshot` | Capture pre-action infrastructure state |
| `execute_action` | Execute the remediation via the connector layer |
| `validate_health` | Verify resource health after execution |
| `perform_rollback` | Restore pre-action state from snapshot |

### Conditional Edges

- **After `evaluate_policy`:** Denied actions go directly to END.
- **After `assess_risk`:** High/critical risk actions require approval.
- **After `execute_action`:** Failures trigger immediate rollback.
- **After `validate_health`:** Unhealthy resources trigger rollback.

---

## State Model

```python
class RemediationState(BaseModel):
    action: RemediationAction          # The action to execute
    policy_result: PolicyDecision | None  # OPA evaluation result
    playbook: dict | None              # Matched playbook steps
    assessed_risk: RiskLevel | None    # Classified risk level
    approval_status: ApprovalStatus | None  # Approval result
    approval_request_id: str | None    # Pending approval ID
    snapshot: Snapshot | None          # Pre-action state snapshot
    execution_result: ActionResult | None  # Action execution result
    validation_passed: bool | None     # Post-action health check
    rollback_result: ActionResult | None  # Rollback result (if triggered)
    error: str | None
```

---

## Approval Workflow

High-risk and critical-risk actions trigger the approval workflow:

1. A Slack message is sent to the configured approval channel
2. The agent waits for a response (default timeout: 5 minutes)
3. If no response, the request escalates through the escalation chain
4. Critical actions require **two independent approvals** (four-eyes principle)

Approvals can also be managed via the API:

```bash
# Approve a pending remediation
curl -X POST http://localhost:8000/api/v1/remediations/{id}/approve \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"approver": "sre-lead@company.com", "reason": "Verified safe to proceed"}'

# Deny a pending remediation
curl -X POST http://localhost:8000/api/v1/remediations/{id}/deny \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"approver": "sre-lead@company.com", "reason": "Too risky during peak hours"}'
```

---

## Rollback

Rollback is available for any completed remediation that has a snapshot:

```bash
curl -X POST http://localhost:8000/api/v1/remediations/{id}/rollback \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"reason": "Change caused increased error rate"}'
```

---

## Example Usage

### Trigger a remediation

```bash
curl -X POST http://localhost:8000/api/v1/remediations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "restart_pod",
    "target_resource": "pod/web-server-01",
    "environment": "production",
    "risk_level": "medium",
    "parameters": {"namespace": "default"},
    "description": "Restart pod to recover from OOM state"
  }'
```

Response (202 Accepted):

```json
{
  "status": "accepted",
  "action_id": "act-a1b2c3d4e5f6",
  "action_type": "restart_pod",
  "message": "Remediation started. Use GET /remediations to track progress."
}
```

---

## Playbook Integration

The remediation agent matches actions to YAML playbooks in `playbooks/`.
Playbooks define investigation steps, decision trees, and action parameters:

```yaml
# playbooks/pod-crash-loop.yaml
name: pod-crash-loop
trigger:
  alert_type: "KubePodCrashLooping"

remediation:
  decision_tree:
    - condition: "OOMKilled"
      action: increase_memory_limit
    - condition: "recent_deployment"
      action: rollback_deployment
    - condition: "dependency_unhealthy"
      action: restart_pod_with_backoff
```
