# ShieldOps — Feature Implementation Tracker

**Last Updated:** 2026-02-22
**Platform Completeness:** Phase 9 complete — all 12 features shipped

---

## Phase 2 — Multi-Cloud & Security Hardening

### P0 — Critical (Blocks Multi-Cloud Story)

- [x] **GCP Connector** — Full `InfraConnector` implementation for Compute Engine + Cloud Run
  - File: `src/shieldops/connectors/gcp/connector.py` (505 LOC, 37 tests)
  - Pattern: Follow AWS connector — lazy client init, async wrappers, 7 methods
  - Services: Compute Engine (instances), Cloud Run (services)
  - Auth: Application Default Credentials via `google-cloud-compute`, `google-cloud-run`
  - Tests: `tests/unit/test_gcp_connector.py`

- [x] **Azure Connector** — Full `InfraConnector` implementation for VMs + Container Apps
  - File: `src/shieldops/connectors/azure/connector.py` (572 LOC, 49 tests)
  - Pattern: Follow AWS connector — lazy client init, async wrappers, 7 methods
  - Services: Virtual Machines, Container Apps
  - Auth: DefaultAzureCredential via `azure-mgmt-compute`, `azure-mgmt-appcontainers`
  - Tests: `tests/unit/test_azure_connector.py`

- [x] **Settings + Factory Wiring** — Add GCP/Azure config to Settings, register in factory
  - Files: `src/shieldops/config/settings.py`, `src/shieldops/connectors/factory.py`
  - Settings: `gcp_project_id`, `gcp_region`, `azure_subscription_id`, `azure_resource_group`

### P1 — High (Security Agent Backends)

- [x] **NVD CVE Source** — `CVESource` implementation using NIST NVD API 2.0
  - File: `src/shieldops/integrations/cve/nvd.py` (261 LOC, 22 tests)
  - Protocol: `CVESource.scan(resource_id, severity_threshold) -> list[dict]`
  - Features: CVSS v3.1 scoring, package-name correlation, rate-limit handling
  - Tests: `tests/unit/test_nvd_cve_source.py`

- [x] **AWS Secrets Manager Credential Store** — `CredentialStore` implementation
  - File: `src/shieldops/integrations/credentials/aws_secrets.py` (181 LOC, 15 tests)
  - Protocol: `CredentialStore.list_credentials()`, `rotate_credential()`
  - Features: Secret listing with rotation metadata, rotation via SDK
  - Tests: `tests/unit/test_aws_credential_store.py`

- [x] **HashiCorp Vault Credential Store** — `CredentialStore` implementation
  - File: `src/shieldops/integrations/credentials/vault.py` (271 LOC, 26 tests)
  - Protocol: Same as above
  - Features: KV v2 read/write, database credential rotation, lease management

### P2 — Medium (Production Readiness)

- [x] **AWS CloudTrail Integration** — Real `get_events()` via CloudTrail LookupEvents
  - File: `src/shieldops/connectors/aws/connector.py`
  - Features: Pagination (2 pages), structured event parsing, error handling
  - Tests: 6 new tests in `tests/unit/test_aws_connector.py`

- [x] **Compliance Framework Integration** — Real infra checks per control
  - File: `src/shieldops/agents/security/tools.py`
  - Supports: SOC2, PCI-DSS, HIPAA, CIS frameworks with 12 control evaluators
  - Tests: 23 tests in `tests/unit/test_security_tools_compliance.py`

- [x] **Playbook Wiring** — Playbooks loaded into remediation agent workflow
  - Files: models.py, tools.py, nodes.py, graph.py, runner.py (remediation agent)
  - Features: `resolve_playbook` node, playbook-driven validation checks
  - Tests: 16 tests in `tests/unit/test_playbook_wiring.py`

### P3 — Low (Polish)

- [x] **Additional OPA Policies** — Expand policy coverage
  - Compliance mapping Rego policy (SOC2, PCI-DSS, HIPAA, CIS controls) — `playbooks/policies/compliance.rego`, 13 tests
  - Per-team action scoping policy — `playbooks/policies/team_scoping.rego`, 10 tests
  - Extended rate limiting (per-minute burst + per-team hourly) — `playbooks/policies/rate_limits.rego`, 26 tests
  - PolicyEngine enrichment: team, resource_labels, actions_this_minute, team_actions_this_hour

- [x] **Integration Tests** — E2E flows for new connectors
  - GCP fake connector + integration tests — `tests/integration/fakes/gcp_fake.py`, 17 tests
  - Azure fake connector + integration tests — `tests/integration/fakes/azure_fake.py`, 16 tests
  - Cross-connector remediation flow tests — 9 tests (multi-provider routing, rollback, failure isolation)

---

## Phase 3 — Event-Driven Architecture & Production Hardening

### P0 — Critical (Core Infrastructure)

