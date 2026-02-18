###############################################################################
# ShieldOps — Artifact Registry
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# Docker Repository
# ---------------------------------------------------------------------------

resource "google_artifact_registry_repository" "main" {
  location      = var.gcp_region
  repository_id = "${var.project_name}-${var.environment}"
  description   = "Docker container images for ShieldOps ${var.environment}"
  format        = "DOCKER"
  mode          = "STANDARD_REPOSITORY"

  docker_config {
    immutable_tags = true
  }

  cleanup_policies {
    id     = "keep-minimum-versions"
    action = "KEEP"

    most_recent_versions {
      keep_count = 10
    }
  }

  cleanup_policies {
    id     = "delete-old-untagged"
    action = "DELETE"

    condition {
      tag_state  = "UNTAGGED"
      older_than = "604800s" # 7 days
    }
  }

  labels = {
    name = "${var.project_name}-${var.environment}-registry"
  }

  depends_on = [google_project_service.apis]
}
