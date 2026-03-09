# ADR-004: Enterprise ChatOps & Automation Architecture

**Status:** Accepted
**Date:** 2026-03-08
**Decision Makers:** Founding Team

## Context

Enterprise SRE teams interact with infrastructure through multiple communication channels
(Slack, Microsoft Teams, PagerDuty) and need to trigger investigations, remediations, and
status checks without leaving their existing workflows. Additionally, recurring operational
patterns (e.g., auto-restart on high CPU, notify on deploy failure) should be codified as
automation rules that execute without human intervention while remaining subject to safety
policies.

Key requirements:
- Natural language command processing from Slack, Teams, and PagerDuty
- Bi-directional communication: receive commands, send formatted responses back to channels
- Approval workflows for high-risk operations (production changes, destructive actions)
- Event-driven automation with configurable trigger/condition/action patterns
- Enterprise integration health monitoring and self-healing
- All actions must pass OPA policy evaluation before execution
- Audit trail for every command and automated action

## Options Considered

### Option 1: Three Specialized LangGraph Agents (Selected)

Deploy three LangGraph-based agents, each handling a distinct domain:

1. **ChatOps Agent** -- Parses natural language commands, routes to specialist agents
   (investigation, remediation, security), formats channel-specific responses
2. **Enterprise Integration Agent** -- Manages external system connectors (SIEM, ITSM, CI/CD),
   runs health checks, diagnostics, syncing, and configuration
3. **Automation Orchestrator Agent** -- Evaluates incoming events against rules, executes
   matched actions, tracks execution history and cooldowns

Each agent follows the established LangGraph StateGraph pattern with OPA policy gates.

### Option 2: Direct API Integration Without Agents

Build channel-specific webhook handlers that map commands directly to API calls without
LLM-based parsing. Simpler architecture but loses natural language understanding, requires
rigid command syntax, and cannot adapt to ambiguous or novel commands.

### Option 3: Separate Command Processors Per Channel

Build independent Slack bot, Teams bot, and PagerDuty integration services, each with their
own command parsing and execution logic. Maximizes channel-specific features but duplicates
core logic, creates maintenance burden, and makes policy enforcement inconsistent.

### Option 4: Single Monolithic Agent

Combine ChatOps, integration management, and automation into one large agent graph. Simpler
deployment but creates a complex state schema, makes testing difficult, and violates the
single-responsibility principle established across the platform.

## Decision

**Option 1: Three Specialized LangGraph Agents** for the following reasons:

1. **Consistency with Platform Architecture:** All ShieldOps agents use LangGraph StateGraph
   (ADR-001). Using the same pattern for ChatOps, integrations, and automation maintains
   architectural consistency and allows the team to reuse orchestration infrastructure
   (tracing, checkpointing, error recovery).

2. **Channel-Agnostic Command Parsing:** The ChatOps agent parses commands into a
   channel-independent intermediate representation, then formats responses for the target
   channel. This separates parsing logic from channel-specific webhook handling:
   - Slack: Block Kit formatting, threaded replies, ephemeral messages
   - Teams: Adaptive Cards, Bot Framework responses
   - PagerDuty: Incident notes, status updates

3. **OPA Policy Gates on All Actions:** Every command and automation action passes through
   OPA policy evaluation before execution. High-risk operations (production restarts,
   security changes, IAM modifications) require explicit approval through the approval
   workflow. This is consistent with the defense-in-depth model (ADR-003).

4. **Event-Driven Automation with Safety Controls:** The Automation Orchestrator evaluates
   events against rules with configurable conditions, cooldown periods, and priority ordering.
   Rules support dry-run testing before activation. All automated actions are subject to the
   same OPA policies as manual commands.

5. **Approval Workflows for High-Risk Operations:** Commands classified as high-risk by OPA
   policy enter a pending state. Designated approvers (admin/operator role) can approve or
   deny through the API or directly in Slack/Teams. This prevents accidental production
   changes from chat commands.

6. **Enterprise Integration Health Management:** The Integration agent proactively monitors
   connector health, runs diagnostics, and provides remediation recommendations. This reduces
   the operational burden of maintaining connections to external systems (Splunk, Jira,
   ServiceNow, etc.).

## Detailed Design

### ChatOps Agent Graph

```
parse_command -> classify_intent -> check_policy -> [route_to_agent | request_approval | deny]
                                                         |
                                                    execute_action -> format_response -> deliver
```

- **parse_command**: LLM-based natural language parsing into structured command
- **classify_intent**: Map to agent type (investigate, remediate, status, help)
- **check_policy**: OPA evaluation for permission and risk level
- **route_to_agent**: Delegate to the appropriate specialist agent
- **format_response**: Channel-specific output formatting

### Automation Orchestrator Graph

```
receive_event -> match_rules -> evaluate_conditions -> check_policy -> execute_actions -> record_result
                      |                                      |
                 [no match]                             [denied]
                      |                                      |
                 skip_event                           log_denial
```

- **match_rules**: Priority-ordered rule matching against event
- **evaluate_conditions**: Expression evaluation against event payload
- **check_policy**: OPA gate on each action
- **execute_actions**: Run matched actions with cooldown enforcement

### API Surface

Three FastAPI routers expose the agents:

| Router | Prefix | Endpoints |
|--------|--------|-----------|
| ChatOps | `/api/v1/chatops` | command, webhooks (Slack/Teams), approve, list/get commands |
| Integrations | `/api/v1/integrations` | check, diagnose, sync, config, list, health, runs |
| Automation | `/api/v1/automation` | events, rules CRUD, execute, test, history |

### Webhook Architecture

```
Slack/Teams -> Webhook Endpoint -> Background Task -> Agent Processing -> Response Delivery
                    |
              Immediate ACK (200)
```

Webhooks return immediately with an acknowledgment to satisfy platform timeout requirements
(Slack: 3 seconds, Teams: 15 seconds). Actual processing happens in FastAPI background tasks.
Responses are delivered back via platform APIs (Slack `response_url`, Teams Bot Framework).

## Trade-offs Accepted

- **LLM Latency on Command Parsing:** Natural language parsing adds 500-2000ms latency
  compared to rigid command syntax. Mitigated by returning immediate acknowledgments and
  processing asynchronously.
- **Webhook Complexity:** Supporting multiple webhook formats (Slack Events API, Slack slash
  commands, Teams Bot Framework) requires platform-specific payload handling. Mitigated by
  isolating webhook parsing in thin route handlers and delegating to channel-agnostic agents.
- **Three Agents Instead of One:** Increases deployment complexity with three agent instances.
  Mitigated by shared infrastructure (same LangGraph runtime, same OPA client, same tracing).
- **Cooldown State Management:** Automation rule cooldowns require distributed state tracking
  to prevent duplicate executions across replicas. Mitigated by Redis-based cooldown tracking.

## Consequences

- All ChatOps commands are auditable via the commands API and immutable audit log
- New communication channels can be added by implementing a webhook handler and response
  formatter without modifying agent logic
- Automation rules can be tested with dry-runs before activation in production
- OPA policies govern both interactive commands and automated actions uniformly
- Enterprise integrations are self-monitoring with proactive health checks
- Team must maintain webhook handlers for each supported platform (Slack, Teams, PagerDuty)
- LangSmith tracing covers all ChatOps and automation agent executions

## References

- ADR-001: LangGraph as Agent Orchestration Framework
- ADR-003: Defense-in-Depth Safety Model
- Slack Events API: https://api.slack.com/events-api
- Teams Bot Framework: https://learn.microsoft.com/en-us/azure/bot-service/
- OPA documentation: https://www.openpolicyagent.org/docs/
