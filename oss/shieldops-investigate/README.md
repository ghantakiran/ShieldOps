# ShieldOps Investigate

### Open Source K8s Investigation Toolkit

> **AI-powered root cause analysis for Kubernetes incidents. From alert to diagnosis in under 60 seconds.**

---

ShieldOps Investigate is a lightweight, async Python toolkit that automatically correlates Prometheus metrics, Kubernetes events, and deployment history to identify the root cause of incidents. Optionally, plug in an Anthropic API key for Claude-powered root cause summaries.

**This is the open-source core of the [ShieldOps](https://shieldops.dev) autonomous SRE platform.**

## Features

- **Automated signal collection** -- queries Prometheus for CPU, memory, error rate, latency, and restart metrics
- **Kubernetes-native** -- inspects pod status, events, deployments, and node conditions via the K8s API
- **Rule-based correlation** -- 7 built-in detection rules covering the most common K8s failure patterns
- **Anomaly detection** -- compares current metrics against a 7-day baseline using statistical analysis
- **AI-powered summaries** -- optional Claude integration for human-quality root cause narratives
- **CLI and library** -- use from the command line or import directly into your Python code
- **Async-first** -- built on `httpx` and `kubernetes-asyncio` for non-blocking I/O
- **Minimal dependencies** -- no heavyweight ML frameworks required

## Built-in Detection Rules

| Pattern                  | Confidence | Signals Used                                      |
|--------------------------|------------|---------------------------------------------------|
| Deployment Regression    | High       | Recent rollout + error rate / latency spike        |
| Memory Leak / OOM        | High       | OOMKilled events + rising memory trend             |
| Image Pull Failure       | High       | ErrImagePull / ImagePullBackOff events             |
| CrashLoopBackOff         | High       | Pod restart count + BackOff events                 |
| Node Issue               | Medium     | Node NotReady + scheduling failures                |
| CPU Resource Exhaustion  | Medium     | CPU usage > 90% across pods                        |
| DNS Resolution Issue     | Medium     | DNS-related events + CoreDNS restarts              |

## Quick Start

### Install

```bash
pip install shieldops-investigate
```

For AI-powered summaries (optional):

```bash
pip install "shieldops-investigate[ai]"
```

### CLI Usage

```bash
# Basic investigation
shieldops-investigate --alert HighErrorRate --namespace production --service payment-service

# With a specific Prometheus URL
shieldops-investigate \
  --alert PodCrashLooping \
  --namespace staging \
  --prometheus-url http://prometheus.monitoring:9090

# JSON output (for piping to other tools)
shieldops-investigate --alert HighLatency --namespace production --json

# With AI-powered root cause summary
export ANTHROPIC_API_KEY=sk-ant-...
shieldops-investigate --alert HighErrorRate --namespace production --service api-gateway
```

### Python API

```python
import asyncio
from shieldops_investigate import Investigator

async def main():
    investigator = Investigator(
        prometheus_url="http://prometheus:9090",
        anthropic_api_key="sk-ant-...",  # optional
    )

    result = await investigator.investigate(
        alert_name="HighErrorRate",
        namespace="production",
        service="payment-service",
    )

    print(f"Top hypothesis: {result.top_hypothesis.title}")
    print(f"Confidence: {result.top_hypothesis.confidence:.0%}")
    print(f"Action: {result.top_hypothesis.suggested_action}")
    print(f"\nSummary: {result.summary}")

    await investigator.close()

asyncio.run(main())
```

## Architecture

```
                    +---------------------+
                    |    Alert Trigger     |
                    | (HighErrorRate, etc) |
                    +---------+-----------+
                              |
                              v
                    +---------------------+
                    |    Investigator      |
                    | (orchestrates flow)  |
                    +---------+-----------+
                              |
              +---------------+---------------+
              |                               |
              v                               v
    +-------------------+           +-------------------+
    | Prometheus Source  |           | Kubernetes Source  |
    | - CPU, memory     |           | - Pod status      |
    | - Error rate      |           | - Events          |
    | - Latency (p99)   |           | - Deployments     |
    | - Restarts        |           | - Node conditions |
    | - Anomaly detect  |           +-------------------+
    +-------------------+                     |
              |                               |
              +---------------+---------------+
                              |
                              v
                    +-------------------+
                    |    Correlator     |
                    | - 7 detection     |
                    |   rules           |
                    | - Ranked output   |
                    +---------+---------+
                              |
                    +---------+---------+
                    |  (Optional) Claude |
                    |  RCA Summary       |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | InvestigationResult|
                    | - Hypotheses      |
                    | - Evidence        |
                    | - Summary         |
                    +-------------------+
```

## Configuration

### Environment Variables

| Variable           | Default                  | Description                              |
|--------------------|--------------------------|------------------------------------------|
| `PROMETHEUS_URL`   | `http://localhost:9090`   | Prometheus server URL                    |
| `KUBECONFIG`       | `~/.kube/config`          | Path to kubeconfig file                  |
| `ANTHROPIC_API_KEY`| (none)                   | Anthropic API key for AI summaries       |
| `NO_COLOR`         | (none)                   | Disable colored CLI output when set      |

### Investigator Parameters

| Parameter          | Type            | Required | Description                          |
|--------------------|-----------------|----------|--------------------------------------|
| `prometheus_url`   | `str`           | Yes      | Prometheus base URL                  |
| `kubeconfig_path`  | `str \| None`   | No       | Path to kubeconfig                   |
| `anthropic_api_key`| `str \| None`   | No       | Enables AI-powered summaries         |

## Examples

See the [`examples/`](examples/) directory:

- **[`basic_investigation.py`](examples/basic_investigation.py)** -- Simple investigation using rule-based correlation
- **[`with_claude.py`](examples/with_claude.py)** -- Investigation with Claude-powered root cause analysis

## Data Model

### `InvestigationResult`

The top-level result object containing:

- `alert_name` -- the alert that triggered the investigation
- `namespace` -- Kubernetes namespace investigated
- `hypotheses` -- list of `Hypothesis` objects, ranked by confidence
- `evidence` -- all collected evidence from Prometheus and Kubernetes
- `summary` -- plain-language summary (AI-generated or rule-based)
- `duration_seconds` -- wall-clock time of the investigation
- `top_hypothesis` -- convenience property for the highest-confidence hypothesis

### `Hypothesis`

A ranked root cause hypothesis:

- `title` -- short name (e.g., "Deployment Regression")
- `description` -- detailed explanation
- `confidence` -- float from 0.0 to 1.0
- `evidence` -- supporting evidence list
- `suggested_action` -- recommended remediation step

### `Evidence`

A single observable signal:

- `source` -- `prometheus`, `kubernetes`, `claude`, or `correlator`
- `query` -- the query or API call that produced the evidence
- `value` -- human-readable value
- `anomaly_score` -- 0.0 (normal) to 1.0 (extreme outlier)

## Development

```bash
# Clone the repo
git clone https://github.com/shieldops/shieldops-investigate.git
cd shieldops-investigate

# Install in development mode
pip install -e ".[dev]"

# Run linter
ruff check src/

# Run type checker
mypy src/

# Run tests
pytest
```

## Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-detection-rule`)
3. Commit your changes (`git commit -m 'feat: add amazing detection rule'`)
4. Push to the branch (`git push origin feat/amazing-detection-rule`)
5. Open a Pull Request

## License

MIT License. See [LICENSE](LICENSE) for details.

---

### Powered by [ShieldOps](https://shieldops.dev)

ShieldOps Investigate is the open-source core of **ShieldOps** -- the autonomous SRE platform that doesn't just analyze, it acts. The full platform adds:

- **Automated remediation** with policy gates and rollback safety
- **Security enforcement** -- CVE patching, credential rotation, compliance
- **Learning agents** that improve playbooks from historical outcomes
- **Multi-cloud support** -- AWS, GCP, Azure, Kubernetes, bare-metal Linux
- **Enterprise features** -- SSO, audit trails, approval workflows, RBAC

[Learn more at shieldops.dev](https://shieldops.dev)