- [x] **Kafka Event Bus** — Producer/consumer framework for agent event streaming
  - New module: `src/shieldops/messaging/` (bus.py, producer.py, consumer.py, topics.py)
  - aiokafka-based async producer + consumer with topic routing
  - Topics: `shieldops.events`, `shieldops.agent.results`, `shieldops.audit`
  - EventEnvelope Pydantic model with serialize/deserialize helpers
  - Tests: `tests/unit/test_kafka_event_bus.py` — 43 tests

- [x] **WebSocket Broadcasting Wiring** — Connect ws_manager to agent runners
  - Singleton `get_ws_manager()` in `src/shieldops/api/ws/manager.py`
  - Injected into InvestigationRunner + RemediationRunner in app.py lifespan
  - WS routes now share the same ConnectionManager instance
  - Tests: `tests/unit/test_ws_broadcasting.py` — 15 tests

### P1 — High (Agent Completeness)

- [x] **GCP Cloud Audit Log Events** — Real `get_events()` for GCP connector
  - File: `src/shieldops/connectors/gcp/connector.py` — Cloud Logging API integration
  - Compute Engine + Cloud Run resource-scoped audit log queries
  - Structured event parsing with actor, severity, details
  - Tests: 6 new tests in `tests/unit/test_gcp_connector.py`

- [x] **Azure Activity Log Events** — Real `get_events()` for Azure connector
  - File: `src/shieldops/connectors/azure/connector.py` — Activity Log API integration
  - VM + Container App resource-scoped activity queries via azure-mgmt-monitor
  - OData filtering, structured event parsing, null-field robustness
  - Tests: 7 new tests in `tests/unit/test_azure_connector.py`

- [x] **Learning Agent Persistence** — Persist learning cycles to DB
  - New ORM model: `LearningCycleRecord` in `src/shieldops/db/models.py`
  - New repo methods: `save_learning_cycle()`, `query_learning_cycles()` in repository.py
  - `LearningRunner.learn()` now persists completed cycles (graceful on failure)
  - Tests: `tests/unit/test_learning_persistence.py` — 23 tests

- [x] **Notification Service** — PagerDuty + unified notification dispatch
  - New module: `src/shieldops/integrations/notifications/` (base.py, pagerduty.py, dispatcher.py)
  - PagerDuty Events API v2 with severity mapping, summary truncation
  - `NotificationDispatcher` with register/send/broadcast + channel routing
  - Wired into SupervisorRunner notification_channels in app.py
  - Tests: `tests/unit/test_notification_service.py` — 34 tests

### P2 — Medium (Operational Maturity)

- [x] **Scheduled Job Framework** — Periodic task triggers for agents
  - New module: `src/shieldops/scheduler/` (scheduler.py, jobs.py)
  - Lightweight asyncio-based scheduler (no APScheduler dependency)
  - Jobs: nightly learning (24h), security scan (6h), cost analysis (24h)
  - Wired into app.py lifespan with graceful shutdown
  - Tests: `tests/unit/test_scheduler.py` — 42 tests

- [x] **AWS Cost Explorer Billing Source** — Real billing data for cost agent
  - New module: `src/shieldops/integrations/billing/` (base.py, aws_cost_explorer.py)
  - Protocol: `BillingSource.query(environment, period) -> BillingData`
  - AWS Cost Explorer: GetCostAndUsage with service grouping + daily breakdown
  - Wired into CostRunner.billing_sources in app.py
  - Tests: `tests/unit/test_aws_billing_source.py` — 33 tests

- [x] **Cleanup Legacy Supervisor Stub** — Remove dead orchestration/supervisor.py
  - Deleted `src/shieldops/orchestration/supervisor.py` and its test file
  - Verified no imports reference it (agents/supervisor/ is the real impl)
  - Updated README.md and build-agent.md referencing the old path

### P3 — Low (Developer Experience)

- [x] **New Claude Code Skills** — Workspace-specific development skills
  - `add-connector` — Scaffold a new infrastructure connector following InfraConnector protocol
  - `add-integration` — Scaffold a new integration (billing, notification, etc.)
  - `run-agent` — Test-run an agent workflow locally with mock data
  - `check-health` — Run health checks on all platform dependencies

---

## Phase 4 — Production Readiness & Frontend

### P0 — Critical (Production Hardening)

- [x] **Prometheus Metrics** — `/metrics` endpoint with request/agent/system histograms
  - Module: `src/shieldops/api/middleware/metrics.py`
  - Custom MetricsRegistry with counter, histogram, gauge support
  - Tests: `tests/unit/test_prometheus_metrics.py`

- [x] **Slack Notifications** — SlackNotifier via Incoming Webhooks
  - File: `src/shieldops/integrations/notifications/slack.py`
  - Severity-based formatting, channel routing, Block Kit
  - Tests: `tests/unit/test_slack_notifier.py`

- [x] **Email Notifications** — SMTP-based EmailNotifier
  - File: `src/shieldops/integrations/notifications/email.py`
  - Async SMTP (aiosmtplib), HTML templates, TLS support
  - Tests: `tests/unit/test_email_notifier.py`

- [x] **Circuit Breakers + Retry** — Resilience patterns for external calls
  - Module: `src/shieldops/utils/resilience.py`
  - CircuitBreaker (closed/open/half-open), retry_with_backoff decorator
  - Tests: `tests/unit/test_resilience.py`

