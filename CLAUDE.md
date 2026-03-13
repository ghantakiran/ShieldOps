# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ShieldOps is an enterprise SaaS platform deploying autonomous AI agents for Site Reliability Engineering (SRE) operations. Agents investigate incidents, execute remediations, enforce security policies, and learn from outcomes — across multi-cloud (AWS/GCP/Azure) and on-premise Linux environments.

**Core thesis:** The only autonomous SRE agent platform that doesn't just analyze — it acts. Built for security-first enterprises managing hybrid cloud + on-prem at scale.

## Build & Development Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run all tests
python3 -m pytest tests/ -v --tb=short

# Run a single test file
python3 -m pytest tests/unit/test_<module>.py -v

# Run tests with coverage
python3 -m pytest tests/ -v --cov=src/shieldops

# Linting and formatting
ruff check src/ tests/ --fix
ruff format src/ tests/

# Type checking
mypy src/shieldops/

# Security scan
bandit -c pyproject.toml -ll -r src/

# Pre-commit hooks (ruff lint+format, mypy, bandit, trailing whitespace, etc.)
pre-commit run --all-files

# Start API server
uvicorn shieldops.api.main:app --reload

# CLI
shieldops --help
```

## Architecture

### Four Layers
1. **Connector Layer** — Abstracts cloud/on-prem: AWS, GCP, Azure, Kubernetes, Linux, Windows (`src/shieldops/connectors/{provider}/`)
2. **Observability Ingestion** — Vendor-neutral OpenTelemetry (Splunk, Datadog, Prometheus)
3. **Agent Orchestration** — LangGraph-based agents with graph→nodes→tools pattern
4. **Policy & Safety** — OPA policies, approval workflows, rollback, compliance

### Agent Architecture (LangGraph)
Each agent in `src/shieldops/agents/{type}/` follows this structure:
```
graph.py      # LangGraph StateGraph definition — nodes + edges + routing
nodes.py      # Node function implementations (investigate, act, validate)
tools.py      # Tool functions called by nodes (API calls, infra ops)
models.py     # Pydantic state/input/output models
prompts.py    # LLM prompt templates
runner.py     # Entry point — lifecycle management, execution
policy.py     # OPA policy integration (optional)
```

There are 29 LangGraph agents: investigation, remediation, security, learning, supervisor, soc_analyst, threat_hunter, forensics, deception, incident_response, attack_surface, ml_governance, finops_intelligence, zero_trust, threat_automation, soar_orchestration, itdr, auto_remediation, observability_intelligence, xdr, intelligent_automation, platform_intelligence, security_convergence, autonomous_defense, chatops, enterprise_integration, automation_orchestrator, cost, prediction.

### Engine Module Pattern
The bulk of the codebase (~1,200+ modules) are analytics/intelligence engines across 13 packages. Each follows a strict pattern:
```python
# 3 StrEnum classes, 3 Pydantic models (Record, Analysis, Report)
# Engine class with: add_record()/record_item(), process(key),
#   generate_report(), get_stats(), clear_data(), 3 domain methods
# Ring-buffer storage with max_records eviction
```
- `add_record(**kwargs)` for: analytics, observability, security, knowledge, sla, billing, incidents, compliance
- `record_item(**kwargs)` for: changes, operations, topology

### Key Packages
| Package | Purpose | Count |
|---------|---------|-------|
| `observability/` | Alert intelligence, telemetry, SLI/SLO, sampling, eBPF, OTel pipelines | 145+ |
| `security/` | Threat detection, SOAR, zero trust, XDR, risk-based alerting | 310+ |
| `operations/` | Runbooks, automation, chaos, capacity, resource budgets | 124+ |
| `analytics/` | DORA, AIOps, root cause, auto-learning, agent optimization | 156+ |
| `incidents/` | Triage, escalation, postmortem, noise reduction, risk correlation | 82+ |
| `compliance/` | Evidence, audit, regulatory, policy enforcement, risk bridge | 98+ |
| `billing/` | FinOps, cost optimization, RI planning, telemetry cost attribution | 76+ |
| `topology/` | Service mesh, dependencies, API lifecycle, OTel service graph | 56+ |
| `sla/` | SLO tracking, error budgets, reliability, resilience | 51+ |
| `knowledge/` | Knowledge base, onboarding, feedback, agent knowledge distillation | 26+ |
| `audit/` | Audit trails, evidence, compliance mapping, governance | 30+ |
| `changes/` | GitOps, IaC validation, deployment intelligence, canary | 58+ |
| `config/` | Feature flags, drift analysis, validation | 11 |

### API & Dashboard
- FastAPI at `src/shieldops/api/` — RESTful, versioned `/api/v1/`, JWT auth, OpenAPI auto-gen
- React + TypeScript + Tailwind dashboard at `dashboard-ui/`
- Notification integrations: Slack, Teams, PagerDuty, email, SMS, voice, webhooks

## Tech Stack
- Python 3.12+, LangGraph, LangChain, Anthropic Claude (primary LLM)
- FastAPI, Pydantic v2, SQLAlchemy (async), PostgreSQL, Redis, Kafka
- OpenTelemetry, LangSmith, structlog
- OPA (Open Policy Agent) for policy enforcement
- Terraform/OpenTofu, Kubernetes
- React, TypeScript, Tailwind CSS (dashboard)
- pytest, pytest-asyncio, playwright (e2e)
- GitHub Actions CI/CD

## Development Conventions

### Code Standards
- **Ruff** for lint + format (line-length=100, target py312)
- **mypy** strict mode — type hints required on all public functions
- **Pydantic v2** models for all data structures
- **structlog** for structured logging
- **async/await** for all I/O operations
- Pre-commit hooks: ruff, ruff-format, mypy, bandit, trailing-whitespace, end-of-file-fixer

### Testing
- Unit tests: `tests/unit/` (mirror source structure)
- Integration tests: `tests/integration/` (require Docker)
- Agent simulations: `tests/agents/` (replay historical incidents)
- Minimum 80% coverage on new code

### Git
- Branch naming: `feat/`, `fix/`, `chore/`, `docs/`
- Commit messages: conventional commits (`feat:`, `fix:`, `chore:`, `docs:`)
- PRs require passing CI + 1 review

### Security (Non-Negotiable)
- Never hardcode credentials — use env vars or secret managers
- All agent actions must pass OPA policy evaluation before execution
- Audit trail for every infrastructure change (immutable log)
- Blast-radius limits enforced per environment (dev/staging/prod)
- No agent can delete databases, drop tables, or modify IAM root policies
- Confidence thresholds: autonomous >0.85, human approval 0.5-0.85, escalate <0.5

## Environment Variables
```
ANTHROPIC_API_KEY=     # Claude API key (primary LLM)
OPENAI_API_KEY=        # Fallback LLM
DATABASE_URL=          # PostgreSQL connection
REDIS_URL=             # Redis connection
KAFKA_BROKERS=         # Kafka broker list
OPA_ENDPOINT=          # OPA policy engine URL
LANGSMITH_API_KEY=     # Agent tracing
```

## Custom Slash Commands
`/build`, `/test`, `/deploy`, `/scan`, `/review`, `/analyze`, `/design`, `/task`, `/build-agent`, `/scan-security`, `/check-health`, `/run-agent`, `/review-agent`
