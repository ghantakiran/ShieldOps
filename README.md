# ShieldOps

**AI-Powered Autonomous SRE Platform**

> Your infrastructure never sleeps. Neither should its intelligence.

ShieldOps deploys autonomous AI agents that investigate incidents, execute remediations, enforce security policies, and learn from outcomes — across multi-cloud (AWS/GCP/Azure), Kubernetes, on-premise Linux, and Windows environments.

Unlike existing tools that only *analyze*, ShieldOps agents *act* — with policy-gated safety, full audit trails, and one-click rollback.

---

## Why ShieldOps?

| Problem | ShieldOps Solution |
|---------|-------------------|
| SRE teams handle 50+ alerts/day manually | Agents auto-investigate and resolve incidents 24/7 |
| MTTR averages 2+ hours for P1 incidents | Root cause in minutes, remediation in seconds |
| 70% of enterprises lack DevSecOps expertise | Security policies enforced continuously by agents |
| Multi-cloud complexity growing 3x faster than teams | One agent works across AWS, GCP, Azure, K8s, Linux, and Windows |
| Alert fatigue causes burnout and missed incidents | Intelligent triage reduces noise, escalates what matters |

## How It Works

```
Alert Fires → Investigation Agent → Root Cause Hypothesis
                                          │
                              confidence > 0.85?
                             ╱                  ╲
                          Yes                     No
                           │                       │
                    Remediation Agent         Escalate to Human
                           │                  (with full context)
                    Policy Check (OPA)
                           │
                    Execute + Validate
                           │
                    Success → Learn
                    Failure → Rollback + Escalate
```

## Architecture

ShieldOps is built on a four-layer stack:

```
┌─────────────────────────────────────────────────────┐
│  Layer 4: Policy & Safety                           │
│  OPA policies · Approval workflows · Rollback       │
│  Compliance reporting · Blast-radius limits          │
├─────────────────────────────────────────────────────┤
│  Layer 3: Agent Orchestration (LangGraph)           │
│  Investigation · Remediation · Security · Learning  │
│  Cost · Prediction · Supervisor · Custom agents      │
├─────────────────────────────────────────────────────┤
│  Layer 2: Observability Ingestion                   │
│  OpenTelemetry · Splunk · Datadog · Prometheus      │
│  CloudWatch · New Relic · Elastic · Jaeger           │
├─────────────────────────────────────────────────────┤
│  Layer 1: Multi-Environment Connectors              │
│  AWS · GCP · Azure · Kubernetes · Linux · Windows   │
│  Unified interface · Write once, deploy anywhere     │
└─────────────────────────────────────────────────────┘
```

### Agent Types

| Agent | Role | Actions |
|-------|------|---------|
| **Investigation** | Root cause analysis | Query logs, metrics, traces; correlate events; generate hypotheses |
| **Remediation** | Infrastructure execution | Restart pods, scale services, rollback deployments, patch systems |
| **Security** | Continuous security posture | CVE patching, credential rotation, compliance monitoring |
| **Learning** | Continuous improvement | Update playbooks, refine thresholds, learn from outcomes |
| **Cost** | Cloud cost optimization | Analyze spend, identify waste, recommend savings |
| **Prediction** | Proactive incident prevention | Detect trends, forecast anomalies, generate predictions |
| **Supervisor** | Orchestration | Delegates to specialists, manages escalation, chains workflows |

### Safety Model (Defense in Depth)

Every agent action passes through five safety layers:

