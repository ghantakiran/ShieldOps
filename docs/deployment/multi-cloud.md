# Multi-Cloud Deployment

ShieldOps supports deployment on AWS, GCP, and Azure using Terraform. Each cloud
provider has its own Terraform configuration in `infrastructure/terraform/{provider}/`.

---

## AWS Deployment

ShieldOps deploys on AWS using **ECS Fargate** with RDS PostgreSQL, ElastiCache Redis,
MSK (Kafka), and an Application Load Balancer.

### Architecture

```
Internet --> ALB --> ECS Fargate (ShieldOps API)
                         |
              +----------+----------+
              |          |          |
          RDS (PG)  ElastiCache  MSK (Kafka)
                     (Redis)
```

### Prerequisites

- AWS CLI 2.x
- Terraform >= 1.5
- Docker 24+

### Steps

1. **Store secrets** in AWS Secrets Manager:

    ```bash
    aws secretsmanager create-secret \
      --name shieldops/production/app-secrets \
      --secret-string '{
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "JWT_SECRET": "your-production-jwt-secret"
      }' \
      --region us-east-1
    ```

2. **Configure Terraform** variables:

    ```bash
    cd infrastructure/terraform/aws
    cp terraform.tfvars.example terraform.tfvars
    # Edit terraform.tfvars
    ```

3. **Provision infrastructure:**

    ```bash
    terraform init && terraform plan -out=tfplan && terraform apply tfplan
    ```

4. **Build and push Docker image:**

    ```bash
    aws ecr get-login-password --region us-east-1 | \
      docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

    docker build -t shieldops -f infrastructure/docker/Dockerfile .
    IMAGE_TAG="sha-$(git rev-parse --short HEAD)"
    docker tag shieldops:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/shieldops-production:${IMAGE_TAG}
    docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/shieldops-production:${IMAGE_TAG}
    ```

5. **Deploy the service:**

    ```bash
    aws ecs update-service \
      --cluster shieldops-production-cluster \
      --service shieldops-production-service \
      --force-new-deployment
    ```

### Key Resources Created

- VPC with public/private subnets across 3 AZs
- ECS Fargate cluster and service
- ECR repository
- RDS PostgreSQL (private subnet, encrypted)
- ElastiCache Redis (private subnet)
- ALB with optional HTTPS
- CloudWatch alarms and log groups
- IAM roles and security groups
- Auto-scaling policies (2-10 instances)

---

## GCP Deployment

ShieldOps deploys on GCP using **Cloud Run** with Cloud SQL (PostgreSQL),
Memorystore (Redis), and a global HTTPS load balancer.

### Prerequisites

- gcloud CLI
- Terraform >= 1.5
- Docker 24+

### Steps

1. **Enable APIs and store secrets:**

    ```bash
    gcloud services enable run.googleapis.com sqladmin.googleapis.com redis.googleapis.com
    echo -n "sk-ant-..." | gcloud secrets create anthropic-api-key --data-file=-
    ```

2. **Configure and provision:**

    ```bash
    cd infrastructure/terraform/gcp
    cp terraform.tfvars.example terraform.tfvars
    terraform init && terraform plan -out=tfplan && terraform apply tfplan
    ```

3. **Build and deploy:**

    ```bash
    gcloud auth configure-docker us-central1-docker.pkg.dev
    IMAGE_TAG="sha-$(git rev-parse --short HEAD)"
    docker build -t us-central1-docker.pkg.dev/PROJECT/shieldops-production/shieldops:${IMAGE_TAG} \
      -f infrastructure/docker/Dockerfile .
    docker push us-central1-docker.pkg.dev/PROJECT/shieldops-production/shieldops:${IMAGE_TAG}
    gcloud run services update shieldops-api --image ...${IMAGE_TAG} --region us-central1
    ```

### Key Resources Created

- VPC with private services access
- Cloud Run service with VPC connector
- Artifact Registry repository
- Cloud SQL PostgreSQL (private IP, encrypted)
- Memorystore Redis
- Global HTTPS load balancer with managed SSL
- Cloud Monitoring alert policies

---

## Azure Deployment

ShieldOps deploys on Azure using **Container Apps** with Azure Database for PostgreSQL
Flexible Server, Azure Cache for Redis, and Azure Container Registry.

### Prerequisites

- Azure CLI 2.x
- Terraform >= 1.5
- Docker 24+

### Steps

1. **Store secrets in Key Vault:**

    ```bash
    az keyvault secret set --vault-name shieldops-kv --name anthropic-api-key --value "sk-ant-..."
    ```

2. **Configure and provision:**

    ```bash
    cd infrastructure/terraform/azure
    cp terraform.tfvars.example terraform.tfvars
    terraform init && terraform plan -out=tfplan && terraform apply tfplan
    ```

3. **Build and deploy:**

    ```bash
    az acr login --name shieldopsproductionacr
    IMAGE_TAG="sha-$(git rev-parse --short HEAD)"
    docker build -t shieldopsproductionacr.azurecr.io/shieldops:${IMAGE_TAG} \
      -f infrastructure/docker/Dockerfile .
    docker push shieldopsproductionacr.azurecr.io/shieldops:${IMAGE_TAG}
    az containerapp update --name shieldops-api --resource-group shieldops-production-rg \
      --image shieldopsproductionacr.azurecr.io/shieldops:${IMAGE_TAG}
    ```

### Key Resources Created

- Virtual Network with subnets
- Container Apps Environment and Container App
- Azure Container Registry
- PostgreSQL Flexible Server (VNet-integrated, encrypted)
- Azure Cache for Redis
- Key Vault for secrets
- Azure Monitor alert rules
- Managed identities with RBAC

---

## CI/CD Pipeline

ShieldOps uses three GitHub Actions workflows:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push/PR to `main` | Lint, typecheck, test, Terraform validate, security scan |
| `cd-staging.yml` | CI passes on `main` | Build image, Trivy scan, deploy to staging ECS |
| `cd-production.yml` | Manual dispatch | Promote staging image to production |

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AWS_DEPLOY_ROLE_ARN` | IAM role ARN for OIDC-based AWS auth |
| `STAGING_HEALTH_URL` | ALB health endpoint for staging |
| `PRODUCTION_HEALTH_URL` | ALB health endpoint for production |

---

## Post-Deployment Verification

After deploying to any environment:

```bash
# Health check
curl https://api.shieldops.io/health

# Readiness check (DB, Redis, OPA)
curl https://api.shieldops.io/ready

# API documentation
curl https://api.shieldops.io/api/v1/docs

# Prometheus metrics
curl https://api.shieldops.io/metrics
```
