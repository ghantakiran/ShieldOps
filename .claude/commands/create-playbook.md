# Create Playbook Skill

Create a new remediation playbook for ShieldOps agents.

## Usage
`/create-playbook <name> [--trigger <alert-type>] [--risk-level <level>]`

## Process

1. **Identify the incident type**: What alert/condition triggers this playbook?
2. **Define investigation steps**: What data should the agent gather?
3. **Design decision tree**: What conditions map to which remediation actions?
4. **Specify remediation actions**: What does the agent do for each condition?
5. **Define validation checks**: How do we confirm the fix worked?
6. **Set failure handling**: What happens if remediation fails?

## Playbook YAML Structure
```yaml
name: playbook-name
version: "1.0"
description: "What this playbook handles"
trigger:
  alert_type: "AlertName"
  severity: ["critical", "warning"]

investigation:
  steps:
    - name: step_name
      action: query_type  # query_logs, query_metrics, query_k8s, query_health
      query: "query string"
      extract: [fields]

remediation:
  decision_tree:
    - condition: "condition expression"
      action: action_name
      risk_level: low|medium|high|critical
      params: {}

validation:
  checks:
    - name: check_name
      query: "validation query"
      expected: "expected result"
      timeout_seconds: 300

  on_failure:
    action: rollback_and_escalate
    escalation_channel: "#sre-oncall"
```

## Runbook Recommendation
After creating a playbook, register it with the Runbook Recommender (`src/shieldops/playbooks/runbook_recommender.py`) so it can be auto-suggested for matching incident symptoms via `RunbookRecommender.register_runbook()`.

## Save playbook to `playbooks/{name}.yaml`
