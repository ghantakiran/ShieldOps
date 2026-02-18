###############################################################################
# ShieldOps — Azure Cache for Redis
###############################################################################

# ---------------------------------------------------------------------------
# Redis Cache
# ---------------------------------------------------------------------------

resource "azurerm_redis_cache" "main" {
  name                          = "${var.project_name}-${var.environment}-redis"
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  capacity                      = var.redis_capacity
  family                        = "C"
  sku_name                      = var.redis_sku_name
  minimum_tls_version           = "1.2"
  public_network_access_enabled = false
  redis_version                 = "6"

  redis_configuration {}

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-redis"
  })
}

# ---------------------------------------------------------------------------
# Private DNS Zone for Redis
# ---------------------------------------------------------------------------

resource "azurerm_private_dns_zone" "redis" {
  name                = "privatelink.redis.cache.windows.net"
  resource_group_name = azurerm_resource_group.main.name

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-redis-dns"
  })
}

resource "azurerm_private_dns_zone_virtual_network_link" "redis" {
  name                  = "${var.project_name}-${var.environment}-redis-dns-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.redis.name
  virtual_network_id    = azurerm_virtual_network.main.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-redis-dns-link"
  })
}

# ---------------------------------------------------------------------------
# Private Endpoint for Redis
# ---------------------------------------------------------------------------

resource "azurerm_private_endpoint" "redis" {
  name                = "${var.project_name}-${var.environment}-redis-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.redis.id

  private_service_connection {
    name                           = "${var.project_name}-${var.environment}-redis-psc"
    private_connection_resource_id = azurerm_redis_cache.main.id
    subresource_names              = ["redisCache"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "redis-dns-zone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.redis.id]
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-redis-pe"
  })
}
