# PRD-007: Learning Agent

**Status:** Implemented
**Author:** ShieldOps Team
**Date:** 2026-02-17
**Priority:** P1

## Problem Statement

Autonomous SRE agents that don't learn from past incidents degrade operator trust over time. If the same alert fires repeatedly and the agent applies the same fix that previously failed, engineers lose confidence and revert to manual workflows. Without a feedback loop, alert thresholds stay stale (producing false positives), playbooks become outdated, and the platform's automation accuracy plateaus.

## Objective

Build a Learning Agent that analyzes historical incident outcomes, detects recurring patterns, recommends playbook updates, tunes alerting thresholds, and synthesizes improvement scores — creating a continuous feedback loop that makes the entire agent system smarter over time.

## Target Persona

- **Primary:** SRE Team Lead — wants evidence that automation is improving, not stagnating
- **Secondary:** Platform Engineer — needs playbook recommendations grounded in real incident data
- **Tertiary:** VP Engineering — wants quantitative proof that the platform delivers ROI over time

## User Stories

### US-1: Recurring Pattern Detection
**As** an SRE team lead, **I want** the agent to automatically identify recurring incident patterns across alert types **so that** we can prioritize permanent fixes for the most impactful issues.

**Acceptance Criteria:**
- Analyzes incident outcomes over configurable time periods (7d, 30d, 90d)
- Groups incidents by alert type and identifies recurring patterns (2+ occurrences)
- Reports common root cause, common resolution, frequency, and affected environments
- Assigns confidence scores to detected patterns
- LLM-powered assessment identifies automation gaps and high-impact opportunities

### US-2: Playbook Evolution
**As** a platform engineer, **I want** the agent to recommend new playbooks and improvements to existing ones **so that** our operational runbooks stay current with real-world incident data.

**Acceptance Criteria:**
- Detects alert types with no existing playbook and proposes new ones
- Identifies playbooks that need improvement (recurring patterns despite existing playbook)
- Flags incorrect automations and recommends pre-checks to prevent recurrence
- Provides actionable step-by-step recommendations based on actual incident data
- LLM-powered assessment prioritizes and refines recommendations

### US-3: Threshold Tuning
**As** an SRE, **I want** the agent to recommend alerting threshold adjustments **so that** we reduce false positive noise without missing real incidents.

**Acceptance Criteria:**
- Analyzes correlation between alert types and incorrect automated actions
- Maps alert types to underlying metrics (CPU, memory, disk, error rate, latency)
- Recommends threshold increases when false positive rate exceeds 10%
- Estimates false positive reduction for each proposed adjustment
- LLM-powered assessment validates and refines threshold recommendations

### US-4: Improvement Synthesis
**As** a VP Engineering, **I want** a quantitative improvement score each learning cycle **so that** I can track platform effectiveness over time and justify continued investment.

**Acceptance Criteria:**
- Computes automation accuracy (% of automated actions that were correct)
- Calculates average resolution time across all incident types
- Produces an overall improvement score (0-100) combining accuracy, pattern reduction, and actionable recommendations
- LLM-powered synthesis generates a narrative summary with key takeaways
- Full audit trail of reasoning chain for every learning cycle

## Technical Design

### LangGraph Workflow

```
[gather_outcomes] → [analyze_patterns]
                         ↓
              ┌──────────┼──────────┐
              ↓          ↓          ↓
    [pattern_only]  [recommend_playbooks]  [threshold_only]
                         ↓
                  [recommend_thresholds]
                         ↓
              [synthesize_improvements] → END
```

Conditional routing allows targeted learning cycles: `pattern_only`, `playbook_only`, `threshold_only`, or `full` (default).

### State Schema

```python
class LearningState(BaseModel):
    learning_id: str
    learning_type: str  # full, pattern_only, playbook_only, threshold_only
    target_period: str  # 7d, 30d, 90d

    # Input
    incident_outcomes: list[IncidentOutcome]
    total_incidents_analyzed: int

    # Pattern analysis
    pattern_insights: list[PatternInsight]
    recurring_pattern_count: int

    # Playbook updates
    playbook_updates: list[PlaybookUpdate]

    # Threshold adjustments
    threshold_adjustments: list[ThresholdAdjustment]
    estimated_false_positive_reduction: float

    # Effectiveness metrics
    automation_accuracy: float
    avg_resolution_time_ms: int
    improvement_score: float  # 0-100

    # Workflow tracking
    learning_start: datetime | None
    learning_duration_ms: int
    reasoning_chain: list[LearningStep]
    current_step: str
    error: str | None
```

