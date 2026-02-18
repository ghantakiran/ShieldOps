###############################################################################
# ShieldOps — Managed Identities & Role Assignments
###############################################################################

# ---------------------------------------------------------------------------
# Application Managed Identity
# Used by Container Apps at runtime for ACR pull and Key Vault access
# ---------------------------------------------------------------------------

resource "azurerm_user_assigned_identity" "app" {
  name                = "${var.project_name}-${var.environment}-app-identity"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-app-identity"
  })
}

# ---------------------------------------------------------------------------
# Application Role Assignments
# ---------------------------------------------------------------------------

# AcrPull — allow the app to pull container images from ACR
resource "azurerm_role_assignment" "app_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# Key Vault Secrets User — allow the app to read secrets
resource "azurerm_role_assignment" "app_key_vault_secrets" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# ---------------------------------------------------------------------------
# GitHub Actions Managed Identity (OIDC — keyless CI/CD)
# ---------------------------------------------------------------------------

resource "azurerm_user_assigned_identity" "github_actions" {
  name                = "${var.project_name}-github-actions-identity"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-github-actions-identity"
  })
}

# ---------------------------------------------------------------------------
# GitHub Actions — Federated Identity Credentials (OIDC)
# ---------------------------------------------------------------------------

# Main branch
resource "azurerm_federated_identity_credential" "github_actions_main" {
  name                = "${var.project_name}-github-main"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.github_actions.id
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:ghantakiran/ShieldOps:ref:refs/heads/main"
  audience            = ["api://AzureADTokenExchange"]
}

# Staging environment
resource "azurerm_federated_identity_credential" "github_actions_staging" {
  name                = "${var.project_name}-github-staging"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.github_actions.id
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:ghantakiran/ShieldOps:environment:staging"
  audience            = ["api://AzureADTokenExchange"]
}

# Production environment
resource "azurerm_federated_identity_credential" "github_actions_production" {
  name                = "${var.project_name}-github-production"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.github_actions.id
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:ghantakiran/ShieldOps:environment:production"
  audience            = ["api://AzureADTokenExchange"]
}

# ---------------------------------------------------------------------------
# GitHub Actions — Role Assignments
# ---------------------------------------------------------------------------

# AcrPush — allow GitHub Actions to push container images
resource "azurerm_role_assignment" "github_actions_acr_push" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPush"
  principal_id         = azurerm_user_assigned_identity.github_actions.principal_id
}

# Contributor — allow GitHub Actions to manage resources in the resource group
resource "azurerm_role_assignment" "github_actions_contributor" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.github_actions.principal_id
}
