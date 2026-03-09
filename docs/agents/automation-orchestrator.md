# Automation Orchestrator Agent

The Automation Orchestrator is an event-driven rules engine that matches incoming
events to automation rules, evaluates OPA policy gates, plans and executes action
chains through specialist agents, and summarizes results. It supports cooldown periods,
concurrency limits, and dry-run testing.

---

## Purpose

- Evaluate incoming events against enabled automation rules
- Perform deterministic trigger matching (type, source) with LLM-based condition expression evaluation
- Enforce cooldown periods and concurrency limits per rule
- Evaluate OPA policy gates before execution
- Use LLM to plan optimal action execution order and skip inappropriate actions
- Execute action chains sequentially with configurable failure handling
- Summarize execution results via LLM
- Notify relevant channels about execution outcomes
- Support dry-run testing of rules without executing actions

---

## Graph Workflow

```
evaluate_trigger
      |
      +-- [no match / cooldown / concurrency] --> END
      |
      +-- [matched] --> check_policy
                             |
                             +-- [denied] --> send_denial_notification --> END
                             |
                             +-- [approval needed] --> queue_for_approval --> END
                             |
                             +-- [allowed] --> plan_execution
                                                    |
                                                    +-- [plan rejects] --> send_notifications --> END
                                                    |
                                                    +-- [plan approves] --> execute_actions
                                                                                |
                                                                                v
                                                                       summarize_execution
                                                                                |
                                                                                v
                                                                       send_notifications --> END
```

### Nodes

| Node | Description |
|------|-------------|
| `evaluate_trigger` | Checks cooldown, concurrency, deterministic type/source match, then LLM evaluation of `condition_expression`. |
| `check_policy` | Evaluates the rule's `policy_gate` OPA policy with rule metadata and event data. |
| `plan_execution` | LLM plans action order, identifies actions to skip, and can reject execution entirely. |
| `execute_actions` | Runs actions sequentially. Halts on failure unless `continue_on_failure` is set. Tracks active execution count. |
| `summarize_execution` | LLM generates a human-readable summary of execution results. |
| `send_notifications` | Sends notifications for each `notify`-type action in the rule. |
| `send_denial_notification` | Sends denial notifications when policy blocks execution. |
| `queue_for_approval` | Queues execution for manual approval with status `awaiting_approval`. |

### Conditional Edges

- **After `evaluate_trigger`:** If trigger does not match, is in cooldown, or at
  concurrency limit, route to `END`. Otherwise, route to `check_policy`.
- **After `check_policy`:** If denied, route to `send_denial_notification`. If
  approval required, route to `queue_for_approval`. If allowed, route to `plan_execution`.
- **After `plan_execution`:** If LLM determines execution is inappropriate, route to
  `send_notifications`. Otherwise, route to `execute_actions`.

---

## State Model

```python
class AutomationState(BaseModel):
    # Input
    event: AutomationEvent      # id, rule_id, trigger_data, timestamp, source
    rule: AutomationRule        # id, name, trigger, actions, policy_gate, etc.

    # Processing
    policy_allowed: bool
    policy_reason: str
    requires_approval: bool
    approval_status: str        # pending, approved, denied, not_required
    current_action_index: int
    action_results: list[ActionResult]

    # Output
    execution_id: str
    overall_status: str         # completed, partial, failed, denied, awaiting_approval
    summary: str
    notifications_sent: list[str]

    # Metadata
    execution_start: datetime | None
    execution_duration_ms: int
    reasoning_chain: list[ReasoningStep]
    current_step: str
    error: str | None
```

---

## Trigger Types

| Type | Value | Description |
|------|-------|-------------|
| Alert | `alert` | Monitoring alerts from Prometheus, Datadog, PagerDuty |
| K8s Event | `k8s_event` | Kubernetes events (OOMKilled, CrashLoopBackOff, etc.) |
| Vulnerability Scan | `vulnerability_scan` | CVE scan results from security tools |
| Cost Alert | `cost_alert` | Budget threshold or cost anomaly alerts |
| SLO Alert | `slo_alert` | SLO burn rate or error budget exhaustion |
| Webhook | `webhook` | Generic webhook from external systems |
| Schedule | `schedule` | Cron-based scheduled triggers |
| Custom | `custom` | User-defined event types |

Each trigger has a `condition_expression` (e.g., `"severity = critical"`,
`"reason = OOMKilled, count > 3 in 10m"`) evaluated by the LLM when deterministic
matching passes.

---

## Action Types

| Type | Value | Execution Method |
|------|-------|------------------|
| Launch Agent | `launch_agent` | Routes to agent runner via registry |
| Investigate | `investigate` | Routes to agent runner |
| Analyze | `analyze` | Routes to agent runner |
| Benchmark | `benchmark` | Routes to agent runner |
| Notify | `notify` | Sends via notification dispatcher |
| Create Ticket | `create_ticket` | Creates Jira/ServiceNow ticket via connector |
| Remediate | `remediate` | Executes via connector router |
| Patch | `patch` | Executes via connector router |
| Scale | `scale` | Executes via connector router |
| Scan | `scan` | Executes via connector router |
| Tag | `tag` | Executes via connector router |
| Gate | `gate` | Evaluates OPA policy inline |
| Check | `check` | Evaluates OPA policy inline |

