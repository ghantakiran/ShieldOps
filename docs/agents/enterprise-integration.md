# Enterprise Integration Agent

The Enterprise Integration Agent manages connections to 12+ enterprise tools.
It runs automated health checks, diagnoses degraded integrations using LLM-powered
root cause analysis, applies automated fixes (credential rotation, reconnection),
and generates actionable recommendations.

---

## Purpose

- Load and validate integration configurations from the repository
- Run health checks: endpoint reachability, auth validity, latency measurement, rate limit status
- Analyze sync history for failure rate and performance anomalies
- Diagnose degraded/disconnected integrations using LLM reasoning
- Apply automated fixes (credential rotation, reconnection) when safe
- Re-verify health after fixes to confirm recovery
- Generate prioritized recommendations with risk assessments

---

## Graph Workflow

```
load_config
      |
      v
check_health
      |
      +-- [connected] --> analyze_sync_history --> generate_recommendations --> END
      |
      +-- [degraded/disconnected/error] --> diagnose_issues
      |                                          |
      |                                          +-- [auto-fixable] --> apply_fixes
      |                                          |                        |
      |                                          |                        v
      |                                          |                  check_health_again --> END
      |                                          |
      |                                          +-- [manual] --> generate_recommendations --> END
      |
      +-- [error/no health] --> generate_recommendations --> END
```

### Nodes

| Node | Description |
|------|-------------|
| `load_config` | Loads `IntegrationConfig` from the repository (provider, auth type, endpoint, rate limits). |
| `check_health` | Pings endpoint, validates auth, measures latency, checks rate limit status. |
| `analyze_sync_history` | Retrieves 24h sync events; flags high failure rates (>30%) and elevated latency (>5s avg). |
| `diagnose_issues` | Gathers 6h error logs and uses LLM (`SYSTEM_DIAGNOSE_INTEGRATION`) to identify root cause, severity, affected components, and fix steps. |
| `apply_fixes` | Executes automated remediation: credential rotation when "rotate" + "credential" in recommendation, reconnection when "reconnect" in recommendation. |
| `check_health_again` | Re-runs health check after fixes to verify recovery. |
| `generate_recommendations` | Uses LLM (`SYSTEM_RECOMMEND_FIXES`) to produce prioritized recommendations with risk levels. Falls back to diagnostic-derived recommendations if LLM fails. |

### Conditional Edges

- **After `check_health`:** If status is `connected`, route to `analyze_sync_history`.
  If `degraded`, `disconnected`, `error`, or `configuring`, route to `diagnose_issues`.
  If health data is unavailable, route to `generate_recommendations`.
- **After `diagnose_issues`:** If any diagnostic recommendation contains auto-fix keywords
  (`rotat`, `reconnect`, `restart`, `retry`, `refresh`), route to `apply_fixes`.
  Otherwise, route to `generate_recommendations`.

---

## State Model

```python
class IntegrationState(BaseModel):
    # Input
    integration_id: str
    action: str               # health_check, sync, configure, diagnose, reconnect

    # Processing
    config: IntegrationConfig | None
    health: IntegrationHealth | None
    sync_events: list[SyncEvent]
    diagnostics: list[DiagnosticFinding]

    # Output
    result: dict[str, Any]    # e.g., {"fixes_applied": [...], "fixes_failed": [...]}
    recommendations: list[str]
    status_changed: bool

    # Metadata
    action_start: datetime | None
    processing_duration_ms: int
    reasoning_chain: list[ReasoningStep]
    current_step: str
    error: str | None
```

---

## Supported Integrations

| Provider | Category | Direction |
|----------|----------|-----------|
| Slack | Communication | Bidirectional |
| Microsoft Teams | Communication | Bidirectional |
| PagerDuty | Communication | Bidirectional |
| Jira | Ticketing | Bidirectional |
| GitHub | DevOps | Bidirectional |
| Datadog | Monitoring | Inbound |
| Splunk | Monitoring | Inbound |
| CrowdStrike | Security | Inbound |
| ServiceNow | ITSM | Bidirectional |
| OpsGenie | Communication | Bidirectional |
| Prometheus | Monitoring | Inbound |
| Microsoft Sentinel | Security | Inbound |

---

## Health Monitoring

Each health check collects:

| Metric | Source |
|--------|--------|
| Status | `connected`, `degraded`, `disconnected`, `configuring`, `error` |
| Latency (ms) | Round-trip ping to endpoint |
| Auth validity | Connector `test_auth()` call |
| Error count (1h) | Repository error count |
| Uptime (24h) | Repository uptime percentage |
| Rate limit remaining | Repository rate limit status |
| Events today | Repository event count |
| Last successful sync | Repository timestamp |

---

## Diagnostics

When health status is not `connected`, the agent:

1. Retrieves error logs (6h window, capped at 200 entries for LLM context)
2. Builds a structured prompt with config, health data, sync events, and error logs
3. Calls LLM with `SYSTEM_DIAGNOSE_INTEGRATION` for structured diagnosis
4. Returns `DiagnosticFinding` with severity, component, finding, and recommendation
5. Falls back to raw error log analysis if LLM is unavailable

---

## Auto-Remediation

The agent applies automated fixes based on diagnostic recommendations:

| Fix | Trigger Keyword | Action |
|-----|----------------|--------|
| Credential rotation | "rotat" + "credential" | Calls `rotate_credentials()` via repository |
| Reconnection | "reconnect" | Re-checks health to verify connectivity |

After fixes, `check_health_again` verifies recovery and records status change.

---

## Configuration

Each integration is configured via `IntegrationConfig`:

```python
class IntegrationConfig(BaseModel):
    id: str
    name: str
    provider: str             # slack, teams, pagerduty, jira, etc.
    category: IntegrationCategory  # communication, monitoring, security, devops, ticketing, cloud, itsm
    direction: IntegrationDirection  # inbound, outbound, bidirectional
    endpoint_url: str
    auth_type: str            # oauth2, api_key, service_account, webhook
    scopes: list[str]
    rate_limit: RateLimitConfig   # requests_per_minute, burst_limit
    retry_policy: RetryPolicy     # max_retries, backoff_seconds
    health_check_interval_seconds: int  # default: 60
    enabled: bool
```

---

## API Endpoints

### POST /api/v1/integrations/check

Run a health-check workflow for an integration.

```bash
curl -X POST http://localhost:8000/api/v1/integrations/check \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"integration_id": "slack-main"}'
```

### POST /api/v1/integrations/diagnose

Run a full diagnostic workflow.

```bash
curl -X POST http://localhost:8000/api/v1/integrations/diagnose \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"integration_id": "datadog-prod"}'
```

### POST /api/v1/integrations/sync

Trigger a data sync.

```bash
curl -X POST http://localhost:8000/api/v1/integrations/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "integration_id": "jira-cloud",
    "direction": "bidirectional"
  }'
```

### PUT /api/v1/integrations/config

Update integration configuration.

```bash
curl -X PUT http://localhost:8000/api/v1/integrations/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "integration_id": "splunk-prod",
    "updates": {
      "rate_limit": {"requests_per_minute": 120, "burst_limit": 20},
      "health_check_interval_seconds": 30
    }
  }'
```

### GET /api/v1/integrations/

List all integrations with current status.

```bash
curl http://localhost:8000/api/v1/integrations/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## Integration with Other Agents

The Enterprise Integration Agent supports the entire platform by ensuring connectivity
to external tools. When integrations degrade, it notifies via the notification dispatcher
and can be triggered by the [Automation Orchestrator](automation-orchestrator.md) for
automated health monitoring schedules.
