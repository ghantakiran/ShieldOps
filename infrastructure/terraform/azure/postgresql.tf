###############################################################################
# ShieldOps — Azure Database for PostgreSQL Flexible Server
###############################################################################

# ---------------------------------------------------------------------------
# Private DNS Zone for PostgreSQL
# ---------------------------------------------------------------------------

resource "azurerm_private_dns_zone" "postgresql" {
  name                = "${var.project_name}-${var.environment}.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.main.name

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-postgresql-dns"
  })
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgresql" {
  name                  = "${var.project_name}-${var.environment}-postgresql-dns-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.postgresql.name
  virtual_network_id    = azurerm_virtual_network.main.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-postgresql-dns-link"
  })
}

# ---------------------------------------------------------------------------
# PostgreSQL Flexible Server
# ---------------------------------------------------------------------------

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "${var.project_name}-${var.environment}-postgres"
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  version                       = "16"
  sku_name                      = var.db_sku_name
  storage_mb                    = var.db_storage_mb
  auto_grow_enabled             = true
  zone                          = "1"
  delegated_subnet_id           = azurerm_subnet.database.id
  private_dns_zone_id           = azurerm_private_dns_zone.postgresql.id
  administrator_login           = "shieldops_admin"
  administrator_password        = random_password.db.result
  backup_retention_days         = 7
  geo_redundant_backup_enabled  = false
  public_network_access_enabled = false

  # High availability — Zone-Redundant for production only
  dynamic "high_availability" {
    for_each = var.environment == "production" ? [1] : []
    content {
      mode = "ZoneRedundant"
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-postgres"
  })

  depends_on = [
    azurerm_private_dns_zone_virtual_network_link.postgresql,
  ]
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = "shieldops"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# ---------------------------------------------------------------------------
# Server Configuration Parameters
# ---------------------------------------------------------------------------

resource "azurerm_postgresql_flexible_server_configuration" "log_connections" {
  name      = "log_connections"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

resource "azurerm_postgresql_flexible_server_configuration" "log_disconnections" {
  name      = "log_disconnections"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

resource "azurerm_postgresql_flexible_server_configuration" "log_statement" {
  name      = "log_statement"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "ddl"
}
