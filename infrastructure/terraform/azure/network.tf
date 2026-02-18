###############################################################################
# ShieldOps — Virtual Network & Networking
###############################################################################

locals {
  subnets = {
    container-apps = "10.1.0.0/23"
    database       = "10.1.2.0/24"
    redis          = "10.1.3.0/24"
    default        = "10.1.4.0/24"
  }
}

# ---------------------------------------------------------------------------
# Virtual Network
# ---------------------------------------------------------------------------

resource "azurerm_virtual_network" "main" {
  name                = "${var.project_name}-${var.environment}-vnet"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = ["10.1.0.0/16"]

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-vnet"
  })
}

# ---------------------------------------------------------------------------
# Subnets
# ---------------------------------------------------------------------------

resource "azurerm_subnet" "container_apps" {
  name                 = "${var.project_name}-${var.environment}-container-apps-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [local.subnets["container-apps"]]

  delegation {
    name = "container-apps-delegation"

    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_subnet" "database" {
  name                 = "${var.project_name}-${var.environment}-database-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [local.subnets["database"]]

  delegation {
    name = "postgresql-delegation"

    service_delegation {
      name    = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_subnet" "redis" {
  name                 = "${var.project_name}-${var.environment}-redis-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [local.subnets["redis"]]
}

resource "azurerm_subnet" "default" {
  name                 = "${var.project_name}-${var.environment}-default-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [local.subnets["default"]]
}

# ---------------------------------------------------------------------------
# NAT Gateway (single — cost optimization)
# ---------------------------------------------------------------------------

resource "azurerm_public_ip" "nat" {
  name                = "${var.project_name}-${var.environment}-nat-pip"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-nat-pip"
  })
}

resource "azurerm_nat_gateway" "main" {
  name                = "${var.project_name}-${var.environment}-nat"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = "Standard"

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-nat"
  })
}

resource "azurerm_nat_gateway_public_ip_association" "main" {
  nat_gateway_id       = azurerm_nat_gateway.main.id
  public_ip_address_id = azurerm_public_ip.nat.id
}

resource "azurerm_subnet_nat_gateway_association" "container_apps" {
  subnet_id      = azurerm_subnet.container_apps.id
  nat_gateway_id = azurerm_nat_gateway.main.id
}

resource "azurerm_subnet_nat_gateway_association" "default" {
  subnet_id      = azurerm_subnet.default.id
  nat_gateway_id = azurerm_nat_gateway.main.id
}

# ---------------------------------------------------------------------------
# Network Security Group — Container Apps
# ---------------------------------------------------------------------------

resource "azurerm_network_security_group" "container_apps" {
  name                = "${var.project_name}-${var.environment}-container-apps-nsg"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "AllowHTTPSInbound"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "AllowOutboundToVNet"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "VirtualNetwork"
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-container-apps-nsg"
  })
}

resource "azurerm_subnet_network_security_group_association" "container_apps" {
  subnet_id                 = azurerm_subnet.container_apps.id
  network_security_group_id = azurerm_network_security_group.container_apps.id
}

# ---------------------------------------------------------------------------
# Network Security Group — Database
# ---------------------------------------------------------------------------

resource "azurerm_network_security_group" "database" {
  name                = "${var.project_name}-${var.environment}-database-nsg"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "AllowPostgreSQLFromContainerApps"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "5432"
    source_address_prefix      = local.subnets["container-apps"]
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "DenyAllInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-database-nsg"
  })
}

resource "azurerm_subnet_network_security_group_association" "database" {
  subnet_id                 = azurerm_subnet.database.id
  network_security_group_id = azurerm_network_security_group.database.id
}

# ---------------------------------------------------------------------------
# Network Security Group — Redis
# ---------------------------------------------------------------------------

resource "azurerm_network_security_group" "redis" {
  name                = "${var.project_name}-${var.environment}-redis-nsg"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "AllowRedisSSLFromContainerApps"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "6380"
    source_address_prefix      = local.subnets["container-apps"]
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "DenyAllInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-redis-nsg"
  })
}

resource "azurerm_subnet_network_security_group_association" "redis" {
  subnet_id                 = azurerm_subnet.redis.id
  network_security_group_id = azurerm_network_security_group.redis.id
}
