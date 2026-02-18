###############################################################################
# ShieldOps — Cloud SQL PostgreSQL
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# Cloud SQL Instance
# ---------------------------------------------------------------------------

resource "google_sql_database_instance" "main" {
  name             = "${var.project_name}-${var.environment}-postgres"
  database_version = "POSTGRES_16"
  region           = var.gcp_region

  deletion_protection = true

  settings {
    tier              = var.db_tier
    availability_type = "REGIONAL"
    disk_size         = var.db_disk_size
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.main.id
      enable_private_path_for_google_cloud_services = true
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = 7
      }
    }

    maintenance_window {
      day          = 7
      hour         = 4
      update_track = "stable"
    }

    database_flags {
      name  = "log_connections"
      value = "on"
    }
    database_flags {
      name  = "log_disconnections"
      value = "on"
    }
    database_flags {
      name  = "log_statement"
      value = "ddl"
    }

    insights_config {
      query_insights_enabled  = true
      query_plans_per_minute  = 5
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }

    user_labels = {
      name = "${var.project_name}-${var.environment}-postgres"
    }
  }

  depends_on = [
    google_service_networking_connection.private_services,
    google_project_service.apis,
  ]

  lifecycle {
    prevent_destroy = true
  }
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

resource "google_sql_database" "main" {
  name     = "shieldops"
  instance = google_sql_database_instance.main.name
}

# ---------------------------------------------------------------------------
# Database User
# ---------------------------------------------------------------------------

resource "google_sql_user" "main" {
  name     = "shieldops_admin"
  instance = google_sql_database_instance.main.name
  password = random_password.db.result
}
