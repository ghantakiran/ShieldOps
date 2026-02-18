###############################################################################
# ShieldOps — Azure Key Vault & Secrets
###############################################################################

locals {
  # Key Vault names must be 3–24 alphanumeric characters and globally unique
  key_vault_name = "${var.project_name}-${var.environment}-kv"
}

# ---------------------------------------------------------------------------
# Key Vault
# ---------------------------------------------------------------------------

resource "azurerm_key_vault" "main" {
  name                       = local.key_vault_name
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = true
  soft_delete_retention_days = 90

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-kv"
  })
}

# ---------------------------------------------------------------------------
# Role assignment — allow Terraform deployer to manage secrets
# ---------------------------------------------------------------------------

resource "azurerm_role_assignment" "deployer_key_vault_admin" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

# ---------------------------------------------------------------------------
# Database Password (managed by Terraform)
# ---------------------------------------------------------------------------

resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}:?"
}

resource "azurerm_key_vault_secret" "db_password" {
  name         = "db-password"
  value        = random_password.db.result
  key_vault_id = azurerm_key_vault.main.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-db-password"
  })

  depends_on = [azurerm_role_assignment.deployer_key_vault_admin]
}

# ---------------------------------------------------------------------------
# Application Secrets (placeholders — update after initial deployment)
# ---------------------------------------------------------------------------

resource "azurerm_key_vault_secret" "anthropic_api_key" {
  name         = "anthropic-api-key"
  value        = "CHANGE_ME"
  key_vault_id = azurerm_key_vault.main.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-anthropic-api-key"
  })

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_key_vault_admin]
}

resource "azurerm_key_vault_secret" "jwt_secret" {
  name         = "jwt-secret"
  value        = "CHANGE_ME"
  key_vault_id = azurerm_key_vault.main.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-jwt-secret"
  })

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_key_vault_admin]
}

resource "azurerm_key_vault_secret" "openai_api_key" {
  name         = "openai-api-key"
  value        = "CHANGE_ME"
  key_vault_id = azurerm_key_vault.main.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-openai-api-key"
  })

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_key_vault_admin]
}

resource "azurerm_key_vault_secret" "langsmith_api_key" {
  name         = "langsmith-api-key"
  value        = "CHANGE_ME"
  key_vault_id = azurerm_key_vault.main.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-langsmith-api-key"
  })

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_role_assignment.deployer_key_vault_admin]
}
