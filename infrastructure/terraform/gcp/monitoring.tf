###############################################################################
# ShieldOps — Cloud Monitoring Alert Policies & Uptime Checks
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# Notification Channel (email — only if alarm_email is set)
# ---------------------------------------------------------------------------

resource "google_monitoring_notification_channel" "email" {
  count = var.alarm_email != "" ? 1 : 0

  display_name = "${var.project_name}-${var.environment}-email-alerts"
  type         = "email"

  labels = {
    email_address = var.alarm_email
  }
}

locals {
  notification_channels = var.alarm_email != "" ? [google_monitoring_notification_channel.email[0].name] : []
}

# ---------------------------------------------------------------------------
# Cloud Run — CPU Utilization > 80% for 5 minutes
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "cloud_run_high_cpu" {
  display_name = "${var.project_name}-${var.environment}-cloud-run-high-cpu"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run CPU utilization > 80%"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"${google_cloud_run_v2_service.main.name}\" AND metric.type = \"run.googleapis.com/container/cpu/utilizations\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_99"
      }
    }
  }

  notification_channels = local.notification_channels

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = {
    environment = var.environment
    project     = var.project_name
  }
}

# ---------------------------------------------------------------------------
# Cloud Run — Memory Utilization > 80% for 5 minutes
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "cloud_run_high_memory" {
  display_name = "${var.project_name}-${var.environment}-cloud-run-high-memory"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run memory utilization > 80%"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"${google_cloud_run_v2_service.main.name}\" AND metric.type = \"run.googleapis.com/container/memory/utilizations\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_99"
      }
    }
  }

  notification_channels = local.notification_channels

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = {
    environment = var.environment
    project     = var.project_name
  }
}

# ---------------------------------------------------------------------------
# Cloud Run — Request Latency p99 > 2s for 5 minutes
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "cloud_run_high_latency" {
  display_name = "${var.project_name}-${var.environment}-cloud-run-high-latency"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run request latency p99 > 2s"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"${google_cloud_run_v2_service.main.name}\" AND metric.type = \"run.googleapis.com/request_latencies\""
      comparison      = "COMPARISON_GT"
      threshold_value = 2000
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_99"
      }
    }
  }

  notification_channels = local.notification_channels

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = {
    environment = var.environment
    project     = var.project_name
  }
}

# ---------------------------------------------------------------------------
# Cloud SQL — CPU Utilization > 80% for 5 minutes
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "cloud_sql_high_cpu" {
  display_name = "${var.project_name}-${var.environment}-cloud-sql-high-cpu"
  combiner     = "OR"

  conditions {
    display_name = "Cloud SQL CPU utilization > 80%"

    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${var.gcp_project}:${google_sql_database_instance.main.name}\" AND metric.type = \"cloudsql.googleapis.com/database/cpu/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = local.notification_channels

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = {
    environment = var.environment
    project     = var.project_name
  }
}

# ---------------------------------------------------------------------------
# Cloud SQL — Connections > 80% of max
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "cloud_sql_high_connections" {
  display_name = "${var.project_name}-${var.environment}-cloud-sql-high-connections"
  combiner     = "OR"

  conditions {
    display_name = "Cloud SQL connections > 80% of max"

    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${var.gcp_project}:${google_sql_database_instance.main.name}\" AND metric.type = \"cloudsql.googleapis.com/database/postgresql/num_backends\""
      comparison      = "COMPARISON_GT"
      threshold_value = 80
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = local.notification_channels

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = {
    environment = var.environment
    project     = var.project_name
  }
}

# ---------------------------------------------------------------------------
# Cloud SQL — Disk Utilization > 90%
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "cloud_sql_high_disk" {
  display_name = "${var.project_name}-${var.environment}-cloud-sql-high-disk"
  combiner     = "OR"

  conditions {
    display_name = "Cloud SQL disk utilization > 90%"

    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${var.gcp_project}:${google_sql_database_instance.main.name}\" AND metric.type = \"cloudsql.googleapis.com/database/disk/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.9
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = local.notification_channels

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = {
    environment = var.environment
    project     = var.project_name
  }
}

# ---------------------------------------------------------------------------
# Uptime Check — Cloud Run /health endpoint
# ---------------------------------------------------------------------------

resource "google_monitoring_uptime_check_config" "cloud_run_health" {
  display_name = "${var.project_name}-${var.environment}-health-check"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/health"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.gcp_project
      host       = replace(google_cloud_run_v2_service.main.uri, "https://", "")
    }
  }
}

resource "google_monitoring_alert_policy" "uptime_check" {
  display_name = "${var.project_name}-${var.environment}-uptime-check-failed"
  combiner     = "OR"

  conditions {
    display_name = "Uptime check failed"

    condition_threshold {
      filter          = "resource.type = \"uptime_url\" AND metric.type = \"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.labels.check_id = \"${google_monitoring_uptime_check_config.cloud_run_health.uptime_check_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.project_id"]
      }
    }
  }

  notification_channels = local.notification_channels

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = {
    environment = var.environment
    project     = var.project_name
  }
}
