# Investigations API

The Investigations API provides endpoints for triggering, tracking, and managing
investigation agent workflows.

---

## Endpoints

### Trigger Investigation (async)

```
POST /api/v1/investigations
```

Start a new investigation for an alert. Runs asynchronously and returns immediately
with a 202 status.

**Required role:** `admin` or `operator`

**Request body:**

```json
{
  "alert_id": "prom-001",
  "alert_name": "HighCPU",
  "severity": "critical",
  "source": "prometheus",
  "resource_id": "pod/web-server-01",
  "labels": {"namespace": "production", "team": "platform"},
  "annotations": {},
  "description": "CPU usage at 97% for 15 minutes"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `alert_id` | string | yes | Unique alert identifier |
| `alert_name` | string | yes | Human-readable alert name |
| `severity` | string | no | `warning`, `critical` (default: `warning`) |
| `source` | string | no | Alert source system (default: `api`) |
| `resource_id` | string | no | Target resource identifier |
| `labels` | object | no | Key-value labels |
| `annotations` | object | no | Key-value annotations |
| `description` | string | no | Free-text description |

**Response (202):**

```json
{
  "status": "accepted",
  "alert_id": "prom-001",
  "message": "Investigation started. Use GET /investigations to track progress."
}
```

---

### Trigger Investigation (sync)

```
POST /api/v1/investigations/sync
```

Same as above but waits for the investigation to complete. Useful for testing and
CLI tools. Not recommended for production use.

**Required role:** `admin` or `operator`

**Response (200):** Full investigation result object.

---

### List Investigations

```
GET /api/v1/investigations
```

List active and recent investigations with pagination.

**Required role:** any authenticated user

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | (all) | Filter by status |
| `limit` | int | 50 | Page size |
| `offset` | int | 0 | Page offset |

**Response (200):**

```json
{
  "investigations": [
    {
      "investigation_id": "inv-abc123",
      "alert_id": "prom-001",
      "alert_name": "HighCPU",
      "status": "complete",
      "confidence": 0.92,
      "hypotheses_count": 3,
      "duration_ms": 4200
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

---

### Get Investigation Detail

```
GET /api/v1/investigations/{investigation_id}
```

Get full investigation detail including reasoning chain, evidence, and hypotheses.

**Required role:** any authenticated user

**Response (200):**

```json
{
  "investigation_id": "inv-abc123",
  "alert_context": {
    "alert_id": "prom-001",
    "alert_name": "HighCPU",
    "severity": "critical",
    "source": "prometheus"
  },
  "status": "complete",
  "confidence_score": 0.92,
  "hypotheses": [
    {
      "description": "Memory leak in web-server-01 causing increased CPU due to GC pressure",
      "confidence": 0.92,
      "evidence": ["OOM events in logs", "Heap usage trending up 300% over 2 hours"],
      "affected_resources": ["pod/web-server-01"],
      "recommended_action": "restart_pod"
    }
  ],
  "reasoning_chain": [
    {
      "step_number": 1,
      "action": "gather_context",
      "input_summary": "Alert: HighCPU on web-server-01",
      "output_summary": "Identified Kubernetes pod in production namespace",
      "duration_ms": 120,
      "tool_used": "kubernetes_connector"
    }
  ],
  "recommended_action": {
    "action_type": "restart_pod",
    "target_resource": "pod/web-server-01",
    "risk_level": "medium"
  },
  "duration_ms": 4200
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 404 | Investigation not found |

---

## WebSocket Updates

Connect to the WebSocket endpoint for real-time investigation progress:

```
ws://localhost:8000/ws/investigations
```

Events are published as the investigation progresses through each graph node.
