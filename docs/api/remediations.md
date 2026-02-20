# Remediations API

The Remediations API provides endpoints for triggering, tracking, approving, denying,
and rolling back remediation agent workflows.

---

## Endpoints

### Trigger Remediation (async)

```
POST /api/v1/remediations
```

Start a new remediation action. Runs asynchronously and returns immediately.

**Required role:** `admin` or `operator`

**Request body:**

```json
{
  "action_type": "restart_pod",
  "target_resource": "pod/web-server-01",
  "environment": "production",
  "risk_level": "medium",
  "parameters": {"namespace": "default"},
  "description": "Restart pod to recover from OOM state",
  "investigation_id": "inv-abc123",
  "alert_id": "prom-001"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action_type` | string | yes | Action to execute (e.g., `restart_pod`, `scale_horizontal`) |
| `target_resource` | string | yes | Target resource identifier |
| `environment` | string | no | `development`, `staging`, `production` (default: `production`) |
| `risk_level` | string | no | `low`, `medium`, `high`, `critical` (default: `medium`) |
| `parameters` | object | no | Action-specific parameters |
| `description` | string | no | Free-text description |
| `investigation_id` | string | no | Link to originating investigation |
| `alert_id` | string | no | Link to originating alert |

**Response (202):**

```json
{
  "status": "accepted",
  "action_id": "act-a1b2c3d4e5f6",
  "action_type": "restart_pod",
  "message": "Remediation started. Use GET /remediations to track progress."
}
```

---

### Trigger Remediation (sync)

```
POST /api/v1/remediations/sync
```

Same as above but waits for the remediation to complete. Useful for testing.

**Required role:** `admin` or `operator`

---

### List Remediations

```
GET /api/v1/remediations
```

List remediation timeline (newest first) with pagination.

**Required role:** any authenticated user

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `environment` | string | (all) | Filter by environment |
| `status` | string | (all) | Filter by status |
| `limit` | int | 50 | Page size |
| `offset` | int | 0 | Page offset |

**Response (200):**

```json
{
  "remediations": [
    {
      "remediation_id": "rem-abc123",
      "action_type": "restart_pod",
      "target_resource": "pod/web-server-01",
      "environment": "production",
      "status": "complete",
      "risk_level": "medium"
    }
  ],
  "total": 15,
  "limit": 50,
  "offset": 0
}
```

---

### Get Remediation Detail

```
GET /api/v1/remediations/{remediation_id}
```

Get full remediation detail with execution results and audit trail.

**Required role:** any authenticated user

**Errors:** 404 if not found.

---

### Approve Remediation

```
POST /api/v1/remediations/{remediation_id}/approve
```

Approve a pending remediation action.

**Required role:** `admin` or `operator`

**Request body:**

```json
{
  "approver": "sre-lead@company.com",
  "reason": "Verified safe to proceed"
}
```

**Response (200):**

```json
{
  "remediation_id": "rem-abc123",
  "action": "approved",
  "approver": "sre-lead@company.com"
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 400 | No pending approval request |
| 404 | Remediation not found |

---

### Deny Remediation

```
POST /api/v1/remediations/{remediation_id}/deny
```

Deny a pending remediation action.

**Required role:** `admin` or `operator`

**Request body:**

```json
{
  "approver": "sre-lead@company.com",
  "reason": "Too risky during peak hours"
}
```

**Response (200):**

```json
{
  "remediation_id": "rem-abc123",
  "action": "denied",
  "denier": "sre-lead@company.com",
  "reason": "Too risky during peak hours"
}
```

---

### Rollback Remediation

```
POST /api/v1/remediations/{remediation_id}/rollback
```

Rollback a completed remediation to the pre-action state using the saved snapshot.

**Required role:** `admin` or `operator`

**Request body:**

```json
{
  "reason": "Change caused increased error rate"
}
```

**Response (200):**

```json
{
  "remediation_id": "rem-abc123",
  "action": "rollback_initiated",
  "snapshot_id": "snap-xyz789",
  "status": "success",
  "message": "Rollback completed successfully"
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 400 | No snapshot available for rollback |
| 404 | Remediation not found |
