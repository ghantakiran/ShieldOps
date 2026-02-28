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
- `src/shieldops/policy/` — OPA policies, approval logic, tenant isolation, cross-agent policy enforcer
- `src/shieldops/api/` — FastAPI routes and middleware
- `src/shieldops/dashboard/` — React dashboard components
- `src/shieldops/integrations/notifications/` — PagerDuty, Slack, email, webhook, push, Twilio SMS, Twilio voice, Microsoft Teams
- `src/shieldops/observability/` — Alert noise, threshold tuning, backup verification, resilience scoring, chaos experiment design, alert correlation rules, metric baseline, alert fatigue, alert rule linter, outage predictor, alert storm correlator, alert tuning feedback, coverage scorer, cardinality manager, log retention optimizer, dashboard quality, data pipeline, queue depth forecast, observability cost, retention policy, predictive alert engine, chaos automator
- `src/shieldops/incidents/` — Severity prediction, on-call fatigue analysis, incident deduplication, timeline reconstruction, on-call rotation optimization, incident review board, incident timeline analyzer, severity calibrator, communication planner, impact quantifier, oncall workload balancer, duration predictor, handoff tracker, response advisor, escalation effectiveness, action tracker, learning tracker, comm effectiveness, auto triage, recurrence pattern, incident similarity, incident cost, followup tracker, postmortem quality, escalation optimizer, prevention engine, war room orchestrator, root cause verifier, comm automator
- `src/shieldops/topology/` — Service dependency impact analysis, service catalog, dependency health scoring, cascade failure prediction, failure mode catalog, service health aggregator, dependency update planner, dependency mapper, service maturity model, dependency lag, API version health, traffic pattern, rate limit policy, circuit breaker health, reliability antipattern, dependency risk, service mesh intelligence
- `src/shieldops/audit/` — Configuration audit trail, audit intelligence, decision audit
- `src/shieldops/analytics/` — Deployment velocity, capacity trends, SRE metrics, latency profiling, toil tracking, trace analysis, log anomaly detection, event correlation, team performance, API deprecation tracking, dependency freshness, deployment cadence, capacity forecast engine, latency budget tracker, resource exhaustion forecaster, metric RCA, cache effectiveness, build pipeline, review velocity, connection pool, capacity demand, collaboration scorer, api performance, resource contention, dynamic risk scorer
- `src/shieldops/compliance/` — Compliance automation, gap analysis, license scanning, access certification, evidence chain, compliance drift detector, policy violation tracker, evidence scheduler, evidence freshness monitor, audit trail analyzer, license risk, policy impact, evidence automator
- `src/shieldops/knowledge/` — Knowledge base article management, knowledge decay, contribution tracker
- `src/shieldops/billing/` — Cost forecasting, cost tag enforcement, orphan detection, budget management, tag governance, right-sizing, storage optimization, resource lifecycle, RI optimization, cost anomaly RCA, spend allocation, commitment planning, cost simulation, FinOps maturity, resource waste detector, billing reconciler, chargeback engine, cost anomaly predictor, unit economics engine, idle resource detector, discount optimizer, spot advisor, llm cost tracker, cloud arbitrage, platform cost optimizer
- `src/shieldops/changes/` — Deployment risk, change advisory, release management, change intelligence, change failure rate tracking, change window optimizer, deployment approval gate, deploy health scorer, change conflict detector, canary analyzer, velocity throttle, deployment confidence, rollback analyzer, lead time analyzer, deployment dependency
- `src/shieldops/security/` — Security incident response, vulnerability lifecycle, API security monitoring, certificate monitoring, network flow analysis, container scanning, cloud posture management, secrets detection, credential expiry forecaster, posture trend analyzer, access anomaly detector, permission drift, attack surface, risk aggregator, threat hunt orchestrator, response automator, zero trust verifier, posture simulator, credential rotator
- `src/shieldops/operations/` — Runbook execution engine, workload scheduling optimization, runbook effectiveness analysis, game day planning, toil automation recommendations, runbook versioner, team skill matrix, infrastructure drift reconciler, capacity right-timing, runbook gap analyzer, remediation decision, SRE maturity, dev environment, readiness scorer, self healing, automation gap, scaling efficiency, cognitive load, runbook recommender, dr drill tracker, tenant quota, remediation pipeline, recovery coordinator, runbook chainer, failover coordinator, burst manager, runbook generator
- `src/shieldops/sla/` — SLA engine, SLO burn rate prediction, SLO target advisory, SLI calculation pipeline, error budget policy, reliability target advisor, SLA cascader, penalty calculator, SLO forecast, reliability regression, error budget forecast, reliability scorecard, SLO auto-scaler, reliability automator
- `src/shieldops/config/` — Configuration, parity validation, flag lifecycle, flag impact
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
