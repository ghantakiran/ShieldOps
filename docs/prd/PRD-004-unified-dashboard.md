# PRD-004: Unified Agent Dashboard

**Status:** Implemented
**Author:** ShieldOps Team
**Date:** 2026-02-17
**Priority:** P0 (MVP)

## Problem Statement
Operating autonomous AI agents without visibility is unacceptable for enterprise customers. Teams need to see what agents are doing, why they made decisions, and whether to trust their actions. Current agent platforms offer limited observability into agent reasoning and execution.

## Objective
Build a unified dashboard that provides real-time visibility into all ShieldOps agents across all managed environments — showing agent status, active investigations, remediation actions, security posture, and performance metrics.

## Target Persona
- **Primary:** SRE Team Lead (monitors fleet of agents across environments)
- **Secondary:** On-call SRE (needs quick view of active incidents and agent actions)
- **Tertiary:** VP Engineering / CISO (executive view of operational health)

## User Stories

### US-1: Agent Fleet Overview
**As** an SRE team lead, **I want** a single-pane-of-glass view of all deployed agents **so that** I can see fleet health at a glance.

**Acceptance Criteria:**
- Dashboard shows all agents with status (active, idle, investigating, remediating, error)
- Environment breakdown (AWS, GCP, Azure, on-prem) with agent count per environment
- Real-time agent heartbeat (last check-in, uptime)
- Alert badges for agents in error state or requiring attention
- Filterable by environment, agent type, status

### US-2: Live Investigation Feed
**As** an on-call SRE, **I want** to see live agent investigations with reasoning chains **so that** I can understand what the agent is doing and intervene if needed.

**Acceptance Criteria:**
- Real-time feed of active investigations (newest first)
- Each investigation shows: alert source, current step, elapsed time, confidence score
- Expandable reasoning chain showing step-by-step agent logic
- Evidence panel: logs, metrics, traces the agent examined
- Action buttons: approve, reject, take over manually, add context

### US-3: Remediation Timeline
**As** an SRE, **I want** a chronological timeline of all remediations **so that** I can track what the agent changed and when.

**Acceptance Criteria:**
- Timeline view with all remediation actions (newest first)
- Each entry shows: action, target, risk level, approval status, outcome
- Diff view: before/after state for infrastructure changes
- One-click rollback button for any remediation
- Filter by environment, time range, action type, outcome

### US-4: Performance Analytics
**As** a VP Engineering, **I want** to see MTTR trends and agent effectiveness over time **so that** I can justify ROI to leadership.

**Acceptance Criteria:**
- MTTR trend chart (before vs. after ShieldOps)
- Automated resolution rate (% of incidents resolved without human)
- Agent accuracy over time (correct diagnoses / total investigations)
- Alert volume trend (total alerts, auto-resolved, escalated)
- Cost savings estimate (hours saved × engineer hourly rate)
- Exportable PDF report for stakeholder presentations

### US-5: Security Posture View
**As** a CISO, **I want** a security dashboard showing vulnerability status and compliance scores **so that** I have continuous security visibility.

**Acceptance Criteria:**
- CVE heatmap across managed infrastructure
- Compliance score gauges per framework (SOC 2, PCI-DSS, HIPAA)
- Credential rotation status (upcoming expirations, recent rotations)
- Security event timeline (patches applied, policies enforced)
- Drift alerts with remediation status

### US-6: Agent Configuration & Control
**As** an admin, **I want** to configure agent behavior from the dashboard **so that** I can adjust policies without code changes.

**Acceptance Criteria:**
- View/edit OPA policies per environment
- Adjust agent confidence thresholds
- Enable/disable agent types per environment
- Set change freeze windows
- Manage approval workflows and escalation paths
- View agent logs and debug traces

## Dashboard Pages

