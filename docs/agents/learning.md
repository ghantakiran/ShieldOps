# Learning Agent

The Learning Agent analyzes historical investigation and remediation outcomes to
continuously improve playbooks, refine alert thresholds, and identify recurring
incident patterns.

---

## Purpose

- Gather investigation and remediation outcomes from the database
- Analyze patterns across incidents (recurring root causes, common failures)
- Recommend playbook updates based on what worked and what didn't
- Recommend threshold adjustments to reduce false positives/negatives
- Synthesize a prioritized list of improvements

---

## Graph Workflow

```
gather_outcomes
      |
      v
analyze_patterns
      |
      +-- [pattern_only] --> synthesize_improvements --> END
      |
      +-- [threshold_only] --> recommend_thresholds --> synthesize_improvements --> END
      |
      +-- [full] --> recommend_playbooks
                          |
                          +-- [playbook_only] --> synthesize_improvements --> END
                          |
                          +-- [full] --> recommend_thresholds --> synthesize_improvements --> END
```

### Nodes

| Node | Description |
|------|-------------|
| `gather_outcomes` | Query the database for completed investigations and remediations |
| `analyze_patterns` | Use LLM to identify recurring patterns and correlations |
| `recommend_playbooks` | Generate playbook additions/modifications based on patterns |
| `recommend_thresholds` | Suggest alert threshold changes to improve signal quality |
| `synthesize_improvements` | Prioritize and format all recommendations |

### Learning Types

| Type | Description |
|------|-------------|
| `full` | All analysis: patterns + playbooks + thresholds (default) |
| `pattern_only` | Only analyze incident patterns |
| `playbook_only` | Only generate playbook recommendations |
| `threshold_only` | Only suggest threshold adjustments |

---

## State Model

```python
class LearningState(BaseModel):
    learning_type: str           # full, pattern_only, playbook_only, threshold_only
    outcomes: list[dict]         # Historical investigation/remediation data
    patterns: list[dict]         # Identified recurring patterns
    playbook_recommendations: list[dict]  # Suggested playbook changes
    threshold_recommendations: list[dict]  # Suggested threshold changes
    improvements: list[dict]     # Synthesized, prioritized improvements
    error: str | None
```

---

## Scheduled Execution

The learning agent runs automatically as a nightly job:

```python
scheduler.add_job(
    "nightly_learning",
    nightly_learning_cycle,
    interval_seconds=86400,  # 24 hours
    learning_runner=learn_runner,
)
```

This ensures playbooks and thresholds stay current without manual intervention.

---

## Example Improvements

The learning agent might produce recommendations such as:

- **Playbook update:** "Add OOMKilled check before restart in pod-crash-loop playbook.
  18/25 recent pod restarts were caused by memory pressure."
- **Threshold adjustment:** "Reduce CPU alert threshold from 95% to 85% for the
  `api-gateway` service. 12 investigations triggered at 95% found issues that started
  at 80%."
- **New playbook:** "Create a playbook for `CertificateExpiringSoon` alerts. 8 similar
  incidents in the last 30 days all required the same `trigger_renewal` action."

---

## Integration

The learning agent reads from the same PostgreSQL database that the investigation
and remediation agents write to. It accesses the playbook store via the
`PlaybookLoader` to understand existing playbooks and suggest modifications.
