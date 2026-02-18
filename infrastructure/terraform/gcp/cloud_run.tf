###############################################################################
# ShieldOps — Cloud Run Service
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# Cloud Run V2 Service
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "main" {
  name     = "${var.project_name}-${var.environment}-app"
  location = var.gcp_region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.app.email

    scaling {
      min_instance_count = var.app_min_instances
      max_instance_count = var.app_max_instances
    }

    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "ALL_TRAFFIC"
    }

    # -------------------------------------------------------------------
    # Application Container
    # -------------------------------------------------------------------
    containers {
      name  = "shieldops-app"
      image = var.container_image

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = var.app_cpu
          memory = var.app_memory
        }
      }

      # -- Plain-text environment variables --------------------------------
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "DATABASE_HOST"
        value = google_sql_database_instance.main.private_ip_address
      }
      env {
        name  = "DATABASE_PORT"
        value = "5432"
      }
      env {
        name  = "DATABASE_NAME"
        value = "shieldops"
      }
      env {
        name  = "DATABASE_USER"
        value = "shieldops_admin"
      }
      env {
        name  = "REDIS_HOST"
        value = google_redis_instance.main.host
      }
      env {
        name  = "REDIS_PORT"
        value = tostring(google_redis_instance.main.port)
      }
      env {
        name  = "REDIS_TLS"
        value = "true"
      }
      env {
        name  = "OPA_ENDPOINT"
        value = "http://localhost:8181"
      }
      env {
        name  = "APP_PORT"
        value = "8000"
      }

      # -- Secrets from Secret Manager -------------------------------------
      env {
        name = "DATABASE_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.rds_password.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "JWT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "OPENAI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.openai_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "LANGSMITH_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.langsmith_api_key.secret_id
            version = "latest"
          }
        }
      }

      # -- Health Probes ---------------------------------------------------
      startup_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        timeout_seconds       = 5
        failure_threshold     = 6
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        period_seconds    = 30
        timeout_seconds   = 5
        failure_threshold = 3
      }
    }

    # -------------------------------------------------------------------
    # OPA Sidecar Container
    # -------------------------------------------------------------------
    containers {
      name  = "opa-sidecar"
      image = "openpolicyagent/opa:latest"

      command = ["run", "--server", "--addr", "0.0.0.0:8181"]

      ports {
        container_port = 8181
      }

      resources {
        limits = {
          cpu    = "500m"
          memory = "256Mi"
        }
      }
    }
  }

  labels = {
    name = "${var.project_name}-${var.environment}-app"
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_version.rds_password,
    google_secret_manager_secret_version.anthropic_api_key,
    google_secret_manager_secret_version.jwt_secret,
    google_secret_manager_secret_version.openai_api_key,
    google_secret_manager_secret_version.langsmith_api_key,
  ]
}
