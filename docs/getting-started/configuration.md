# Configuration

ShieldOps is configured via environment variables with the `SHIELDOPS_` prefix.
All settings are defined in `src/shieldops/config/settings.py` using Pydantic Settings.

Variables can be set in a `.env` file (loaded automatically) or as system environment
variables.

---

## Application

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_ENVIRONMENT` | `development` | Runtime environment: `development`, `staging`, `production` |
| `SHIELDOPS_DEBUG` | `false` | Enable debug mode |
| `SHIELDOPS_APP_NAME` | `ShieldOps` | Application name (used in logs and headers) |
| `SHIELDOPS_APP_VERSION` | `0.1.0` | Application version |

## API Server

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_API_HOST` | `0.0.0.0` | Bind address |
| `SHIELDOPS_API_PORT` | `8000` | Bind port |
| `SHIELDOPS_API_PREFIX` | `/api/v1` | API route prefix |
| `SHIELDOPS_CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins (JSON array) |

## Database

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_DATABASE_URL` | `postgresql+asyncpg://shieldops:shieldops@localhost:5432/shieldops` | PostgreSQL connection string (must use `asyncpg` driver) |
| `SHIELDOPS_DATABASE_POOL_SIZE` | `20` | SQLAlchemy connection pool size |

!!! warning
    The database URL **must** use the `postgresql+asyncpg://` scheme. ShieldOps uses
    asyncpg for async database access via SQLAlchemy.

## Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |

## Kafka

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_KAFKA_BROKERS` | `localhost:9092` | Kafka broker addresses (comma-separated) |
| `SHIELDOPS_KAFKA_CONSUMER_GROUP` | `shieldops-agents` | Kafka consumer group ID |

## LLM Providers

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_ANTHROPIC_API_KEY` | `""` | Anthropic Claude API key (primary LLM) |
| `SHIELDOPS_ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Anthropic model to use |
| `SHIELDOPS_OPENAI_API_KEY` | `""` | OpenAI API key (fallback LLM) |
| `SHIELDOPS_OPENAI_MODEL` | `gpt-4o` | OpenAI model to use |

!!! tip
    Without an Anthropic API key, ShieldOps runs in demo mode with simulated agent
    responses. Set at least `SHIELDOPS_ANTHROPIC_API_KEY` for real agent functionality.

## Agent Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_AGENT_CONFIDENCE_THRESHOLD_AUTO` | `0.85` | Minimum confidence for autonomous action |
| `SHIELDOPS_AGENT_CONFIDENCE_THRESHOLD_APPROVAL` | `0.50` | Minimum confidence before requesting approval (below this, escalate immediately) |
| `SHIELDOPS_AGENT_MAX_INVESTIGATION_TIME_SECONDS` | `600` | Maximum investigation duration (10 min) |
| `SHIELDOPS_AGENT_MAX_REMEDIATION_RETRIES` | `3` | Maximum retries for failed remediations |

## OPA Policy Engine

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_OPA_ENDPOINT` | `http://localhost:8181` | OPA server URL |

## Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_RATE_LIMIT_ENABLED` | `true` | Enable HTTP API rate limiting |
| `SHIELDOPS_RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window |
| `SHIELDOPS_SLIDING_WINDOW_RATE_LIMIT_ENABLED` | `false` | Enable sliding window rate limiter |
| `SHIELDOPS_RATE_LIMIT_ADMIN` | `300` | Requests/window for admin role |
| `SHIELDOPS_RATE_LIMIT_OPERATOR` | `120` | Requests/window for operator role |
| `SHIELDOPS_RATE_LIMIT_VIEWER` | `60` | Requests/window for viewer role |
| `SHIELDOPS_RATE_LIMIT_DEFAULT` | `60` | Requests/window (default) |
| `SHIELDOPS_RATE_LIMIT_AUTH_LOGIN` | `10` | Login attempts/window |
| `SHIELDOPS_RATE_LIMIT_AUTH_REGISTER` | `5` | Registration attempts/window |

## Security / Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_JWT_SECRET_KEY` | `change-me-in-production` | JWT signing secret |
| `SHIELDOPS_JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `SHIELDOPS_JWT_EXPIRE_MINUTES` | `60` | Token expiry in minutes |

!!! warning
    **Always** change `JWT_SECRET_KEY` in staging and production deployments.
    Use a cryptographically random value of at least 32 characters.

## OIDC / SSO

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_OIDC_ENABLED` | `false` | Enable OIDC/SSO authentication |
| `SHIELDOPS_OIDC_ISSUER_URL` | `""` | OIDC provider issuer URL |
| `SHIELDOPS_OIDC_CLIENT_ID` | `""` | OIDC client ID |
| `SHIELDOPS_OIDC_CLIENT_SECRET` | `""` | OIDC client secret |
| `SHIELDOPS_OIDC_REDIRECT_URI` | `http://localhost:8000/api/v1/auth/oidc/callback` | OAuth callback URL |
| `SHIELDOPS_OIDC_SCOPES` | `openid email profile` | Requested OIDC scopes |

## Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_LANGSMITH_API_KEY` | `""` | LangSmith API key (agent tracing) |
| `SHIELDOPS_LANGSMITH_PROJECT` | `shieldops` | LangSmith project name |
| `SHIELDOPS_LANGSMITH_ENABLED` | `false` | Enable LangSmith tracing |
| `SHIELDOPS_OTEL_EXPORTER_ENDPOINT` | `http://localhost:4317` | OpenTelemetry collector endpoint |
| `SHIELDOPS_PROMETHEUS_URL` | `http://localhost:9090` | Prometheus server URL |
| `SHIELDOPS_JAEGER_URL` | `""` | Jaeger tracing URL |

