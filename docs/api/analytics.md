# Analytics API

The Analytics API provides operational metrics and reporting for the ShieldOps platform.

---

## Endpoints

### MTTR Trends

```
GET /api/v1/analytics/mttr
```

Get Mean Time to Resolution trends over a specified period.

**Required role:** any authenticated user

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `30d` | Time period (e.g., `7d`, `30d`, `90d`) |
| `environment` | string | (all) | Filter by environment |

**Response (200):**

```json
{
  "period": "30d",
  "data_points": [
    {"date": "2026-02-01", "mttr_minutes": 45},
    {"date": "2026-02-02", "mttr_minutes": 32}
  ],
  "current_mttr_minutes": 12
}
```

---

### Resolution Rate

```
GET /api/v1/analytics/resolution-rate
```

Get automated vs. manual resolution rates.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `30d` | Time period |

**Response (200):**

```json
{
  "period": "30d",
  "automated_rate": 0.73,
  "manual_rate": 0.27,
  "total_incidents": 156
}
```

---

### Agent Accuracy

```
GET /api/v1/analytics/agent-accuracy
```

Get agent diagnosis accuracy over time.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `30d` | Time period |

**Response (200):**

```json
{
  "period": "30d",
  "accuracy": 0.89,
  "total_investigations": 234
}
```

---

### Cost Savings

```
GET /api/v1/analytics/cost-savings
```

Estimate cost savings from automated operations.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `30d` | Time period |
| `engineer_hourly_rate` | float | `75.0` | Hourly rate for ROI calculation |

**Response (200):**

```json
{
  "period": "30d",
  "hours_saved": 120,
  "estimated_savings_usd": 9000.0,
  "engineer_hourly_rate": 75.0
}
```

---

### Analytics Summary

```
GET /api/v1/analytics/summary
```

Get an aggregated analytics summary for the dashboard.

**Response (200):**

```json
{
  "total_investigations": 456,
  "total_remediations": 189,
  "auto_resolved_percent": 73.2,
  "mean_time_to_resolve_seconds": 720,
  "investigations_by_status": {
    "complete": 420,
    "in_progress": 12,
    "failed": 24
  },
  "remediations_by_status": {
    "complete": 165,
    "rolled_back": 8,
    "pending_approval": 3,
    "failed": 13
  }
}
```
