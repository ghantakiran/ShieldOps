###############################################################################
# ShieldOps — Outputs
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# Cloud Run
# ---------------------------------------------------------------------------

output "cloud_run_url" {
  description = "URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.main.uri
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

output "cloud_sql_ip" {
  description = "Private IP address of the Cloud SQL PostgreSQL instance"
  value       = google_sql_database_instance.main.private_ip_address
}

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

output "memorystore_host" {
  description = "Memorystore Redis host"
  value       = google_redis_instance.main.host
}

output "memorystore_port" {
  description = "Memorystore Redis port"
  value       = google_redis_instance.main.port
}

# ---------------------------------------------------------------------------
# Load Balancer
# ---------------------------------------------------------------------------

output "load_balancer_ip" {
  description = "Global static IP address of the HTTPS load balancer"
  value       = google_compute_global_address.main.address
}

# ---------------------------------------------------------------------------
# Artifact Registry
# ---------------------------------------------------------------------------

output "artifact_registry_url" {
  description = "URL of the Artifact Registry Docker repository"
  value       = format("%s-docker.pkg.dev/%s/%s", var.gcp_region, var.gcp_project, google_artifact_registry_repository.main.repository_id)
}

# ---------------------------------------------------------------------------
# IAM
# ---------------------------------------------------------------------------

output "service_account_email" {
  description = "Email of the application service account"
  value       = google_service_account.app.email
}

# ---------------------------------------------------------------------------
# CI/CD
# ---------------------------------------------------------------------------

output "github_actions_service_account_email" {
  description = "Email of the GitHub Actions deploy service account"
  value       = google_service_account.github_actions.email
}

output "workload_identity_pool_provider" {
  description = "Full name of the Workload Identity Pool Provider for GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github_actions.name
}
