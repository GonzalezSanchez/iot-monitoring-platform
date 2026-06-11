# ─────────────────────────────────────────────
# Unity Catalog — metastore (Azure-managed, niet aangemaakt door Terraform)
#
# Azure maakt automatisch één regionale metastore aan bij elke nieuwe
# Unity Catalog workspace. Er is precies één metastore per regio,
# gedeeld over alle workspaces in het account.
#
# Terraform-principe: beheer alleen wat je zelf aanmaakt.
# data source = "ik gebruik dit" / resource = "ik maak dit aan"
#
# Alternatief (verkeerd): databricks_metastore resource aanmaken
# → faalt: metastore bestaat al voor westeurope
# → vereist account-level provider (accounts.azuredatabricks.net)
# → accounts.azuredatabricks.net vereist organisatieaccount, niet personal Microsoft account
# ─────────────────────────────────────────────

data "databricks_current_metastore" "main" {}

# ─────────────────────────────────────────────
# Storage credential
# Links de Access Connector Managed Identity aan Unity Catalog.
# Unity Catalog gebruikt deze credential voor lezen/schrijven in ADLS.
# Geen keys of secrets — Managed Identity is best practice.
# ─────────────────────────────────────────────

resource "databricks_storage_credential" "adls" {
  name = "${var.project}-${var.environment}-storage-credential"

  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.main.id
  }

  comment = "Managed Identity credential for ADLS Gen2 access — no keys or secrets"
}

# ─────────────────────────────────────────────
# External locations
#
# Twee aparte locaties zijn verplicht:
# 1. bronze — exclusief voor raw JSON ingestion (cloudFiles source path)
# 2. metastore — exclusief voor catalog managed storage
#
# Ze mogen NIET overlappen: Unity Catalog gooit LOCATION_OVERLAP als
# cloudFiles source path en catalog storage_root in dezelfde container zitten.
# ─────────────────────────────────────────────

resource "databricks_external_location" "adls_bronze" {
  name            = "${var.project}-${var.environment}-bronze"
  url             = "abfss://bronze@${azurerm_storage_account.adls.name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.adls.name
  comment         = "Bronze container — raw JSON ingestion only, never used for managed catalog storage"
}

resource "databricks_external_location" "adls_metastore" {
  name            = "${var.project}-${var.environment}-metastore"
  url             = "abfss://metastore@${azurerm_storage_account.adls.name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.adls.name
  comment         = "Metastore container — catalog managed storage only, never used for raw data"
}

# ─────────────────────────────────────────────
# Catalogs
# Één catalog per environment. SQL pad: catalog.schema.table
# bv. p2c_dev.silver.sensor_events
# ─────────────────────────────────────────────

resource "databricks_catalog" "dev" {
  metastore_id = data.databricks_current_metastore.main.id
  name         = "p2c_dev"
  comment      = "Development catalog for project 2c"
  force_destroy = true

  # Metastore container — gescheiden van bronze om LOCATION_OVERLAP te voorkomen
  storage_root = "abfss://metastore@${azurerm_storage_account.adls.name}.dfs.core.windows.net/catalogs/dev"
  depends_on   = [databricks_external_location.adls_metastore]
}

resource "databricks_catalog" "prod" {
  metastore_id = data.databricks_current_metastore.main.id
  name         = "p2c_prod"
  comment      = "Production catalog for project 2c"
  force_destroy = true

  storage_root = "abfss://metastore@${azurerm_storage_account.adls.name}.dfs.core.windows.net/catalogs/prod"
  depends_on   = [databricks_external_location.adls_metastore]
}

# ─────────────────────────────────────────────
# Schemas (dev catalog)
# ─────────────────────────────────────────────

resource "databricks_schema" "dev_bronze" {
  catalog_name  = databricks_catalog.dev.name
  name          = "bronze"
  comment       = "Raw sensor events — exact as received, no transformations"
  force_destroy = true
}

resource "databricks_schema" "dev_silver" {
  catalog_name  = databricks_catalog.dev.name
  name          = "silver"
  comment       = "Cleansed sensor events + quarantine table (WAP pattern)"
  force_destroy = true
}

resource "databricks_schema" "dev_gold" {
  catalog_name  = databricks_catalog.dev.name
  name          = "gold"
  comment       = "dbt fact + dim models served via SQL Warehouse"
  force_destroy = true
}

# ─────────────────────────────────────────────
# Schemas (prod catalog)
# ─────────────────────────────────────────────

resource "databricks_schema" "prod_bronze" {
  catalog_name  = databricks_catalog.prod.name
  name          = "bronze"
  comment       = "Raw sensor events — exact as received, no transformations"
  force_destroy = true
}

resource "databricks_schema" "prod_silver" {
  catalog_name  = databricks_catalog.prod.name
  name          = "silver"
  comment       = "Cleansed sensor events + quarantine table (WAP pattern)"
  force_destroy = true
}

resource "databricks_schema" "prod_gold" {
  catalog_name  = databricks_catalog.prod.name
  name          = "gold"
  comment       = "dbt fact + dim models served via SQL Warehouse"
  force_destroy = true
}
