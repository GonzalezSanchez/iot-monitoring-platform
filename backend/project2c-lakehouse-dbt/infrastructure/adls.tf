# ─────────────────────────────────────────────
# ADLS Gen2 — storage account + containers
# ─────────────────────────────────────────────

resource "azurerm_storage_account" "adls" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  # is_hns_enabled = true makes this ADLS Gen2:
  # required for Delta Lake, directory-level ACLs, and the Unity Catalog external location
  is_hns_enabled = true

  blob_properties {
    delete_retention_policy {
      days = 7
    }
  }

  tags = {
    project     = var.project
    environment = var.environment
  }
}

# Metastore root storage — Unity Catalog writes its own metadata here
resource "azurerm_storage_container" "metastore" {
  name                  = "metastore"
  storage_account_id = azurerm_storage_account.adls.id
  container_access_type = "private"
}

# Bronze — raw JSON from the sensor generator, written by Auto Loader
resource "azurerm_storage_container" "bronze" {
  name                  = "bronze"
  storage_account_id = azurerm_storage_account.adls.id
  container_access_type = "private"
}

# Silver — cleansed Delta tables; quarantine table lives here too
resource "azurerm_storage_container" "silver" {
  name                  = "silver"
  storage_account_id = azurerm_storage_account.adls.id
  container_access_type = "private"
}

# Gold — dbt-built fact + dim tables, served via SQL Warehouse to Power BI
resource "azurerm_storage_container" "gold" {
  name                  = "gold"
  storage_account_id = azurerm_storage_account.adls.id
  container_access_type = "private"
}

# ─────────────────────────────────────────────
# IAM — Access Connector → Storage Blob Data Contributor
# Best practice: Managed Identity, no keys or secrets for ADLS access
# ─────────────────────────────────────────────

resource "azurerm_role_assignment" "adls_contributor" {
  scope                = azurerm_storage_account.adls.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.main.identity[0].principal_id
}
