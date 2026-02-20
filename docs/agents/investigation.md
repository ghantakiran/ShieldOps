# Investigation Agent

The Investigation Agent performs autonomous root cause analysis when alerts fire.
It gathers context from logs, metrics, and traces, correlates findings, and generates
ranked hypotheses with confidence scores.

---

## Purpose

- Parse incoming alerts and extract structured context
- Query observability sources (Prometheus, Splunk, Datadog) for relevant signals
- Check historical patterns for similar incidents
- Correlate multi-signal findings using LLM reasoning
- Generate ranked root cause hypotheses with evidence
- Recommend remediation actions when confidence is high (> 0.85)

---

## Graph Workflow

```
gather_context
      |
      v
check_historical_patterns
      |
      v
analyze_logs
      |
      v
analyze_metrics
      |
      +-- [distributed errors?] --> analyze_traces --> correlate_findings
      |
      +-- [no trace needed] --> correlate_findings
                                       |
                                       v
                              generate_hypotheses
                                       |
                                       +-- [confidence >= 0.85] --> recommend_action --> END
                                       |
                                       +-- [confidence < 0.85] --> END
```

### Nodes

| Node | Description |
|------|-------------|
| `gather_context` | Extract structured data from the alert, identify target resources |
| `check_historical_patterns` | Query DB for similar past incidents and their resolutions |
| `analyze_logs` | Query log sources for error patterns, exceptions, and anomalies |
| `analyze_metrics` | Query metric sources for resource usage spikes, latency changes |
| `analyze_traces` | (Conditional) Follow distributed request paths for timeout/error propagation |
| `correlate_findings` | Cross-reference log, metric, and trace findings |
| `generate_hypotheses` | Use LLM to produce ranked root cause hypotheses from evidence |
| `recommend_action` | Generate a remediation action recommendation with risk assessment |

### Conditional Edges

- **After `analyze_metrics`:** If distributed errors (e.g., timeout patterns) are found
  in logs, route to `analyze_traces`. Otherwise, skip directly to `correlate_findings`.
- **After `generate_hypotheses`:** If confidence >= 0.85, route to `recommend_action`.
  Otherwise, end with the hypotheses for human review.

---

## State Model

```python
class InvestigationState(BaseModel):
    alert_context: AlertContext       # Parsed alert data
    log_findings: list[LogFinding]    # Findings from log analysis
    metric_findings: list[MetricFinding]  # Findings from metric analysis
    trace_findings: list[TraceFinding]    # Findings from trace analysis
    historical_matches: list[dict]    # Similar past incidents
    hypotheses: list[Hypothesis]      # Ranked root cause hypotheses
    confidence_score: float           # Overall confidence (0.0 - 1.0)
    reasoning_chain: list[ReasoningStep]  # Full reasoning trace
    recommended_action: RemediationAction | None  # Suggested remediation
    error: str | None                 # Error message if workflow failed
```

---

## Tools Available

The investigation agent uses these tools via the connector layer:

- **Log queries:** Splunk, CloudWatch, Loki (via observability sources)
- **Metric queries:** Prometheus, Datadog, CloudWatch Metrics
- **Trace queries:** Jaeger, Datadog APM
- **Resource health:** Kubernetes pod status, AWS instance state
- **Event history:** Kubernetes events, CloudTrail events

---

## Example Usage

### Via API

```bash
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "prom-001",
    "alert_name": "HighCPU",
    "severity": "critical",
    "source": "prometheus",
    "resource_id": "pod/web-server-01",
    "labels": {"namespace": "production", "team": "platform"},
    "description": "CPU usage at 97% for 15 minutes"
  }'
```

Response (202 Accepted):

```json
{
  "status": "accepted",
  "alert_id": "prom-001",
  "message": "Investigation started. Use GET /investigations to track progress."
}
```

### Synchronous mode (for testing)

```bash
curl -X POST http://localhost:8000/api/v1/investigations/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ ... same body ... }'
```

This waits for the investigation to complete and returns the full result.

---

## Integration with Other Agents

When the investigation produces a high-confidence hypothesis with a recommended action,
the [Supervisor Agent](supervisor.md) can automatically chain it to the
[Remediation Agent](remediation.md) for execution.

The confidence threshold is configurable via
`SHIELDOPS_AGENT_CONFIDENCE_THRESHOLD_AUTO` (default: 0.85).
