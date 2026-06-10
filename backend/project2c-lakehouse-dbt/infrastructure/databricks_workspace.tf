# ─────────────────────────────────────────────
# Databricks workspace
# ─────────────────────────────────────────────

resource "azurerm_databricks_workspace" "main" {
  name                = "${var.project}-${var.environment}-workspace"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  # premium is required for Unity Catalog; standard does not support it
  sku = "premium"

  custom_parameters {
    no_public_ip = true
  }

  tags = {
    project     = var.project
    environment = var.environment
  }
}

# ─────────────────────────────────────────────
# Databricks Access Connector
# The connector exposes a System-Assigned Managed Identity that
# Azure RBAC role assignments attach to. This replaces service
# principal credentials and storage account keys entirely.
# ─────────────────────────────────────────────

resource "azurerm_databricks_access_connector" "main" {
  name                = "${var.project}-${var.environment}-access-connector"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  identity {
    type = "SystemAssigned"
  }

  tags = {
    project     = var.project
    environment = var.environment
  }
}
