# ChatOps API

The ChatOps API provides endpoints for processing natural language commands from
enterprise communication tools (Slack, Microsoft Teams, PagerDuty) and managing
approval workflows for high-risk operations.

---

## Endpoints

### Process Command

```
POST /api/v1/chatops/command
```

Submit a ChatOps command for processing by the LangGraph-based ChatOps agent.
The agent parses the command, evaluates OPA policies, and executes the
appropriate action. Returns immediately with a 202 status while processing
continues asynchronously.

**Required role:** any authenticated user

**Request body:**

```json
{
  "command": "/investigate api-gateway",
  "channel": "slack",
  "user_id": "U12345",
  "user_name": "jane.ops",
  "channel_id": "C-incidents",
  "channel_name": "incidents",
  "thread_id": "1234567890.123456",
  "metadata": {}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | string | yes | The command text (e.g., `/investigate api-gateway`) |
| `channel` | string | no | Channel type: `slack`, `teams`, `pagerduty`, `webhook` (default: `slack`) |
| `user_id` | string | no | User identifier from the source platform (default: `api-user`) |
| `user_name` | string | no | Human-readable user name (default: `API User`) |
| `channel_id` | string | no | Channel identifier from the source platform (default: `api`) |
| `channel_name` | string | no | Channel name (default: `api-channel`) |
| `thread_id` | string | no | Thread identifier for threaded replies |
| `metadata` | object | no | Arbitrary key-value metadata passed to the agent |

**Response (202):**

```json
{
  "command_id": "cmd-a1b2c3d4",
  "status": "completed",
  "response_text": "Investigation started for api-gateway. Root cause: memory leak in pod/api-gateway-7b...",
  "execution_status": "success",
  "agent_result": {
    "action": "investigate",
    "target": "api-gateway",
    "findings": []
  },
  "processing_duration_ms": 3200
}
```

| Field | Type | Description |
|-------|------|-------------|
| `command_id` | string | Unique identifier for this command execution |
| `status` | string | Current processing step |
| `response_text` | string | Human-readable response formatted for the source channel |
| `execution_status` | string | Execution outcome: `success`, `failed`, `pending_approval`, `denied` |
| `agent_result` | object | Structured result from the agent (nullable) |
| `processing_duration_ms` | int | Total processing time in milliseconds |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/chatops/command \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "/investigate high-cpu web-server-01",
    "channel": "slack",
    "user_id": "U12345",
    "user_name": "jane.ops"
  }'
```

---

### Slack Webhook

```
POST /api/v1/chatops/webhook/slack
```

Handle incoming Slack Events API payloads and slash command invocations.
Supports Slack URL verification challenges, slash commands, and `@shieldops`
mentions in messages. Commands are processed asynchronously in background tasks.

**Authentication:** Slack request signing (no JWT required)

**Request body (slash command):**

```json
{
  "command": "/shieldops",
  "text": "investigate api-gateway",
  "user_id": "U12345",
  "user_name": "jane.ops",
  "channel_id": "C-incidents",
  "channel_name": "incidents",
  "response_url": "https://hooks.slack.com/commands/...",
  "trigger_id": "123456.789"
}
```

**Request body (URL verification):**

```json
{
  "type": "url_verification",
  "challenge": "abc123xyz",
  "token": "verification-token"
}
```

**Request body (event message):**

```json
{
  "type": "event_callback",
  "event": {
    "type": "message",
    "text": "@shieldops investigate api-gateway",
    "user": "U12345",
    "channel": "C-incidents",
    "thread_ts": "1234567890.123456"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | no | Payload type: `url_verification`, `event_callback` |
| `token` | string | no | Slack verification token |
| `challenge` | string | no | Challenge string for URL verification |
| `event` | object | no | Event payload (for event callbacks) |
| `command` | string | no | Slash command name |
| `text` | string | no | Command arguments text |
| `user_id` | string | no | Slack user ID |
| `user_name` | string | no | Slack username |
| `channel_id` | string | no | Slack channel ID |
| `channel_name` | string | no | Slack channel name |
| `response_url` | string | no | URL for delayed responses |
| `trigger_id` | string | no | Trigger ID for interactive messages |

**Response (200 - slash command):**

```json
{
  "response_type": "ephemeral",
  "text": "Processing your command..."
}
```

**Response (200 - URL verification):**

```json
{
  "challenge": "abc123xyz"
}
```

**Response (200 - event):**

```json
{
  "ok": true
}
```

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/chatops/webhook/slack \
  -H "Content-Type: application/json" \
  -d '{
    "command": "/shieldops",
    "text": "status web-server-01",
    "user_id": "U12345",
    "user_name": "jane.ops",
    "channel_id": "C-incidents",
    "channel_name": "incidents"
  }'
```