### Page 1: Fleet Overview (Home)
```
┌─────────────────────────────────────────────────────────────┐
│  ShieldOps Command Center                    [env filter ▾] │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Agents   │ │ Active   │ │ Resolved │ │ MTTR     │      │
│  │ 24 total │ │ 3 invest │ │ 47 today │ │ 4.2 min  │      │
│  │ 23 ✓ 1 ⚠│ │ 1 remed  │ │ ↓32% wow │ │ ↓58% mom │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│                                                             │
│  Environment Map                                            │
│  ┌──────────────────────────────────────────────┐          │
│  │  AWS (12 agents)  │  GCP (6)  │  On-Prem (6) │         │
│  │  ✓✓✓✓✓✓✓✓✓✓✓⚠   │  ✓✓✓✓✓✓  │  ✓✓✓✓✓✓    │         │
│  └──────────────────────────────────────────────┘          │
│                                                             │
│  Live Activity Feed                          [filter ▾]    │
│  ┌─────────────────────────────────────────────┐           │
│  │ 🔍 Investigation: High latency on api-svc  │ 2m ago    │
│  │    Confidence: 0.78 │ Step: Analyzing traces│           │
│  │ ✅ Remediation: Restarted cart-svc pod     │ 5m ago    │
│  │    Auto-resolved │ Health check passed      │           │
│  │ 🔒 Security: Patched CVE-2026-1234        │ 12m ago   │
│  │    3 hosts patched │ Validation complete     │           │
│  └─────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

### Page 2: Investigation Detail
- Full reasoning chain with expandable steps
- Evidence panel (logs, metrics, traces)
- Hypothesis ranking with confidence scores
- Action panel (approve remediation, take over, add context)

### Page 3: Remediation Timeline
- Chronological feed of all actions
- Before/after diffs
- Rollback controls
- Approval audit trail

### Page 4: Analytics & Reporting
- MTTR trends, resolution rates, agent accuracy
- Cost savings calculator
- Exportable reports (PDF, CSV)

### Page 5: Security Posture
- CVE heatmap, compliance scores
- Credential rotation status
- Policy enforcement history

### Page 6: Settings & Configuration
- OPA policy editor
- Agent threshold configuration
- Environment management
- Approval workflow builder
- Integration settings (Slack, PagerDuty, etc.)

## Technical Design

### Frontend Architecture
- **Framework:** React 18 + TypeScript
- **Styling:** Tailwind CSS + shadcn/ui components
- **State:** React Query (server state) + Zustand (client state)
- **Real-time:** WebSocket connection for live agent feed
- **Charts:** Recharts for analytics visualizations
- **Build:** Vite

### Backend API (FastAPI)
```
GET    /api/v1/agents                     # List all agents with status
GET    /api/v1/agents/{id}                # Agent detail + config
GET    /api/v1/investigations             # Active/recent investigations
GET    /api/v1/investigations/{id}        # Investigation detail with reasoning
GET    /api/v1/remediations               # Remediation timeline
POST   /api/v1/remediations/{id}/rollback # Trigger rollback
POST   /api/v1/remediations/{id}/approve  # Approve pending remediation
GET    /api/v1/analytics/mttr             # MTTR trends
GET    /api/v1/analytics/resolution-rate  # Auto-resolution metrics
GET    /api/v1/security/posture           # Security overview
GET    /api/v1/security/cves              # CVE status
PUT    /api/v1/settings/policies          # Update OPA policies
PUT    /api/v1/settings/thresholds        # Update agent thresholds
WS     /api/v1/ws/feed                    # Real-time event stream
```

### Real-Time Architecture
```
Agent Events → Kafka → WebSocket Gateway → Dashboard
                  ↓
           PostgreSQL (persistence) → REST API → Dashboard (historical)
```

## Success Metrics
| Metric | Target |
|--------|--------|
| Dashboard Load Time | < 2 seconds (P95) |
| Real-time Event Latency | < 500ms (agent action → dashboard) |
| User Session Duration | > 10 minutes (indicates value) |
| Feature Adoption | 80% of users access analytics weekly |
| NPS | > 50 from dashboard users |

## MVP Scope
- Fleet overview page
- Live investigation feed with reasoning
- Remediation timeline with rollback
- Basic analytics (MTTR, resolution rate)
- WebSocket real-time updates

## Phase 2 Additions
- Security posture page
- OPA policy editor
- Exportable reports
- Mobile-responsive design
- Dark mode

## Timeline
- **Week 1-2:** API endpoints + WebSocket gateway
- **Week 3-4:** Fleet overview page + agent status
- **Week 5-6:** Investigation detail view with reasoning chain
- **Week 7-8:** Remediation timeline + rollback controls
- **Week 9-10:** Analytics page + chart components
