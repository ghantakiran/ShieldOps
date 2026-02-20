# Safety Model

ShieldOps implements a **five-layer defense-in-depth** safety model. Autonomous agents
executing infrastructure changes carry inherent risk -- this model ensures that every
action is evaluated, constrained, recoverable, and auditable.

---

## The Five Layers

```
+-------------------------------------------------+
|  Layer 5: Human Escalation                      |
|  Confidence-based routing to humans             |
+-------------------------------------------------+
|  Layer 4: Validation Loop                       |
|  Post-action health checks + auto-rollback      |
+-------------------------------------------------+
|  Layer 3: Snapshot & Rollback                   |
|  State captured before every write operation    |
+-------------------------------------------------+
|  Layer 2: Risk Classification                   |
|  Actions rated with approval requirements       |
+-------------------------------------------------+
|  Layer 1: Policy Gate (OPA)                     |
|  Rego policies evaluate every action            |
+-------------------------------------------------+
```

---

## Layer 1: Policy Gate (OPA)

Every agent action is evaluated against OPA Rego policies **before** execution.

- Blast radius limits per environment
- Environment-specific permissions (dev/staging/prod)
- Change freeze windows
- Rate limiting (actions per hour)
- Forbidden action hard-deny list

!!! note
    The policy engine is fail-closed: if OPA is unreachable, all actions are denied.
    See [Policy Engine](policy-engine.md) for details.

---

## Layer 2: Risk Classification

Actions are classified into four risk levels with corresponding approval requirements:

| Risk Level | Development | Staging | Production |
|------------|-------------|---------|------------|
| **Low** | Autonomous | Autonomous | Autonomous (notify) |
| **Medium** | Autonomous | Autonomous | Autonomous (safe actions) |
| **High** | Requires approval | Requires approval | Requires approval |
| **Critical** | Two-person approval | Two-person approval | Two-person approval |

The `PolicyEngine.classify_risk()` method determines risk based on action type and
environment. Destructive actions (e.g., `drain_node`, `delete_namespace`) are always
classified as CRITICAL.

---

## Layer 3: Snapshot & Rollback

Infrastructure state is captured **before** every write operation:

- **Kubernetes:** Resource YAML snapshots
- **AWS:** Resource state via APIs
- **Linux:** Config file backups

Rollback is available via:

- Dashboard one-click rollback button
- API endpoint: `POST /api/v1/remediations/{id}/rollback`
- Automatic rollback on validation failure (Layer 4)

The `RollbackManager` in `src/shieldops/policy/rollback/manager.py` orchestrates
rollback operations with full audit logging. It follows a defensive design -- it never
raises exceptions and always returns an `ActionResult`.

---

## Layer 4: Validation Loop

After every action, the agent validates the result:

1. **Health checks** on affected resources
2. **Metric comparison** (before vs. after)
3. **Error rate monitoring** for 5 minutes post-change
4. **Automatic rollback** if validation fails

The remediation graph implements this as a conditional edge:

```
execute_action --> validate_health --> [healthy?] --> END
                                   --> [unhealthy?] --> perform_rollback --> END
```

---

## Layer 5: Human Escalation

Agents route to humans based on confidence scores:

| Confidence | Action |
|------------|--------|
| > 0.85 | Execute autonomously (subject to policy) |
| 0.50 - 0.85 | Request human approval |
| < 0.50 | Escalate immediately with full context |
| Any failure | Escalate with full context |

The approval workflow in `src/shieldops/policy/approval/workflow.py` supports:

- **Slack notifications** for approval requests
- **Timeout handling** (default: 5 minutes for primary, 10 minutes for escalation)
- **Escalation chains** -- if the primary approver doesn't respond, escalate to next
- **Four-eyes principle** -- CRITICAL actions require two independent approvals

---

## Reliability Math

Without safety layers:

- Single-step reliability: ~95%
- 20-step workflow success rate: 0.95^20 = **36%**

With checkpoint and retry (ShieldOps model):

- Each checkpoint is independently restartable
- Failed steps retry up to 3 times
- Validation catches post-action issues
- Automatic rollback recovers from detected failures
- **Target: > 99% effective reliability** for end-to-end workflows

---

## Audit Trail

Every action produces an immutable audit entry in PostgreSQL:

```python
class AuditEntry(BaseModel):
    id: str
    timestamp: datetime
    agent_type: str
    action: str
    target_resource: str
    environment: Environment
    risk_level: RiskLevel
    policy_evaluation: str  # allowed | denied
    outcome: ExecutionStatus
    reasoning: str
    actor: str  # agent_id or user_id
```

Audit entries are written best-effort (failures don't block the action pipeline).

---

## Performance Impact

The safety model adds latency to every action:

| Layer | Added Latency |
|-------|--------------|
| Policy evaluation (OPA) | ~50ms |
| Snapshot creation | ~100-500ms (depends on resource) |
| Health validation | Up to 300s (configurable timeout) |
| **Total overhead** | **~200ms** per action (excluding validation wait) |

Storage costs for snapshots are estimated at ~$0.50/customer/month.
