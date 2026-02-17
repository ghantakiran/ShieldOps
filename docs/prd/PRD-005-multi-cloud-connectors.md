# PRD-005: Multi-Cloud Connector Layer

**Status:** Draft
**Author:** ShieldOps Team
**Date:** 2026-02-17
**Priority:** P0 (MVP: AWS+K8s+Linux) / P1 (GCP, Azure)

## Problem Statement
84% of enterprises operate multi-cloud environments, yet most AI SRE tools are single-cloud or cloud-only. Agents need a unified interface to manage infrastructure across AWS, GCP, Azure, Kubernetes, and bare-metal Linux without cloud-specific agent implementations.

## Objective
Build an abstraction layer that provides agents with a unified interface to read telemetry, execute operations, and manage infrastructure across all supported environments — write agent logic once, deploy anywhere.

## Architecture

### Connector Interface
```python
class InfraConnector(Protocol):
    async def get_health(self, resource_id: str) -> HealthStatus: ...
    async def list_resources(self, resource_type: str, filters: dict) -> list[Resource]: ...
    async def execute_action(self, action: Action) -> ActionResult: ...
    async def get_events(self, resource_id: str, time_range: TimeRange) -> list[Event]: ...
    async def create_snapshot(self, resource_id: str) -> Snapshot: ...
    async def rollback(self, snapshot_id: str) -> RollbackResult: ...
```

### Supported Environments
| Environment | Phase | Read | Write | Snapshot |
|------------|-------|------|-------|----------|
| AWS (EC2, ECS, Lambda) | MVP | Yes | Yes | Yes |
| Kubernetes (all clouds) | MVP | Yes | Yes | Yes |
| Linux (SSH/Ansible) | MVP | Yes | Yes | Yes |
| GCP (GCE, GKE, Cloud Run) | Phase 2 | Yes | Yes | Yes |
| Azure (VMs, AKS, Functions) | Phase 2 | Yes | Yes | Yes |

### Authentication
- AWS: IAM roles (STS AssumeRole) — no long-lived credentials
- Kubernetes: ServiceAccount tokens with RBAC
- Linux: SSH key-based auth via SSH agent forwarding
- GCP: Workload Identity Federation
- Azure: Managed Identity

## Success Metrics
| Metric | Target |
|--------|--------|
| Connector Latency | < 500ms per operation (P95) |
| Environment Coverage | 3 environments MVP, 5 by Phase 2 |
| Agent Code Reuse | 100% — same agent logic across all environments |

## Timeline
- **Week 1-3:** Connector interface + AWS implementation
- **Week 4-5:** Kubernetes connector
- **Week 6-7:** Linux (SSH/Ansible) connector
- **Phase 2:** GCP + Azure connectors
