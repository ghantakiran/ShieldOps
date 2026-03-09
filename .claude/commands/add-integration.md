# Add Integration Skill

Scaffold a new external integration (billing, notification, CVE source, credential store, etc.).

## Usage
`/add-integration <type> <provider-name>`

Types: `billing`, `notification`, `cve`, `credential`, `cost-forecast`

## Process

1. **Read existing integrations**: Review `src/shieldops/integrations/` for patterns
2. **Check the protocol**: Each integration type has a base protocol:
   - Billing: `src/shieldops/integrations/billing/base.py` — `BillingSource.query()`
   - Notification: `src/shieldops/integrations/notifications/base.py` — `NotificationChannel.send()`
   - CVE: `src/shieldops/integrations/cve/` — `CVESource.scan()`
   - Credential: `src/shieldops/integrations/credentials/` — `CredentialStore.list_credentials()`
   - Cost-forecast: `src/shieldops/billing/cost_forecast.py` — `CostForecastEngine.record_cost()`
3. **Create the integration**:
   - File: `src/shieldops/integrations/{type}/{provider}.py`
   - Implement the protocol with async methods
   - Use httpx for HTTP APIs, boto3 for AWS, lazy client init
4. **Add settings**: Provider-specific config in `src/shieldops/config/settings.py`
5. **Wire into app**: Register in `src/shieldops/api/app.py` lifespan
6. **Write tests**: `tests/unit/test_{provider}_{type}.py` with mocked API calls

## Enterprise Integration Patterns

Use the Enterprise Integration Agent (`src/shieldops/agents/enterprise_integration/`) for complex integrations that require bidirectional data flow, event-driven workflows, or multi-system orchestration.

### Webhook Setup (Slack/Teams)
1. **Slack Integration**:
   - Register Slack app with required scopes (chat:write, commands, incoming-webhook)
   - Configure webhook URL in `src/shieldops/integrations/notifications/slack.py`
   - Register slash commands for ChatOps via `src/shieldops/api/routes/chatops.py`
   - Set up interactive message handlers for approval buttons
2. **Microsoft Teams Integration**:
   - Register Teams connector and bot in Azure AD
   - Configure incoming webhook URL in `src/shieldops/integrations/notifications/teams.py`
   - Set up adaptive card templates for structured responses
   - Register Teams command handlers via ChatOps routes

### OPA Policy Gate Configuration
- Every new integration MUST have a corresponding OPA policy in `playbooks/policies/`
- Define allowed actions, data access scope, and rate limits per integration
- Wire policy evaluation via `src/shieldops/policy/opa_client.py` before any outbound data flow
- Template: `playbooks/policies/integration_{provider}.rego`
- Test policies: `python3 -m pytest tests/unit/test_policy_{provider}.py`

### Integration Health Monitoring
- Register health check endpoint for each integration in `src/shieldops/api/routes/enterprise_integrations.py`
- Implement circuit breaker pattern for external API calls (see `src/shieldops/utils/circuit_breaker.py`)
- Configure dead-letter queue for failed events (Kafka topic: `integration.{provider}.dlq`)
- Set up alerting thresholds: error rate >5%, latency p99 >2s, queue depth >100
- Add integration to `/check-health` monitoring (see `check-health.md`)

## Conventions
- All I/O is async (use `run_in_executor` for sync SDKs)
- Graceful error handling — return empty/default on failure, never crash
- Structured logging with structlog
- Type hints on all public methods
