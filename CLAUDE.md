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
- `src/shieldops/agents/` — Agent implementations
- `src/shieldops/connectors/` — Cloud/infra connectors
- `src/shieldops/orchestration/` — LangGraph workflow definitions
- `src/shieldops/policy/` — OPA policies, approval logic, tenant isolation
- `src/shieldops/api/` — FastAPI routes and middleware
- `src/shieldops/dashboard/` — React dashboard components
- `src/shieldops/observability/` — Alert noise, threshold tuning, backup verification
- `src/shieldops/incidents/` — Severity prediction, on-call fatigue analysis
- `src/shieldops/topology/` — Service dependency impact analysis
- `src/shieldops/audit/` — Configuration audit trail
- `src/shieldops/analytics/` — Deployment velocity, capacity trends, SRE metrics
- `src/shieldops/compliance/` — Compliance automation rules, gap analysis
- `src/shieldops/knowledge/` — Knowledge base article management
- `src/shieldops/billing/` — Cost forecasting, cost tag enforcement
- `src/shieldops/changes/` — Deployment risk, change advisory
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
