# ChatOps Agent

The ChatOps Agent processes natural language commands from Slack, Microsoft Teams,
PagerDuty, and webhook sources. It parses commands (slash or free-text), evaluates
OPA policies, routes to specialist agents, and delivers formatted responses back
to the originating channel.

---

## Purpose

- Accept slash commands and natural language from chat platforms
- Parse intent via deterministic matching or LLM-based NLP
- Evaluate OPA policy gates before executing any action
- Route to specialist agents (Investigation, Remediation, Security, Cost, Escalation)
- Format responses as Slack blocks or Teams adaptive cards
- Maintain thread context for follow-up command resolution
- Track per-user command history (capped at 100 per user)

---

## Graph Workflow

```
parse_command
      |
      v
validate_permissions
      |
      +-- [denied] -----------> format_denial_response --+
      |                                                   |
      +-- [approval needed] --> queue_for_approval -------+
      |                                                   |
      +-- [allowed] --> route_to_agent                    |
                             |                            |
                             v                            |
                       execute_action                     |
                             |                            |
                             +-- [failed] --> format_error_response --+
                             |                                        |
                             +-- [success] --> format_response -------+
                                                                      |
                                                                      v
                                                               deliver_response
                                                                      |
                                                                      v
                                                                     END
```

### Nodes

| Node | Description |
|------|-------------|
| `parse_command` | Deterministic slash parsing first; falls back to LLM NLP. Enriches with thread context for follow-ups. |
| `validate_permissions` | Evaluates OPA policy `chatops/command_auth`. Help/status bypass policy checks. |
| `route_to_agent` | Maps parsed intent to specialist agent via the agent registry. |
| `execute_action` | Invokes the matched agent runner or handles built-in intents (help). |
| `format_response` | Formats agent results into channel-appropriate blocks. Uses LLM for rich formatting when details are available. |
| `format_denial_response` | Formats a structured access-denied message. |
| `queue_for_approval` | Queues the command and notifies the user that approval is required. |
| `format_error_response` | Formats execution failure messages. |
| `deliver_response` | Sends the formatted payload to the originating channel via the notification dispatcher. Records bot reply in thread context. |

### Conditional Edges

- **After `validate_permissions`:** Routes to `route_to_agent` (allowed),
  `format_denial_response` (denied), or `queue_for_approval` (approval required).
- **After `execute_action`:** Routes to `format_response` (success) or
  `format_error_response` (failed).

---

## State Model

```python
class ChatOpsState(BaseModel):
    # Input
    command_id: str
    command_text: str
    channel: ChannelType          # slack, teams, pagerduty, webhook
    user_id: str
    user_name: str
    channel_id: str
    channel_name: str
    thread_id: str | None
    metadata: dict[str, Any]

    # Processing
    parsed_command: ParsedCommand  # intent, entity, parameters, confidence
    matched_agent: str             # agent registry key
    policy_evaluation: PolicyResult
    approval_status: ChatOpsApprovalStatus

    # Output
    response_text: str
    response_blocks: list[ResponseBlock]  # Slack blocks / Teams adaptive cards
    agent_result: dict[str, Any]
    execution_status: ChatOpsExecutionStatus

    # Metadata
    command_received_at: datetime | None
    processing_duration_ms: int
    reasoning_chain: list[ReasoningStep]
    current_step: str
    error: str | None
```

---

## Supported Commands

| Slash Command | Aliases | Intent | Routed Agent |
|---------------|---------|--------|--------------|
| `/investigate <service>` | `/inv` | `investigate` | Investigation Agent |
| `/remediate <service>` | `/fix`, `/restart`, `/scale`, `/rollback` | `remediate` | Remediation Agent |
| `/scan <target>` | `/security` | `scan` | Security Agent |
| `/cost <query>` | `/costs`, `/billing` | `cost_report` | Cost Agent |
| `/escalate [team]` | `/page` | `escalate` | Escalation Agent |
| `/status <id>` | | `status` | Status Agent |
| `/help` | | `help` | Built-in (no agent) |

