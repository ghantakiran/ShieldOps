###############################################################################
# ShieldOps — Input Variables
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

variable "gcp_project" {
  description = "GCP project ID for all resources"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
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
# Cloud Run / Application
# ---------------------------------------------------------------------------

variable "app_cpu" {
  description = "CPU allocation for Cloud Run containers (millicores, e.g. 1000m = 1 vCPU)"
  type        = string
  default     = "1000m"
}

variable "app_memory" {
  description = "Memory allocation for Cloud Run containers"
  type        = string
  default     = "1Gi"
}

variable "app_min_instances" {
  description = "Minimum number of Cloud Run instances"
  type        = number
  default     = 2
}

variable "app_max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 10
}

variable "container_image" {
  description = "Docker image URI for the ShieldOps application (e.g. us-central1-docker.pkg.dev/my-project/shieldops-production/shieldops:latest)"
  type        = string
}

# ---------------------------------------------------------------------------
# Database (Cloud SQL PostgreSQL)
# ---------------------------------------------------------------------------

variable "db_tier" {
  description = "Cloud SQL machine tier (e.g. db-custom-2-7680 = 2 vCPU, 7.5 GB RAM)"
  type        = string
  default     = "db-custom-2-7680"
}

variable "db_disk_size" {
  description = "Disk size in GB for the Cloud SQL instance"
  type        = number
  default     = 50
}

# ---------------------------------------------------------------------------
# Cache (Memorystore Redis)
# ---------------------------------------------------------------------------

variable "redis_memory_size_gb" {
  description = "Memory size in GB for the Memorystore Redis instance"
  type        = number
  default     = 1
}

# ---------------------------------------------------------------------------
# TLS / Domain
# ---------------------------------------------------------------------------

variable "domain_name" {
  description = "Custom domain name for the HTTPS load balancer (leave empty to skip managed certificate)"
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

variable "alarm_email" {
  description = "Email address for alert notifications (leave empty to skip notification channel)"
  type        = string
  default     = ""
}
