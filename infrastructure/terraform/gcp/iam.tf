###############################################################################
# ShieldOps — IAM Service Accounts & Workload Identity
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

# ---------------------------------------------------------------------------
# Application Service Account
# Used by Cloud Run to access Cloud SQL, Secret Manager, logging, monitoring
# ---------------------------------------------------------------------------

resource "google_service_account" "app" {
  account_id   = "${var.project_name}-${var.environment}-app"
  display_name = "ShieldOps Application"
  description  = "Service account for the ShieldOps Cloud Run application (${var.environment})"
}

# -- Cloud SQL Client -------------------------------------------------------

resource "google_project_iam_member" "app_cloudsql_client" {
  project = var.gcp_project
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.app.email}"
}

# -- Secret Manager Secret Accessor -----------------------------------------

resource "google_project_iam_member" "app_secret_accessor" {
  project = var.gcp_project
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.app.email}"
}

# -- Cloud Logging Writer ----------------------------------------------------

resource "google_project_iam_member" "app_log_writer" {
  project = var.gcp_project
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.app.email}"
}

# -- Cloud Monitoring Metric Writer ------------------------------------------

resource "google_project_iam_member" "app_metric_writer" {
  project = var.gcp_project
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.app.email}"
}

# -- Cloud Run Invoker (allow load balancer to invoke the service) -----------

resource "google_cloud_run_v2_service_iam_member" "app_invoker" {
  project  = var.gcp_project
  location = var.gcp_region
  name     = google_cloud_run_v2_service.main.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------------------------------------------------------------------
# Workload Identity Federation for GitHub Actions
# Enables keyless authentication from GitHub Actions via OpenID Connect
# ---------------------------------------------------------------------------

resource "google_iam_workload_identity_pool" "github_actions" {
  workload_identity_pool_id = "${var.project_name}-github-actions"
  display_name              = "GitHub Actions"
  description               = "Workload Identity Pool for GitHub Actions CI/CD"
}

resource "google_iam_workload_identity_pool_provider" "github_actions" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC Provider"
  description                        = "OIDC provider for GitHub Actions"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
    "attribute.actor"            = "assertion.actor"
    "attribute.ref"              = "assertion.ref"
  }

  attribute_condition = "assertion.repository_owner == 'ghantakiran'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# ---------------------------------------------------------------------------
# GitHub Actions Deploy Service Account
# ---------------------------------------------------------------------------

resource "google_service_account" "github_actions" {
  account_id   = "${var.project_name}-github-deploy"
  display_name = "GitHub Actions Deploy"
  description  = "Service account for GitHub Actions CI/CD deployments"
}

# -- Cloud Run Developer (deploy new revisions) -----------------------------

resource "google_project_iam_member" "github_run_developer" {
  project = var.gcp_project
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# -- Artifact Registry Writer (push images) ---------------------------------

resource "google_project_iam_member" "github_ar_writer" {
  project = var.gcp_project
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# -- Allow GitHub Actions to act as the deploy service account ---------------

resource "google_service_account_iam_member" "github_actions_wif" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_actions.name}/attribute.repository/ghantakiran/ShieldOps"
}

# -- Allow GitHub Actions SA to act as the app SA (for Cloud Run deploy) -----

resource "google_service_account_iam_member" "github_actions_act_as_app" {
  service_account_id = google_service_account.app.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.github_actions.email}"
}