Each action step has `timeout_seconds` (default 300) and `continue_on_failure` (default false).

---

## Policy Gates

Rules can specify a `policy_gate` field referencing an OPA policy. The policy receives:

```json
{
  "rule_id": "<rule_id>",
  "rule_name": "<name>",
  "category": "<category>",
  "trigger_type": "<trigger_type>",
  "event_source": "<source>",
  "event_data": { ... },
  "actions": [{"type": "<type>", "target": "<target>"}, ...]
}
```

Policy returns `allow`, `reason`, and `requires_approval`. If no `policy_gate` is
configured, execution is allowed by default.

---

## Cooldown and Concurrency

| Control | Field | Description |
|---------|-------|-------------|
| Debounce | `trigger.debounce_seconds` | Minimum interval between trigger evaluations |
| Cooldown | `trigger.cooldown_seconds` | Minimum interval between executions (default 300s) |
| Max concurrent | `rule.max_concurrent` | Maximum parallel executions per rule (default 1) |

Cooldown is checked against `rule.last_triggered`. Concurrency is tracked via an
in-memory counter (`increment_active` / `decrement_active`) with try/finally cleanup.

---

## Rule Management

Rules are managed via the `AutomationRunner`:

| Operation | Method | Description |
|-----------|--------|-------------|
| Create | `create_rule(config)` | Validates and stores a new rule |
| Update | `update_rule(rule_id, updates)` | Merges updates into existing rule |
| Toggle | `toggle_rule(rule_id, enabled)` | Enable or disable a rule |
| Delete | `delete_rule(rule_id)` | Removes a rule |
| List | `list_rules(category, enabled_only)` | Lists rules with summary stats |
| Get | `get_rule(rule_id)` | Retrieves a single rule |

---

## API Endpoints

### POST /api/v1/automation/events

Process an incoming event against all enabled rules.

```bash
curl -X POST http://localhost:8000/api/v1/automation/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_data": {
      "type": "alert",
      "severity": "critical",
      "service": "api-gateway",
      "message": "High error rate detected"
    },
    "source": "PagerDuty"
  }'
```

### POST /api/v1/automation/rules/{rule_id}/execute

Execute a specific rule against an event.

```bash
curl -X POST http://localhost:8000/api/v1/automation/rules/rule-abc123/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_data": {
      "type": "alert",
      "severity": "critical",
      "source": "prometheus"
    }
  }'
```

### POST /api/v1/automation/rules/{rule_id}/test

Dry-run a rule without executing actions.

```bash
curl -X POST http://localhost:8000/api/v1/automation/rules/rule-abc123/test \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_data": {
      "type": "k8s_event",
      "reason": "OOMKilled",
      "pod": "web-server-01",
      "namespace": "production"
    }
  }'
```

### POST /api/v1/automation/rules

Create a new automation rule.

```bash
curl -X POST http://localhost:8000/api/v1/automation/rules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Critical Alert Auto-Investigation",
    "description": "Auto-investigate critical alerts from PagerDuty",
    "category": "incident_response",
    "trigger": {
      "type": "alert",
      "source": "PagerDuty",
      "condition_expression": "severity = critical",
      "cooldown_seconds": 600
    },
    "actions": [
      {"type": "launch_agent", "target": "Investigation Agent", "timeout_seconds": 300},
      {"type": "notify", "target": "Slack #incidents", "detail": "Investigation started"},
      {"type": "create_ticket", "target": "Jira", "parameters": {"project": "INC", "priority": "high"}}
    ],
    "policy_gate": "automation/critical_alert",
    "max_concurrent": 3
  }'
```

### PUT /api/v1/automation/rules/{rule_id}

Update an existing rule.

```bash
curl -X PUT http://localhost:8000/api/v1/automation/rules/rule-abc123 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

### DELETE /api/v1/automation/rules/{rule_id}

Delete an automation rule.

```bash
curl -X DELETE http://localhost:8000/api/v1/automation/rules/rule-abc123 \
  -H "Authorization: Bearer $TOKEN"
```

### GET /api/v1/automation/rules

List automation rules.

```bash
curl "http://localhost:8000/api/v1/automation/rules?category=incident_response&enabled_only=true" \
  -H "Authorization: Bearer $TOKEN"
```

### GET /api/v1/automation/executions

Get execution history.

```bash
curl "http://localhost:8000/api/v1/automation/executions?rule_id=rule-abc123&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Integration with Other Agents

The Automation Orchestrator acts as the event-driven backbone of ShieldOps. It
connects external event sources to specialist agents:

- Triggers the [Investigation Agent](investigation.md) for alert-based investigations
- Routes to the [Remediation Agent](remediation.md) for auto-remediation actions
- Invokes the [Security Agent](security.md) for vulnerability-triggered scans
- Creates tickets and sends notifications via the
  [Enterprise Integration Agent](enterprise-integration.md)
- Can be triggered from the [ChatOps Agent](chatops.md) via manual rule execution