### P1 — High (Infrastructure Reliability)

- [x] **Kafka Dead Letter Queue** — Failed message handling
  - File: `src/shieldops/messaging/dlq.py`
  - `shieldops.dlq` topic, retry tracking, max-retry threshold
  - Tests: `tests/unit/test_kafka_dlq.py`

- [x] **Redis Distributed Locking** — Leader election and mutex
  - File: `src/shieldops/utils/distributed_lock.py`
  - Lua-based atomic acquire/release, heartbeat renewal
  - Tests: `tests/unit/test_distributed_lock.py`

- [x] **Graceful Shutdown** — Zero-downtime shutdown middleware
  - File: `src/shieldops/api/middleware/shutdown.py`
  - Request draining, health check degradation, signal handling
  - Tests: `tests/unit/test_graceful_shutdown.py`

- [x] **Webhook Notifications** — HTTP callback notification channel
  - File: `src/shieldops/integrations/notifications/webhook.py`
  - HMAC-SHA256 signing, configurable retry, custom headers
  - Tests: `tests/unit/test_webhook_notifier.py`

### P2 — Medium (Frontend & Operations)

- [x] **React Dashboard** — Full SPA with 11 pages
  - Tech: React 18 + TypeScript + Tailwind CSS + Vite
  - Pages: Login, FleetOverview, Analytics, Investigations/Detail, Remediations/Detail, Security, Cost, Learning, Settings
  - Components: Layout, Sidebar, Header, DataTable, MetricCard, StatusBadge, LoadingSpinner
  - State: @tanstack/react-query, Zustand auth store, WebSocket hook
  - Docker: Multi-stage build (Node → Nginx) with SPA routing

- [x] **Deployment Docs** — Multi-cloud deployment guide + quickstart
  - Files: `docs/DEPLOYMENT.md` (750 LOC), `docs/QUICKSTART_DEMO.md`
  - Covers: Local dev, AWS, GCP, Azure, Kubernetes, CI/CD, troubleshooting

- [x] **Makefile** — 27 development and deployment targets
  - Targets: dev, setup, run, test, lint, format, build, push, deploy, seed, docs

- [x] **Grafana + Prometheus Monitoring** — Dashboards, alerts, recording rules
  - Files: `infrastructure/monitoring/grafana/shieldops-overview.json`
  - Prometheus: 12 alert rules, 12 recording rules, scrape config

- [x] **Seed Data Script** — Demo data for local development
  - File: `scripts/seed_demo_data.py`
  - Seeds: 3 users, 6 agents, 10 investigations, 8 remediations, 3 security scans

---

## Phase 5.5 — Platform Hardening (12 Items)

- [x] Wire ApprovalNotifier to ApprovalWorkflow (Slack notifications)
- [x] Durable snapshot state for connectors (DB fallback on rollback)
- [x] Wire Analytics dashboard to backend (MTTR, resolution rate, accuracy charts)
- [x] Create AlertConfigStoreAdapter for Learning Agent
- [x] Add rollback button + confirmation modal to RemediationDetail
- [x] Wire Kafka EventBus in app lifespan (alert → investigation pipeline)
- [x] Historical pattern matching for Investigation Agent
- [x] Integration tests for Cost and Learning agents (9 tests)
- [x] Settings notification config (full-stack: ORM + API + dashboard)
- [x] Kafka and Redis K8s StatefulSet manifests
- [x] ExternalSecrets CRD for AWS Secrets Manager
- [x] OPA Policy ConfigMap + CI sync job
- [x] Fix pre-existing ruff (12) and mypy (61) errors for CI

---

## Phase 6 — Enterprise Readiness & Scanner Activation

### P0 — Critical (Core Value Prop & Enterprise Blockers)

- [x] **Wire Security Scanners into Security Runner** — Activate IaC, git, k8s, network scanners
  - Files: `src/shieldops/api/app.py`, `src/shieldops/config/settings.py`
  - 4 scanner types: IaC, Git (secrets+deps), K8s, Network — all opt-in via settings
  - Tests: `tests/unit/test_scanner_wiring.py` — 7 tests

- [x] **Audit Log API + Dashboard Page** — Expose immutable audit trail
  - Backend: `src/shieldops/api/routes/audit.py` — GET /audit-logs (paginated, filterable)
  - Dashboard: `dashboard-ui/src/pages/AuditLog.tsx` — table with filters + pagination
  - Tests: `tests/unit/api/test_audit_routes.py` — 4 tests

- [x] **SSO / OIDC Authentication** — Enterprise identity provider support
  - Module: `src/shieldops/auth/oidc.py` — OIDCClient (discovery, auth URL, exchange, userinfo)
  - Routes: `GET /auth/oidc/login`, `GET /auth/oidc/callback` — redirect flow
  - Auto-provision users on first OIDC login with viewer role
  - Dashboard: "Sign in with SSO" button on Login page
  - Tests: `tests/unit/auth/test_oidc.py` — 11 tests

