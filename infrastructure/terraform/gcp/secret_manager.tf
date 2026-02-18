###############################################################################
# ShieldOps — Secret Manager
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# Database Password (managed by Terraform)
# ---------------------------------------------------------------------------

resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}:?"
}

resource "google_secret_manager_secret" "rds_password" {
  secret_id = "${var.project_name}-${var.environment}-rds-password"

  replication {
    auto {}
  }

  labels = {
    name = "${var.project_name}-${var.environment}-rds-password"
  }

  depends_on = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_version" "rds_password" {
  secret      = google_secret_manager_secret.rds_password.id
  secret_data = random_password.db.result
}

# ---------------------------------------------------------------------------
# Anthropic API Key (placeholder — update after initial deploy)
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "${var.project_name}-${var.environment}-anthropic-api-key"

  replication {
    auto {}
  }

  labels = {
    name = "${var.project_name}-${var.environment}-anthropic-api-key"
  }

  depends_on = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_version" "anthropic_api_key" {
  secret      = google_secret_manager_secret.anthropic_api_key.id
  secret_data = "REPLACE_ME_WITH_ACTUAL_KEY"
}

# ---------------------------------------------------------------------------
# JWT Secret (placeholder — update after initial deploy)
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "${var.project_name}-${var.environment}-jwt-secret"

  replication {
    auto {}
  }

  labels = {
    name = "${var.project_name}-${var.environment}-jwt-secret"
  }

  depends_on = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_version" "jwt_secret" {
  secret      = google_secret_manager_secret.jwt_secret.id
  secret_data = "REPLACE_ME_WITH_ACTUAL_SECRET"
}

# ---------------------------------------------------------------------------
# OpenAI API Key (placeholder — update after initial deploy)
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "${var.project_name}-${var.environment}-openai-api-key"

  replication {
    auto {}
  }

  labels = {
    name = "${var.project_name}-${var.environment}-openai-api-key"
  }

  depends_on = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_version" "openai_api_key" {
  secret      = google_secret_manager_secret.openai_api_key.id
  secret_data = "REPLACE_ME_WITH_ACTUAL_KEY"
}

# ---------------------------------------------------------------------------
# LangSmith API Key (placeholder — update after initial deploy)
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "langsmith_api_key" {
  secret_id = "${var.project_name}-${var.environment}-langsmith-api-key"

  replication {
    auto {}
  }

  labels = {
    name = "${var.project_name}-${var.environment}-langsmith-api-key"
  }

  depends_on = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_version" "langsmith_api_key" {
  secret      = google_secret_manager_secret.langsmith_api_key.id
  secret_data = "REPLACE_ME_WITH_ACTUAL_KEY"
}
