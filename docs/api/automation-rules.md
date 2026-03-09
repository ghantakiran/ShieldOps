# Automation Rules API

The Automation Rules API provides endpoints for creating, managing, and executing
event-driven automation rules. Rules define conditions matched against incoming
events and actions executed by the LangGraph-based Automation Orchestrator agent.
All actions are evaluated against OPA policies before execution.

---

## Endpoints

### Process Incoming Event

```
POST /api/v1/automation/events
```

Submit an event for evaluation against all enabled automation rules. The event
is matched against rule conditions in priority order, and matched rules execute
their configured actions. Returns results for all rules that matched.

**Required role:** any authenticated user

**Request body:**

```json
{
  "event_type": "alert.fired",
  "source": "prometheus",
  "severity": "critical",
  "resource_id": "pod/web-server-01",
  "labels": {
    "namespace": "production",
    "team": "platform"
  },
  "payload": {
    "metric": "cpu_usage_percent",
    "value": 97.2,
    "threshold": 90
  },
  "timestamp": "2026-03-08T14:30:00Z"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_type` | string | yes | Event type (e.g., `alert.fired`, `deploy.failed`, `security.cve_found`) |
| `source` | string | yes | Event source system (e.g., `prometheus`, `github`, `pagerduty`) |
| `severity` | string | no | Severity level (default: `info`) |
| `resource_id` | string | no | Affected resource identifier |
| `labels` | object | no | Key-value labels for matching |
| `payload` | object | no | Full event payload for condition evaluation |
| `timestamp` | string | no | Event timestamp in ISO 8601 (defaults to server time) |

**Response (200):**

```json
[
  {
    "execution_id": "exec-a1b2c3",
    "rule_id": "rule-highcpu-restart",
    "status": "completed",
    "matched": true,
    "actions_executed": 2,
    "duration_ms": 1450,
    "output": {
      "summary": "Restarted pod/web-server-01, notified #incidents channel"
    },
    "error": null
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `execution_id` | string | Unique execution identifier |
| `rule_id` | string | ID of the matched rule |
| `status` | string | Execution status: `completed`, `failed`, `denied` |
| `matched` | bool | Whether the rule conditions matched |
| `actions_executed` | int | Number of actions executed |
| `duration_ms` | int | Execution time in milliseconds |
| `output` | object | Execution output with summary |
| `error` | string | Error message (nullable) |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/automation/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "alert.fired",
    "source": "prometheus",
    "severity": "critical",
    "resource_id": "pod/web-server-01",
    "payload": {"metric": "cpu_usage_percent", "value": 97.2}
  }'
```

---

### Execute Rule Manually

```
POST /api/v1/automation/rules/{rule_id}/execute
```

Execute a specific rule manually, bypassing condition evaluation. Useful for
testing rules and manual intervention scenarios. Actions are still subject to
OPA policy evaluation.

**Required role:** `admin` or `operator`

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `rule_id` | string | Unique rule identifier |

**Response (200):**

```json
{
  "execution_id": "exec-d4e5f6",
  "rule_id": "rule-highcpu-restart",
  "status": "completed",
  "matched": true,
  "actions_executed": 2,
  "duration_ms": 1200,
  "output": {
    "summary": "Rule executed manually. 2 actions completed."
  },
  "error": null
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 404 | Rule not found |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/automation/rules/rule-highcpu-restart/execute \
  -H "Authorization: Bearer $TOKEN"
```

---

### Dry-Run Test Rule

```
POST /api/v1/automation/rules/{rule_id}/test
```

Dry-run test a rule against a sample event. Evaluates conditions and simulates
actions without actually executing them. Returns what would happen if the event
were real.

**Required role:** `admin` or `operator`

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `rule_id` | string | Unique rule identifier |

**Request body:** Same as the `EventPayload` schema used in `POST /events`.

```json
{
  "event_type": "alert.fired",
  "source": "prometheus",
  "severity": "critical",
  "resource_id": "pod/web-server-01",
  "labels": {"namespace": "production"},
  "payload": {"metric": "cpu_usage_percent", "value": 97.2}
}
```

**Response (200):**

