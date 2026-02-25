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
    maintenance_window_max_duration_hours: int = 48

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

    # Phase 16: Dependency Health Tracker
    dependency_health_enabled: bool = True
    dependency_health_max_checks: int = 10000
    dependency_cascade_threshold: int = 3

    # Phase 16: Deployment Freeze Manager
    deployment_freeze_enabled: bool = True
    deployment_freeze_max_windows: int = 200
    deployment_freeze_max_duration_days: int = 30

    # Phase 16: Error Budget Tracker
    error_budget_enabled: bool = True
    error_budget_warning_threshold: float = 0.3
    error_budget_critical_threshold: float = 0.1

    # Phase 16: Alert Grouping Engine
    alert_grouping_enabled: bool = True
    alert_grouping_window_seconds: int = 300
    alert_grouping_max_groups: int = 5000

    # Phase 16: Status Page Manager
    status_page_enabled: bool = True
    status_page_max_components: int = 200
    status_page_max_incidents: int = 1000

    # Phase 16: Rollback Registry
    rollback_registry_enabled: bool = True
    rollback_registry_max_events: int = 10000
    rollback_pattern_lookback_days: int = 90

    # Phase 16: Capacity Reservation System
    capacity_reservation_enabled: bool = True
    capacity_reservation_max_active: int = 500
    capacity_reservation_max_duration_days: int = 90

    # Phase 16: Dependency Vulnerability Mapper
    dep_vuln_mapping_enabled: bool = True
    dep_vuln_max_services: int = 1000
    dep_vuln_max_depth: int = 10

    # Phase 16: Operational Readiness Reviewer
    readiness_review_enabled: bool = True
    readiness_review_max_checklists: int = 200
    readiness_review_passing_threshold: float = 0.8

    # Phase 16: Rate Limit Analytics Engine
    rate_limit_analytics_enabled: bool = True
    rate_limit_analytics_max_events: int = 100000
    rate_limit_analytics_retention_hours: int = 168

    # Phase 16: Agent Decision Explainer
    agent_decision_tracking_enabled: bool = True
    agent_decision_max_records: int = 50000
    agent_decision_retention_days: int = 90

    # Phase 16: Runbook Scheduler
    runbook_scheduler_enabled: bool = True
    runbook_scheduler_max_schedules: int = 500
    runbook_scheduler_lookahead_minutes: int = 60

    # Phase 17: War Room
    war_room_enabled: bool = True
    war_room_max_rooms: int = 500
    war_room_auto_escalate_minutes: int = 30

    # Phase 17: Retrospective
    retrospective_enabled: bool = True
    retrospective_max_retros: int = 1000
    retrospective_action_overdue_days: int = 14

    # Phase 17: Change Risk Scorer
    change_risk_enabled: bool = True
    change_risk_max_records: int = 50000
    change_risk_high_threshold: float = 0.7
    change_risk_critical_threshold: float = 0.9

    # Phase 17: SLA Violation Tracker
    sla_violation_enabled: bool = True
    sla_violation_max_targets: int = 1000
    sla_violation_max_violations: int = 50000

    # Phase 17: Tagging Compliance
    tagging_compliance_enabled: bool = True
    tagging_compliance_max_policies: int = 200
    tagging_compliance_max_records: int = 100000

    # Phase 17: Cost Attribution
    cost_attribution_enabled: bool = True
    cost_attribution_max_rules: int = 500
    cost_attribution_max_entries: int = 100000

    # Phase 17: Cost Normalizer
    cost_normalizer_enabled: bool = True
    cost_normalizer_max_pricing: int = 10000

    # Phase 17: Temporal Patterns
    temporal_patterns_enabled: bool = True
    temporal_patterns_max_events: int = 100000
    temporal_patterns_min_occurrences: int = 3

    # Phase 17: Continuous Compliance
    continuous_compliance_enabled: bool = True
    continuous_compliance_max_controls: int = 5000
    continuous_compliance_max_records: int = 100000

    # Phase 17: Third-Party Risk
    third_party_risk_enabled: bool = True
    third_party_risk_max_vendors: int = 1000
    third_party_risk_reassessment_days: int = 90

    # Phase 17: ROI Tracker
    roi_tracker_enabled: bool = True
    roi_tracker_max_entries: int = 100000

    # Phase 17: Infrastructure Map
    infrastructure_map_enabled: bool = True
    infrastructure_map_max_nodes: int = 10000
    infrastructure_map_max_relationships: int = 50000

    # Phase 18: Secret Rotation
    secret_rotation_enabled: bool = True
    secret_rotation_max_secrets: int = 1000
    secret_rotation_default_days: int = 90

    # Phase 18: Anomaly Correlation
    anomaly_correlation_enabled: bool = True
    anomaly_correlation_max_events: int = 50000
    anomaly_correlation_window_seconds: int = 300

    # Phase 18: Synthetic Monitor
    synthetic_monitor_enabled: bool = True
    synthetic_monitor_max_monitors: int = 500
    synthetic_monitor_max_results: int = 100000
    synthetic_monitor_failure_threshold: int = 3

    # Phase 18: Chaos Experiments
    chaos_experiments_enabled: bool = True
    chaos_experiments_max_experiments: int = 5000
    chaos_experiments_max_results: int = 50000

    # Phase 18: Data Quality
    data_quality_enabled: bool = True
    data_quality_max_rules: int = 1000
    data_quality_max_results: int = 100000
    data_quality_alert_cooldown: int = 3600

    # Phase 18: Canary Tracker
    canary_tracker_enabled: bool = True
    canary_tracker_max_deployments: int = 1000
    canary_tracker_max_metrics: int = 50000

    # Phase 18: Incident Communications
    incident_comms_enabled: bool = True
    incident_comms_max_templates: int = 500
    incident_comms_max_messages: int = 50000

    # Phase 18: Dependency SLA
    dependency_sla_enabled: bool = True
    dependency_sla_max_slas: int = 2000
    dependency_sla_max_evaluations: int = 100000

    # Phase 18: Security Posture Scorer
    posture_scorer_enabled: bool = True
    posture_scorer_max_checks: int = 100000
    posture_scorer_max_scores: int = 10000

    # Phase 18: Workload Fingerprint
    workload_fingerprint_enabled: bool = True
    workload_fingerprint_max_samples: int = 100000
    workload_fingerprint_min_stable: int = 20
    workload_fingerprint_drift_threshold: float = 50.0

    # Phase 18: Maintenance Window
    maintenance_window_enabled: bool = True
    maintenance_window_max_windows: int = 2000

    # Phase 18: Compliance Evidence
    evidence_collector_enabled: bool = True
    evidence_collector_max_evidence: int = 50000
    evidence_collector_max_packages: int = 500

    # Phase 19: Runbook Recommender
    runbook_recommender_enabled: bool = True
    runbook_recommender_max_profiles: int = 1000
    runbook_recommender_max_candidates: int = 10
    runbook_recommender_min_score: float = 0.1

    # Phase 19: Incident Clustering
    incident_clustering_enabled: bool = True
    incident_clustering_max_incidents: int = 50000
    incident_clustering_max_clusters: int = 5000
    incident_clustering_similarity: float = 0.4

    # Phase 19: Policy Generator
    policy_generator_enabled: bool = True
    policy_generator_max_requirements: int = 1000
    policy_generator_max_policies: int = 5000

    # Phase 19: Change Advisory Board
    change_advisory_enabled: bool = True
    change_advisory_max_requests: int = 10000
    change_advisory_max_votes: int = 50000
    change_advisory_auto_approve: float = 0.5

    # Phase 19: SRE Metrics
    sre_metrics_enabled: bool = True
    sre_metrics_max_datapoints: int = 100000
    sre_metrics_max_scorecards: int = 5000

    # Phase 19: Health Reports
    health_report_enabled: bool = True
    health_report_max_reports: int = 10000

    # Phase 19: Approval Delegation
    approval_delegation_enabled: bool = True
    approval_delegation_max_rules: int = 1000
    approval_delegation_max_audit: int = 50000

    # Phase 19: Compliance Gap Analyzer
    gap_analyzer_enabled: bool = True
    gap_analyzer_max_controls: int = 5000
    gap_analyzer_max_gaps: int = 50000

    # Phase 19: Cost Forecast
    cost_forecast_enabled: bool = True
    cost_forecast_max_datapoints: int = 100000
    cost_forecast_max_forecasts: int = 5000
    cost_forecast_alert_threshold: float = 0.9

    # Phase 19: Deployment Risk
    deployment_risk_enabled: bool = True
    deployment_risk_max_records: int = 50000
    deployment_risk_max_assessments: int = 10000

    # Phase 19: Capacity Trends
    capacity_trends_enabled: bool = True
    capacity_trends_max_snapshots: int = 100000
    capacity_trends_max_analyses: int = 10000
    capacity_trends_exhaustion_threshold: float = 0.85

    # Phase 19: Incident Learning
    incident_learning_enabled: bool = True
    incident_learning_max_lessons: int = 10000
    incident_learning_max_applications: int = 50000

    # Phase 20: Tenant Resource Isolation
    tenant_isolation_enabled: bool = True
    tenant_isolation_max_tenants: int = 500
    tenant_isolation_max_violations: int = 50000

    # Phase 20: Alert Noise Analyzer
    alert_noise_enabled: bool = True
    alert_noise_max_records: int = 100000
    alert_noise_threshold: float = 0.3

    # Phase 20: Automated Threshold Tuner
    threshold_tuner_enabled: bool = True
    threshold_tuner_max_thresholds: int = 2000
    threshold_tuner_max_samples: int = 100000

    # Phase 20: Incident Severity Predictor
    severity_predictor_enabled: bool = True
    severity_predictor_max_predictions: int = 50000
    severity_predictor_max_profiles: int = 1000

    # Phase 20: Service Dependency Impact Analyzer
    impact_analyzer_enabled: bool = True
    impact_analyzer_max_dependencies: int = 5000
    impact_analyzer_max_simulations: int = 10000

    # Phase 20: Configuration Audit Trail
    config_audit_enabled: bool = True
    config_audit_max_entries: int = 100000
    config_audit_max_versions_per_key: int = 50

    # Phase 20: Deployment Velocity Tracker
    deployment_velocity_enabled: bool = True
    deployment_velocity_max_events: int = 100000
    deployment_velocity_default_period_days: int = 30

    # Phase 20: Compliance Automation Rule Engine
    compliance_automation_enabled: bool = True
    compliance_automation_max_rules: int = 500
    compliance_automation_max_executions: int = 50000

    # Phase 20: Knowledge Base Article Manager
    knowledge_base_enabled: bool = True
    knowledge_base_max_articles: int = 5000
    knowledge_base_max_votes: int = 50000

    # Phase 20: On-Call Fatigue Analyzer
    oncall_fatigue_enabled: bool = True
    oncall_fatigue_max_events: int = 100000
    oncall_fatigue_burnout_threshold: float = 75.0

    # Phase 20: Backup Verification Engine
    backup_verification_enabled: bool = True
    backup_verification_max_backups: int = 10000
    backup_verification_stale_hours: float = 48.0

    # Phase 20: Cost Allocation Tag Enforcer
    cost_tag_enforcer_enabled: bool = True
    cost_tag_enforcer_max_policies: int = 200
    cost_tag_enforcer_max_checks: int = 100000

    # Phase 21: Disaster Recovery Readiness Tracker
    dr_readiness_enabled: bool = True
    dr_readiness_max_plans: int = 2000
    dr_readiness_drill_max_age_days: int = 90

    # Phase 21: Service Catalog Manager
    service_catalog_enabled: bool = True
    service_catalog_max_services: int = 5000
    service_catalog_stale_days: int = 180

    # Phase 21: API Contract Testing Engine
    contract_testing_enabled: bool = True
    contract_testing_max_schemas: int = 5000
    contract_testing_max_checks: int = 50000

    # Phase 21: Orphaned Resource Detector
    orphan_detector_enabled: bool = True
    orphan_detector_max_resources: int = 50000
    orphan_detector_stale_days: int = 30

    # Phase 21: Service Latency Profiler
    latency_profiler_enabled: bool = True
    latency_profiler_max_samples: int = 500000
    latency_profiler_regression_threshold: float = 0.1

    # Phase 21: Dependency License Compliance Scanner
    license_scanner_enabled: bool = True
    license_scanner_max_dependencies: int = 100000
    license_scanner_max_violations: int = 50000

    # Phase 21: Release Management Tracker
    release_manager_enabled: bool = True
    release_manager_max_releases: int = 10000
    release_manager_require_approval: bool = True

    # Phase 21: Infrastructure Cost Budget Manager
    budget_manager_enabled: bool = True
    budget_manager_max_budgets: int = 2000
    budget_manager_warning_threshold: float = 0.8

    # Phase 21: Configuration Parity Validator
    config_parity_enabled: bool = True
    config_parity_max_configs: int = 5000
    config_parity_max_violations: int = 50000

    # Phase 21: Incident Deduplication Engine
    incident_dedup_enabled: bool = True
    incident_dedup_max_incidents: int = 100000
    incident_dedup_similarity_threshold: float = 0.8

    # Phase 21: Access Certification Manager
    access_certification_enabled: bool = True
    access_certification_max_grants: int = 50000
    access_certification_default_expiry_days: int = 90

    # Phase 21: Toil Measurement Tracker
    toil_tracker_enabled: bool = True
    toil_tracker_max_entries: int = 100000
    toil_tracker_automation_min_occurrences: int = 3

    # Phase 22: Distributed Trace Analyzer
    trace_analyzer_enabled: bool = True
    trace_analyzer_max_traces: int = 500000
    trace_analyzer_bottleneck_threshold: float = 0.2

    # Phase 22: Log Anomaly Detector
    log_anomaly_enabled: bool = True
    log_anomaly_max_patterns: int = 100000
    log_anomaly_sensitivity: float = 0.7

    # Phase 22: Event Correlation Engine
    event_correlation_enabled: bool = True
    event_correlation_max_events: int = 500000
    event_correlation_window_minutes: int = 30

    # Phase 22: Security Incident Response Tracker
    security_incident_enabled: bool = True
    security_incident_max_incidents: int = 50000
    security_incident_auto_escalate_minutes: int = 30

    # Phase 22: Vulnerability Lifecycle Manager
    vuln_lifecycle_enabled: bool = True
    vuln_lifecycle_max_records: int = 100000
    vuln_lifecycle_patch_sla_days: int = 14

    # Phase 22: API Security Monitor
    api_security_enabled: bool = True
    api_security_max_endpoints: int = 50000
    api_security_alert_threshold: float = 0.75

    # Phase 22: Resource Tag Governance Engine
    tag_governance_enabled: bool = True
    tag_governance_max_policies: int = 5000
    tag_governance_max_reports: int = 100000

    # Phase 22: Team Performance Analyzer
    team_performance_enabled: bool = True
    team_performance_max_members: int = 10000
    team_performance_burnout_threshold: float = 0.8

    # Phase 22: Runbook Execution Engine
    runbook_engine_enabled: bool = True
    runbook_engine_max_executions: int = 100000
    runbook_engine_step_timeout: int = 300

    # Phase 22: Dependency Health Scorer
    dependency_scorer_enabled: bool = True
    dependency_scorer_max_dependencies: int = 10000
    dependency_scorer_check_interval: int = 60

    # Phase 22: SLO Burn Rate Predictor
    burn_predictor_enabled: bool = True
    burn_predictor_max_slos: int = 5000
    burn_predictor_forecast_hours: int = 24

    # Phase 22: Change Intelligence Analyzer
    change_intelligence_enabled: bool = True
    change_intelligence_max_records: int = 200000
    change_intelligence_risk_threshold: float = 0.6

    # Phase 23: Database Performance Analyzer
    db_performance_enabled: bool = True
    db_performance_max_queries: int = 200000
    db_performance_slow_threshold_ms: float = 500.0

    # Phase 23: Queue Health Monitor
    queue_health_enabled: bool = True
    queue_health_max_metrics: int = 200000
    queue_health_stall_threshold_seconds: int = 300

    # Phase 23: Certificate Expiry Monitor
    cert_monitor_enabled: bool = True
    cert_monitor_max_certificates: int = 50000
    cert_monitor_expiry_warning_days: int = 30

    # Phase 23: Network Flow Analyzer
    network_flow_enabled: bool = True
    network_flow_max_records: int = 500000
    network_flow_anomaly_threshold: float = 0.8

    # Phase 23: DNS Health Monitor
    dns_health_enabled: bool = True
    dns_health_max_checks: int = 200000
    dns_health_timeout_ms: int = 5000

    # Phase 23: Escalation Pattern Analyzer
    escalation_analyzer_enabled: bool = True
    escalation_analyzer_max_events: int = 100000
    escalation_analyzer_false_alarm_threshold: float = 0.3

    # Phase 23: Capacity Right-Sizing Recommender
    right_sizer_enabled: bool = True
    right_sizer_max_samples: int = 500000
    right_sizer_underutil_threshold: float = 0.3

    # Phase 23: Storage Tier Optimizer
    storage_optimizer_enabled: bool = True
    storage_optimizer_max_assets: int = 100000
    storage_optimizer_cold_threshold_days: int = 90

    # Phase 23: Resource Lifecycle Tracker
    resource_lifecycle_enabled: bool = True
    resource_lifecycle_max_resources: int = 100000
    resource_lifecycle_stale_days: int = 180

    # Phase 23: Alert Routing Optimizer
    alert_routing_enabled: bool = True
    alert_routing_max_records: int = 200000
    alert_routing_reroute_threshold: float = 0.2

    # Phase 23: SLO Target Advisor
    slo_advisor_enabled: bool = True
    slo_advisor_max_samples: int = 500000
    slo_advisor_min_sample_count: int = 100

    # Phase 23: Workload Scheduling Optimizer
    workload_scheduler_enabled: bool = True
    workload_scheduler_max_workloads: int = 50000
    workload_scheduler_conflict_window_seconds: int = 600

    # Phase 24: Cascading Failure Predictor
    cascade_predictor_enabled: bool = True
    cascade_predictor_max_services: int = 50000
    cascade_predictor_max_cascade_depth: int = 10

    # Phase 24: Resilience Score Calculator
    resilience_scorer_enabled: bool = True
    resilience_scorer_max_profiles: int = 50000
    resilience_scorer_minimum_score_threshold: float = 60.0

    # Phase 24: Incident Timeline Reconstructor
    timeline_reconstructor_enabled: bool = True
    timeline_reconstructor_max_events: int = 200000
    timeline_reconstructor_correlation_window_seconds: int = 300

    # Phase 24: Reserved Instance Optimizer
    reserved_instance_optimizer_enabled: bool = True
    reserved_instance_optimizer_max_reservations: int = 100000
    reserved_instance_optimizer_expiry_warning_days: int = 30

    # Phase 24: Cost Anomaly Root Cause Analyzer
    cost_anomaly_rca_enabled: bool = True
    cost_anomaly_rca_max_spikes: int = 100000
    cost_anomaly_rca_deviation_threshold_pct: float = 25.0

    # Phase 24: Spend Allocation Engine
    spend_allocation_enabled: bool = True
    spend_allocation_max_pools: int = 50000
    spend_allocation_min_allocation_threshold: float = 0.01

    # Phase 24: Container Image Scanner
    container_scanner_enabled: bool = True
    container_scanner_max_images: int = 100000
    container_scanner_stale_threshold_days: int = 90

    # Phase 24: Cloud Security Posture Manager
    cloud_posture_manager_enabled: bool = True
    cloud_posture_manager_max_resources: int = 200000
    cloud_posture_manager_auto_resolve_days: int = 30

    # Phase 24: Secrets Sprawl Detector
    secrets_detector_enabled: bool = True
    secrets_detector_max_findings: int = 200000
    secrets_detector_high_severity_threshold: int = 10

    # Phase 24: Runbook Effectiveness Analyzer
    runbook_effectiveness_enabled: bool = True
    runbook_effectiveness_max_outcomes: int = 200000
    runbook_effectiveness_decay_window_days: int = 90

    # Phase 24: API Deprecation Tracker
    api_deprecation_tracker_enabled: bool = True
    api_deprecation_tracker_max_records: int = 100000
    api_deprecation_tracker_sunset_warning_days: int = 30

    # Phase 24: Dependency Freshness Monitor
    dependency_freshness_enabled: bool = True
    dependency_freshness_max_dependencies: int = 200000
    dependency_freshness_stale_version_threshold: int = 3

    # Phase 25: Chaos Experiment Designer
    chaos_designer_enabled: bool = True
    chaos_designer_max_experiments: int = 50000
    chaos_designer_max_blast_radius: int = 3

    # Phase 25: Game Day Planner
    game_day_planner_enabled: bool = True
    game_day_planner_max_game_days: int = 10000
    game_day_planner_min_scenarios_per_day: int = 3

    # Phase 25: Failure Mode Catalog
    failure_mode_catalog_enabled: bool = True
    failure_mode_catalog_max_modes: int = 100000
    failure_mode_catalog_mtbf_window_days: int = 365

    # Phase 25: On-Call Rotation Optimizer
    oncall_optimizer_enabled: bool = True
    oncall_optimizer_max_members: int = 10000
    oncall_optimizer_max_consecutive_days: int = 7

    # Phase 25: Alert Correlation Rule Engine
    alert_correlation_rules_enabled: bool = True
    alert_correlation_rules_max_rules: int = 50000
    alert_correlation_rules_time_window_seconds: int = 300

    # Phase 25: Incident Review Board
    review_board_enabled: bool = True
    review_board_max_reviews: int = 100000
    review_board_action_sla_days: int = 14

    # Phase 25: Cloud Commitment Planner
    commitment_planner_enabled: bool = True
    commitment_planner_max_workloads: int = 100000
    commitment_planner_min_savings_threshold_pct: float = 10.0

    # Phase 25: Cost Simulation Engine
    cost_simulator_enabled: bool = True
    cost_simulator_max_scenarios: int = 50000
    cost_simulator_budget_breach_threshold_pct: float = 20.0

    # Phase 25: FinOps Maturity Scorer
    finops_maturity_enabled: bool = True
    finops_maturity_max_assessments: int = 50000
    finops_maturity_target_level: int = 3

    # Phase 25: Change Failure Rate Tracker
    change_failure_tracker_enabled: bool = True
    change_failure_tracker_max_deployments: int = 200000
    change_failure_tracker_trend_window_days: int = 30

    # Phase 25: Toil Automation Recommender
    toil_recommender_enabled: bool = True
    toil_recommender_max_patterns: int = 100000
    toil_recommender_min_roi_multiplier: float = 2.0

    # Phase 25: SLI Calculation Pipeline
    sli_pipeline_enabled: bool = True
    sli_pipeline_max_definitions: int = 50000
    sli_pipeline_data_retention_hours: int = 168

    # Phase 26: Deployment Cadence Analyzer
    deployment_cadence_enabled: bool = True
    deployment_cadence_max_deployments: int = 200000

    # Phase 26: Metric Baseline Manager
    metric_baseline_enabled: bool = True
    metric_baseline_max_baselines: int = 100000
    metric_baseline_deviation_threshold_pct: float = 25.0

    # Phase 26: Incident Timeline Analyzer
    incident_timeline_enabled: bool = True
    incident_timeline_max_entries: int = 200000
    incident_timeline_target_resolution_minutes: int = 60

    # Phase 26: Service Health Aggregator
    service_health_agg_enabled: bool = True
    service_health_agg_max_signals: int = 500000
    service_health_agg_health_threshold: float = 70.0

    # Phase 26: Alert Fatigue Scorer
    alert_fatigue_enabled: bool = True
    alert_fatigue_max_records: int = 500000
    alert_fatigue_threshold: float = 70.0

    # Phase 26: Change Window Optimizer
    change_window_enabled: bool = True
    change_window_max_records: int = 200000
    change_window_min_success_rate: float = 90.0

    # Phase 26: Resource Waste Detector
    resource_waste_enabled: bool = True
    resource_waste_max_records: int = 200000
    resource_waste_idle_threshold_pct: float = 5.0

    # Phase 26: Compliance Evidence Chain
    evidence_chain_enabled: bool = True
    evidence_chain_max_chains: int = 50000
    evidence_chain_max_items_per_chain: int = 10000

    # Phase 26: Dependency Update Planner
    dependency_update_planner_enabled: bool = True
    dependency_update_planner_max_updates: int = 100000
    dependency_update_planner_max_risk_threshold: int = 3

    # Phase 26: Capacity Forecast Engine
    capacity_forecast_engine_enabled: bool = True
    capacity_forecast_engine_max_data_points: int = 500000
    capacity_forecast_engine_headroom_target_pct: float = 70.0

    # Phase 26: Runbook Version Manager
    runbook_versioner_enabled: bool = True
    runbook_versioner_max_versions: int = 100000
    runbook_versioner_stale_age_days: int = 90

    # Phase 26: Team Skill Matrix
    team_skill_matrix_enabled: bool = True
    team_skill_matrix_max_entries: int = 100000
    team_skill_matrix_min_coverage_per_domain: int = 2

    # Phase 27: Error Budget Policy Engine
    error_budget_policy_enabled: bool = True
    error_budget_policy_max_policies: int = 50000
    error_budget_policy_warning_threshold_pct: float = 50.0

    # Phase 27: Reliability Target Advisor
    reliability_target_enabled: bool = True
    reliability_target_max_targets: int = 50000
    reliability_target_default_target_pct: float = 99.9

    # Phase 27: Incident Severity Calibrator
    severity_calibrator_enabled: bool = True
    severity_calibrator_max_records: int = 200000
    severity_calibrator_accuracy_target_pct: float = 85.0

    # Phase 27: Service Dependency Mapper
    dependency_mapper_enabled: bool = True
    dependency_mapper_max_edges: int = 200000
    dependency_mapper_max_chain_depth: int = 10

    # Phase 27: Alert Rule Linter
    alert_rule_linter_enabled: bool = True
    alert_rule_linter_max_rules: int = 100000
    alert_rule_linter_min_quality_score: float = 80.0

    # Phase 27: Deployment Approval Gate
    deployment_gate_enabled: bool = True
    deployment_gate_max_gates: int = 100000
    deployment_gate_expiry_hours: int = 24

    # Phase 27: Cloud Billing Reconciler
    billing_reconciler_enabled: bool = True
    billing_reconciler_max_records: int = 500000
    billing_reconciler_discrepancy_threshold_pct: float = 5.0

    # Phase 27: Cost Chargeback Engine
    chargeback_engine_enabled: bool = True
    chargeback_engine_max_records: int = 500000
    chargeback_engine_unallocated_threshold_pct: float = 5.0

    # Phase 27: Compliance Drift Detector
    compliance_drift_enabled: bool = True
    compliance_drift_max_records: int = 200000
    compliance_drift_max_drift_rate_pct: float = 5.0

    # Phase 27: Incident Communication Planner
    comm_planner_enabled: bool = True
    comm_planner_max_plans: int = 100000
    comm_planner_max_overdue_minutes: int = 30

    # Phase 27: Infrastructure Drift Reconciler
    infra_drift_reconciler_enabled: bool = True
    infra_drift_reconciler_max_drifts: int = 200000
    infra_drift_reconciler_auto_reconcile_enabled: bool = True

    # Phase 27: Service Maturity Model
    service_maturity_enabled: bool = True
    service_maturity_max_assessments: int = 100000
    service_maturity_target_level: int = 3

    # Phase 28: Capacity Right-Timing Advisor
    capacity_right_timing_enabled: bool = True
    capacity_right_timing_max_records: int = 200000
    capacity_right_timing_lookahead_hours: int = 24

    # Phase 28: Predictive Outage Detector
    outage_predictor_enabled: bool = True
    outage_predictor_max_records: int = 300000
    outage_predictor_composite_threshold: float = 0.75

    # Phase 28: Incident Impact Quantifier
    impact_quantifier_enabled: bool = True
    impact_quantifier_max_assessments: int = 100000
    impact_quantifier_default_hourly_rate_usd: float = 150.0

    # Phase 28: Policy Violation Tracker
    policy_violation_tracker_enabled: bool = True
    policy_violation_tracker_max_records: int = 500000
    policy_violation_tracker_repeat_threshold: int = 5

    # Phase 28: Deployment Health Scorer
    deploy_health_scorer_enabled: bool = True
    deploy_health_scorer_max_records: int = 200000
    deploy_health_scorer_failing_threshold: float = 40.0

    # Phase 28: Runbook Gap Analyzer
    runbook_gap_analyzer_enabled: bool = True
    runbook_gap_analyzer_max_gaps: int = 100000
    runbook_gap_analyzer_critical_incident_threshold: int = 3

    # Phase 28: Credential Expiry Forecaster
    credential_expiry_forecaster_enabled: bool = True
    credential_expiry_forecaster_max_records: int = 200000
    credential_expiry_forecaster_warning_days: int = 30

    # Phase 28: On-Call Workload Balancer
    oncall_workload_balancer_enabled: bool = True
    oncall_workload_balancer_max_records: int = 200000
    oncall_workload_balancer_imbalance_threshold_pct: float = 30.0

    # Phase 28: Cost Anomaly Predictor
    cost_anomaly_predictor_enabled: bool = True
    cost_anomaly_predictor_max_records: int = 300000
    cost_anomaly_predictor_spike_threshold_usd: float = 1000.0

    # Phase 28: Compliance Evidence Scheduler
    evidence_scheduler_enabled: bool = True
    evidence_scheduler_max_schedules: int = 50000
    evidence_scheduler_overdue_grace_days: int = 7

    # Phase 28: API Latency Budget Tracker
    latency_budget_tracker_enabled: bool = True
    latency_budget_tracker_max_records: int = 500000
    latency_budget_tracker_chronic_violation_threshold: int = 10

    # Phase 28: Change Conflict Detector
    change_conflict_detector_enabled: bool = True
    change_conflict_detector_max_records: int = 100000
    change_conflict_detector_lookahead_hours: int = 168

    # Phase 29: Incident Duration Predictor
    duration_predictor_enabled: bool = True
    duration_predictor_max_records: int = 200000
    duration_predictor_accuracy_target_pct: float = 80.0

    # Phase 29: Resource Exhaustion Forecaster
    resource_exhaustion_enabled: bool = True
    resource_exhaustion_max_records: int = 200000
    resource_exhaustion_default_critical_hours: float = 12.0

    # Phase 29: Alert Storm Correlator
    alert_storm_correlator_enabled: bool = True
    alert_storm_correlator_max_records: int = 200000
    alert_storm_correlator_storm_window_seconds: float = 300.0

    # Phase 29: Deployment Canary Analyzer
    canary_analyzer_enabled: bool = True
    canary_analyzer_max_records: int = 200000
    canary_analyzer_deviation_threshold_pct: float = 10.0

    # Phase 29: Service Dependency SLA Cascader
    sla_cascader_enabled: bool = True
    sla_cascader_max_records: int = 200000
    sla_cascader_min_acceptable_sla_pct: float = 99.0

    # Phase 29: Incident Handoff Tracker
    handoff_tracker_enabled: bool = True
    handoff_tracker_max_records: int = 200000
    handoff_tracker_quality_threshold: float = 0.7

    # Phase 29: Cost Unit Economics Engine
    unit_economics_enabled: bool = True
    unit_economics_max_records: int = 200000
    unit_economics_high_cost_threshold: float = 0.01

    # Phase 29: Idle Resource Detector
    idle_resource_detector_enabled: bool = True
    idle_resource_detector_max_records: int = 200000
    idle_resource_detector_idle_threshold_pct: float = 5.0

    # Phase 29: SLA Penalty Calculator
    penalty_calculator_enabled: bool = True
    penalty_calculator_max_records: int = 200000
    penalty_calculator_default_credit_multiplier: float = 1.0

    # Phase 29: Security Posture Trend Analyzer
    posture_trend_enabled: bool = True
    posture_trend_max_records: int = 200000
    posture_trend_regression_threshold: float = 5.0

    # Phase 29: Compliance Evidence Freshness Monitor
    evidence_freshness_enabled: bool = True
    evidence_freshness_max_records: int = 200000
    evidence_freshness_stale_days: int = 90

    # Phase 29: Access Anomaly Detector
    access_anomaly_enabled: bool = True
    access_anomaly_max_records: int = 200000
    access_anomaly_threat_threshold: float = 0.7

    model_config = {
        "env_prefix": "SHIELDOPS_",
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
