# ShieldOps Unified Dashboard — Design Specification

## Overview
The unified dashboard provides real-time visibility into all ShieldOps agents across managed environments. It serves as the command center for SRE teams to monitor, control, and audit autonomous agent operations.

## Information Architecture

```
ShieldOps Dashboard
├── Fleet Overview (Home)          ← Real-time agent status, live feed
├── Investigations                  ← Active/historical investigation details
│   └── Investigation Detail        ← Full reasoning chain, evidence
├── Remediations                    ← Action timeline, rollback controls
│   └── Remediation Detail          ← Before/after diff, audit trail
├── Analytics                       ← MTTR trends, resolution rates, ROI
├── Security                        ← CVE heatmap, compliance scores
└── Settings                        ← Policies, thresholds, integrations
```

## Page Designs

### Page 1: Fleet Overview (Home)

```
┌──────────────────────────────────────────────────────────────────┐
│  SHIELDOPS COMMAND CENTER                                        │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                 │
│  │ All  │ │ AWS  │ │ GCP  │ │Azure │ │OnPrem│  [+ Add Env]    │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐│
│  │ AGENTS      │ │ ACTIVE NOW  │ │ RESOLVED    │ │ MTTR       ││
│  │    24       │ │    4        │ │   47 today  │ │  4.2 min   ││
│  │ 23●  1▲    │ │ 3 invest    │ │ ↓32% vs     │ │ ↓58% vs    ││
│  │ healthy err │ │ 1 remediate │ │ last week   │ │ last month ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘│
│                                                                  │
│  ┌────────────────────────────────────┬─────────────────────────┐│
│  │  ENVIRONMENT MAP                   │  AGENT HEALTH           ││
│  │                                    │                         ││
│  │  AWS us-east-1  [8 agents]        │  Investigation  6 ●●●●●●││
│  │    ●●●●●●●● (all healthy)        │  Remediation   4 ●●●●  ││
│  │                                    │  Security      8 ●●●●●●●●│
│  │  AWS us-west-2  [4 agents]        │  Learning      6 ●●●●●● ││
│  │    ●●●▲ (1 error)                │                         ││
│  │                                    │  ● Healthy  ▲ Error    ││
│  │  On-Prem DC1   [6 agents]        │  ◆ Idle     ■ Disabled  ││
│  │    ●●●●●● (all healthy)          │                         ││
│  │                                    │                         ││
│  │  GCP us-central [6 agents]        │                         ││
│  │    ●●●●●● (all healthy)          │                         ││
│  └────────────────────────────────────┴─────────────────────────┘│
│                                                                  │
│  LIVE ACTIVITY FEED                              [filter ▾]      │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │ ● 14:23  INVESTIGATING  High latency on payment-svc         ││
│  │          Confidence: 0.78  Step: Analyzing traces            ││
│  │          AWS us-east-1 / production                          ││
│  │                                          [View] [Take Over] ││
│  ├──────────────────────────────────────────────────────────────┤│
│  │ ✓ 14:18  RESOLVED  Restarted cart-svc pod (crash loop)      ││
│  │          Auto-resolved  Health check passed  Duration: 3.2m ││
│  │          AWS us-east-1 / production                          ││
│  │                                          [View] [Rollback]  ││
│  ├──────────────────────────────────────────────────────────────┤│
│  │ ✓ 14:05  PATCHED  CVE-2026-1234 on 3 hosts                 ││
│  │          Security agent  All validations passed              ││
│  │          On-Prem DC1 / production                            ││
│  │                                                    [View]   ││
│  ├──────────────────────────────────────────────────────────────┤│
│  │ ⏳ 14:01  AWAITING APPROVAL  Scale order-svc to 8 replicas  ││
│  │          Risk: MEDIUM  Requested by: investigation-agent-7   ││
│  │          AWS us-east-1 / production                          ││
│  │                                       [Approve] [Deny]     ││
│  └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

### Page 2: Investigation Detail View

```
┌──────────────────────────────────────────────────────────────────┐
│  ← Back to Investigations                                        │
│                                                                  │
│  INVESTIGATION: High latency on payment-svc                      │
│  Alert: HighP99Latency | Severity: Critical | Duration: 4m 23s  │
│  Environment: AWS us-east-1 / production                         │
│                                                                  │
│  ┌──────────────────────────┬───────────────────────────────────┐│
│  │  REASONING CHAIN         │  EVIDENCE PANEL                   ││
│  │                          │                                   ││
│  │  1. ● Gather Context     │  [Logs] [Metrics] [Traces]       ││
│  │     Service topology     │                                   ││
│  │     loaded, 3 deps found │  Metric: P99 Latency             ││
│  │     Duration: 1.2s       │  ┌──────────────────────┐        ││
│  │                          │  │     ╱‾‾‾‾‾╲          │        ││
│  │  2. ● Analyze Logs       │  │    ╱       ╲  ← alert│        ││
│  │     Found 47 error       │  │───╱         ╲────────│        ││
│  │     entries in last 5m   │  │  baseline    current  │        ││
│  │     Pattern: "conn       │  └──────────────────────┘        ││
│  │     timeout to db-main"  │                                   ││
│  │     Duration: 3.4s       │  Log Samples:                    ││
│  │                          │  14:21:03 ERROR conn timeout      ││
│  │  3. ● Analyze Metrics    │  14:21:05 ERROR conn timeout      ││
│  │     CPU: 45% (normal)    │  14:21:07 WARN pool exhausted    ││
│  │     Memory: 72% (normal) │  14:21:09 ERROR conn timeout      ││
│  │     DB conn pool: 100%   │                                   ││
│  │     ← ANOMALY            │  Trace: request-id-xyz           ││
│  │     Duration: 2.1s       │  payment-svc ──→ db-main (5.2s)  ││
│  │                          │  ↑ bottleneck                     ││
│  │  4. ● Analyze Traces     │                                   ││
│  │     Bottleneck: db-main  │                                   ││
│  │     Slow span: 5.2s      │                                   ││
│  │     Duration: 4.5s       │                                   ││
│  │                          │                                   ││
│  │  5. ● Correlate          │                                   ││
│  │     DB conn pool         │                                   ││
│  │     exhausted → timeouts │                                   ││
│  │     → high latency       │                                   ││
│  │                          │                                   ││
│  │  6. ● Hypothesis         │                                   ││
│  │     Generated 2 hypos    │                                   ││
│  └──────────────────────────┴───────────────────────────────────┘│
│                                                                  │
│  HYPOTHESES                                                      │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  #1  Connection pool exhaustion (confidence: 0.91)           ││
│  │      DB connection pool saturated at 100%. Recent traffic    ││
│  │      spike exceeded pool capacity. All new requests timeout. ││
│  │      Recommended: Increase pool size from 20 → 30            ││
│  │                                                              ││
│  │      [Approve Remediation]  [Modify]  [Reject]              ││
│  ├──────────────────────────────────────────────────────────────┤│
│  │  #2  Database performance degradation (confidence: 0.34)     ││
│  │      Possible slow query or lock contention on db-main.      ││
│  │                                                              ││
│  │      [Investigate Further]                                   ││
│  └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

