# ShieldOps

**AI-Powered Autonomous SRE Platform**

> Your infrastructure never sleeps. Neither should its intelligence.

ShieldOps deploys autonomous AI agents that investigate incidents, execute remediations, enforce security policies, and learn from outcomes — across multi-cloud (AWS/GCP/Azure) and on-premise Linux environments.

Unlike existing tools that only *analyze*, ShieldOps agents *act* — with policy-gated safety, full audit trails, and one-click rollback.

---

## Why ShieldOps?

| Problem | ShieldOps Solution |
|---------|-------------------|
| SRE teams handle 50+ alerts/day manually | Agents auto-investigate and resolve incidents 24/7 |
| MTTR averages 2+ hours for P1 incidents | Root cause in minutes, remediation in seconds |
| 70% of enterprises lack DevSecOps expertise | Security policies enforced continuously by agents |
| Multi-cloud complexity growing 3x faster than teams | One agent works across AWS, GCP, Azure, K8s, and bare-metal Linux |
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
│  Supervisor agent · Multi-agent coordination         │
├─────────────────────────────────────────────────────┤
│  Layer 2: Observability Ingestion                   │
│  OpenTelemetry · Splunk · Datadog · Prometheus      │
│  Vendor-neutral telemetry · No rip-and-replace       │
├─────────────────────────────────────────────────────┤
│  Layer 1: Multi-Environment Connectors              │
│  AWS · GCP · Azure · Kubernetes · Linux (SSH)       │
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
| Dashboard | React + TypeScript + Tailwind CSS |
| Database | PostgreSQL (state), Redis (coordination) |
| Messaging | Apache Kafka |
| Infrastructure | Kubernetes, Terraform |
| Observability | OpenTelemetry, LangSmith |
| Policy Engine | Open Policy Agent (OPA) |
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
│   │   │   ├── graph.py               #   LangGraph workflow
│   │   │   ├── nodes.py               #   Node implementations
│   │   │   └── models.py              #   State models
│   │   ├── remediation/               # Infrastructure execution agent
│   │   ├── security/                  # Security posture agent
│   │   ├── learning/                  # Continuous improvement agent
│   │   └── supervisor/                # Multi-agent orchestrator
│   ├── connectors/                    # Multi-cloud abstraction layer
│   │   ├── base.py                    #   Connector interface & router
│   │   ├── kubernetes/connector.py    #   K8s implementation
│   │   ├── aws/                       #   AWS (EC2, ECS, Lambda)
│   │   ├── gcp/                       #   GCP (Phase 2)
│   │   ├── azure/                     #   Azure (Phase 2)
│   │   └── linux/                     #   Bare-metal SSH/Ansible
│   ├── observability/                 # Telemetry ingestion
│   │   ├── splunk/                    #   Splunk integration
│   │   ├── datadog/                   #   Datadog integration
│   │   ├── prometheus/                #   Prometheus integration
│   │   └── otel/                      #   OpenTelemetry native
│   ├── policy/                        # Safety & governance
│   │   ├── opa/client.py              #   OPA policy evaluation
│   │   ├── approval/workflow.py       #   Human approval workflows
│   │   └── rollback/                  #   Rollback mechanisms
│   ├── orchestration/supervisor.py    # Supervisor agent
│   ├── api/                           # FastAPI application
│   │   ├── app.py                     #   App factory & middleware
│   │   └── routes/                    #   API endpoints
│   ├── models/base.py                 # Core Pydantic models
│   ├── config/settings.py             # Environment configuration
│   └── cli.py                         # CLI entry point
│
├── playbooks/                         # Remediation playbooks (YAML)
│   ├── pod-crash-loop.yaml
│   ├── high-latency.yaml
│   └── policies/shieldops.rego        # Default OPA policies
│
├── infrastructure/
│   ├── docker/                        # Dockerfile & docker-compose
│   └── kubernetes/                    # K8s manifests with RBAC
│
├── tests/
│   └── unit/                          # Unit tests
│
├── docs/
│   ├── prd/                           # Product Requirements Documents
│   ├── architecture/                  # ADRs & design specs
│   └── business/                      # Pitch deck, GTM, financials
│
└── .github/workflows/ci.yml          # CI pipeline
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/agents` | List all agents with status |
| `GET` | `/api/v1/agents/{id}` | Agent detail & config |
| `GET` | `/api/v1/investigations` | Active/recent investigations |
| `GET` | `/api/v1/investigations/{id}` | Investigation detail with reasoning chain |
| `GET` | `/api/v1/remediations` | Remediation timeline |
| `POST` | `/api/v1/remediations/{id}/approve` | Approve pending remediation |
| `POST` | `/api/v1/remediations/{id}/rollback` | Rollback a remediation |
| `GET` | `/api/v1/analytics/mttr` | MTTR trends |
| `GET` | `/api/v1/analytics/resolution-rate` | Auto-resolution metrics |
| `GET` | `/api/v1/security/posture` | Security overview |
| `GET` | `/api/v1/security/compliance/{framework}` | Compliance status (SOC 2, PCI-DSS, HIPAA) |

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

## Roadmap

### Phase 1: MVP (Months 0-6)
- [x] Project scaffolding & architecture
- [ ] Investigation Agent (AWS + K8s + Splunk + Prometheus)
- [ ] Remediation Agent with OPA policy gates
- [ ] Unified Dashboard (Fleet Overview + Investigation Detail)
- [ ] 10 pre-built remediation playbooks
- [ ] 3 design partners in production

### Phase 2: Multi-Cloud (Months 7-12)
- [ ] GCP + Azure connector parity
- [ ] Security Agent (CVE patching, credential rotation)
- [ ] Compliance packs (SOC 2, PCI-DSS, HIPAA)
- [ ] Datadog + New Relic integrations
- [ ] Self-service Starter tier

### Phase 3: Scale (Months 13-18)
- [ ] Learning Agent (continuous improvement from outcomes)
- [ ] Custom playbook builder UI
- [ ] AWS/Azure/GCP Marketplace listings
- [ ] Advanced analytics & ROI reporting
- [ ] Enterprise SSO & multi-tenancy

## Documentation

| Document | Description |
|----------|-------------|
| [PRD-001: Investigation Agent](docs/prd/PRD-001-investigation-agent.md) | Autonomous root cause analysis |
| [PRD-002: Remediation Agent](docs/prd/PRD-002-remediation-agent.md) | Policy-gated infrastructure execution |
| [PRD-003: Security Agent](docs/prd/PRD-003-security-agent.md) | Continuous security posture management |
| [PRD-004: Unified Dashboard](docs/prd/PRD-004-unified-dashboard.md) | Real-time agent monitoring command center |
| [PRD-005: Multi-Cloud Connectors](docs/prd/PRD-005-multi-cloud-connectors.md) | Unified abstraction layer |
| [PRD-006: Policy Engine](docs/prd/PRD-006-policy-engine.md) | OPA-powered action governance |
| [ADR-001: LangGraph Selection](docs/architecture/adr-001-langgraph-selection.md) | Why LangGraph over CrewAI/AutoGen |
| [ADR-002: Multi-Cloud Abstraction](docs/architecture/adr-002-multi-cloud-abstraction.md) | Connector architecture |
| [ADR-003: Agent Safety Model](docs/architecture/adr-003-agent-safety-model.md) | Five-layer defense in depth |
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
