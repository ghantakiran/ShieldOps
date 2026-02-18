###############################################################################
# ShieldOps — Terraform Root Configuration
# AI-Powered Autonomous SRE Platform — Azure Deployment
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  backend "azurerm" {
    resource_group_name  = "shieldops-terraform-rg"
    storage_account_name = "shieldopstfstate"
    container_name       = "tfstate"
    key                  = "infrastructure/terraform.tfstate"
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }
}

# ---------------------------------------------------------------------------
# Data Sources
# ---------------------------------------------------------------------------

data "azurerm_client_config" "current" {}

# ---------------------------------------------------------------------------
# Resource Group
# ---------------------------------------------------------------------------

resource "azurerm_resource_group" "main" {
  name     = "${var.project_name}-${var.environment}-rg"
  location = var.azure_location

  tags = {
    Project     = "ShieldOps"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ---------------------------------------------------------------------------
# Common Tags (used across all modules)
# ---------------------------------------------------------------------------

locals {
  common_tags = {
    Project     = "ShieldOps"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