### Page 3: Analytics Dashboard

```
┌──────────────────────────────────────────────────────────────────┐
│  ANALYTICS                     Period: [7d] [30d] [90d] [Custom]│
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ MTTR         │ │ AUTO-RESOLVE │ │ COST SAVINGS │            │
│  │  4.2 min     │ │    67%       │ │  $142K       │            │
│  │  ↓58% MoM    │ │  ↑12% MoM   │ │  ↑23% MoM   │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│                                                                  │
│  MTTR TREND                                                      │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │ 60m ┤                                                        ││
│  │ 50m ┤  ╲                                                     ││
│  │ 40m ┤   ╲                                                    ││
│  │ 30m ┤    ╲     before ShieldOps                              ││
│  │ 20m ┤     ╲                                                  ││
│  │ 10m ┤      ╲───── ShieldOps deployed ─── ─── ───            ││
│  │  5m ┤                                      ╲___╱  ← current ││
│  │     └──────────────────────────────────────────────          ││
│  │      Jan    Feb    Mar    Apr    May    Jun                   ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                  │
│  RESOLUTION BREAKDOWN              AGENT ACCURACY                │
│  ┌────────────────────────┐       ┌────────────────────────┐    │
│  │  ██████████░░ Auto 67% │       │  Correct:     78%      │    │
│  │  ████░░░░░░░░ Appr 22% │       │  Partially:   15%      │    │
│  │  ██░░░░░░░░░░ Esc  11% │       │  Incorrect:    7%      │    │
│  └────────────────────────┘       └────────────────────────┘    │
│                                                                  │
│  [Export PDF Report]  [Export CSV]  [Schedule Weekly Report]     │
└──────────────────────────────────────────────────────────────────┘
```