- [x] **Helm Chart** — Parameterized K8s deployment for enterprise customers
  - Directory: `infrastructure/helm/shieldops/` — 15 templates
  - Chart.yaml with Bitnami dependencies (PostgreSQL, Redis, Kafka)
  - values.yaml (250+ lines), ingress, HPA, PDB, NetworkPolicy, ServiceMonitor
  - `helm lint --strict` passes clean

### P1 — High (Multi-Cloud Completeness & Data Isolation)

- [x] **GCP Cloud Billing Source** — Cost agent support for GCP
  - File: `src/shieldops/integrations/billing/gcp_billing.py` — BigQuery billing export
  - Tests: `tests/unit/integrations/billing/test_gcp_billing.py` — 16 tests

- [x] **Azure Cost Management Source** — Cost agent support for Azure
  - File: `src/shieldops/integrations/billing/azure_cost.py` — Cost Management Query API
  - Tests: `tests/unit/integrations/billing/test_azure_billing.py` — 24 tests

- [x] **Playbooks Dashboard Page** — View, search, and trigger playbooks
  - File: `dashboard-ui/src/pages/Playbooks.tsx` — card grid, search, YAML expansion, trigger

- [x] **Multi-Org / Tenant Isolation** — Organization-scoped data access
  - ORM: `OrganizationRecord`, Migration 009, `TenantMiddleware`
  - API: `GET/POST /organizations`, `PUT /organizations/{id}` (admin only)
  - Tests: 14 new tests (API CRUD + middleware), zero regressions

- [x] **User Management API + Dashboard** — Full user lifecycle
  - Routes: `src/shieldops/api/routes/users.py` — GET /users, PUT role, PUT active
  - Dashboard: `dashboard-ui/src/pages/UserManagement.tsx` — table, role editor, invite modal

### P2 — Medium (Observability & Polish)

- [x] **OTel Metrics Pipeline** — Agent-level metrics via OpenTelemetry
  - File: `src/shieldops/observability/otel/metrics.py` — MeterProvider + OTLP exporter
  - AgentMetrics class: execution counter, error counter, duration histogram
  - Tests: `tests/unit/observability/test_otel_metrics.py` — 5 tests

- [x] **LangSmith Agent Tracing** — Debug and replay agent workflows
  - File: `src/shieldops/observability/langsmith.py` — init_langsmith(), get_client()
  - Conditional activation via `langsmith_enabled` setting
  - Tests: `tests/unit/observability/test_langsmith.py` — 3 tests

- [x] **Refresh Tokens + Revocation** — Secure token lifecycle
  - Routes: `POST /auth/refresh`, `POST /auth/revoke` (Redis JTI blacklist)
  - JTI field added to JWT payload in service.py
  - Tests: `tests/unit/auth/test_refresh_revoke.py` — 4 tests

- [x] **Terraform State Backend + CI** — Safe infrastructure-as-code workflow
  - Updated S3/GCS/Azure backend blocks in all 3 main.tf files
  - New CI job: `terraform-plan` on PRs (matrix: aws, gcp, azure)

- [x] **Dashboard Page Tests** — Vitest coverage for all 13 pages
  - 7 new test files: Analytics, Security, Cost, Learning, Settings, Investigations, Remediations
  - ResizeObserver polyfill for recharts in jsdom
  - 48 total dashboard tests passing (13 test files)

---

## Phase 7 — Enterprise SaaS & Developer Platform

### P0 — Critical (Enterprise SaaS Requirements)

- [x] **Multi-Org / Tenant Isolation** — Organization-scoped data access
  - ORM: `OrganizationRecord`, Migration 009, `TenantMiddleware`
  - API: `GET/POST /organizations`, `PUT /organizations/{id}` (admin only)
  - Tests: 14 new tests (API CRUD + middleware), zero regressions

- [x] **Fine-grained RBAC / Permissions** — Resource-level access control
  - Module: `src/shieldops/api/auth/permissions.py` — `require_permission(resource, action)`
  - Seed permissions: admin (all), operator (CRUD), viewer (read-only)
  - API: `GET /permissions`, `PUT /permissions/{id}` (admin only)
  - Tests: Permission checks, role escalation prevention, default deny

- [x] **API Rate Limiting v2** — Per-tenant sliding window with Redis
  - Module: `src/shieldops/api/middleware/sliding_window.py` — sliding window algorithm
  - Per-tenant limits, per-endpoint tiers, X-RateLimit-* headers
  - Tests: Sliding window accuracy, tenant isolation, header correctness

### P1 — High (Developer Platform & Quality)

- [x] **Agent Context Store** — Persistent cross-incident memory for agents
  - ORM: `AgentContextRecord`, Migration 010: `agent_context` table
  - Module: `src/shieldops/agents/context_store.py` — get/set/search with TTL
  - Tests: CRUD, TTL expiry, search by key pattern

- [x] **Python SDK Client** — `shieldops-sdk` package for programmatic API access
  - Directory: `sdk/` — sync `ShieldOpsClient` + async `AsyncShieldOpsClient`
  - Resources: investigations, remediations, security_scans, vulnerabilities, agents
  - Tests: 32 tests covering all resources, error handling, pagination

