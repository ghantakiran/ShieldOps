# Agents API

The Agents API provides endpoints for managing the agent fleet -- listing agents,
viewing their status, and enabling/disabling individual agents.

---

## Endpoints

### List Agents

```
GET /api/v1/agents
```

List all deployed agents with status and health information.

**Required role:** any authenticated user

**Query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `environment` | string | Filter by environment |
| `status` | string | Filter by status (`active`, `disabled`, `error`) |

**Response (200):**

```json
{
  "agents": [
    {
      "agent_id": "agent-inv-001",
      "agent_type": "investigation",
      "environment": "development",
      "status": "active",
      "last_activity": "2026-02-19T10:30:00Z",
      "investigations_completed": 42,
      "average_duration_ms": 3500
    },
    {
      "agent_id": "agent-rem-001",
      "agent_type": "remediation",
      "environment": "development",
      "status": "active"
    }
  ],
  "total": 6,
  "filters": {
    "environment": null,
    "status": null
  }
}
```

---

### Get Agent Detail

```
GET /api/v1/agents/{agent_id}
```

Get detailed agent information including configuration and recent activity.

**Required role:** any authenticated user

**Errors:** 404 if agent not found.

---

### Enable Agent

```
POST /api/v1/agents/{agent_id}/enable
```

Enable a previously disabled agent.

**Required role:** `admin` or `operator`

**Response (200):**

```json
{
  "agent_id": "agent-inv-001",
  "action": "enabled",
  "agent": {
    "agent_id": "agent-inv-001",
    "agent_type": "investigation",
    "status": "active"
  }
}
```

---

### Disable Agent

```
POST /api/v1/agents/{agent_id}/disable
```

Disable an active agent (graceful shutdown -- in-progress work completes before
the agent stops accepting new tasks).

**Required role:** `admin` or `operator`

**Response (200):**

```json
{
  "agent_id": "agent-inv-001",
  "action": "disabled",
  "agent": {
    "agent_id": "agent-inv-001",
    "agent_type": "investigation",
    "status": "disabled"
  }
}
```

---

## Agent Types

The platform registers six agent types at startup:

| Type | Description |
|------|-------------|
| `investigation` | Root cause analysis agent |
| `remediation` | Infrastructure execution agent |
| `security` | Security posture management agent |
| `cost` | Cloud cost analysis agent |
| `learning` | Continuous improvement agent |
| `supervisor` | Multi-agent orchestration agent |