### Component Inventory

| Component | File | Purpose |
|-----------|------|---------|
| `LearningState` | `agents/learning/models.py` | Pydantic state model for the workflow |
| `IncidentOutcome` | `agents/learning/models.py` | Record of a resolved incident |
| `PatternInsight` | `agents/learning/models.py` | Detected pattern from analysis |
| `PlaybookUpdate` | `agents/learning/models.py` | Recommended playbook change |
| `ThresholdAdjustment` | `agents/learning/models.py` | Recommended threshold change |
| `LearningToolkit` | `agents/learning/tools.py` | Pluggable data access layer |
| `gather_outcomes` | `agents/learning/nodes.py` | Fetches incident data + computes metrics |
| `analyze_patterns` | `agents/learning/nodes.py` | Groups incidents, detects patterns, LLM assessment |
| `recommend_playbooks` | `agents/learning/nodes.py` | Generates playbook updates from patterns |
| `recommend_thresholds` | `agents/learning/nodes.py` | Proposes threshold adjustments |
| `synthesize_improvements` | `agents/learning/nodes.py` | Combines findings into improvement score |
| `create_learning_graph` | `agents/learning/graph.py` | Builds the LangGraph workflow with conditional edges |
| `LearningRunner` | `agents/learning/runner.py` | Entry point: constructs graph, runs cycle, stores results |
| LLM Prompts | `agents/learning/prompts.py` | Structured output schemas for each LLM call |
| API Routes | `api/routes/learning.py` | REST endpoints for triggering and querying cycles |

### Data Flow

1. **gather_outcomes** — Queries `incident_store` for resolved incidents within the target period. Computes automation rate and accuracy. Falls back to stub data when no store is configured.

2. **analyze_patterns** — Groups incidents by alert type. Builds `PatternInsight` entries for recurring types (2+ incidents). Calls LLM with `PatternAnalysisResult` schema for deeper assessment.

3. **recommend_playbooks** — Compares detected patterns against existing playbooks. Proposes new playbooks for uncovered alert types, improvements for insufficient ones, and fixes for incorrect automations. LLM refines recommendations.

4. **recommend_thresholds** — Maps alert types to metrics via `alert_metric_map`. When false positive rate exceeds 10% for a metric, recommends threshold increase. LLM validates adjustments.

5. **synthesize_improvements** — Aggregates all findings. Computes improvement score (base 50, +20 for >90% accuracy, +15 for zero recurring patterns, +10 for actionable recommendations). LLM generates narrative summary.

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Pattern Detection Rate | > 80% of recurring incidents identified | Patterns found / actual recurring incidents |
| False Positive Reduction | > 15% per quarter | FP count before vs. after threshold adjustments |
| Automation Accuracy Trend | Increasing quarter-over-quarter | Correct automated actions / total automated |
| Playbook Coverage | > 90% of alert types have playbooks | Alert types with playbooks / total alert types |
| Learning Cycle Latency | < 60 seconds | End-to-end learning cycle duration |
| Improvement Score Trend | Increasing over time | Composite score from synthesis node |

## Dependencies

- Investigation Agent (provides incident context)
- Remediation Agent (provides resolution outcomes and accuracy data)
- Incident store (PostgreSQL — incident outcomes with feedback)
- Playbook store (YAML playbooks in `playbooks/` directory)
- Alert configuration store (threshold definitions)
- LLM provider (Claude for structured analysis)

## Timeline

### Completed (Weeks 1-8)
- **Week 1-2:** Core state models + LangGraph workflow definition
- **Week 3-4:** Node implementations (gather, analyze, recommend, synthesize)
- **Week 5-6:** LearningToolkit with pluggable stores + stub data
- **Week 7-8:** LearningRunner, API routes, LLM-powered assessments

### Planned (Weeks 9-12)
- **Week 9-10:** Production store integration (PostgreSQL incident store, YAML playbook loader)
- **Week 11-12:** Scheduled learning triggers (daily pattern analysis, weekly full cycles), dashboard integration with trend charts