- [x] **E2E Playwright Tests** — Coverage for new dashboard pages
  - Specs: `audit-log.spec.ts`, `playbooks.spec.ts`, `user-management.spec.ts`, `analytics.spec.ts`
  - Updated fixtures with mock data for new pages

- [x] **CLI Tool** — Command-line interface for ShieldOps operations
  - Module: `src/shieldops/cli/` — status, investigate, remediate, scan, agents commands
  - Click-based with table/JSON output, auth support
  - Tests: 31 tests (26 new + 5 legacy)

### P2 — Medium (Operational Confidence & Documentation)

- [x] **k6 Load Testing Suite** — Performance validation scripts
  - Directory: `tests/load/` — smoke, API CRUD, auth flow, read-heavy, WebSocket scenarios
  - Thresholds: p95 < 200ms reads, p95 < 500ms writes, error rate < 1%
  - Makefile targets: `make load-test`, `load-test-full`, `load-test-stress`

- [x] **MkDocs Documentation Site** — Structured docs from existing markdown
  - `mkdocs.yml` with Material theme, 30+ pages across 7 sections
  - Structure: Getting Started, Architecture, API Reference, Agents, Deployment, Contributing

- [x] **OpenAPI Enhancement + API Versioning** — Production API contract
  - Module: `src/shieldops/api/schemas/responses.py` — 10 typed Pydantic response models
  - `APIVersionMiddleware` + `GET /api/v1/changelog`
  - TypeScript generation script: `scripts/generate_types.sh`
  - Tests: 32 tests (response models + versioning)

---

## Phase 8 — Revenue Readiness & Operational Excellence

### P0 — Critical (Revenue & Demo Impact)

- [x] **API Key Management** — Service account API keys for programmatic access
  - ORM: `APIKeyRecord`, Migration 011, `src/shieldops/api/auth/api_keys.py`
  - Auth middleware enhanced: `sk-` prefixed keys alongside JWT
  - API: `POST /api-keys`, `GET /api-keys`, `DELETE /api-keys/{id}`
  - Tests: 28 tests (key generation, scope validation, expiry, ownership)

- [x] **Data Export / Compliance Reports** — CSV/PDF export for enterprise compliance
  - Module: `src/shieldops/api/routes/exports.py` + `src/shieldops/utils/export_helpers.py`
  - Endpoints: `/export/investigations`, `/export/remediations`, `/export/compliance`
  - CSV streaming + JSON, OWASP CSV injection prevention
  - Tests: 30 tests (format, filters, sanitization, auth)

- [x] **Dashboard Real-time Updates** — WebSocket-powered live data refresh
  - Hook: `useRealtimeUpdates.ts` with Zustand connection store
  - Components: `ConnectionStatus`, `LiveIndicator` (pulse animation)
  - Wired into: Layout, Header, FleetOverview, Investigations, Remediations
  - Exponential backoff reconnection, React Query cache invalidation

- [x] **Incident Timeline View** — Unified investigation lifecycle page
  - Page: `IncidentTimeline.tsx` + reusable `Timeline.tsx` component
  - API: `GET /investigations/{id}/timeline` — merged events
  - Color-coded event types, expandable details, filter bar
  - Tests: 10 tests

### P1 — High (Monetization & Self-Service)

- [x] **Stripe Billing Integration** — Subscription management for SaaS
  - Module: `src/shieldops/integrations/billing/stripe_billing.py`
  - Plans: Free (5 agents), Pro (25), Enterprise (unlimited)
  - API: checkout, subscription, usage, webhook handler (4 event types)
  - Dashboard: Billing page with usage meters + plan comparison cards
  - Tests: 23 tests

- [x] **Custom Playbook Editor** — In-dashboard YAML editor for playbooks
  - Backend: `playbook_crud.py` — 7 endpoints with YAML validation + dangerous action blocking
  - ORM: `PlaybookRecord`, Migration 012
  - Dashboard: Split-pane editor with validate/dry-run preview
  - Tests: 21 tests

- [x] **Batch Operations API** — Bulk management for enterprise scale
  - Module: `src/shieldops/api/routes/batch.py`
  - 4 endpoints: bulk create investigations/remediations, update status, job polling
  - 202 async processing, partial failure handling, 1-hour job expiry
  - Tests: 26 tests

- [x] **Agent Performance Dashboard** — Dedicated metrics visualization
  - Page: `AgentPerformance.tsx` with line/bar/heatmap charts
  - API: `GET /analytics/agent-performance` with deterministic demo data
  - Sortable breakdown table with color-coded success rates
  - Tests: 13 tests

### P2 — Medium (Operational Maturity)

- [x] **Health Check Dashboard** — System dependency status page
  - API: `GET /health/detailed` — concurrent DB/Redis/Kafka/OPA checks with 2s timeout
  - Dashboard: `SystemHealth.tsx` with status banner, 4 service cards, auto-refresh
  - Overall status: healthy/degraded/unhealthy logic
  - Tests: 16 tests

