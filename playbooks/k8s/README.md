# Kubernetes Remediation Playbooks

Production-ready playbooks for automated Kubernetes incident remediation. These playbooks are executed by the ShieldOps Remediation Agent when matching alerts are detected.

## Playbooks

| Playbook | Trigger | Severity | Auto-Approval |
|----------|---------|----------|---------------|
| [pod-crash-loop.yml](pod-crash-loop.yml) | Pod restart count > 5 in 10 min | Critical | Yes |
| [oom-kill.yml](oom-kill.yml) | Container terminated with OOMKilled reason | High | Yes |
| [deployment-failure.yml](deployment-failure.yml) | Deployment rollout stalled or failed | Critical | Yes |
| [high-latency.yml](high-latency.yml) | P99 latency exceeds SLO threshold for 5 min | High | Yes |
| [certificate-expiry.yml](certificate-expiry.yml) | TLS certificate expires within 7 days | High | Yes |
| [disk-pressure.yml](disk-pressure.yml) | Node reports DiskPressure condition | High | Yes |
| [connection-pool-exhaustion.yml](connection-pool-exhaustion.yml) | Database connection pool at 95%+ utilization | Critical | Yes |
| [dns-failure.yml](dns-failure.yml) | DNS lookup failures (SERVFAIL/NXDOMAIN spikes) | Critical | Yes |
| [rate-limiting.yml](rate-limiting.yml) | HTTP 429 responses exceed 5% of total traffic | High | Yes |
| [memory-leak.yml](memory-leak.yml) | Memory usage monotonically increasing over 1 hour | High | Yes |

## Playbook Structure

Each playbook follows a consistent structure:

- **detection** -- Signal definitions (metrics, logs, events) that trigger the playbook
- **investigation** -- Diagnostic steps to determine root cause
- **remediation** -- Actions to fix the issue, with blast radius limits
- **rollback** -- Steps to revert if remediation fails
- **escalation** -- Notification channels and timeout before auto-escalation

## Usage

Playbooks are automatically selected by the Remediation Agent based on alert type matching. They can also be triggered manually via the API:

```
POST /api/v1/remediations/execute
{
  "playbook": "k8s/pod-crash-loop",
  "parameters": {
    "namespace": "production",
    "pod_name": "api-server-7f8b9c6d4-x2k9p",
    "deployment_name": "api-server"
  }
}
```

All playbook executions are subject to OPA policy evaluation before any infrastructure changes are made.
