# Connector Layer

The connector layer provides a unified interface for infrastructure operations across
all supported cloud providers and on-premise environments. Agents interact exclusively
through this abstraction -- they never call cloud APIs directly.

---

## Architecture

```
Agent Logic (LangGraph)
        |
        v
+---------------------+
|  ConnectorRouter     | <-- Routes to correct connector based on provider
+---------------------+
| AWSConnector        | <-- boto3 + STS AssumeRole
| GCPConnector        | <-- google-cloud-* + Workload Identity
| AzureConnector      | <-- azure-mgmt-* + Managed Identity
| KubernetesConnector | <-- kubernetes-client + ServiceAccount
| LinuxConnector      | <-- asyncssh + Ansible
| WindowsConnector    | <-- WinRM + PowerShell
+---------------------+
```

---

## InfraConnector Interface

All connectors implement the `InfraConnector` abstract base class defined in
`src/shieldops/connectors/base.py`:

```python
class InfraConnector(ABC):
    provider: str  # aws, gcp, azure, kubernetes, linux

    async def get_health(self, resource_id: str) -> HealthStatus: ...
    async def list_resources(self, resource_type: str, environment: Environment, filters: dict | None = None) -> list[Resource]: ...
    async def get_events(self, resource_id: str, time_range: TimeRange) -> list[dict]: ...
    async def execute_action(self, action: RemediationAction) -> ActionResult: ...
    async def create_snapshot(self, resource_id: str) -> Snapshot: ...
    async def rollback(self, snapshot_id: str) -> ActionResult: ...
    async def validate_health(self, resource_id: str, timeout_seconds: int = 300) -> bool: ...
```

### Key design principles

1. **Agents never call cloud APIs directly** -- always through the connector interface
2. **One connector per environment type** -- not per cloud service
3. **Authentication is abstracted** -- agents don't know about IAM roles vs. SSH keys
4. **All operations return standard models** -- `Resource`, `HealthStatus`, `ActionResult`

---

## ConnectorRouter

The `ConnectorRouter` dispatches operations to the correct connector based on the
`provider` string:

```python
router = ConnectorRouter()
router.register(KubernetesConnector())
router.register(AWSConnector(region="us-east-1"))

# In agent code:
connector = router.get("kubernetes")
health = await connector.get_health("pod/web-server-01")
```

---

## Supported Providers

### Kubernetes (always registered)

- **Module:** `src/shieldops/connectors/kubernetes/connector.py`
- **Auth:** ServiceAccount (in-cluster) or kubeconfig (local dev)
- **Capabilities:** Pod management, deployment scaling/rollback, resource listing, event querying

### AWS (registered when `SHIELDOPS_AWS_REGION` is set)

- **Module:** `src/shieldops/connectors/aws/connector.py`
- **Auth:** boto3 credential chain (env vars, IAM role, STS AssumeRole)
- **Capabilities:** EC2, ECS, Lambda resource management

### GCP (registered when `SHIELDOPS_GCP_PROJECT_ID` is set)

- **Module:** `src/shieldops/connectors/gcp/connector.py`
- **Auth:** Application Default Credentials / Workload Identity
- **Capabilities:** GCE, GKE, Cloud Run resource management

### Azure (registered when `SHIELDOPS_AZURE_SUBSCRIPTION_ID` is set)

- **Module:** `src/shieldops/connectors/azure/connector.py`
- **Auth:** Managed Identity / Service Principal
- **Capabilities:** VM, Container Apps, AKS resource management

### Linux SSH (registered when `SHIELDOPS_LINUX_HOST` is set)

- **Module:** `src/shieldops/connectors/linux/connector.py`
- **Auth:** SSH key-based authentication
- **Capabilities:** Remote command execution, file management, service control

### Windows WinRM (registered when `SHIELDOPS_WINDOWS_HOST` is set)

- **Module:** `src/shieldops/connectors/windows/connector.py`
- **Auth:** WinRM with NTLM/Kerberos authentication
- **Capabilities:** PowerShell command execution, Windows service management, IIS administration

---

## Connector Registration

Connectors are registered at startup by the factory in
`src/shieldops/connectors/factory.py`:

```python
def create_connector_router(settings: Settings) -> ConnectorRouter:
    router = ConnectorRouter()

    # Kubernetes is always available
    router.register(KubernetesConnector())

    # Cloud connectors registered based on configuration
    if settings.aws_region:
        router.register(AWSConnector(region=settings.aws_region))

    if settings.gcp_project_id:
        router.register(GCPConnector(
            project_id=settings.gcp_project_id,
            region=settings.gcp_region,
        ))

    if settings.azure_subscription_id:
        router.register(AzureConnector(
            subscription_id=settings.azure_subscription_id,
            resource_group=settings.azure_resource_group,
            location=settings.azure_location,
        ))

    if settings.linux_host:
        router.register(LinuxConnector(
            host=settings.linux_host,
            username=settings.linux_username,
            private_key_path=settings.linux_private_key_path,
        ))

    return router
```

---

## Adding a New Connector

To add support for a new infrastructure provider:

1. Create a new module at `src/shieldops/connectors/{provider}/connector.py`

2. Implement the `InfraConnector` interface:

    ```python
    from shieldops.connectors.base import InfraConnector

    class NewProviderConnector(InfraConnector):
        provider = "new_provider"

        async def get_health(self, resource_id: str) -> HealthStatus:
            # Implementation here
            ...
    ```

3. Register it in `src/shieldops/connectors/factory.py`:

    ```python
    if settings.new_provider_enabled:
        router.register(NewProviderConnector())
    ```

4. Add configuration variables to `src/shieldops/config/settings.py`

5. Write unit tests using mock connectors (no real cloud resources needed)

---

## Performance Budgets

| Operation | Target Latency |
|-----------|---------------|
| Read (get_health, list_resources, get_events) | < 200ms |
| Write (execute_action) | < 2s |
| Snapshot (create_snapshot) | < 10s |
| Validation (validate_health) | < 300s (configurable timeout) |
