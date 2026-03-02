# ShieldOps - AI-Powered Autonomous SRE Platform

## Project Overview
ShieldOps is an enterprise SaaS platform that deploys autonomous AI agents for Site Reliability Engineering (SRE) operations. Agents investigate incidents, execute remediations, enforce security policies, and learn from outcomes — across multi-cloud (AWS/GCP/Azure) and on-premise Linux environments.

**Core Thesis:** "The only autonomous SRE agent platform that doesn't just analyze — it acts. Built for security-first enterprises managing hybrid cloud + on-prem at scale."

## Tech Stack
- **Language:** Python 3.12+
- **Agent Framework:** LangGraph (graph-based agent orchestration)
- **LLM Provider:** Anthropic Claude (primary), OpenAI (fallback)
- **API Framework:** FastAPI
- **Dashboard:** React + TypeScript + Tailwind CSS
- **Database:** PostgreSQL (agent state), Redis (real-time coordination)
- **Message Queue:** Kafka (event streaming)
- **Infrastructure:** Kubernetes, Terraform/OpenTofu
- **Observability:** OpenTelemetry, LangSmith (agent tracing)
- **Policy Engine:** Open Policy Agent (OPA)
- **Testing:** pytest, pytest-asyncio, playwright (e2e)
- **CI/CD:** GitHub Actions

## Architecture Layers
1. **Multi-Environment Connector Layer** — Abstracts cloud/on-prem differences (AWS/GCP/Azure/K8s/Linux)
2. **Observability Ingestion Layer** — Vendor-neutral telemetry via OpenTelemetry (Splunk, Datadog, Prometheus)
3. **Agent Orchestration Layer** — LangGraph-based agents (Investigation, Remediation, Security, Learning)
4. **Policy & Safety Layer** — OPA policies, approval workflows, rollback mechanisms, compliance reporting

## Agent Types
- **Investigation Agent:** Root cause analysis from alerts, logs, metrics, traces
- **Remediation Agent:** Executes infrastructure changes (restart, scale, patch, rollback) with policy gates
- **Security Agent:** CVE patching, credential rotation, network policy enforcement
- **Learning Agent:** Updates playbooks, refines thresholds from historical outcomes
- **Supervisor Agent:** Orchestrates specialist agents, manages escalation

## Development Conventions

### Python
- Use `ruff` for linting and formatting (line-length=100)
- Type hints required on all public functions
- Async-first: use `async/await` for all I/O operations
- Pydantic v2 models for all data structures
- Structured logging via `structlog`

### Code Organization
- Each agent type lives in `src/shieldops/agents/{type}/`
- Each connector lives in `src/shieldops/connectors/{provider}/`
- Shared utilities in `src/shieldops/utils/`
- Configuration via environment variables + `src/shieldops/config/`

### Testing
- Unit tests mirror source structure: `tests/unit/agents/`, `tests/unit/connectors/`
- Integration tests in `tests/integration/` require Docker
- Agent simulation tests in `tests/agents/` replay historical incidents
- Minimum 80% coverage on all new code
- Run tests: `pytest tests/ -v --cov=src/shieldops`

### Git Conventions
- Branch naming: `feat/`, `fix/`, `chore/`, `docs/`
- Commit messages: conventional commits (`feat:`, `fix:`, `chore:`, `docs:`)
- PRs require passing CI + 1 review

### Security (Non-Negotiable)
- Never hardcode credentials — use environment variables or secret managers
- All agent actions must pass OPA policy evaluation before execution
- Audit trail for every infrastructure change (immutable log)
- Blast-radius limits enforced per environment (dev/staging/prod)
- No agent can delete databases, drop tables, or modify IAM root policies

### API Design
- RESTful API with FastAPI, versioned at `/api/v1/`
- All endpoints require authentication (JWT)
- Rate limiting on all public endpoints
- OpenAPI spec auto-generated

