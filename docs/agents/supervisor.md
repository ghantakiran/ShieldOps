# Supervisor Agent

The Supervisor Agent orchestrates all specialist agents. It classifies incoming events,
dispatches them to the appropriate agent, evaluates results, and handles chaining and
escalation.

---

## Purpose

- Classify incoming events/alerts to determine which agent should handle them
- Dispatch work to the correct specialist agent (investigation, remediation, security, cost)
- Evaluate results and decide whether to chain follow-up actions
- Handle escalation when agents fail or produce low-confidence results
- Send notifications via configured channels (Slack, PagerDuty, email, webhook)

---

## Graph Workflow

```
classify_event
      |
      v
dispatch_to_agent
      |
      v
evaluate_result
      |
      +-- [error] --> finalize --> END
      |
      +-- [should chain] --> chain_followup
      |                           |
      |                     +-- [needs escalation] --> escalate --> finalize --> END
      |                     |
      |                     +-- [no escalation] --> finalize --> END
      |
      +-- [needs escalation] --> escalate --> finalize --> END
      |
      +-- [complete] --> finalize --> END
```

### Nodes

| Node | Description |
|------|-------------|
| `classify_event` | Determine event type and select the target agent |
| `dispatch_to_agent` | Execute the selected specialist agent's workflow |
| `evaluate_result` | Assess the agent result (success, confidence, errors) |
| `chain_followup` | Dispatch a follow-up action to another agent |
| `escalate` | Notify humans via configured notification channels |
| `finalize` | Write audit trail and clean up state |

---

## Event Classification

The supervisor classifies incoming events to determine routing:

| Event Type | Dispatched To |
|------------|--------------|
| Alert (high CPU, memory, latency) | Investigation Agent |
| Security alert (CVE, credential issue) | Security Agent |
| Cost anomaly | Cost Agent |
| Remediation request | Remediation Agent |
| Learning trigger | Learning Agent |

---

## Agent Chaining

The supervisor can chain agents together. For example:

1. **Alert fires** --> Supervisor dispatches to Investigation Agent
2. **Investigation completes** with high confidence --> Supervisor chains to Remediation Agent
3. **Remediation completes** --> Supervisor chains to Learning Agent for outcome recording

Chaining decisions are made in `evaluate_result` based on:

- Agent result status (success/failure)
- Confidence score (above threshold?)
- Whether a recommended action was produced

---

## Escalation

The supervisor escalates to humans when:

- An agent returns an error
- Investigation confidence is below the approval threshold (< 0.50)
- A remediation fails and rollback is needed
- All retry attempts are exhausted

Escalation notifications are sent via configured channels:

- **Slack** -- `SHIELDOPS_SLACK_BOT_TOKEN`
- **PagerDuty** -- `SHIELDOPS_PAGERDUTY_ROUTING_KEY`
- **Email** -- `SHIELDOPS_SMTP_HOST` + recipients
- **Webhook** -- `SHIELDOPS_WEBHOOK_URL`

---

## State Model

```python
class SupervisorState(BaseModel):
    event: dict                      # Incoming event data
    event_type: str | None          # Classified event type
    target_agent: str | None        # Selected agent
    agent_result: dict | None       # Result from dispatched agent
    should_chain: bool              # Whether to chain a follow-up
    chain_target: str | None        # Follow-up agent type
    needs_escalation: bool          # Whether to escalate to humans
    escalation_reason: str | None   # Why escalation is needed
    notifications_sent: list[str]   # Notification channel IDs
    error: str | None
```

---

## Runner Configuration

The supervisor runner is wired with all specialist agent runners at startup:

```python
sup_runner = SupervisorRunner(
    agent_runners={
        "investigation": inv_runner,
        "remediation": rem_runner,
        "security": sec_runner,
        "cost": cost_runner,
        "learning": learn_runner,
    },
    playbook_loader=playbook_loader,
    notification_channels=notification_channels,
)
```

---

## Kafka Integration

The supervisor receives alerts via the Kafka event bus. An `AlertEventHandler` consumes
messages from Kafka topics and routes them through the supervisor workflow:

```python
event_bus = EventBus(
    brokers=settings.kafka_brokers,
    group_id=settings.kafka_consumer_group,
)
alert_handler = AlertEventHandler(investigation_runner=inv_runner)
await event_bus.start()
asyncio.create_task(event_bus.consumer.consume(alert_handler.handle))
```

This enables real-time, event-driven incident response.