- [x] **Notification Preferences API** — Per-user notification settings
  - ORM: `NotificationPreferenceRecord`, Migration 013, unique constraint
  - API: list/upsert/delete preferences + event types listing
  - 12 event types x 4 channels, toggle grid in Settings page
  - Tests: 15 tests

- [x] **API Usage Analytics** — Per-tenant usage tracking and dashboard
  - Middleware: `UsageTrackerMiddleware` — in-memory per-org/endpoint/hour tracking
  - API: 4 endpoints (usage, top endpoints, hourly, by-org)
  - Dashboard: API Usage section in Analytics page with charts + tables
  - Tests: 33 tests

- [x] **Global Search** — Unified search across all entities
  - API: `GET /search` — parallel ILIKE across 3 entity types, relevance scoring
  - Dashboard: `GlobalSearch.tsx` — Cmd+K command palette with keyboard nav
  - Recent searches in localStorage, debounced, grouped results
  - Tests: 25 tests

---

## Phase 9 — Growth & Enterprise Differentiation

### Tier 1 — Investor/Demo Impact (Revenue-Critical)

- [x] **Multi-tenant Billing Enforcement** — Wire Stripe plans to feature gates
  - Middleware: enforce agent limits, API call quotas per org based on plan
  - Module: `src/shieldops/api/middleware/billing_enforcement.py`
  - Wire: check org plan on agent creation, API call counting against quota
  - Dashboard: usage meters on Settings page, upgrade prompts on limit hit
  - Tests: quota enforcement, plan upgrade/downgrade, grace period

- [x] **Onboarding Wizard** — Guided setup flow for new organizations
  - Backend: `src/shieldops/api/routes/onboarding.py` — step tracking, cloud validation
  - Dashboard: `OnboardingWizard.tsx` — 5 steps (org, cloud, agent, playbook, demo)
  - Features: cloud credential validation, first agent deployment, demo trigger
  - Tests: step progression, validation, skip/resume

- [x] **Agent Marketplace / Templates** — Pre-built agent configs for common scenarios
  - Backend: `src/shieldops/api/routes/marketplace.py` — template CRUD + deploy
  - Templates: `playbooks/templates/` — 8+ templates (auto-scale, restart, cert-rotate, etc.)
  - Dashboard: `Marketplace.tsx` — card grid, categories, one-click deploy
  - Tests: template validation, deployment, customization

### Tier 2 — Enterprise Differentiation

- [x] **Incident Correlation Engine** — Group related alerts into unified incidents
  - Module: `src/shieldops/agents/investigation/correlation.py` — CorrelationEngine
  - Features: time-window grouping, service-graph linking, dedup scoring, severity escalation
  - API: `GET /incidents`, `POST /incidents/merge`, `PUT /incidents/{id}/status`
  - Dashboard: `IncidentCorrelation.tsx` — stats cards, search/filter, merge workflow
  - Tests: `tests/unit/test_incident_correlation.py` — 17 tests

- [x] **Runbook-as-Code** — Git-backed playbooks with PR approval flow
  - Module: `src/shieldops/playbooks/git_sync.py` — GitPlaybookSync
  - Features: async git subprocess, clone/pull/diff, rollback, version history
  - API: 6 endpoints (git-status, sync, diff, history, rollback, files)
  - Tests: `tests/unit/test_git_sync.py` — 21 tests

- [x] **Custom Webhook Triggers** — Ingest alerts from external monitoring tools
  - Module: `src/shieldops/api/routes/webhook_triggers.py`
  - Adapters: Datadog, PagerDuty, Grafana, OpsGenie, generic JSON
  - Features: HMAC-SHA256 verification, fingerprint dedup, auto-investigation trigger
  - Tests: `tests/unit/api/test_webhook_triggers.py` — 25 tests

- [x] **Role-scoped Dashboard Views** — UI adapts to user permissions
  - Hook: `dashboard-ui/src/hooks/usePermissions.ts` — permission matrix (3 roles x 12 resources x 6 actions)
  - Components: `PermissionGate`, `ConditionalAction` wrappers
  - Tests: `dashboard-ui/src/__tests__/permissions.test.ts` — 14 tests

### Tier 3 — Platform Maturity

- [x] **Agent Simulation Mode** — Dry-run remediation without touching infra
  - Module: `src/shieldops/agents/remediation/simulator.py` — RemediationSimulator
  - Features: step planning, impact estimation, OPA policy check, no side effects
  - API: `POST /remediations/simulate`, `GET /remediations/simulations`
  - Tests: `tests/unit/test_simulation.py` — 16 tests

- [x] **Cost Optimization Autopilot** — Auto-execute low-risk cost recommendations
  - Module: `src/shieldops/agents/cost/autopilot.py` — CostAutopilot
  - Features: risk scoring, auto-approval threshold, env exclusion, dry-run mode
  - API: 7 endpoints (config, analyze, recommendations, approve, execute, history)
  - Tests: `tests/unit/test_cost_autopilot.py` — 18 tests