1. **Policy Gate (OPA)** — Rego policies evaluate every action before execution
2. **Risk Classification** — Actions rated Low/Medium/High/Critical with approval requirements
3. **Snapshot & Rollback** — State captured before every change; one-click rollback
4. **Validation Loop** — Health checks confirm success; auto-rollback on failure
5. **Human Escalation** — Graceful degradation from autonomous → approval → manual

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| Agent Framework | LangGraph |
| LLM | Anthropic Claude (primary), OpenAI (fallback) |
| API | FastAPI |
| Dashboard | React + TypeScript + Tailwind CSS + shadcn/ui |
| Database | PostgreSQL (state), Redis (coordination) |
| Messaging | Apache Kafka |
| Infrastructure | Kubernetes, Terraform |
| Observability | OpenTelemetry, LangSmith |
| Policy Engine | Open Policy Agent (OPA) |
| Logging | structlog (structured logging) |
| Validation | Pydantic v2 |
| CI/CD | GitHub Actions |

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- An Anthropic API key ([get one here](https://console.anthropic.com/))

### Quick Start

```bash
# Clone the repo
git clone https://github.com/ghantakiran/ShieldOps.git
cd ShieldOps

# Configure environment
cp .env.example .env
# Edit .env and add your SHIELDOPS_ANTHROPIC_API_KEY

# Start backing services (PostgreSQL, Redis, Kafka, OPA)
docker compose -f infrastructure/docker/docker-compose.yml up -d

# Install Python dependencies
pip install -e ".[dev]"

# Start the API server
shieldops serve --reload
```

The API is now running at `http://localhost:8000`. View the interactive docs at `http://localhost:8000/api/v1/docs`.

### Run Tests

```bash
pytest tests/ -v --cov=src/shieldops
```

### Lint & Type Check

```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/shieldops/
```

## Project Structure

```
ShieldOps/
├── CLAUDE.md                          # Project conventions & architecture
├── pyproject.toml                     # Python package configuration
├── .env.example                       # Environment variable template
│
├── src/shieldops/
│   ├── agents/                        # AI agent implementations
│   │   ├── investigation/             # Root cause analysis agent
│   │   ├── remediation/               # Infrastructure execution agent
│   │   ├── security/                  # Security posture agent
│   │   ├── learning/                  # Continuous improvement agent
│   │   ├── cost/                      # Cloud cost optimization agent
│   │   ├── prediction/                # Predictive incident detection
│   │   ├── supervisor/                # Multi-agent orchestrator
│   │   ├── custom/                    # Custom agent builder
│   │   ├── knowledge/                 # RAG over incidents & runbooks
│   │   ├── calibration/               # Agent confidence calibration
│   │   └── registry.py                # Agent fleet registry
│   ├── connectors/                    # Multi-cloud abstraction layer
│   │   ├── base.py                    #   Connector interface & router
│   │   ├── kubernetes/                #   Kubernetes
│   │   ├── aws/                       #   AWS (EC2, ECS, Lambda)
│   │   ├── gcp/                       #   GCP
│   │   ├── azure/                     #   Azure
│   │   ├── linux/                     #   Bare-metal SSH/Ansible
│   │   └── windows/                   #   Windows WinRM
│   ├── observability/                 # Telemetry ingestion
│   │   ├── splunk/                    #   Splunk integration
│   │   ├── datadog/                   #   Datadog integration
│   │   ├── prometheus/                #   Prometheus integration
│   │   ├── cloudwatch/                #   AWS CloudWatch
│   │   ├── newrelic/                  #   New Relic integration
│   │   ├── elastic/                   #   Elastic/OpenSearch integration
│   │   └── otel/                      #   OpenTelemetry native
│   ├── policy/                        # Safety & governance
│   │   ├── opa/client.py              #   OPA policy evaluation
│   │   ├── approval/workflow.py       #   Human approval workflows
│   │   └── rollback/                  #   Rollback mechanisms
│   ├── orchestration/                 # Agent orchestration utilities
│   ├── compliance/                    # SOC2, PCI-DSS, HIPAA engines
│   ├── analytics/                     # Anomaly detection, capacity planning
│   ├── auth/                          # OIDC/SSO authentication
│   ├── billing/                       # Stripe billing & plan enforcement
│   ├── sla/                           # SLA management engine
│   ├── topology/                      # Service dependency mapping
│   ├── vulnerability/                 # Posture aggregation & reporting
│   ├── workers/                       # Background task queue
│   ├── integrations/                  # CVE sources, scanners, billing, ITSM
│   ├── scheduler/                     # Job scheduling (learning, scans)
│   ├── changes/                       # Change tracking / deployment correlation
│   ├── cache/                         # Redis cache layer
│   ├── plugins/                       # Plugin SDK & extension framework
│   ├── playbooks/                     # Playbook loader, AI generator, auto-applier
│   ├── api/                           # FastAPI application
│   │   ├── app.py                     #   App factory & middleware
│   │   ├── auth/                      #   JWT auth, RBAC
│   │   ├── routes/                    #   API endpoints
│   │   ├── middleware/                #   Rate limiting, security headers
│   │   └── ws/                        #   WebSocket routes
│   ├── models/base.py                 # Core Pydantic models
│   ├── config/settings.py             # Environment configuration
│   └── cli.py                         # CLI entry point
│
├── playbooks/                         # Remediation playbooks (YAML)
│   └── policies/                      # Default OPA policies
│
├── infrastructure/
│   ├── docker/                        # Dockerfile & docker-compose
│   └── kubernetes/                    # K8s manifests with RBAC
│
├── dashboard-ui/                      # React + TypeScript dashboard
│
├── tests/
│   ├── unit/                          # Unit tests (9,000+ tests)
│   └── integration/                   # Integration tests
│
├── docs/
│   ├── prd/                           # Product Requirements Documents
│   ├── architecture/                  # ADRs & design specs
│   └── business/                      # Pitch deck, GTM, financials
│
└── .github/workflows/ci.yml          # CI pipeline
```

## API Endpoints

| Category | Key Endpoints |
|----------|--------------|
| **Health** | `GET /health`, `GET /ready`, `GET /metrics` |
| **Agents** | `GET /api/v1/agents`, `GET /api/v1/agents/{id}` |
| **Investigations** | `GET /api/v1/investigations`, `POST /api/v1/investigations` |
| **Remediations** | `GET /api/v1/remediations`, `POST /api/v1/remediations/{id}/approve` |
| **Security** | `GET /api/v1/security/posture`, `GET /api/v1/security/compliance/{framework}` |
| **Vulnerabilities** | `GET /api/v1/vulnerabilities`, `GET /api/v1/vulnerabilities/{id}` |
| **Compliance** | `GET /api/v1/compliance/soc2`, `GET /api/v1/compliance/pci-dss`, `GET /api/v1/compliance/hipaa` |
| **Cost** | `GET /api/v1/cost/analysis`, `GET /api/v1/cost/recommendations` |
| **Learning** | `GET /api/v1/learning/cycles`, `GET /api/v1/learning/recommendations` |
| **Predictions** | `POST /api/v1/predictions/run`, `GET /api/v1/predictions/active` |
| **Playbooks** | `GET /api/v1/playbooks`, `POST /api/v1/playbooks/ai/generate` |
| **Billing** | `GET /api/v1/billing/usage`, `POST /api/v1/billing/subscribe` |
| **Webhooks** | `POST /api/v1/webhooks/subscriptions`, `GET /api/v1/webhooks/subscriptions` |
| **Plugins** | `GET /api/v1/plugins`, `POST /api/v1/plugins/install` |
| **Analytics** | `GET /api/v1/analytics/mttr`, `GET /api/v1/analytics/resolution-rate` |
| **Tenant Isolation** | `POST /api/v1/tenant-isolation`, `GET /api/v1/tenant-isolation/{id}` |
| **Alert Noise** | `POST /api/v1/alert-noise/alerts`, `POST /api/v1/alert-noise/analyze` |
| **Threshold Tuning** | `POST /api/v1/threshold-tuner/thresholds`, `POST /api/v1/threshold-tuner/recommendations/generate` |
| **Severity Prediction** | `POST /api/v1/severity-predictor/predict`, `GET /api/v1/severity-predictor/accuracy` |
| **Impact Analysis** | `POST /api/v1/impact-analyzer/simulate`, `GET /api/v1/impact-analyzer/critical-services` |
| **Config Audit** | `POST /api/v1/config-audit/changes`, `GET /api/v1/config-audit/history` |
| **Deployment Velocity** | `POST /api/v1/deployment-velocity/events`, `GET /api/v1/deployment-velocity/velocity` |
| **Compliance Automation** | `POST /api/v1/compliance-automation/rules`, `POST /api/v1/compliance-automation/violations` |
| **Knowledge Base** | `POST /api/v1/knowledge-articles`, `GET /api/v1/knowledge-articles/search` |
| **On-Call Fatigue** | `POST /api/v1/oncall-fatigue/pages`, `GET /api/v1/oncall-fatigue/burnout-risks` |
| **Backup Verification** | `POST /api/v1/backup-verification/backups`, `GET /api/v1/backup-verification/recovery-readiness` |
| **Cost Tag Enforcement** | `POST /api/v1/cost-tag-enforcer/policies`, `GET /api/v1/cost-tag-enforcer/compliance-summary` |
| **DR Readiness** | `POST /api/v1/dr-readiness/plans`, `GET /api/v1/dr-readiness/readiness/{service}` |
| **Service Catalog** | `POST /api/v1/service-catalog/services`, `POST /api/v1/service-catalog/validate` |
| **Contract Testing** | `POST /api/v1/contract-testing/schemas`, `POST /api/v1/contract-testing/check` |
| **Orphan Detector** | `POST /api/v1/orphan-detector/orphans`, `GET /api/v1/orphan-detector/summary` |
| **Latency Profiler** | `POST /api/v1/latency-profiler/samples`, `POST /api/v1/latency-profiler/regressions` |
| **License Scanner** | `POST /api/v1/license-scanner/dependencies`, `POST /api/v1/license-scanner/evaluate/{project}` |
| **Release Manager** | `POST /api/v1/release-manager/releases`, `POST /api/v1/release-manager/{id}/approve` |
| **Budget Manager** | `POST /api/v1/budget-manager/budgets`, `GET /api/v1/budget-manager/alerts` |
| **Config Parity** | `POST /api/v1/config-parity/configs`, `POST /api/v1/config-parity/compare` |
| **Incident Dedup** | `POST /api/v1/incident-dedup/incidents`, `POST /api/v1/incident-dedup/{id}/auto-merge` |
| **Access Certification** | `POST /api/v1/access-certification/grants`, `POST /api/v1/access-certification/campaigns` |
| **Toil Tracker** | `POST /api/v1/toil-tracker/entries`, `GET /api/v1/toil-tracker/candidates` |

Full interactive API documentation is available at `/api/v1/docs` when the server is running.

## Remediation Playbooks

Playbooks define how agents investigate and remediate specific incident types:

```yaml
# playbooks/pod-crash-loop.yaml
name: pod-crash-loop
trigger:
  alert_type: "KubePodCrashLooping"

investigation:
  steps:
    - check_pod_status
    - check_pod_logs
    - check_recent_deployments
    - check_resource_usage

remediation:
  decision_tree:
    - condition: "OOMKilled"
      action: increase_memory_limit
    - condition: "recent_deployment"
      action: rollback_deployment
    - condition: "dependency_unhealthy"
      action: restart_pod_with_backoff
```

## OPA Policies

Default policies ship with the platform and can be customized per environment:

- **`no_delete_data`** — Agents cannot delete databases or persistent volumes
- **`prod_requires_approval`** — All production writes require human approval
- **`max_blast_radius`** — Limit affected resources per action (dev: 50, staging: 20, prod: 5)
- **`rate_limit_actions`** — Max actions per hour per environment
- **`change_freeze_window`** — Block changes during configured freeze windows

## Development Phases

| Phase | Theme | Status |
|-------|-------|--------|
| Phase 1 | Project scaffolding & core architecture | Completed |
| Phase 2 | Investigation Agent (AWS + K8s + Splunk + Prometheus) | Completed |
| Phase 3 | Remediation Agent with OPA policy gates | Completed |
| Phase 4 | Unified Dashboard (React + TypeScript) | Completed |
| Phase 5 | Multi-Cloud Connectors (GCP, Azure, Windows) | Completed |
| Phase 6 | Security Agent + CVE management | Completed |
| Phase 7 | Learning Agent + Cost Agent | Completed |
| Phase 8 | Enterprise features (SSO, RBAC, billing, multi-tenant) | Completed |
| Phase 9 | Production-scale ops (scheduler, webhooks, GraphQL) | Completed |
| Phase 10 | Production-scale ops (caching, workers, ITSM, mobile push) | Completed |
| Phase 11 | Security Platform Sophistication (SBOM, MITRE ATT&CK, EPSS) | Completed |
| Phase 12 | Autonomous Intelligence & Platform Ecosystem | Completed |
| Phase 13 | Advanced Observability & Platform Hardening | Completed |
| Phase 14 | Enterprise Scalability & Developer Experience | Completed |
| Phase 15 | Operational Intelligence & Reliability Engineering | Completed |
| Phase 16 | Operational Resilience & Intelligent Automation | Completed |
| Phase 17 | Incident Intelligence & FinOps Automation | Completed |
| Phase 18 | Advanced Security & Intelligent Operations | Completed |
| Phase 19 | Intelligent Automation & Governance | Completed |
| Phase 20 | Platform Intelligence & Enterprise Hardening | Completed |
| Phase 21 | Disaster Recovery, Service Intelligence & Resource Governance | Completed |
| Phase 22 | Proactive Intelligence & Security Operations | Completed |
| Phase 23 | Infrastructure Intelligence & Resource Optimization | Completed |
| Phase 24 | Autonomous Resilience & Platform Hardening | Completed |
| Phase 25 | Chaos Engineering & Operational Intelligence | Completed |
| Phase 26 | Platform Intelligence & Operational Excellence | Completed |
| Phase 27 | Advanced Reliability & Cost Governance | Completed |
| Phase 28 | Predictive Operations & Intelligent Governance | Completed |
| Phase 29 | Predictive Intelligence & Platform Resilience | Completed |
| Phase 30 | Adaptive Platform Intelligence & Autonomous Operations | Completed |
| Phase 31 | Intelligent Signal Management & Operational Excellence | Completed |
| Phase 32 | Developer Productivity & Service Mesh Intelligence | Completed |
| Phase 33 | Incident Self-Healing & Platform Governance Intelligence | Completed |
| Phase 34 | Proactive Intelligence & Cross-Functional Analytics | Completed |
| Phase 35 | Platform Economics & Governance Intelligence | Completed |
| Phase 36 | Multi-Channel Communication & Multi-Agent Intelligence | Completed |
| Phase 37 | Security Automation & Autonomous Remediation | Completed |
| Phase 38 | Intelligent Operations & Platform Resilience | Completed |
| Phase 39 | Advanced Platform Intelligence & Operational Excellence | Completed |

## Documentation

| Document | Description |
|----------|-------------|
| [PRD-001: Investigation Agent](docs/prd/PRD-001-investigation-agent.md) | Autonomous root cause analysis |
| [PRD-002: Remediation Agent](docs/prd/PRD-002-remediation-agent.md) | Policy-gated infrastructure execution |
| [PRD-003: Security Agent](docs/prd/PRD-003-security-agent.md) | Continuous security posture management |
| [PRD-004: Unified Dashboard](docs/prd/PRD-004-unified-dashboard.md) | Real-time agent monitoring command center |
| [PRD-005: Multi-Cloud Connectors](docs/prd/PRD-005-multi-cloud-connectors.md) | Unified abstraction layer |
| [PRD-006: Policy Engine](docs/prd/PRD-006-policy-engine.md) | OPA-powered action governance |
| [PRD-007: Learning Agent](docs/prd/PRD-007-learning-agent.md) | Continuous improvement from outcomes |
| [ADR-001: LangGraph Selection](docs/architecture/adr-001-langgraph-selection.md) | Why LangGraph over CrewAI/AutoGen |
| [ADR-002: Multi-Cloud Abstraction](docs/architecture/adr-002-multi-cloud-abstraction.md) | Connector architecture |
| [ADR-003: Agent Safety Model](docs/architecture/adr-003-agent-safety-model.md) | Five-layer defense in depth |
| [Architecture Overview](docs/architecture/overview.md) | Four-layer architecture design |
| [Dashboard Design](docs/architecture/dashboard-design.md) | Wireframes & component hierarchy |

## Contributing

We're building in the open. To contribute:

1. Fork the repository
2. Create a feature branch (`feat/your-feature`)
3. Write tests for new functionality
4. Ensure `ruff check` and `pytest` pass
5. Submit a pull request

Please follow [conventional commits](https://www.conventionalcommits.org/) for commit messages.

## License

Proprietary. All rights reserved.

---

<p align="center">
  <strong>ShieldOps</strong> — Stop firefighting infrastructure. Start letting AI handle it.
</p>
