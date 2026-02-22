# ADR-002: Unified Multi-Cloud Abstraction Layer

**Status:** Accepted
**Date:** 2026-02-17

## Context
ShieldOps agents must operate across AWS, GCP, Azure, Kubernetes, and bare-metal Linux. We need an architecture that lets us write agent logic once and deploy across any environment.

## Decision
Build a **Protocol-based connector abstraction** where each cloud/environment implements a standard `InfraConnector` interface.

### Architecture
```
Agent Logic (LangGraph)
        │
        ▼
┌─────────────────────┐
│  ConnectorRouter     │ ← Routes to correct connector based on resource type
├─────────────────────┤
│ AWSConnector        │ ← boto3 + STS AssumeRole
│ GCPConnector        │ ← google-cloud-* + Workload Identity
│ AzureConnector      │ ← azure-mgmt-* + Managed Identity
│ KubernetesConnector │ ← kubernetes-client + ServiceAccount
│ LinuxConnector      │ ← asyncssh + Ansible
│ WindowsConnector    │ ← WinRM + PowerShell
└─────────────────────┘
```

### Key Principles
1. **Agents never call cloud APIs directly** — always through connector interface
2. **One connector per environment type** — not per service
3. **Authentication abstracted** — agents don't know about IAM roles vs. SSH keys
4. **All operations return standard models** — `Resource`, `HealthStatus`, `ActionResult`

## Alternatives Rejected
- **Terraform-only abstraction:** Too slow for real-time operations (plan+apply cycle)
- **Per-cloud agent implementations:** Doesn't scale, duplicates logic
- **Pulumi SDK:** Good but adds unnecessary JavaScript/TypeScript dependency

## Consequences
- Each new cloud requires only a connector implementation (not agent changes)
- Testing uses mock connectors (no cloud resources needed for unit tests)
- Connector latency budgets: read < 200ms, write < 2s, snapshot < 10s
