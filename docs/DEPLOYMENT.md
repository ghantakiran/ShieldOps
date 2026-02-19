# ShieldOps Deployment Guide

This guide covers deploying ShieldOps across all supported environments: local development,
AWS, GCP, Azure, and bare Kubernetes clusters.

---

## Table of Contents

- [Local Development](#local-development)
- [AWS Deployment](#aws-deployment)
- [GCP Deployment](#gcp-deployment)
- [Azure Deployment](#azure-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [CI/CD Pipeline](#cicd-pipeline)
- [Post-Deployment Verification](#post-deployment-verification)
- [Troubleshooting](#troubleshooting)

---

## Local Development

### Prerequisites

| Tool       | Version  | Purpose                        |
|------------|----------|--------------------------------|
| Docker     | 24+      | Infrastructure containers      |
| Python     | 3.12+    | Backend runtime                |
| Node.js    | 20+      | Frontend build tooling         |
| Git        | 2.40+    | Version control                |

### 1. Clone the repository

```bash
git clone https://github.com/ghantakiran/ShieldOps.git
cd ShieldOps
```

### 2. Start infrastructure services

The docker-compose file at `infrastructure/docker/docker-compose.yml` provisions PostgreSQL 16,
Redis 7, Kafka (KRaft mode), and OPA with the project's Rego policies pre-loaded.

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d postgres redis kafka opa
```

Wait for health checks to pass:

```bash
docker compose -f infrastructure/docker/docker-compose.yml ps
```

All four services should show `healthy` or `running` status. PostgreSQL and Redis expose health
checks; Kafka and OPA are considered ready once their containers start.

**Default ports:**

| Service    | Port  | Notes                                   |
|------------|-------|-----------------------------------------|
| PostgreSQL | 5432  | User: `shieldops` / Pass: `shieldops`   |
| Redis      | 6379  | No authentication                       |
| Kafka      | 9092  | KRaft mode (no ZooKeeper)               |
| OPA        | 8181  | Policies from `playbooks/policies/`     |

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
SHIELDOPS_ENVIRONMENT=development
SHIELDOPS_DATABASE_URL=postgresql+asyncpg://shieldops:shieldops@localhost:5432/shieldops
SHIELDOPS_REDIS_URL=redis://localhost:6379/0
SHIELDOPS_KAFKA_BROKERS=localhost:9092
SHIELDOPS_OPA_ENDPOINT=http://localhost:8181
SHIELDOPS_JWT_SECRET_KEY=local-dev-secret-key
```

For agent functionality, add your LLM provider keys:

```
SHIELDOPS_ANTHROPIC_API_KEY=sk-ant-...
SHIELDOPS_OPENAI_API_KEY=sk-...       # Optional fallback
```

See `.env.example` for the full list of supported variables. All variables use the
`SHIELDOPS_` prefix as defined in `src/shieldops/config/settings.py`.

### 4. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 5. Install frontend dependencies

```bash
cd dashboard-ui
npm install
cd ..
```

### 6. Run database migrations

```bash
alembic upgrade head
```

This runs all migrations from `alembic/versions/` against your local PostgreSQL instance.

### 7. Seed demo data (optional)

```bash
python -m shieldops.db.seed
```

This creates a default admin user (`admin@shieldops.dev` / `shieldops-admin`), sample agents,
and historical investigation data for the dashboard.

### 8. Start the application

**API server** (port 8000):

```bash
shieldops serve --reload
```

Or directly via uvicorn:

```bash
uvicorn shieldops.api.app:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend dev server** (port 3000):

```bash
cd dashboard-ui
npm run dev
```

### 9. Verify

- API docs: http://localhost:8000/api/v1/docs
- Health check: http://localhost:8000/health
- Readiness check: http://localhost:8000/ready
- Dashboard: http://localhost:3000

---

## AWS Deployment

ShieldOps deploys on AWS using ECS Fargate with RDS PostgreSQL, ElastiCache Redis, MSK (Kafka),
and an Application Load Balancer.

### Prerequisites

| Tool        | Version  | Purpose                         |
|-------------|----------|---------------------------------|
| AWS CLI     | 2.x      | AWS resource management         |
| Terraform   | >= 1.5   | Infrastructure provisioning     |
| Docker      | 24+      | Image building                  |

### Architecture

```
Internet --> ALB --> ECS Fargate (ShieldOps API)
                         |
              +----------+----------+
              |          |          |
          RDS (PG)  ElastiCache  MSK (Kafka)
                     (Redis)
```

### 1. Configure AWS credentials

```bash
aws configure
# Or use SSO:
aws sso login --profile shieldops
```

### 2. Create Secrets Manager secret

Store application secrets before Terraform runs. The `secrets_arn` variable points to this
secret.

```bash
aws secretsmanager create-secret \
  --name shieldops/production/app-secrets \
  --secret-string '{
    "ANTHROPIC_API_KEY": "sk-ant-...",
    "JWT_SECRET": "your-production-jwt-secret",
    "OPENAI_API_KEY": "sk-...",
    "LANGSMITH_API_KEY": "ls-..."
  }' \
  --region us-east-1
```

Note the ARN in the output -- you will need it for `terraform.tfvars`.

### 3. Configure Terraform state backend

Create the S3 bucket and DynamoDB table for state locking (one-time setup):

```bash
aws s3api create-bucket \
  --bucket shieldops-terraform-state \
  --region us-east-1

aws s3api put-bucket-versioning \
  --bucket shieldops-terraform-state \
  --versioning-configuration Status=Enabled

aws dynamodb create-table \
  --table-name shieldops-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 4. Configure Terraform variables

```bash
cd infrastructure/terraform/aws
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
aws_region   = "us-east-1"
environment  = "production"      # production | staging | development
project_name = "shieldops"

vpc_cidr          = "10.0.0.0/16"
app_cpu           = 512           # 0.5 vCPU
app_memory        = 1024          # 1 GB
app_desired_count = 2
container_image   = "<account-id>.dkr.ecr.us-east-1.amazonaws.com/shieldops-production:latest"

db_instance_class    = "db.t3.medium"
db_allocated_storage = 50

redis_node_type = "cache.t3.medium"

domain_name     = "api.shieldops.io"      # Optional
certificate_arn = "arn:aws:acm:..."       # Required if domain_name is set

secrets_arn = "arn:aws:secretsmanager:us-east-1:<account-id>:secret:shieldops/production/app-secrets-AbCdEf"

alarm_email = "sre-team@shieldops.io"     # Optional

autoscaling_min_capacity = 2
autoscaling_max_capacity = 10
```

### 5. Provision infrastructure

```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Key resources created:
- VPC with public/private subnets across 3 AZs
- ECS Fargate cluster and service
- ECR repository
- RDS PostgreSQL (private subnet, encrypted)
- ElastiCache Redis (private subnet)
- ALB with optional HTTPS
- CloudWatch alarms and log groups
- IAM roles and security groups
- Auto-scaling policies

### 6. Build and push Docker image

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build the image
docker build -t shieldops -f infrastructure/docker/Dockerfile .

# Tag and push
IMAGE_TAG="sha-$(git rev-parse --short HEAD)"
docker tag shieldops:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/shieldops-production:${IMAGE_TAG}
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/shieldops-production:${IMAGE_TAG}
```

### 7. Deploy the service

After pushing, update the ECS service to use the new image. The CD pipeline handles this
automatically (see [CI/CD Pipeline](#cicd-pipeline)), or manually:

```bash
aws ecs update-service \
  --cluster shieldops-production-cluster \
  --service shieldops-production-service \
  --force-new-deployment \
  --region us-east-1
```

### 8. DNS configuration

If using a custom domain, create a Route 53 alias record pointing to the ALB DNS name
output by Terraform:

```bash
terraform output alb_dns_name
```

---

## GCP Deployment

ShieldOps deploys on GCP using Cloud Run with Cloud SQL (PostgreSQL), Memorystore (Redis),
and a global HTTPS load balancer.

### Prerequisites

| Tool         | Version  | Purpose                            |
|--------------|----------|------------------------------------|
| gcloud CLI   | Latest   | GCP resource management            |
| Terraform    | >= 1.5   | Infrastructure provisioning        |
| Docker       | 24+      | Image building                     |

### 1. Authenticate and set project

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project <your-project-id>
```

### 2. Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  servicenetworking.googleapis.com
```

### 3. Store secrets in Secret Manager

```bash
echo -n "sk-ant-..." | gcloud secrets create anthropic-api-key --data-file=-
echo -n "your-jwt-secret" | gcloud secrets create jwt-secret --data-file=-
```

### 4. Configure Terraform variables

```bash
cd infrastructure/terraform/gcp
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
gcp_project  = "my-shieldops-project"
gcp_region   = "us-central1"
environment  = "production"
project_name = "shieldops"

app_cpu           = "1000m"
app_memory        = "1Gi"
app_min_instances = 2
app_max_instances = 10
container_image   = "us-central1-docker.pkg.dev/my-shieldops-project/shieldops-production/shieldops:latest"

db_tier      = "db-custom-2-7680"
db_disk_size = 50

redis_memory_size_gb = 1

domain_name = "api.shieldops.io"    # Optional
alarm_email = "sre@shieldops.io"    # Optional
```

### 5. Provision infrastructure

```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Key resources created:
- VPC with private services access
- Cloud Run service with VPC connector
- Artifact Registry repository
- Cloud SQL PostgreSQL (private IP, encrypted)
- Memorystore Redis
- Global HTTPS load balancer with managed SSL certificate
- Cloud Monitoring alert policies
- IAM service accounts with least-privilege

### 6. Build and push Docker image

```bash
# Configure Docker for Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build and push
IMAGE_TAG="sha-$(git rev-parse --short HEAD)"
docker build -t us-central1-docker.pkg.dev/my-shieldops-project/shieldops-production/shieldops:${IMAGE_TAG} \
  -f infrastructure/docker/Dockerfile .
docker push us-central1-docker.pkg.dev/my-shieldops-project/shieldops-production/shieldops:${IMAGE_TAG}
```

### 7. Deploy

```bash
gcloud run services update shieldops-api \
  --image us-central1-docker.pkg.dev/my-shieldops-project/shieldops-production/shieldops:${IMAGE_TAG} \
  --region us-central1
```

---

## Azure Deployment

ShieldOps deploys on Azure using Container Apps with Azure Database for PostgreSQL Flexible
Server, Azure Cache for Redis, and Azure Container Registry.

### Prerequisites

| Tool       | Version  | Purpose                       |
|------------|----------|-------------------------------|
| Azure CLI  | 2.x      | Azure resource management     |
| Terraform  | >= 1.5   | Infrastructure provisioning   |
| Docker     | 24+      | Image building                |

### 1. Authenticate

```bash
az login
az account set --subscription <subscription-id>
```

### 2. Store secrets in Key Vault

```bash
az keyvault secret set --vault-name shieldops-kv --name anthropic-api-key --value "sk-ant-..."
az keyvault secret set --vault-name shieldops-kv --name jwt-secret --value "your-jwt-secret"
```

### 3. Configure Terraform variables

```bash
cd infrastructure/terraform/azure
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
azure_location   = "eastus"
environment      = "production"
project_name     = "shieldops"

app_cpu          = 1.0
app_memory       = "2Gi"
app_min_replicas = 2
app_max_replicas = 10
container_image  = "shieldopsproductionacr.azurecr.io/shieldops:latest"

db_sku_name   = "GP_Standard_D2s_v3"
db_storage_mb = 51200

redis_sku_name = "Standard"
redis_capacity = 1

domain_name = "api.shieldops.io"    # Optional
alarm_email = "sre@shieldops.io"    # Optional
```

### 4. Provision infrastructure

```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Key resources created:
- Virtual Network with subnets
- Container Apps Environment and Container App
- Azure Container Registry
- PostgreSQL Flexible Server (VNet-integrated, encrypted)
- Azure Cache for Redis
- Key Vault for secrets
- Azure Monitor alert rules
- Managed identities with RBAC

### 5. Build and push Docker image

```bash
# Login to ACR
az acr login --name shieldopsproductionacr

# Build and push
IMAGE_TAG="sha-$(git rev-parse --short HEAD)"
docker build -t shieldopsproductionacr.azurecr.io/shieldops:${IMAGE_TAG} \
  -f infrastructure/docker/Dockerfile .
docker push shieldopsproductionacr.azurecr.io/shieldops:${IMAGE_TAG}
```

### 6. Deploy

```bash
az containerapp update \
  --name shieldops-api \
  --resource-group shieldops-production-rg \
  --image shieldopsproductionacr.azurecr.io/shieldops:${IMAGE_TAG}
```

---

## Kubernetes Deployment

For self-managed or on-premise Kubernetes clusters.

### Prerequisites

| Tool       | Version  | Purpose                       |
|------------|----------|-------------------------------|
| kubectl    | 1.28+    | Cluster management            |
| Helm       | 3.x      | Optional, for external charts |

### 1. Create the namespace

```bash
kubectl apply -f infrastructure/kubernetes/namespace.yaml
```

This creates the `shieldops` namespace with appropriate labels.

### 2. Create secrets

Create a Kubernetes secret with the required application configuration:

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
- **Deployment** (`shieldops-api`): 2 replicas with liveness/readiness probes, resource limits,
  and a non-root security context
- **Service** (`shieldops-api`): ClusterIP service routing port 80 to container port 8000
- **ServiceAccount** (`shieldops-agent`): For RBAC-controlled Kubernetes API access
- **ClusterRole/ClusterRoleBinding** (`shieldops-agent`): Read access to pods, services,
  deployments, events; write access for pod deletion (restarts) and deployment scaling/rollback

### 5. Verify deployment

```bash
kubectl get pods -n shieldops
kubectl logs -n shieldops -l app=shieldops,component=api --tail=50
kubectl port-forward -n shieldops svc/shieldops-api 8000:80
```

### 6. Expose externally (optional)

Use an Ingress controller or LoadBalancer service depending on your cluster:

```bash
# Example: expose via LoadBalancer
kubectl patch svc shieldops-api -n shieldops -p '{"spec": {"type": "LoadBalancer"}}'
```

### Service dependency order

Deploy infrastructure services before the ShieldOps application:

1. PostgreSQL (or use a managed database)
2. Redis
3. Kafka
4. OPA (with policies mounted)
5. ShieldOps API (runs `alembic upgrade head` on startup, then starts uvicorn)

---

## CI/CD Pipeline

ShieldOps uses three GitHub Actions workflows located in `.github/workflows/`.

### Workflows

| Workflow               | Trigger                          | Purpose                                |
|------------------------|----------------------------------|----------------------------------------|
| `ci.yml`               | Push/PR to `main`                | Lint, typecheck, test, Terraform validate, security scan |
| `cd-staging.yml`       | CI passes on `main`              | Build image, Trivy scan, deploy to staging ECS |
| `cd-production.yml`    | Manual dispatch                  | Promote staging image to production, or rollback |

### CI Pipeline (`ci.yml`)

Runs five parallel jobs:

1. **lint** -- `ruff check` and `ruff format --check` on `src/` and `tests/`
2. **typecheck** -- `mypy src/shieldops/`
3. **test** -- Full test suite with PostgreSQL and Redis service containers, coverage enforcement at 80%
4. **terraform** -- `terraform fmt`, `init`, and `validate` for all three cloud providers (aws, gcp, azure)
5. **security** -- `bandit` static analysis (HIGH+ severity) and `pip-audit` dependency scan

### Staging Deployment (`cd-staging.yml`)

Triggered automatically when CI passes on `main`:

1. Generate image tag from git SHA + run number
2. Authenticate to AWS via OIDC (no static credentials)
3. Build and push Docker image to staging ECR
4. Run Trivy container vulnerability scan (blocks on CRITICAL/HIGH)
5. Deploy to ECS Fargate (update task definition, force new deployment)
6. Wait for service stability (up to 5 minutes)
7. Verify ALB health endpoint (polls for up to 120 seconds)

### Production Deployment (`cd-production.yml`)

Triggered manually via `workflow_dispatch` with required inputs:

- `image_tag` (required): Tag that was verified in staging (e.g., `sha-abc1234-42`)
- `rollback` (optional, boolean): Roll back to the previous ECS task definition revision

Production deployment flow:

1. Promote image from staging ECR to production ECR (re-tag, not rebuild)
2. Update ECS task definition with new image
3. Deploy to production ECS
4. Wait for stability (up to 10 minutes)
5. Verify ALB health (polls for up to 180 seconds)
6. Create a git release tag (e.g., `v20260219-sha-abc1234-42`)

### Required GitHub Secrets

| Secret                   | Description                                             |
|--------------------------|---------------------------------------------------------|
| `AWS_DEPLOY_ROLE_ARN`    | IAM role ARN for OIDC-based AWS authentication          |
| `STAGING_HEALTH_URL`     | ALB health endpoint URL for staging                     |
| `PRODUCTION_HEALTH_URL`  | ALB health endpoint URL for production                  |

### Deployment approval

Production deployments require approval via GitHub Environments. Configure the `production`
environment in your repository settings with required reviewers.

---

## Post-Deployment Verification

After deploying to any environment, verify the following endpoints:

```bash
# Health check (should return 200 with version)
curl https://api.shieldops.io/health

# Readiness check (should show all dependencies as "ok")
curl https://api.shieldops.io/ready

# API documentation
open https://api.shieldops.io/api/v1/docs

# Prometheus metrics
curl https://api.shieldops.io/metrics
```

---

## Troubleshooting

### Database connection failures

Verify the `SHIELDOPS_DATABASE_URL` uses the `postgresql+asyncpg://` scheme. ShieldOps uses
asyncpg for async database access via SQLAlchemy.

```bash
# Test connectivity
python -c "
import asyncio, asyncpg
asyncio.run(asyncpg.connect('postgresql://shieldops:shieldops@localhost:5432/shieldops'))
print('OK')
"
```

### OPA policy loading

OPA must start with the policies directory mounted. Verify policies are loaded:

```bash
curl http://localhost:8181/v1/policies
```

### Kafka connectivity

If running locally, ensure Kafka advertised listeners match the hostname your application uses.
The docker-compose configuration uses `kafka:9092` internally. For host-machine access, you may
need to add a listener for `localhost:9092`.

### ECS task failures

Check CloudWatch logs for the task:

```bash
aws logs get-log-events \
  --log-group-name /ecs/shieldops-production \
  --log-stream-name <stream-name> \
  --region us-east-1
```

### Migration failures

If `alembic upgrade head` fails, check that the database exists and the user has CREATE TABLE
permissions. The Docker entrypoint runs migrations automatically before starting uvicorn.
