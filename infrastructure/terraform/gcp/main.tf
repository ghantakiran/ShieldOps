###############################################################################
# ShieldOps — Terraform Root Configuration
# AI-Powered Autonomous SRE Platform — GCP Deployment
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  backend "gcs" {
    bucket = "shieldops-terraform-state"
    prefix = "gcp/terraform.tfstate"
  }
}

provider "google" {
  project = var.gcp_project
  region  = var.gcp_region

  default_labels = {
    project     = "shieldops"
    environment = var.environment
    managed_by  = "terraform"
  }
}

provider "google-beta" {
  project = var.gcp_project
  region  = var.gcp_region

  default_labels = {
    project     = "shieldops"
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ---------------------------------------------------------------------------
# Enable Required APIs
# ---------------------------------------------------------------------------

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "compute.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "monitoring.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
  ])

  project = var.gcp_project
  service = each.value

  disable_dependent_services = false
  disable_on_destroy         = false
}