- [x] **Mobile Push Notifications** — FCM/APNs for critical alerts
  - Module: `src/shieldops/integrations/notifications/push.py` — PushNotifier
  - Features: device registration, topic subscriptions, priority routing, platform payloads
  - API: `POST /devices/register`, `DELETE /devices/{id}`, `GET /devices`, `PUT /devices/{id}/topics`
  - Tests: `tests/unit/test_push_notifications.py` — 20 tests

- [x] **GraphQL API Layer** — Flexible query API alongside REST
  - Module: `src/shieldops/api/graphql/` — schema.py, routes.py
  - Features: multi-query support, field selection, filtering, 8 resolver types
  - API: `POST /graphql`, `GET /graphql/schema`
  - Tests: `tests/unit/api/test_graphql.py` — 15 tests

- [x] **SOC2 Compliance Dashboard** — Real-time compliance posture
  - Module: `src/shieldops/compliance/soc2.py` — SOC2ComplianceEngine
  - 15 controls across 5 Trust Service Categories (Security, Availability, PI, Confidentiality, Privacy)
  - API: report, controls, trends, evidence, admin override (6 endpoints)
  - Dashboard: `ComplianceDashboard.tsx` — circular gauge, category cards, controls table, trend chart
  - Tests: `tests/unit/test_soc2_compliance.py` — 31 tests

---

## Completed