## Observability Sources

### Splunk

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_SPLUNK_URL` | `""` | Splunk API URL |
| `SHIELDOPS_SPLUNK_TOKEN` | `""` | Splunk HEC token |
| `SHIELDOPS_SPLUNK_INDEX` | `main` | Default Splunk index |
| `SHIELDOPS_SPLUNK_VERIFY_SSL` | `true` | Verify Splunk TLS certificates |

### Datadog

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_DATADOG_API_KEY` | `""` | Datadog API key |
| `SHIELDOPS_DATADOG_APP_KEY` | `""` | Datadog application key |
| `SHIELDOPS_DATADOG_SITE` | `datadoghq.com` | Datadog site domain |

## Cloud Providers

### AWS

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_AWS_REGION` | `""` | AWS region (enables AWS connector when set) |
| `SHIELDOPS_AWS_ACCESS_KEY_ID` | `""` | AWS access key (prefer IAM roles in production) |
| `SHIELDOPS_AWS_SECRET_ACCESS_KEY` | `""` | AWS secret key |
| `SHIELDOPS_CLOUDWATCH_LOG_GROUP` | `""` | CloudWatch log group name |

### GCP

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_GCP_PROJECT_ID` | `""` | GCP project ID (enables GCP connector when set) |
| `SHIELDOPS_GCP_REGION` | `us-central1` | GCP region |
| `SHIELDOPS_GCP_BILLING_DATASET` | `billing_export` | BigQuery billing dataset |
| `SHIELDOPS_GCP_BILLING_TABLE` | `gcp_billing_export_v1` | BigQuery billing table |

### Azure

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_AZURE_SUBSCRIPTION_ID` | `""` | Azure subscription (enables Azure connector when set) |
| `SHIELDOPS_AZURE_RESOURCE_GROUP` | `""` | Azure resource group |
| `SHIELDOPS_AZURE_LOCATION` | `eastus` | Azure region |
| `SHIELDOPS_AZURE_BILLING_ENABLED` | `false` | Enable Azure Cost Management |

### Linux SSH

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_LINUX_HOST` | `""` | SSH target host (enables Linux connector) |
| `SHIELDOPS_LINUX_USERNAME` | `""` | SSH username |
| `SHIELDOPS_LINUX_PRIVATE_KEY_PATH` | `""` | Path to SSH private key |

## Integrations

### Slack

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_SLACK_BOT_TOKEN` | `""` | Slack bot token for notifications |
| `SHIELDOPS_SLACK_SIGNING_SECRET` | `""` | Slack request signing secret |
| `SHIELDOPS_SLACK_APPROVAL_CHANNEL` | `#shieldops-approvals` | Channel for approval requests |

### PagerDuty

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_PAGERDUTY_ROUTING_KEY` | `""` | PagerDuty Events API v2 routing key |

### Webhooks

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_WEBHOOK_URL` | `""` | Webhook endpoint URL |
| `SHIELDOPS_WEBHOOK_SECRET` | `""` | HMAC signing secret for webhook payloads |
| `SHIELDOPS_WEBHOOK_TIMEOUT` | `10.0` | Webhook request timeout in seconds |

### Email / SMTP

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_SMTP_HOST` | `""` | SMTP server hostname |
| `SHIELDOPS_SMTP_PORT` | `587` | SMTP server port |
| `SHIELDOPS_SMTP_USERNAME` | `""` | SMTP authentication username |
| `SHIELDOPS_SMTP_PASSWORD` | `""` | SMTP authentication password |
| `SHIELDOPS_SMTP_USE_TLS` | `true` | Enable STARTTLS |
| `SHIELDOPS_SMTP_FROM_ADDRESS` | `shieldops@localhost` | Sender email address |
| `SHIELDOPS_SMTP_TO_ADDRESSES` | `[]` | Default recipient list (JSON array) |

## Security Scanners

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_NVD_API_KEY` | `""` | NVD (National Vulnerability Database) API key |
| `SHIELDOPS_TRIVY_SERVER_URL` | `""` | Trivy server URL for container scanning |
| `SHIELDOPS_TRIVY_TIMEOUT` | `300` | Trivy scan timeout in seconds |
| `SHIELDOPS_GITLEAKS_PATH` | `gitleaks` | Path to gitleaks binary |
| `SHIELDOPS_OSV_SCANNER_PATH` | `osv-scanner` | Path to osv-scanner binary |
| `SHIELDOPS_CHECKOV_PATH` | `checkov` | Path to checkov binary |
| `SHIELDOPS_IAC_SCANNER_ENABLED` | `false` | Enable IaC scanning (Checkov) |
| `SHIELDOPS_GIT_SCANNER_ENABLED` | `false` | Enable git secret/dependency scanning |
| `SHIELDOPS_K8S_SCANNER_ENABLED` | `false` | Enable Kubernetes security scanning |
| `SHIELDOPS_NETWORK_SCANNER_ENABLED` | `false` | Enable network security scanning |

## HashiCorp Vault

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_VAULT_ADDR` | `""` | Vault server address |
| `SHIELDOPS_VAULT_TOKEN` | `""` | Vault authentication token |
| `SHIELDOPS_VAULT_MOUNT_POINT` | `secret` | Vault KV mount point |
| `SHIELDOPS_VAULT_NAMESPACE` | `""` | Vault namespace (enterprise) |