---

### Teams Webhook

```
POST /api/v1/chatops/webhook/teams
```

Handle incoming Microsoft Teams Bot Framework webhook payloads. Commands are
processed asynchronously in background tasks.

**Authentication:** Teams Bot Framework validation (no JWT required)

**Request body:**

```json
{
  "type": "message",
  "text": "investigate api-gateway",
  "from": {
    "id": "user-abc123",
    "name": "Jane Ops"
  },
  "conversation": {
    "id": "conv-xyz789",
    "name": "incidents-channel"
  },
  "channelData": {
    "tenant": { "id": "tenant-001" }
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | no | Message type |
| `text` | string | no | Message text containing the command |
| `from` | object | no | Sender information (`id`, `name`) |
| `conversation` | object | no | Conversation details (`id`, `name`) |
| `channelData` | object | no | Teams-specific channel metadata |

**Response (200):**

```json
{
  "type": "message",
  "text": "Processing your command..."
}
```

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/chatops/webhook/teams \
  -H "Content-Type: application/json" \
  -d '{
    "type": "message",
    "text": "investigate api-gateway",
    "from": { "id": "user-abc", "name": "Jane Ops" },
    "conversation": { "id": "conv-xyz", "name": "incidents" }
  }'
```

---

### Approve / Deny Command

```
POST /api/v1/chatops/approve
```

Approve or deny a command that is pending approval. Commands requiring approval
are determined by OPA policy evaluation (e.g., destructive actions, production
changes).

**Required role:** `admin` or `operator`

**Request body:**

```json
{
  "command_id": "cmd-a1b2c3d4",
  "approved": true,
  "approved_by": "admin-user-01"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command_id` | string | yes | ID of the command to approve/deny |
| `approved` | bool | yes | `true` to approve, `false` to deny |
| `approved_by` | string | yes | Identifier of the approving user |

**Response (200):**

```json
{
  "status": "approved",
  "command_id": "cmd-a1b2c3d4"
}
```

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/chatops/approve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "command_id": "cmd-a1b2c3d4",
    "approved": true,
    "approved_by": "admin-user-01"
  }'
```

---

### List Recent Commands

```
GET /api/v1/chatops/commands
```

List recent ChatOps commands with optional filtering by user.

**Required role:** any authenticated user

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | string | (current user) | Filter by user ID |
| `limit` | int | 20 | Page size (1-100) |

**Response (200):**

```json
[
  {
    "command_id": "cmd-a1b2c3d4",
    "command": "/investigate api-gateway",
    "channel": "slack",
    "user_id": "U12345",
    "status": "completed",
    "execution_status": "success",
    "created_at": "2026-03-08T14:30:00Z"
  }
]
```

**Example:**

```bash
curl http://localhost:8000/api/v1/chatops/commands?limit=10 \
  -H "Authorization: Bearer $TOKEN"
```

---

### Get Command Details

```
GET /api/v1/chatops/commands/{command_id}
```

Get full details of a specific command execution including agent result,
response text, and processing metadata.

**Required role:** any authenticated user

**Response (200):**

```json
{
  "command_id": "cmd-a1b2c3d4",
  "command": "/investigate api-gateway",
  "channel": "slack",
  "user_id": "U12345",
  "user_name": "jane.ops",
  "status": "completed",
  "response_text": "Investigation complete. Root cause identified...",
  "execution_status": "success",
  "agent_result": {
    "action": "investigate",
    "target": "api-gateway",
    "confidence": 0.91
  },
  "processing_duration_ms": 3200,
  "created_at": "2026-03-08T14:30:00Z"
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 404 | Command not found |

**Example:**

```bash
curl http://localhost:8000/api/v1/chatops/commands/cmd-a1b2c3d4 \
  -H "Authorization: Bearer $TOKEN"
```

---

## Authentication

All endpoints except the webhook handlers require JWT authentication via the
`Authorization: Bearer <token>` header. Webhook endpoints use platform-specific
verification (Slack request signing, Teams Bot Framework tokens).

The `/approve` endpoint requires `admin` or `operator` role.

## Rate Limiting

All endpoints are subject to the platform-wide rate limits configured in the
API gateway. Webhook endpoints have separate rate limits to handle burst traffic
from Slack and Teams.