- [x] Multi-cloud Terraform infrastructure (AWS/GCP/Azure)
- [x] Terraform CI validation (fmt + validate matrix)
- [x] Investigation Agent (85% — production-ready)
- [x] Remediation Agent (85% — production-ready)
- [x] Learning Agent (75% — functional)
- [x] Security Agent framework (graph, nodes, tools, runner)
- [x] AWS Connector (EC2, ECS)
- [x] Kubernetes Connector (pods, deployments)
- [x] Linux Connector (systemd, SSH)
- [x] OPA Policy Engine + Rego policies
- [x] Approval Workflow (Slack, escalation chains)
- [x] Rollback Manager
- [x] FastAPI + Auth + WebSocket
- [x] Supervisor Agent orchestration
- [x] GCP Connector (Compute Engine + Cloud Run) — 505 LOC, 37 tests
- [x] Azure Connector (VMs + Container Apps) — 572 LOC, 49 tests
- [x] Settings + Factory wiring for GCP/Azure connectors
- [x] NVD CVE Source (NIST API 2.0, CVSS v3.1) — 261 LOC, 22 tests
- [x] AWS Secrets Manager Credential Store — 181 LOC, 15 tests
- [x] HashiCorp Vault Credential Store — 271 LOC, 26 tests
- [x] AWS CloudTrail Integration — real get_events() with pagination, 6 tests
- [x] Compliance Framework Integration — 12 control evaluators, 23 tests
- [x] Playbook Wiring — resolve_playbook node + validation checks, 16 tests
- [x] CI fixes — ruff version alignment, mypy stubs, dependency audit (CVE fix)
- [x] OPA Compliance Mapping Policy (SOC2, PCI-DSS, HIPAA, CIS) — 115 LOC, 13 tests
- [x] OPA Team Scoping Policy (ownership, blast radius, env restrictions) — ~50 LOC, 10 tests
- [x] Extended Rate Limiter (per-minute burst, per-team hourly) — 52 LOC + Rego, 26 tests
- [x] GCP Fake Connector + E2E Tests — 347 LOC, 17 tests
- [x] Azure Fake Connector + E2E Tests — 153 LOC, 16 tests
- [x] Cross-Connector E2E Tests (multi-provider, rollback, isolation) — 9 tests
- [x] Kafka Event Bus (producer, consumer, bus, topics, EventEnvelope) — 43 tests
- [x] WebSocket Broadcasting Wiring (singleton manager, runner injection) — 15 tests
- [x] GCP Cloud Audit Log Events (Cloud Logging API integration) — 6 tests
- [x] Azure Activity Log Events (Monitor Activity Log integration) — 7 tests
- [x] Learning Agent Persistence (LearningCycleRecord ORM + repository) — 23 tests
- [x] Notification Service (PagerDuty + NotificationDispatcher) — 34 tests
- [x] Scheduled Job Framework (asyncio scheduler, 3 periodic jobs) — 42 tests
- [x] AWS Cost Explorer Billing Source (GetCostAndUsage integration) — 33 tests
- [x] Cleanup Legacy Supervisor Stub (deleted dead orchestration/supervisor.py)
- [x] New Claude Code Skills (add-connector, add-integration, run-agent, check-health)
- [x] Prometheus Metrics (MetricsRegistry, /metrics endpoint, request histograms)
- [x] Slack Notifications (Incoming Webhooks, Block Kit formatting)
- [x] Email Notifications (async SMTP, HTML templates, TLS)
- [x] Circuit Breakers + Retry (closed/open/half-open, exponential backoff)
- [x] Kafka Dead Letter Queue (retry tracking, max-retry threshold)
- [x] Redis Distributed Locking (Lua atomic acquire/release, heartbeat)
- [x] Graceful Shutdown Middleware (request draining, signal handling)
- [x] Webhook Notifications (HMAC-SHA256 signing, configurable retry)
- [x] React Dashboard (11 pages, React 18 + TypeScript + Tailwind + Vite)
- [x] Deployment Docs (DEPLOYMENT.md + QUICKSTART_DEMO.md)
- [x] Makefile (27 targets for dev, test, build, deploy workflows)
- [x] Grafana + Prometheus Monitoring (dashboards, 12 alerts, 12 recording rules)
- [x] Seed Data Script (users, agents, investigations, remediations, scans)
- [x] Wire Security Scanners (IaC, Git, K8s, Network) — opt-in settings, 7 tests
- [x] Audit Log API + Dashboard Page — GET /audit-logs, AuditLog.tsx, 4 tests
- [x] SSO / OIDC Authentication — OIDCClient, login/callback routes, 11 tests
- [x] Helm Chart — 15 templates, Bitnami deps, helm lint passes
- [x] GCP Cloud Billing Source (BigQuery billing export) — 16 tests
- [x] Azure Cost Management Source (Cost Management Query API) — 24 tests
- [x] Playbooks Dashboard Page — card grid, search, YAML expansion, trigger
- [x] User Management API + Dashboard — CRUD routes, role editor, invite modal
- [x] OTel Metrics Pipeline (MeterProvider + OTLP exporter, AgentMetrics) — 5 tests
- [x] LangSmith Agent Tracing (conditional init, env var setup) — 3 tests
- [x] Refresh Tokens + Revocation (JTI, Redis blacklist) — 4 tests
- [x] Terraform State Backend + CI (S3/GCS/Azure backends, terraform-plan job)
- [x] Dashboard Page Tests (7 new test files, 48 total vitest tests)
- [x] Multi-Org / Tenant Isolation (OrganizationRecord, TenantMiddleware, 14 tests)
- [x] Fine-grained RBAC / Permissions (require_permission dependency, seed roles)
- [x] API Rate Limiting v2 (sliding window, per-tenant, X-RateLimit headers)
- [x] Agent Context Store (AgentContextRecord, TTL, cross-incident memory)
- [x] Python SDK Client (sync + async, 5 resources, 32 tests)
- [x] E2E Playwright Tests (4 new specs: audit-log, playbooks, user-management, analytics)
- [x] CLI Tool (Click-based, 6 command groups, 31 tests)
- [x] k6 Load Testing Suite (5 scenarios, 3 Makefile targets)
- [x] MkDocs Documentation Site (Material theme, 30+ pages, 7 sections)
- [x] OpenAPI Enhancement + API Versioning (10 response models, changelog, 32 tests)
- [x] API Key Management (SHA-256 hashed, sk- prefix auth, scope validation) — 28 tests
- [x] Data Export / Compliance Reports (CSV streaming, JSON, OWASP sanitization) — 30 tests
- [x] Dashboard Real-time Updates (WebSocket + Zustand + React Query invalidation)
- [x] Incident Timeline View (merged events, color-coded, filter bar) — 10 tests
- [x] Stripe Billing Integration (checkout, subscription, webhooks, usage) — 23 tests
- [x] Custom Playbook Editor (7 CRUD endpoints, YAML validation, dry-run) — 21 tests
- [x] Batch Operations API (async 202, partial failure, job polling) — 26 tests
- [x] Agent Performance Dashboard (line/bar/heatmap charts, demo data) — 13 tests
- [x] Health Check Dashboard (concurrent dep checks, 2s timeout, auto-refresh) — 16 tests
- [x] Notification Preferences (12 events x 4 channels, upsert pattern) — 15 tests
- [x] API Usage Analytics (per-org/endpoint/hour tracking middleware) — 33 tests
- [x] Global Search (Cmd+K palette, parallel ILIKE, relevance scoring) — 25 tests
- [x] Multi-tenant Billing Enforcement (plan limits middleware, usage meters) — tests
- [x] Onboarding Wizard (5-step guided setup, cloud validation) — tests
- [x] Agent Marketplace / Templates (8+ templates, one-click deploy) — tests
- [x] Incident Correlation Engine (time-window grouping, dedup, merge) — 17 tests
- [x] Runbook-as-Code (git sync, diff, rollback, version history) — 21 tests
- [x] Custom Webhook Triggers (5 adapters, HMAC, fingerprint dedup) — 25 tests
- [x] Role-scoped Dashboard Views (usePermissions, PermissionGate) — 14 tests
- [x] Agent Simulation Mode (dry-run, impact estimation, OPA check) — 16 tests
- [x] Cost Optimization Autopilot (risk scoring, auto-approval, env exclusion) — 18 tests
- [x] Mobile Push Notifications (FCM/APNs, device registration, topics) — 20 tests
- [x] GraphQL API Layer (multi-query, field selection, 8 resolvers) — 15 tests
- [x] SOC2 Compliance Dashboard (15 controls, 5 categories, evidence, trends) — 31 tests