## Component Hierarchy (React)

```
App
├── Layout
│   ├── Sidebar (navigation)
│   ├── Header (env selector, user, notifications)
│   └── Main Content
├── Pages
│   ├── FleetOverview
│   │   ├── StatsCards (agents, active, resolved, mttr)
│   │   ├── EnvironmentMap
│   │   ├── AgentHealthGrid
│   │   └── LiveActivityFeed
│   │       └── ActivityFeedItem (investigation/remediation/security)
│   ├── Investigations
│   │   ├── InvestigationList
│   │   └── InvestigationDetail
│   │       ├── ReasoningChain
│   │       ├── EvidencePanel (tabs: logs, metrics, traces)
│   │       └── HypothesisList
│   ├── Remediations
│   │   ├── RemediationTimeline
│   │   └── RemediationDetail
│   │       ├── ActionDiff (before/after)
│   │       ├── ApprovalTrail
│   │       └── RollbackControl
│   ├── Analytics
│   │   ├── MTTRTrendChart
│   │   ├── ResolutionBreakdown
│   │   ├── AgentAccuracyChart
│   │   └── CostSavingsCalculator
│   ├── Security
│   │   ├── CVEHeatmap
│   │   ├── ComplianceGauges
│   │   └── CredentialRotationStatus
│   └── Settings
│       ├── PolicyEditor
│       ├── ThresholdConfig
│       ├── IntegrationManager
│       └── ApprovalWorkflowBuilder
└── Shared Components
    ├── StatusBadge
    ├── ConfidenceBar
    ├── RiskLevelBadge
    ├── EnvironmentTag
    ├── TimeAgo
    ├── Chart (Recharts wrapper)
    └── WebSocketProvider (real-time updates)
```

## Real-Time Architecture

```
Agent Events (Kafka) → WebSocket Gateway (FastAPI) → React Dashboard
                              │
                              ▼
                       Event Types:
                       - agent.status_change
                       - investigation.started
                       - investigation.step_completed
                       - investigation.hypothesis_generated
                       - remediation.requested
                       - remediation.approved
                       - remediation.executed
                       - remediation.validated
                       - security.cve_detected
                       - security.patch_applied
```

## Accessibility Requirements
- WCAG 2.1 AA compliance
- Keyboard navigation for all interactive elements
- Screen reader support for status changes
- Color-blind safe color palette for status indicators
- High contrast mode support

## Performance Targets
| Metric | Target |
|--------|--------|
| Initial Load (LCP) | < 2s |
| Event Latency (agent → dashboard) | < 500ms |
| Dashboard refresh rate | 1s (WebSocket) |
| Supports concurrent agents displayed | 500+ |
| Historical data query | < 3s for 90-day range |