```json
{
  "execution_id": "test-g7h8i9",
  "rule_id": "rule-highcpu-restart",
  "status": "completed",
  "matched": true,
  "actions_executed": 2,
  "duration_ms": 50,
  "output": {
    "summary": "DRY RUN: Conditions matched. Would execute: restart_pod, notify_channel"
  },
  "error": null
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 404 | Rule not found |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/automation/rules/rule-highcpu-restart/test \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "alert.fired",
    "source": "prometheus",
    "severity": "critical",
    "payload": {"metric": "cpu_usage_percent", "value": 97.2}
  }'
```

---

### Create Rule

```
POST /api/v1/automation/rules
```

Create a new automation rule. The rule is immediately active if `enabled` is
`true` (the default).

**Required role:** `admin` or `operator`

**Request body:**

```json
{
  "name": "High CPU Auto-Restart",
  "description": "Restart pods when CPU exceeds 95% for production workloads",
  "category": "incident",
  "enabled": true,
  "conditions": {
    "event_type": "alert.fired",
    "severity": {"$in": ["critical", "warning"]},
    "labels.namespace": "production",
    "payload.metric": "cpu_usage_percent",
    "payload.value": {"$gt": 95}
  },
  "actions": [
    {
      "type": "restart_pod",
      "target": "{{resource_id}}",
      "params": {"grace_period_seconds": 30}
    },
    {
      "type": "notify",
      "channel": "slack",
      "target": "#incidents",
      "message": "Auto-restarted {{resource_id}} due to high CPU"
    }
  ],
  "cooldown_seconds": 300,
  "priority": 10,
  "metadata": {
    "owner": "platform-team",
    "runbook": "https://wiki.example.com/runbooks/high-cpu"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Human-readable rule name |
| `description` | string | no | Rule description (default: empty) |
| `category` | string | no | Category: `incident`, `security`, `cost`, `compliance`, `general` (default: `general`) |
| `enabled` | bool | no | Whether the rule is active (default: `true`) |
| `conditions` | object | yes | Condition expression evaluated against incoming events |
| `actions` | array | yes | Actions to execute when conditions match |
| `cooldown_seconds` | int | no | Minimum seconds between rule executions, 0-86400 (default: `300`) |
| `priority` | int | no | Rule priority, 1-1000, lower = higher priority (default: `100`) |
| `metadata` | object | no | Arbitrary metadata |

**Response (201):**

```json
{
  "id": "rule-a1b2c3d4",
  "name": "High CPU Auto-Restart",
  "description": "Restart pods when CPU exceeds 95% for production workloads",
  "category": "incident",
  "enabled": true,
  "conditions": { "..." : "..." },
  "actions": [ "..." ],
  "cooldown_seconds": 300,
  "priority": 10,
  "metadata": {},
  "created_at": "2026-03-08T14:30:00Z"
}
```

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/automation/rules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High CPU Auto-Restart",
    "category": "incident",
    "conditions": {
      "event_type": "alert.fired",
      "payload.value": {"$gt": 95}
    },
    "actions": [
      {"type": "restart_pod", "target": "{{resource_id}}"}
    ]
  }'
```

---

### Update Rule

```
PUT /api/v1/automation/rules/{rule_id}
```

Update an existing automation rule. Only non-null fields in the request body
are updated; omitted fields retain their current values.

**Required role:** `admin` or `operator`

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `rule_id` | string | Unique rule identifier |

**Request body:**

```json
{
  "name": "High CPU Auto-Restart (v2)",
  "cooldown_seconds": 600,
  "priority": 5
}
```

All fields from `CreateRuleRequest` are accepted, all optional. At least one
field must be provided.

**Response (200):** Full updated rule object.

**Errors:**

| Status | Description |
|--------|-------------|
| 400 | No fields to update |
| 404 | Rule not found |

**Example:**

```bash
curl -X PUT http://localhost:8000/api/v1/automation/rules/rule-a1b2c3d4 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cooldown_seconds": 600, "priority": 5}'
```

---

### Enable / Disable Rule

```
PATCH /api/v1/automation/rules/{rule_id}/toggle
```

Enable or disable an automation rule. A disabled rule will not match any
incoming events until re-enabled.

**Required role:** `admin` or `operator`

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `rule_id` | string | Unique rule identifier |

**Request body:**

