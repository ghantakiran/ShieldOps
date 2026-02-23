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

## Conventions
- All I/O is async (use `run_in_executor` for sync SDKs)
- Graceful error handling — return empty/default on failure, never crash
- Structured logging with structlog
- Type hints on all public methods
