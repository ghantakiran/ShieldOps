# Helm Chart

ShieldOps provides a Helm chart for deploying to Kubernetes with all dependencies
managed as subcharts.

---

## Chart Overview

| Field | Value |
|-------|-------|
| Chart name | `shieldops` |
| Chart version | `0.1.0` |
| App version | `0.1.0` |
| Location | `infrastructure/helm/shieldops/` |

### Dependencies (Bitnami subcharts)

| Dependency | Version | Condition |
|------------|---------|-----------|
| PostgreSQL | ~15.0 | `postgresql.enabled` |
| Redis | ~18.0 | `redis.enabled` |
| Kafka | ~26.0 | `kafka.enabled` (disabled by default) |

---

## Quick Install

```bash
cd infrastructure/helm

# Install with default values
helm install shieldops ./shieldops --namespace shieldops --create-namespace

# Install with custom values
helm install shieldops ./shieldops \
  --namespace shieldops \
  --create-namespace \
  --set secrets.anthropicApiKey="sk-ant-..." \
  --set secrets.jwtSecretKey="your-production-secret" \
  --set ingress.hosts[0].host="shieldops.example.com"
```

!!! warning
    Never pass secret values via `--set` in CI/CD pipelines. Use a separate encrypted
    values file or reference an existing Kubernetes Secret via `existingSecret`.

---

## Key Values

### Image

```yaml
image:
  repository: ghcr.io/shieldops/api
  tag: "latest"
  pullPolicy: IfNotPresent

replicaCount: 2
```

### Frontend

```yaml
frontend:
  enabled: true
  image:
    repository: ghcr.io/shieldops/dashboard
    tag: "latest"
  replicaCount: 2
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
```

### Resources

```yaml
resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    cpu: "1"
    memory: 1Gi
```

### Secrets

```yaml
secrets:
  databaseUrl: ""
  redisUrl: ""
  jwtSecretKey: ""
  anthropicApiKey: ""
  openaiApiKey: ""
  langsmithApiKey: ""
  slackBotToken: ""

# Or use an existing Kubernetes Secret:
existingSecret: "my-shieldops-secrets"
```

### Ingress

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: shieldops.example.com
      paths:
        - path: /api
          pathType: Prefix
          service: api
        - path: /
          pathType: Prefix
          service: frontend
  tls:
    - secretName: shieldops-tls
      hosts:
        - shieldops.example.com
```

### Autoscaling

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUPercent: 70
  targetMemoryPercent: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
```

### OPA

```yaml
opa:
  enabled: true
  image:
    repository: openpolicyagent/opa
    tag: "latest-static"
  replicaCount: 2
  policies: {}  # Populated by CI from playbooks/policies/*.rego
```

### Database Migration

```yaml
migration:
  enabled: true
  activeDeadlineSeconds: 300
  backoffLimit: 3
```

### Monitoring

```yaml
monitoring:
  serviceMonitor:
    enabled: false    # Set to true if Prometheus Operator is installed
    interval: 30s
    path: /metrics
```

---

## Security Context

The chart enforces security best practices by default:

```yaml
securityContext:
  runAsNonRoot: true
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
```

---

## Network Policies

When `networkPolicy.enabled: true`, the chart creates network policies that restrict
pod-to-pod communication to only the required paths (API to DB, API to Redis, etc.).

---

## Upgrading

```bash
helm upgrade shieldops ./shieldops \
  --namespace shieldops \
  --set image.tag="sha-abc1234"
```

The migration job runs automatically as a pre-upgrade hook.

---

## Uninstalling

```bash
helm uninstall shieldops --namespace shieldops
```

!!! warning
    This does not delete PersistentVolumeClaims created by subcharts. Delete them
    manually if you want to remove all data.
