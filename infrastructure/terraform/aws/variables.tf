###############################################################################
# ShieldOps — Input Variables
###############################################################################

# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (production, staging, development)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging", "development"], var.environment)
    error_message = "Environment must be one of: production, staging, development."
  }
}

variable "project_name" {
  description = "Project name used as a prefix for all resources"
  type        = string
  default     = "shieldops"
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# ---------------------------------------------------------------------------
# ECS / Application
# ---------------------------------------------------------------------------

variable "app_cpu" {
  description = "CPU units for the ECS task (1 vCPU = 1024)"
  type        = number
  default     = 512
}

variable "app_memory" {
  description = "Memory (MiB) for the ECS task"
  type        = number
  default     = 1024
}

variable "app_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "container_image" {
  description = "Docker image URI for the ShieldOps application (e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com/shieldops:latest)"
  type        = string
}

# ---------------------------------------------------------------------------
# Database (RDS PostgreSQL)
# ---------------------------------------------------------------------------

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB for the RDS instance"
  type        = number
  default     = 50
}

# ---------------------------------------------------------------------------
# Cache (ElastiCache Redis)
# ---------------------------------------------------------------------------

variable "redis_node_type" {
  description = "ElastiCache node type for Redis"
  type        = string
  default     = "cache.t3.medium"
}

# ---------------------------------------------------------------------------
# TLS / Domain
# ---------------------------------------------------------------------------

variable "domain_name" {
  description = "Custom domain name for the ALB (leave empty to skip)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS (required if domain_name is set)"
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

variable "secrets_arn" {
  description = "ARN of the existing Secrets Manager secret containing application secrets (ANTHROPIC_API_KEY, JWT_SECRET, etc.)"
  type        = string
}

# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

variable "alarm_email" {
  description = "Email address for CloudWatch alarm notifications (leave empty to skip)"
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# Auto-Scaling
# ---------------------------------------------------------------------------

variable "autoscaling_min_capacity" {
  description = "Minimum number of ECS tasks for auto-scaling"
  type        = number
  default     = 2
}

variable "autoscaling_max_capacity" {
  description = "Maximum number of ECS tasks for auto-scaling"
  type        = number
  default     = 10
}