```json
{
  "enabled": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | bool | yes | `true` to enable, `false` to disable |

**Response (200):**

```json
{
  "rule_id": "rule-a1b2c3d4",
  "status": "disabled"
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 404 | Rule not found |

**Example:**

```bash
curl -X PATCH http://localhost:8000/api/v1/automation/rules/rule-a1b2c3d4/toggle \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

---

### Delete Rule

```
DELETE /api/v1/automation/rules/{rule_id}
```

Permanently delete an automation rule. This action cannot be undone.

**Required role:** `admin`

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `rule_id` | string | Unique rule identifier |

**Response:** 204 No Content

**Errors:**

| Status | Description |
|--------|-------------|
| 404 | Rule not found |

**Example:**

```bash
curl -X DELETE http://localhost:8000/api/v1/automation/rules/rule-a1b2c3d4 \
  -H "Authorization: Bearer $TOKEN"
```

---

### List Rules

```
GET /api/v1/automation/rules
```

List automation rules with optional filtering and pagination.

**Required role:** any authenticated user

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `category` | string | (all) | Filter by rule category |
| `enabled` | bool | (all) | Filter by enabled status |
| `limit` | int | 50 | Page size (1-200) |
| `offset` | int | 0 | Page offset |

**Response (200):**

```json
[
  {
    "rule_id": "rule-a1b2c3d4",
    "name": "High CPU Auto-Restart",
    "category": "incident",
    "enabled": true,
    "priority": 10,
    "last_triggered_at": "2026-03-08T14:15:00Z",
    "total_executions": 47,
    "error": null
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `rule_id` | string | Rule identifier |
| `name` | string | Rule display name |
| `category` | string | Rule category |
| `enabled` | bool | Whether the rule is active |
| `priority` | int | Rule priority (lower = higher) |
| `last_triggered_at` | string | ISO 8601 timestamp of last trigger (nullable) |
| `total_executions` | int | Total number of executions |
| `error` | string | Current error state (nullable) |

**Example:**

```bash
curl "http://localhost:8000/api/v1/automation/rules?category=incident&enabled=true&limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

---

### Get Rule Details

```
GET /api/v1/automation/rules/{rule_id}
```

Get full rule details including conditions, actions, metadata, and
configuration.

**Required role:** any authenticated user

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `rule_id` | string | Unique rule identifier |

**Response (200):** Full rule object (same schema as `POST /rules` response).

**Errors:**

| Status | Description |
|--------|-------------|
| 404 | Rule not found |

**Example:**

```bash
curl http://localhost:8000/api/v1/automation/rules/rule-a1b2c3d4 \
  -H "Authorization: Bearer $TOKEN"
```

---

### Execution History

```
GET /api/v1/automation/rules/{rule_id}/history
```

Get execution history for a specific rule. Returns a chronological list of
executions with match results, action counts, and any errors encountered.

**Required role:** any authenticated user

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `rule_id` | string | Unique rule identifier |

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Number of entries to return (1-100) |

**Response (200):**

```json
[
  {
    "execution_id": "exec-a1b2c3",
    "rule_id": "rule-highcpu-restart",
    "event_type": "alert.fired",
    "status": "completed",
    "matched": true,
    "actions_executed": 2,
    "duration_ms": 1450,
    "triggered_at": "2026-03-08T14:15:00Z",
    "completed_at": "2026-03-08T14:15:01Z",
    "error": null
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `execution_id` | string | Execution identifier |
| `rule_id` | string | Rule identifier |
| `event_type` | string | Event type that triggered the execution |
| `status` | string | Execution status |
| `matched` | bool | Whether conditions matched |
| `actions_executed` | int | Number of actions executed |
| `duration_ms` | int | Execution time in milliseconds |
| `triggered_at` | string | ISO 8601 timestamp of trigger |
| `completed_at` | string | ISO 8601 timestamp of completion (nullable) |
| `error` | string | Error message (nullable) |

**Example:**

```bash
curl "http://localhost:8000/api/v1/automation/rules/rule-highcpu-restart/history?limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Authentication

All endpoints require JWT authentication via the `Authorization: Bearer <token>`
header.

Write operations (create, update, toggle, execute, test) require `admin` or
`operator` role. Delete requires `admin` role. Read operations (list, get,
history) are available to any authenticated user.

## Rate Limiting

All endpoints are subject to the platform-wide rate limits configured in the
API gateway.
