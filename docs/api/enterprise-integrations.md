# Enterprise Integrations API

The Enterprise Integrations API provides endpoints for managing, monitoring, and
diagnosing integration connectors to external enterprise systems (SIEM, ITSM,
CI/CD, cloud providers). Each integration is backed by a LangGraph-based
Enterprise Integration agent that handles health checks, diagnostics, syncing,
and configuration.

---

## Endpoints

### Run Health Check

```
POST /api/v1/integrations/check/{integration_id}
```

Run an active health check on a specific integration. The agent connects to
the external system, verifies authentication, and measures response latency.

**Required role:** `admin` or `operator`

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `integration_id` | string | Unique integration identifier (e.g., `splunk-prod`, `jira-cloud`) |

**Response (200):**

```json
{
  "integration_id": "splunk-prod",
  "healthy": true,
  "status": "connected",
  "latency_ms": 142,
  "checked_at": "2026-03-08T14:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `integration_id` | string | Integration identifier |
| `healthy` | bool | `true` if status is `connected` |
| `status` | string | Connection status: `connected`, `degraded`, `disconnected`, `unknown` |
| `latency_ms` | int | Round-trip latency in milliseconds |
| `checked_at` | string | ISO 8601 timestamp of the check |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/integrations/check/splunk-prod \
  -H "Authorization: Bearer $TOKEN"
```

---

### Run Full Diagnostic

```
POST /api/v1/integrations/diagnose/{integration_id}
```

Run a full diagnostic on an integration. The agent performs connectivity tests,
validates credentials, checks API version compatibility, and generates
recommendations for fixing any issues found.

**Required role:** `admin` or `operator`

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `integration_id` | string | Unique integration identifier |

**Response (200):**

```json
{
  "integration_id": "jira-cloud",
  "diagnosis": {
    "diagnostics": [
      {
        "check": "connectivity",
        "status": "pass",
        "message": "Successfully connected to Jira API"
      },
      {
        "check": "authentication",
        "status": "pass",
        "message": "API token valid, expires in 45 days"
      },
      {
        "check": "permissions",
        "status": "warning",
        "message": "Missing 'manage_sprints' scope"
      }
    ],
    "recommendations": [
      "Add 'manage_sprints' scope to the Jira API token for full functionality"
    ],
    "error": null
  },
  "diagnosed_at": "2026-03-08T14:32:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `integration_id` | string | Integration identifier |
| `diagnosis.diagnostics` | array | List of diagnostic check results |
| `diagnosis.recommendations` | array | Agent-generated recommendations |
| `diagnosis.error` | string | Top-level error message (nullable) |
| `diagnosed_at` | string | ISO 8601 timestamp |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/integrations/diagnose/jira-cloud \
  -H "Authorization: Bearer $TOKEN"
```

---

### Trigger Sync

```
POST /api/v1/integrations/sync/{integration_id}
```

Trigger a manual sync for an integration. The sync runs asynchronously in the
background. Use the health and runs endpoints to monitor progress.

**Required role:** `admin` or `operator`

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `integration_id` | string | Unique integration identifier |

**Request body:**

```json
{
  "full_sync": false,
  "resources": ["incidents", "alerts"],
  "metadata": {}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `full_sync` | bool | no | If `true`, perform a full sync instead of incremental (default: `false`) |
| `resources` | array | no | Specific resource types to sync (empty = all) |
| `metadata` | object | no | Arbitrary metadata passed to the sync agent |

**Response (202):**

```json
{
  "status": "accepted",
  "integration_id": "splunk-prod",
  "full_sync": false,
  "message": "Sync started for splunk-prod."
}
```

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/integrations/sync/splunk-prod \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_sync": true,
    "resources": ["alerts"]
  }'
```

---

### Update Configuration

```
PUT /api/v1/integrations/{integration_id}/config
```

Update an integration's configuration. Supports changing display name, enabled
state, connection parameters, credentials reference, and sync interval.

**Required role:** `admin`

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `integration_id` | string | Unique integration identifier |

**Request body:**

```json
{
  "name": "Splunk Production",
  "enabled": true,
  "config": {
    "base_url": "https://splunk.corp.example.com:8089",
    "index": "main",
    "verify_ssl": true
  },
  "credentials_ref": "vault://secret/integrations/splunk-prod",
  "sync_interval_seconds": 300
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | no | Display name for the integration |
| `enabled` | bool | no | Whether the integration is active |
| `config` | object | no | Configuration key-value pairs to merge into existing config |
| `credentials_ref` | string | no | Secret manager reference for credentials (e.g., Vault path) |
| `sync_interval_seconds` | int | no | Sync interval in seconds (60-86400) |

**Response (200):**

```json
{
  "integration_id": "splunk-prod",
  "updated": true,
  "result": {
    "name": "Splunk Production",
    "enabled": true,
    "sync_interval_seconds": 300
  }
}
```

**Example:**

```bash
curl -X PUT http://localhost:8000/api/v1/integrations/splunk-prod/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "sync_interval_seconds": 600
  }'
```

---

### List Integrations

```
GET /api/v1/integrations/
```

List all configured integrations with their current status.

**Required role:** any authenticated user

**Response (200):**

```json
[
  {
    "integration_id": "splunk-prod",
    "status": "connected",
    "last_action": "sync",
    "error": null
  },
  {
    "integration_id": "jira-cloud",
    "status": "degraded",
    "last_action": "health_check",
    "error": "API rate limit exceeded"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `integration_id` | string | Integration identifier |
| `status` | string | Current status: `connected`, `degraded`, `disconnected`, `unknown` |
| `last_action` | string | Last action performed (nullable) |
| `error` | string | Current error message (nullable) |

**Example:**

```bash
curl http://localhost:8000/api/v1/integrations/ \
  -H "Authorization: Bearer $TOKEN"
```

---

### Get Health Status

```
GET /api/v1/integrations/{integration_id}/health
```

Get the cached health status of an integration. Unlike the `POST /check`
endpoint, this returns the last known health state without performing a new
check.

**Required role:** any authenticated user

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `integration_id` | string | Unique integration identifier |

**Response (200):**

```json
{
  "integration_id": "splunk-prod",
  "healthy": true,
  "status": "connected",
  "latency_ms": 142,
  "checked_at": "2026-03-08T14:30:00Z"
}
```

**Example:**

```bash
curl http://localhost:8000/api/v1/integrations/splunk-prod/health \
  -H "Authorization: Bearer $TOKEN"
```

---

### List Workflow Runs

```
GET /api/v1/integrations/runs
```

List all integration workflow runs (health checks, diagnostics, syncs) across
all integrations. Useful for auditing integration activity.

**Required role:** any authenticated user

**Response (200):**

```json
[
  {
    "run_id": "run-abc123",
    "integration_id": "splunk-prod",
    "action": "sync",
    "status": "completed",
    "started_at": "2026-03-08T14:30:00Z",
    "completed_at": "2026-03-08T14:30:12Z",
    "duration_ms": 12000
  }
]
```

**Example:**

```bash
curl http://localhost:8000/api/v1/integrations/runs \
  -H "Authorization: Bearer $TOKEN"
```

---

## Authentication

All endpoints require JWT authentication via the `Authorization: Bearer <token>`
header.

Write operations (`POST /check`, `POST /diagnose`, `POST /sync`) require `admin`
or `operator` role. Configuration updates (`PUT /config`) require `admin` role.
Read operations (`GET /`, `GET /health`, `GET /runs`) are available to any
authenticated user.

## Rate Limiting

All endpoints are subject to the platform-wide rate limits configured in the
API gateway.
