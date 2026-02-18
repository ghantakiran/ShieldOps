###############################################################################
# ShieldOps — Azure Container Registry
###############################################################################

locals {
  # ACR names must be alphanumeric only (no hyphens)
  acr_name = "${replace(var.project_name, "-", "")}${var.environment}acr"
}

# ---------------------------------------------------------------------------
# Container Registry
# ---------------------------------------------------------------------------

resource "azurerm_container_registry" "main" {
  name                = local.acr_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Standard"
  admin_enabled       = false

  # Geo-replication — production only (requires Premium SKU, so kept as
  # documentation for when upgrading to Premium)
  # dynamic "georeplications" {
  #   for_each = var.environment == "production" ? ["westus2"] : []
  #   content {
  #     location = georeplications.value
  #     tags     = local.common_tags
  #   }
  # }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-acr"
  })
}
