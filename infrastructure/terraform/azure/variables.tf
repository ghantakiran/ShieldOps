###############################################################################
# ShieldOps — Input Variables
###############################################################################

# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

variable "azure_location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus"
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
# Container Apps / Application
# ---------------------------------------------------------------------------

variable "app_cpu" {
  description = "CPU cores for the Container App (fractional, e.g. 1.0 = 1 vCPU)"
  type        = number
  default     = 1.0
}

variable "app_memory" {
  description = "Memory for the Container App (e.g. 2Gi)"
  type        = string
  default     = "2Gi"
}

variable "app_min_replicas" {
  description = "Minimum number of Container App replicas"
  type        = number
  default     = 2
}

variable "app_max_replicas" {
  description = "Maximum number of Container App replicas"
  type        = number
  default     = 10
}

variable "container_image" {
  description = "Docker image URI for the ShieldOps application (e.g. shieldops.azurecr.io/shieldops:latest)"
  type        = string
}

# ---------------------------------------------------------------------------
# Database (Azure Database for PostgreSQL Flexible Server)
# ---------------------------------------------------------------------------

variable "db_sku_name" {
  description = "SKU name for the PostgreSQL Flexible Server"
  type        = string
  default     = "GP_Standard_D2s_v3"
}

variable "db_storage_mb" {
  description = "Storage size in MB for the PostgreSQL Flexible Server (50 GB = 51200 MB)"
  type        = number
  default     = 51200
}

# ---------------------------------------------------------------------------
# Cache (Azure Cache for Redis)
# ---------------------------------------------------------------------------

variable "redis_sku_name" {
  description = "SKU name for Azure Cache for Redis (Basic, Standard, Premium)"
  type        = string
  default     = "Standard"
}

variable "redis_capacity" {
  description = "Size of the Redis cache (C0–C6 for Basic/Standard, P1–P5 for Premium)"
  type        = number
  default     = 1
}

# ---------------------------------------------------------------------------
# TLS / Domain
# ---------------------------------------------------------------------------

variable "domain_name" {
  description = "Custom domain name for the Container App (leave empty to skip)"
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

variable "alarm_email" {
  description = "Email address for monitoring alert notifications (leave empty to skip)"
  type        = string
  default     = ""
}
