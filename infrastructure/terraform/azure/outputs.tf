###############################################################################
# ShieldOps — Outputs
###############################################################################

# ---------------------------------------------------------------------------
# Container App
# ---------------------------------------------------------------------------

output "container_app_fqdn" {
  description = "FQDN of the Container App"
  value       = azurerm_container_app.main.ingress[0].fqdn
}

output "container_app_url" {
  description = "Full HTTPS URL of the Container App"
  value       = "https://${azurerm_container_app.main.ingress[0].fqdn}"
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

output "postgresql_fqdn" {
  description = "FQDN of the PostgreSQL Flexible Server"
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

output "redis_hostname" {
  description = "Hostname of the Azure Cache for Redis"
  value       = azurerm_redis_cache.main.hostname
}

output "redis_port" {
  description = "SSL port of the Azure Cache for Redis"
  value       = azurerm_redis_cache.main.ssl_port
}

# ---------------------------------------------------------------------------
# Container Registry
# ---------------------------------------------------------------------------

output "container_registry_login_server" {
  description = "Login server URL of the Azure Container Registry"
  value       = azurerm_container_registry.main.login_server
}

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

output "managed_identity_client_id" {
  description = "Client ID of the application managed identity"
  value       = azurerm_user_assigned_identity.app.client_id
}

# ---------------------------------------------------------------------------
# CI/CD
# ---------------------------------------------------------------------------

output "github_actions_identity_client_id" {
  description = "Client ID of the GitHub Actions managed identity (set as AZURE_CLIENT_ID secret)"
  value       = azurerm_user_assigned_identity.github_actions.client_id
}
