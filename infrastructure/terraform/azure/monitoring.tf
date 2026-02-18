###############################################################################
# ShieldOps — Azure Monitor, Log Analytics & Alerts
###############################################################################

# ---------------------------------------------------------------------------
# Log Analytics Workspace
# ---------------------------------------------------------------------------

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.project_name}-${var.environment}-logs"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-logs"
  })
}

# ---------------------------------------------------------------------------
# Action Group (email notifications)
# ---------------------------------------------------------------------------

resource "azurerm_monitor_action_group" "main" {
  count = var.alarm_email != "" ? 1 : 0

  name                = "${var.project_name}-${var.environment}-alerts"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "shieldops"

  email_receiver {
    name          = "shieldops-ops"
    email_address = var.alarm_email
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-alerts"
  })
}

locals {
  action_group_ids = var.alarm_email != "" ? [azurerm_monitor_action_group.main[0].id] : []
}

# ---------------------------------------------------------------------------
# Container App — CPU Alert (>80% for 5 minutes)
# ---------------------------------------------------------------------------

resource "azurerm_monitor_metric_alert" "container_app_cpu" {
  name                = "${var.project_name}-${var.environment}-container-app-high-cpu"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_container_app.main.id]
  description         = "Container App CPU utilization exceeds 80% for 5 minutes"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "Microsoft.App/containerApps"
    metric_name      = "UsageNanoCores"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  dynamic "action" {
    for_each = local.action_group_ids
    content {
      action_group_id = action.value
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-container-app-high-cpu-alert"
  })
}

# ---------------------------------------------------------------------------
# Container App — Memory Alert (>80% for 5 minutes)
# ---------------------------------------------------------------------------

resource "azurerm_monitor_metric_alert" "container_app_memory" {
  name                = "${var.project_name}-${var.environment}-container-app-high-memory"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_container_app.main.id]
  description         = "Container App memory utilization exceeds 80% for 5 minutes"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "Microsoft.App/containerApps"
    metric_name      = "WorkingSetBytes"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  dynamic "action" {
    for_each = local.action_group_ids
    content {
      action_group_id = action.value
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-container-app-high-memory-alert"
  })
}

# ---------------------------------------------------------------------------
# Container App — 5xx Errors (>10 over 5 minutes)
# ---------------------------------------------------------------------------

resource "azurerm_monitor_metric_alert" "container_app_5xx" {
  name                = "${var.project_name}-${var.environment}-container-app-5xx-errors"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_container_app.main.id]
  description         = "Container App is returning more than 10 5xx errors over 5 minutes"
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "Microsoft.App/containerApps"
    metric_name      = "Requests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 10

    dimension {
      name     = "statusCodeCategory"
      operator = "Include"
      values   = ["5xx"]
    }
  }

  dynamic "action" {
    for_each = local.action_group_ids
    content {
      action_group_id = action.value
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-container-app-5xx-errors-alert"
  })
}

# ---------------------------------------------------------------------------
# PostgreSQL — CPU Alert (>80% for 5 minutes)
# ---------------------------------------------------------------------------

resource "azurerm_monitor_metric_alert" "postgresql_cpu" {
  name                = "${var.project_name}-${var.environment}-postgresql-high-cpu"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_postgresql_flexible_server.main.id]
  description         = "PostgreSQL Flexible Server CPU exceeds 80% for 5 minutes"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "cpu_percent"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  dynamic "action" {
    for_each = local.action_group_ids
    content {
      action_group_id = action.value
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-postgresql-high-cpu-alert"
  })
}

# ---------------------------------------------------------------------------
# PostgreSQL — Active Connections (>80% of max)
# ---------------------------------------------------------------------------

resource "azurerm_monitor_metric_alert" "postgresql_connections" {
  name                = "${var.project_name}-${var.environment}-postgresql-high-connections"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_postgresql_flexible_server.main.id]
  description         = "PostgreSQL Flexible Server active connections exceed 80% of max"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "active_connections"
    aggregation      = "Average"
    operator         = "GreaterThan"
    # GP_Standard_D2s_v3 supports ~859 max connections; 80% ~ 687
    threshold = 687
  }

  dynamic "action" {
    for_each = local.action_group_ids
    content {
      action_group_id = action.value
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-postgresql-high-connections-alert"
  })
}

# ---------------------------------------------------------------------------
# Redis — CPU Alert (>80% for 5 minutes)
# ---------------------------------------------------------------------------

resource "azurerm_monitor_metric_alert" "redis_cpu" {
  name                = "${var.project_name}-${var.environment}-redis-high-cpu"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_redis_cache.main.id]
  description         = "Azure Cache for Redis server load exceeds 80% for 5 minutes"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "Microsoft.Cache/redis"
    metric_name      = "serverLoad"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  dynamic "action" {
    for_each = local.action_group_ids
    content {
      action_group_id = action.value
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-redis-high-cpu-alert"
  })
}

# ---------------------------------------------------------------------------
# Diagnostic Settings — Container App → Log Analytics
# ---------------------------------------------------------------------------

resource "azurerm_monitor_diagnostic_setting" "container_app" {
  name                       = "${var.project_name}-${var.environment}-container-app-diag"
  target_resource_id         = azurerm_container_app.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category = "ContainerAppConsoleLogs"
  }

  enabled_log {
    category = "ContainerAppSystemLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

# ---------------------------------------------------------------------------
# Diagnostic Settings — PostgreSQL → Log Analytics
# ---------------------------------------------------------------------------

resource "azurerm_monitor_diagnostic_setting" "postgresql" {
  name                       = "${var.project_name}-${var.environment}-postgresql-diag"
  target_resource_id         = azurerm_postgresql_flexible_server.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category = "PostgreSQLLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