## Key File Paths
- `src/shieldops/agents/` — Agent implementations, swarm coordinator, consensus engine, knowledge mesh, token optimizer, prompt cache, routing optimizer, telemetry analyzer, compliance auditor
- `src/shieldops/connectors/` — Cloud/infra connectors
- `src/shieldops/orchestration/` — LangGraph workflow definitions
- `src/shieldops/policy/` — OPA policies, approval logic, tenant isolation, cross-agent policy enforcer, governance dashboard, governance_scorer
- `src/shieldops/api/` — FastAPI routes and middleware
- `src/shieldops/dashboard/` — React dashboard components
- `src/shieldops/integrations/notifications/` — PagerDuty, Slack, email, webhook, push, Twilio SMS, Twilio voice, Microsoft Teams
- `src/shieldops/observability/` — Alert noise, threshold tuning, backup verification, resilience scoring, chaos experiment design, alert correlation rules, metric baseline, alert fatigue, alert rule linter, outage predictor, alert storm correlator, alert tuning feedback, coverage scorer, cardinality manager, log retention optimizer, dashboard quality, data pipeline, queue depth forecast, alert_dedup, observability cost, retention policy, predictive alert engine, chaos automator, dns health monitor, alert routing optimizer, health index, observability gap, noise_classifier, escalation_analyzer, alert_suppression, alert_priority, alert_correlation_opt, metric_quality, log_quality, dashboard_effectiveness, trace_coverage, metric_cardinality_planner, observability_budget_planner, alert_noise_profiler, alert_correlation_profiler, metric_anomaly_classifier, metric_collection_optimizer
- `src/shieldops/incidents/` — Severity prediction, on-call fatigue analysis, incident deduplication, timeline reconstruction, on-call rotation optimization, incident review board, incident timeline analyzer, severity calibrator, communication planner, impact quantifier, oncall workload balancer, duration predictor, handoff tracker, response advisor, escalation effectiveness, action tracker, learning tracker, comm effectiveness, auto triage, recurrence pattern, incident similarity, incident cost, followup tracker, priority_ranker, knowledge_linker, postmortem quality, escalation optimizer, prevention engine, war room orchestrator, root cause verifier, comm automator, timeline correlator, incident replay, response timer, severity_validator, trend_forecaster, response_time, root_cause_classifier, incident_cluster, noise_filter, response_optimizer, triage_quality, blast_radius, response_playbook, severity_impact, incident_pattern, escalation_path, incident_debrief, incident_response_time, incident_pattern_analyzer, incident_escalation_scorer, incident_mitigation_tracker, stakeholder_impact_tracker
- `src/shieldops/topology/` — Service dependency impact analysis, service catalog, dependency health scoring, cascade failure prediction, failure mode catalog, service health aggregator, dependency update planner, dependency mapper, service maturity model, dependency lag, API version health, traffic pattern, rate limit policy, circuit breaker health, reliability antipattern, dependency risk, comm_mapper, service mesh intelligence, dependency topology, network latency, ownership tracker, deprecation_tracker, dep_vuln_mapper, infra_health_scorer, service_dep_risk, dep_latency, dep_validator, dep_change_tracker, health_trend, api_gateway_health, service_communication, api_contract_drift, dependency_freshness_monitor, dependency_circuit_breaker, topology_change_tracker, service_dependency_scorer, topology_drift_detector, service_routing_optimizer, service_health_predictor
- `src/shieldops/audit/` — Configuration audit trail, audit intelligence, decision audit, audit_readiness, compliance_reporter, evidence_tracker, finding_tracker, remediation_tracker, change_audit, access_review, audit_finding_tracker, audit_compliance_mapper, audit_control_assessor, audit_remediation_tracker, audit_workflow_optimizer, audit_scope_optimizer
- `src/shieldops/analytics/` — Deployment velocity, capacity trends, SRE metrics, latency profiling, toil tracking, trace analysis, log anomaly detection, event correlation, team performance, API deprecation tracking, dependency freshness, deployment cadence, capacity forecast engine, latency budget tracker, resource exhaustion forecaster, metric RCA, cache effectiveness, build pipeline, review velocity, connection pool, capacity demand, collaboration scorer, api performance, resource contention, team_velocity, error_classifier, utilization_scorer, dynamic risk scorer, infra capacity planner, capacity anomaly, bottleneck_detector, anomaly_scorer, service_latency, perf_benchmark, workflow_analyzer, reliability_metrics, alert_response, capacity_simulation, capacity_headroom, capacity_scaling_advisor, capacity_utilization_tracker, capacity_forecast_validator, performance_baseline_tracker, data_quality_scorer
- `src/shieldops/compliance/` — Compliance automation, gap analysis, license scanning, access certification, evidence chain, compliance drift detector, policy violation tracker, evidence scheduler, evidence freshness monitor, audit trail analyzer, license risk, policy impact, automation_scorer, evidence automator, posture scorer, evidence_validator, policy_enforcer, report_automator, control_tester, evidence_consolidator, risk_scorer, regulation_tracker, control_effectiveness, policy_coverage, audit_evidence_mapper, compliance_evidence_chain, compliance_control_mapper, regulatory_impact_tracker
- `src/shieldops/knowledge/` — Knowledge base article management, knowledge decay, contribution tracker, freshness_monitor, search_optimizer, usage_analyzer, knowledge_coverage, expertise_mapper, feedback_loop, taxonomy_manager, knowledge_graph, knowledge_retention, knowledge_gap_detector, knowledge_freshness_scorer, knowledge_quality_assessor, knowledge_reuse_tracker, knowledge_impact_analyzer
- `src/shieldops/billing/` — Cost forecasting, cost tag enforcement, orphan detection, budget management, tag governance, right-sizing, storage optimization, resource lifecycle, RI optimization, cost anomaly RCA, spend allocation, commitment planning, cost simulation, FinOps maturity, resource waste detector, billing reconciler, chargeback engine, cost anomaly predictor, unit economics engine, idle resource detector, discount optimizer, spot advisor, infra_cost_allocator, llm cost tracker, cloud arbitrage, platform cost optimizer, vendor_lockin, cost_efficiency, budget_variance, optimization_planner, capacity_utilizer, cost_trend, cost_alloc_validator, forecast_validator, invoice_validator, commitment_tracker, procurement_optimizer, showback_engine, cost_attribution_engine, cost_forecast_accuracy, capacity_reservation_planner, cost_variance_analyzer, cost_optimization_tracker, cost_allocation_validator, cost_governance_enforcer, cost_forecast_precision
- `src/shieldops/changes/` — Deployment risk, change advisory, release management, change intelligence, change failure rate tracking, change window optimizer, deployment approval gate, deploy health scorer, change conflict detector, canary analyzer, velocity throttle, deployment confidence, rollback analyzer, deploy_frequency, lead time analyzer, deployment dependency, deployment impact, change freeze, pipeline analyzer, release readiness, approval_analyzer, risk_predictor, impact_predictor, freeze_validator, canary_scorer, batch_analyzer, change_correlator, rollback_tracker, deploy_stability, feature_flag_impact, merge_risk, deploy_canary_health, deploy_rollback_health, change_velocity, deploy_gate_tracker, change_approval_flow, deploy_dependency_tracker, change_risk_classifier, deploy_verification_tracker, change_impact_predictor, deploy_canary_analyzer, change_window_analyzer, change_rollout_planner, change_coordination_planner
- `src/shieldops/security/` — Security incident response, vulnerability lifecycle, API security monitoring, certificate monitoring, network flow analysis, container scanning, cloud posture management, secrets detection, credential expiry forecaster, posture trend analyzer, access anomaly detector, permission drift, attack surface, compliance_bridge, risk aggregator, threat hunt orchestrator, response automator, zero trust verifier, posture simulator, credential rotator, posture_benchmark, compliance_mapper, threat_correlator, event_correlator, vuln_prioritizer, lateral_movement, insider_threat, data_classification, secret_rotation_planner, threat_intelligence, security_posture_gap, threat_response_tracker, vulnerability_response_tracker, threat_surface_analyzer, security_signal_correlator, security_compliance_scorer
- `src/shieldops/operations/` — Runbook execution engine, workload scheduling optimization, runbook effectiveness analysis, game day planning, toil automation recommendations, runbook versioner, team skill matrix, infrastructure drift reconciler, capacity right-timing, runbook gap analyzer, remediation decision, SRE maturity, dev environment, readiness scorer, self healing, automation gap, scaling efficiency, cognitive load, runbook recommender, scaling_advisor, dr drill tracker, tenant quota, remediation pipeline, recovery coordinator, runbook chainer, failover coordinator, burst manager, runbook generator, toil quantifier, toil_classifier, runbook_coverage, workload_balancer, config_drift_monitor, oncall_equity, runbook_exec_tracker, metric_aggregator, runbook_compliance, shift_optimizer, toil_automator, handover_quality, reservation_optimizer, operational_readiness, runbook_dependency, runbook_effectiveness_scorer, runbook_quality_scorer, runbook_automation_scorer, operational_hygiene_scorer, team_capacity_planner
- `src/shieldops/sla/` — SLA engine, SLO burn rate prediction, SLO target advisory, SLI calculation pipeline, error budget policy, reliability target advisor, SLA cascader, penalty calculator, SLO forecast, reliability regression, error budget forecast, reliability scorecard, SLO auto-scaler, reliability automator, breach predictor, error budget allocator, slo aggregator, slo_compliance, impact_analyzer, availability_tracker, slo_alignment, slo_dep_mapper, slo_health, breach_impact, customer_impact, degradation_tracker, maintenance_impact, slo_error_budget_tracker, slo_window_analyzer, slo_breach_analyzer, slo_compliance_monitor, slo_error_budget_forecaster, slo_threshold_optimizer, slo_cross_correlation
- `src/shieldops/config/` — Configuration, parity validation, flag lifecycle, flag impact, drift analyzer, config validator
- `docs/prd/` — Product Requirements Documents
- `docs/architecture/` — Architecture Decision Records
- `playbooks/` — Remediation playbook definitions (YAML)
- `infrastructure/` — Terraform configs, K8s manifests, Dockerfiles

## Custom Commands
- `/build` — Build new features following PRD specs
- `/test` — Run test suites with coverage
- `/deploy` — Deploy to staging/production
- `/scan` — Security audit and dependency scan
- `/review` — Code review and quality analysis
- `/analyze` — Architecture and performance analysis
- `/design` — System and API design
- `/task` — Multi-step task management

## Environment Variables (Required)
```
ANTHROPIC_API_KEY=     # Claude API key
OPENAI_API_KEY=        # Fallback LLM
DATABASE_URL=          # PostgreSQL connection
REDIS_URL=             # Redis connection
KAFKA_BROKERS=         # Kafka broker list
OPA_ENDPOINT=          # OPA policy engine URL
LANGSMITH_API_KEY=     # Agent tracing
```
