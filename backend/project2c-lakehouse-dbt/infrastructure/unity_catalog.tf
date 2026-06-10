# ─────────────────────────────────────────────
# Unity Catalog — metastore
# One metastore per Azure region. If a metastore already exists in the
# account for this region, import it instead of creating a new one:
#   terraform import databricks_metastore.main <metastore-id>
# ─────────────────────────────────────────────

resource "databricks_metastore" "main" {
  provider      = databricks.account
  name          = "${var.project}-${var.environment}-metastore"
  storage_root  = "abfss://metastore@${azurerm_storage_account.adls.name}.dfs.core.windows.net/"
  region        = azurerm_resource_group.main.location
  force_destroy = true
}

resource "databricks_metastore_assignment" "main" {
  provider     = databricks.account
  metastore_id = databricks_metastore.main.id
  workspace_id = azurerm_databricks_workspace.main.workspace_id
}

# ─────────────────────────────────────────────
# Storage credential
# Links the Access Connector Managed Identity to Unity Catalog.
# Unity Catalog uses this credential to read/write Delta tables in ADLS.
# ─────────────────────────────────────────────

resource "databricks_storage_credential" "adls" {
  name = "${var.project}-${var.environment}-storage-credential"

  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.main.id
  }

  comment    = "Managed Identity credential for ADLS Gen2 access — no keys or secrets"
  depends_on = [databricks_metastore_assignment.main]
}

# ─────────────────────────────────────────────
# External location
# Registers the ADLS root path as a governed location inside Unity Catalog.
# All Bronze/Silver/Gold tables are created under this location.
# ─────────────────────────────────────────────

resource "databricks_external_location" "adls_root" {
  name            = "${var.project}-${var.environment}-adls-root"
  url             = "abfss://bronze@${azurerm_storage_account.adls.name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.adls.name
  comment         = "ADLS Gen2 root — Bronze ingestion container"
}

# ─────────────────────────────────────────────
# Catalogs
# One catalog per environment. SQL path: catalog.schema.table
# e.g. p2c_dev.silver.sensor_events
# ─────────────────────────────────────────────

resource "databricks_catalog" "dev" {
  metastore_id = databricks_metastore.main.id
  name         = "p2c_dev"
  comment      = "Development catalog for project 2c"

  storage_root = "abfss://bronze@${azurerm_storage_account.adls.name}.dfs.core.windows.net/catalogs/dev"

  depends_on = [databricks_metastore_assignment.main]
}

resource "databricks_catalog" "prod" {
  metastore_id = databricks_metastore.main.id
  name         = "p2c_prod"
  comment      = "Production catalog for project 2c"

  storage_root = "abfss://bronze@${azurerm_storage_account.adls.name}.dfs.core.windows.net/catalogs/prod"

  depends_on = [databricks_metastore_assignment.main]
}

# ─────────────────────────────────────────────
# Schemas (dev catalog)
# ─────────────────────────────────────────────

resource "databricks_schema" "dev_bronze" {
  catalog_name = databricks_catalog.dev.name
  name         = "bronze"
  comment      = "Raw sensor events — exact as received, no transformations"
}

resource "databricks_schema" "dev_silver" {
  catalog_name = databricks_catalog.dev.name
  name         = "silver"
  comment      = "Cleansed sensor events + quarantine table (WAP pattern)"
}

resource "databricks_schema" "dev_gold" {
  catalog_name = databricks_catalog.dev.name
  name         = "gold"
  comment      = "dbt fact + dim models served via SQL Warehouse"
}

# ─────────────────────────────────────────────
# Schemas (prod catalog)
# ─────────────────────────────────────────────

resource "databricks_schema" "prod_bronze" {
  catalog_name = databricks_catalog.prod.name
  name         = "bronze"
  comment      = "Raw sensor events — exact as received, no transformations"
}

resource "databricks_schema" "prod_silver" {
  catalog_name = databricks_catalog.prod.name
  name         = "silver"
  comment      = "Cleansed sensor events + quarantine table (WAP pattern)"
}

resource "databricks_schema" "prod_gold" {
  catalog_name = databricks_catalog.prod.name
  name         = "gold"
  comment      = "dbt fact + dim models served via SQL Warehouse"
}
