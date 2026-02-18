###############################################################################
# ShieldOps — Azure Container Apps
###############################################################################

# ---------------------------------------------------------------------------
# Container App Environment
# ---------------------------------------------------------------------------

resource "azurerm_container_app_environment" "main" {
  name                           = "${var.project_name}-${var.environment}-cae"
  location                       = azurerm_resource_group.main.location
  resource_group_name            = azurerm_resource_group.main.name
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.main.id
  infrastructure_subnet_id       = azurerm_subnet.container_apps.id
  internal_load_balancer_enabled = false

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-cae"
  })
}

# ---------------------------------------------------------------------------
# Container App
# ---------------------------------------------------------------------------

resource "azurerm_container_app" "main" {
  name                         = "${var.project_name}-${var.environment}-app"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "http"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  # -------------------------------------------------------------------------
  # Secrets (referenced by Container App from Key Vault)
  # -------------------------------------------------------------------------

  secret {
    name  = "database-password"
    value = random_password.db.result
  }

  secret {
    name                = "anthropic-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.anthropic_api_key.id
    identity            = azurerm_user_assigned_identity.app.id
  }

  secret {
    name                = "jwt-secret"
    key_vault_secret_id = azurerm_key_vault_secret.jwt_secret.id
    identity            = azurerm_user_assigned_identity.app.id
  }

  secret {
    name                = "openai-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.openai_api_key.id
    identity            = azurerm_user_assigned_identity.app.id
  }

  secret {
    name                = "langsmith-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.langsmith_api_key.id
    identity            = azurerm_user_assigned_identity.app.id
  }

  # -------------------------------------------------------------------------
  # Template — Application & OPA Sidecar Containers
  # -------------------------------------------------------------------------

  template {
    min_replicas = var.app_min_replicas
    max_replicas = var.app_max_replicas

    container {
      name   = "shieldops-app"
      image  = var.container_image
      cpu    = var.app_cpu
      memory = var.app_memory

      # -- Environment Variables (non-sensitive) ----------------------------

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "DATABASE_HOST"
        value = azurerm_postgresql_flexible_server.main.fqdn
      }

      env {
        name  = "DATABASE_PORT"
        value = "5432"
      }

      env {
        name  = "DATABASE_NAME"
        value = "shieldops"
      }

      env {
        name  = "DATABASE_USER"
        value = "shieldops_admin"
      }

      env {
        name  = "REDIS_HOST"
        value = azurerm_redis_cache.main.hostname
      }

      env {
        name  = "REDIS_PORT"
        value = tostring(azurerm_redis_cache.main.ssl_port)
      }

      env {
        name  = "REDIS_TLS"
        value = "true"
      }

      env {
        name  = "OPA_ENDPOINT"
        value = "http://localhost:8181"
      }

      env {
        name  = "APP_PORT"
        value = "8000"
      }

      # -- Environment Variables (secrets) ----------------------------------

      env {
        name        = "DATABASE_PASSWORD"
        secret_name = "database-password"
      }

      env {
        name        = "ANTHROPIC_API_KEY"
        secret_name = "anthropic-api-key"
      }

      env {
        name        = "JWT_SECRET"
        secret_name = "jwt-secret"
      }

      env {
        name        = "OPENAI_API_KEY"
        secret_name = "openai-api-key"
      }

      env {
        name        = "LANGSMITH_API_KEY"
        secret_name = "langsmith-api-key"
      }

      # -- Health Probes ----------------------------------------------------

      liveness_probe {
        path      = "/health"
        port      = 8000
        transport = "HTTP"
      }

      readiness_probe {
        path      = "/health"
        port      = 8000
        transport = "HTTP"
      }
    }

    # -- OPA Sidecar Container ----------------------------------------------

    container {
      name   = "opa-sidecar"
      image  = "openpolicyagent/opa:latest"
      cpu    = 0.25
      memory = "0.5Gi"

      command = ["run", "--server", "--addr", "0.0.0.0:8181"]
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-app"
  })

  depends_on = [
    azurerm_role_assignment.app_acr_pull,
    azurerm_role_assignment.app_key_vault_secrets,
  ]
}
