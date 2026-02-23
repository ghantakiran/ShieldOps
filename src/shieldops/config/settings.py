"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """ShieldOps configuration loaded from environment variables."""

    # Application
    app_name: str = "ShieldOps"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"  # development, staging, production

    # API
    api_host: str = "0.0.0.0"  # noqa: S104  # nosec B104
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Database
    database_url: str = "postgresql+asyncpg://shieldops:shieldops@localhost:5432/shieldops"
    database_pool_size: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Rate Limiting (HTTP API)
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    sliding_window_rate_limit_enabled: bool = False
    rate_limit_admin: int = 300
    rate_limit_operator: int = 120
    rate_limit_viewer: int = 60
    rate_limit_default: int = 60
    rate_limit_auth_login: int = 10
    rate_limit_auth_register: int = 5

    # Kafka
    kafka_brokers: str = "localhost:9092"
    kafka_consumer_group: str = "shieldops-agents"

    # LLM Providers
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Agent Configuration
    agent_confidence_threshold_auto: float = 0.85
    agent_confidence_threshold_approval: float = 0.50
    agent_max_investigation_time_seconds: int = 600
    agent_max_remediation_retries: int = 3

    # OPA Policy Engine
    opa_endpoint: str = "http://localhost:8181"

    # Observability
    langsmith_api_key: str = ""
    langsmith_project: str = "shieldops"
    langsmith_enabled: bool = False
    otel_exporter_endpoint: str = "http://localhost:4317"

    # Observability — Prometheus
    prometheus_url: str = "http://localhost:9090"

    # Observability — Splunk
    splunk_url: str = ""
    splunk_token: str = ""
    splunk_index: str = "main"
    splunk_verify_ssl: bool = True

    # Observability — Datadog
    datadog_api_key: str = ""
    datadog_app_key: str = ""
    datadog_site: str = "datadoghq.com"

    # Observability — Jaeger
    jaeger_url: str = ""

    # Slack Integration
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_approval_channel: str = "#shieldops-approvals"

    # PagerDuty
    pagerduty_routing_key: str = ""

    # Webhooks
    webhook_url: str = ""
    webhook_secret: str = ""
    webhook_timeout: float = 10.0

    # Email / SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_address: str = "shieldops@localhost"
    smtp_to_addresses: list[str] = []

    # AWS
    aws_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    cloudwatch_log_group: str = ""

    # GCP
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"

    # Azure
    azure_subscription_id: str = ""
    azure_resource_group: str = ""
    azure_location: str = "eastus"

    # GCP Billing
    gcp_billing_dataset: str = "billing_export"
    gcp_billing_table: str = "gcp_billing_export_v1"

    # Azure Billing
    azure_billing_enabled: bool = False

    # Stripe Billing (SaaS subscriptions)
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_success_url: str = "http://localhost:5173/settings?billing=success"
    stripe_cancel_url: str = "http://localhost:5173/settings?billing=cancel"

    # NVD CVE Source
    nvd_api_key: str = ""

    # Trivy Scanner
    trivy_server_url: str = ""
    trivy_timeout: int = 300

    # Git Security Scanners
    gitleaks_path: str = "gitleaks"
    osv_scanner_path: str = "osv-scanner"

    # IaC Scanner
    checkov_path: str = "checkov"

    # Scanner Activation (opt-in)
    iac_scanner_enabled: bool = False
    git_scanner_enabled: bool = False
    k8s_scanner_enabled: bool = False
    network_scanner_enabled: bool = False

    # HashiCorp Vault
    vault_addr: str = ""
    vault_token: str = ""
    vault_mount_point: str = "secret"
    vault_namespace: str = ""

    # Linux SSH
    linux_host: str = ""
    linux_username: str = ""
    linux_private_key_path: str = ""

    # Windows WinRM
    windows_host: str = ""
    windows_username: str = ""
    windows_password: str = ""
    windows_use_ssl: bool = True
    windows_port: int = 5986

    # Chat Session Persistence
    chat_session_ttl_seconds: int = 86400
    chat_max_messages_per_session: int = 50

    # GCP Secret Manager
    gcp_secret_manager_enabled: bool = False

    # Azure Key Vault
    azure_keyvault_url: str = ""

    # GitHub Advisory Database (GHSA)
    github_advisory_token: str = ""
    ghsa_enabled: bool = False

    # OS Advisory Feeds
    os_advisory_feeds_enabled: bool = False

    # SBOM Generation
    syft_path: str = "syft"
    sbom_enabled: bool = False

    # Threat Intelligence
    mitre_attack_enabled: bool = False
    epss_enabled: bool = False

    # Security
    jwt_secret_key: str = "change-me-in-production"  # noqa: S105
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Phase 12: Prediction Agent
    prediction_confidence_threshold: float = 0.75
    prediction_schedule_minutes: int = 30

    # Phase 12: RAG Knowledge Store
    rag_enabled: bool = False
    rag_embedding_model: str = "text-embedding-3-small"

    # Phase 12: LLM Router
    llm_routing_enabled: bool = False
    llm_simple_model: str = "claude-haiku-4-5-20251001"
    llm_moderate_model: str = "claude-sonnet-4-20250514"
    llm_complex_model: str = "claude-opus-4-20250514"

    # Phase 12: Observability — New Relic
    newrelic_api_key: str = ""
    newrelic_account_id: str = ""

    # Phase 12: Observability — Elastic / OpenSearch
    elastic_url: str = ""
    elastic_api_key: str = ""

    # Phase 13: Agent Tracing
    tracing_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"

    # Phase 13: SLO Monitoring
    slo_burn_rate_threshold: float = 2.0

    # Phase 13: Idempotency
    idempotency_ttl_seconds: int = 86400

    # Phase 13: Hot Reload
    hot_reload_enabled: bool = False

    # OIDC / SSO
    oidc_enabled: bool = False
    oidc_issuer_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:8000/api/v1/auth/oidc/callback"
    oidc_scopes: str = "openid email profile"

    # Phase 14: Multi-Level Cache
    cache_l1_max_size: int = 1000
    cache_l1_ttl_seconds: int = 60
    cache_l1_enabled: bool = True

    # Phase 14: Feature Flags
    feature_flags_enabled: bool = True
    feature_flags_sync_interval_seconds: int = 30

    # Phase 14: Health Aggregation
    health_history_size: int = 100
    health_check_interval_seconds: int = 60
    health_degraded_threshold: float = 70.0
    health_unhealthy_threshold: float = 40.0

    # Phase 14: Request Correlation
    correlation_enabled: bool = True
    correlation_max_traces: int = 10000
    correlation_trace_ttl_minutes: int = 60

    # Phase 14: Escalation Policies
    escalation_enabled: bool = True
    escalation_default_timeout_seconds: int = 300
    escalation_max_retries: int = 3

    # Phase 14: Agent Resource Quotas
    agent_global_max_concurrent: int = 20
    agent_quota_enabled: bool = True

    # Phase 14: Batch Operations
    batch_max_size: int = 500
    batch_max_parallel: int = 10
    batch_job_ttl_hours: int = 24

    # Phase 14: Incident Timeline
    timeline_max_events_per_incident: int = 1000
    timeline_retention_days: int = 90

    # Phase 14: Export Engine
    export_max_rows: int = 50000
    export_pdf_enabled: bool = True
    export_xlsx_enabled: bool = True

    # Phase 14: Environment Promotion
    promotion_require_approval_for_prod: bool = True
    promotion_allowed_source_envs: list[str] = ["development", "staging"]

    # Phase 14: API Lifecycle
    api_deprecation_header_enabled: bool = True
    api_sunset_warning_days: int = 30

    # Phase 14: Agent Collaboration
    agent_collaboration_enabled: bool = True
    agent_collaboration_max_messages: int = 1000
    agent_collaboration_session_timeout_minutes: int = 60

    # Phase 15: Post-Mortem Generator
    postmortem_enabled: bool = True
    postmortem_max_reports: int = 1000

    # Phase 15: DORA Metrics
    dora_enabled: bool = True
    dora_default_period_days: int = 30
    dora_max_records: int = 50000

    # Phase 15: Alert Suppression
    alert_suppression_enabled: bool = True
    alert_suppression_max_rules: int = 500
    maintenance_window_max_duration_hours: int = 24

    # Phase 15: On-Call Schedules
    oncall_enabled: bool = True
    oncall_default_rotation: str = "weekly"
    oncall_max_schedules: int = 100

    # Phase 15: Service Ownership
    service_ownership_enabled: bool = True
    service_ownership_max_entries: int = 5000

    # Phase 15: Runbook Execution Tracker
    runbook_tracking_enabled: bool = True
    runbook_max_executions: int = 10000
    runbook_execution_ttl_days: int = 90

    # Phase 15: Incident Impact Scoring
    impact_scoring_enabled: bool = True
    impact_max_records: int = 10000

    # Phase 15: Configuration Drift Detection
    drift_detection_enabled: bool = True
    drift_max_snapshots_per_env: int = 100
    drift_retention_days: int = 30

    # Phase 15: Cost Anomaly Detection
    cost_anomaly_enabled: bool = True
    cost_anomaly_z_threshold: float = 2.5
    cost_anomaly_lookback_days: int = 30

    # Phase 15: Compliance Report Generator
    compliance_reports_enabled: bool = True
    compliance_max_reports: int = 500

    # Phase 15: Agent Performance Benchmarker
    agent_benchmark_enabled: bool = True
    agent_benchmark_baseline_days: int = 30
    agent_benchmark_regression_threshold: float = 0.2

    # Phase 15: Webhook Replay Engine
    webhook_replay_enabled: bool = True
    webhook_replay_max_retries: int = 3
    webhook_replay_max_deliveries: int = 50000

    model_config = {
        "env_prefix": "SHIELDOPS_",
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