Special handling for `/scale <service> <count>` extracts `replicas` parameter.
Commands like `/restart`, `/scale`, `/rollback` add `action_type` to parameters.

Natural language commands (e.g., "check why api-gateway is slow") are parsed via
LLM with `CommandParseResult` structured output.

---

## Channel Support

| Channel | Response Format | Context Footer |
|---------|----------------|----------------|
| Slack | `ResponseBlock` with `mrkdwn` elements | "Powered by ShieldOps ChatOps Agent" |
| Teams | `ResponseBlock` with `TextBlock` elements | "Powered by ShieldOps ChatOps Agent" |
| PagerDuty | Plain text fallback | None |
| Webhook | Plain text fallback | None |

---

## OPA Policy Gates

Every non-informational command is evaluated against the `chatops/command_auth` policy:

```json
{
  "action": "<intent>:<entity>",
  "user_id": "<user_id>",
  "channel": "<channel_id>"
}
```

Policy returns:
- `allowed: true` -- command executes immediately
- `allowed: false` -- command denied, user receives denial response
- `required_approval: true` -- command queued, approver notified

Help and status commands bypass policy evaluation entirely.

---

## Approval Workflows

When OPA returns `required_approval: true`:

1. Command state is stored in `_pending_approvals` with status `AWAITING_APPROVAL`
2. User receives a "pending approval" response in-channel
3. Approver calls `handle_approval(command_id, approved_by, approved=True|False)`
4. If approved: command re-processes through the full workflow with approval metadata
5. If denied: user receives denial response with approver identity

---

## Configuration

| Environment Variable | Description |
|---------------------|-------------|
| `OPA_ENDPOINT` | OPA policy engine URL for `chatops/command_auth` |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook for response delivery |
| `TEAMS_WEBHOOK_URL` | Teams incoming webhook for response delivery |
| `PAGERDUTY_API_KEY` | PagerDuty API key for escalation |

The runner requires injection of:
- `connector_router` -- ConnectorRouter for infrastructure access
- `notification_dispatcher` -- for sending responses to channels
- `policy_engine` -- OPA client for policy evaluation
- `agent_runners` -- dict mapping agent types to runner instances

---

## API Endpoints

### POST /api/v1/chatops/command

Process a chat command.

```bash
curl -X POST http://localhost:8000/api/v1/chatops/command \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "/investigate api-gateway",
    "channel": "slack",
    "user_id": "U12345",
    "user_name": "alice",
    "channel_id": "C67890",
    "channel_name": "incidents",
    "thread_id": "1234567890.123456"
  }'
```

### POST /api/v1/chatops/webhook/slack

Receive Slack slash command or interaction payload.

```bash
curl -X POST http://localhost:8000/api/v1/chatops/webhook/slack \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'command=/investigate&text=api-gateway&user_id=U12345&user_name=alice&channel_id=C67890&channel_name=incidents'
```

### POST /api/v1/chatops/webhook/teams

Receive Teams adaptive card action or bot message.

```bash
curl -X POST http://localhost:8000/api/v1/chatops/webhook/teams \
  -H "Authorization: Bearer $TEAMS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "message",
    "text": "/scan production-cluster",
    "from": {"id": "user-001", "name": "bob"},
    "channelId": "msteams",
    "conversation": {"id": "conv-123"}
  }'
```

### POST /api/v1/chatops/approve

Handle approval for a pending command.

```bash
curl -X POST http://localhost:8000/api/v1/chatops/approve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "command_id": "cmd-abc123def456",
    "approved_by": "U99999",
    "approved": true
  }'
```

### GET /api/v1/chatops/commands

List recent commands.

```bash
curl http://localhost:8000/api/v1/chatops/commands?user_id=U12345&limit=10 \
  -H "Authorization: Bearer $TOKEN"
```

---

## Integration with Other Agents

The ChatOps Agent acts as the human interface layer. It routes commands to specialist
agents via the `agent_runners` registry and formats their results for display.
Thread context is preserved across messages, allowing follow-up commands like
"what about the database?" to resolve entities from prior conversation.
