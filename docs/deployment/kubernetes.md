# Kubernetes Deployment

Deploy ShieldOps on a self-managed or on-premise Kubernetes cluster using raw manifests.
For Helm-based deployment, see the [Helm Chart](helm.md) page.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| kubectl | 1.28+ | Cluster management |
| Helm | 3.x | Optional, for subchart dependencies |

---

## Manifests

All Kubernetes manifests are in `infrastructure/kubernetes/`:

| File | Description |
|------|-------------|
| `namespace.yaml` | `shieldops` namespace |
| `secret.yaml` | Application secrets template |
| `configmap.yaml` | Non-secret configuration |
| `deployment.yaml` | API server deployment + service + RBAC |
| `dashboard-deployment.yaml` | Frontend deployment |
| `hpa.yaml` | Horizontal Pod Autoscaler |
| `pdb.yaml` | Pod Disruption Budget |
| `ingress.yaml` | Ingress resource |
| `networkpolicy.yaml` | Zero-trust network policies |
| `opa-deployment.yaml` | OPA sidecar deployment |
| `opa-policies-configmap.yaml` | Rego policies as ConfigMap |
| `migration-job.yaml` | Alembic migration pre-deploy job |
| `redis.yaml` | Redis deployment (or use managed) |
| `kafka.yaml` | Kafka deployment (or use managed) |
| `external-secrets.yaml` | ExternalSecrets operator integration |

---

## Step-by-Step Deployment

### 1. Create namespace

```bash
kubectl apply -f infrastructure/kubernetes/namespace.yaml
```

### 2. Create secrets

```bash
kubectl create secret generic shieldops-secrets \
  --namespace shieldops \
  --from-literal=SHIELDOPS_DATABASE_URL='postgresql+asyncpg://shieldops:password@postgres:5432/shieldops' \
  --from-literal=SHIELDOPS_REDIS_URL='redis://redis:6379/0' \
  --from-literal=SHIELDOPS_KAFKA_BROKERS='kafka:9092' \
  --from-literal=SHIELDOPS_OPA_ENDPOINT='http://opa:8181' \
  --from-literal=SHIELDOPS_ANTHROPIC_API_KEY='sk-ant-...' \
  --from-literal=SHIELDOPS_JWT_SECRET_KEY='your-production-secret'
```

!!! tip
    For production, use the ExternalSecrets operator (`external-secrets.yaml`) to sync
    secrets from AWS Secrets Manager, GCP Secret Manager, or Azure Key Vault.

### 3. Create ConfigMap

```bash
kubectl create configmap shieldops-config \
  --namespace shieldops \
  --from-literal=SHIELDOPS_ENVIRONMENT='production' \
  --from-literal=SHIELDOPS_API_HOST='0.0.0.0' \
  --from-literal=SHIELDOPS_API_PORT='8000'
```

### 4. Deploy the application

```bash
kubectl apply -f infrastructure/kubernetes/deployment.yaml
```

This creates:

- **Deployment** (`shieldops-api`): 2 replicas with liveness/readiness probes, resource
  limits, and a non-root security context
- **Service** (`shieldops-api`): ClusterIP service routing port 80 to container port 8000
- **ServiceAccount** (`shieldops-agent`): For RBAC-controlled Kubernetes API access
- **ClusterRole/ClusterRoleBinding** (`shieldops-agent`): Read access to pods, services,
  deployments, events; write access for pod deletion (restarts) and deployment scaling

### 5. Verify deployment

```bash
kubectl get pods -n shieldops
kubectl logs -n shieldops -l app=shieldops,component=api --tail=50
kubectl port-forward -n shieldops svc/shieldops-api 8000:80
```

### 6. Expose externally (optional)

Apply the ingress manifest or use a LoadBalancer:

```bash
kubectl apply -f infrastructure/kubernetes/ingress.yaml

# Or expose via LoadBalancer
kubectl patch svc shieldops-api -n shieldops -p '{"spec": {"type": "LoadBalancer"}}'
```

---

## Service Dependency Order

Deploy infrastructure services before the ShieldOps application:

1. PostgreSQL (or managed database)
2. Redis
3. Kafka
4. OPA (with policies mounted)
5. ShieldOps API (runs `alembic upgrade head` on startup, then starts uvicorn)

---

## RBAC Configuration

The agent ServiceAccount needs cluster-level access to manage Kubernetes resources.
The default RBAC grants:

**Read access:**

- Pods, services, deployments, replicasets
- Events, configmaps, namespaces

**Write access:**

- Pod deletion (for restarts)
- Deployment scale and rollback

!!! warning
    Review the ClusterRole permissions before applying to production clusters.
    Follow the principle of least privilege.
