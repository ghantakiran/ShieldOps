###############################################################################
# ShieldOps — Memorystore Redis
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# Memorystore Redis Instance
# ---------------------------------------------------------------------------

resource "google_redis_instance" "main" {
  name           = "${var.project_name}-${var.environment}-redis"
  display_name   = "ShieldOps ${var.environment} Redis"
  region         = var.gcp_region
  redis_version  = "REDIS_7_0"
  tier           = "STANDARD_HA"
  memory_size_gb = var.redis_memory_size_gb

  auth_enabled            = true
  transit_encryption_mode = "SERVER_AUTHENTICATION"

  authorized_network = google_compute_network.main.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 5
        minutes = 0
        seconds = 0
        nanos   = 0
      }
    }
  }

  labels = {
    name = "${var.project_name}-${var.environment}-redis"
  }

  depends_on = [
    google_service_networking_connection.private_services,
    google_project_service.apis,
  ]
}
