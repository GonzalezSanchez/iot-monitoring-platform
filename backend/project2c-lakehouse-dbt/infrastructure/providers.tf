terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.52"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }
}

# Workspace-level provider — SQL Warehouse, secret scope, Unity Catalog schemas
# Authentication: Azure CLI (az login) or DATABRICKS_TOKEN environment variable
provider "databricks" {
  host = var.databricks_host
}

# Account-level provider — metastore creation and metastore assignment
# Separate from the workspace provider: host is always accounts.azuredatabricks.net
provider "databricks" {
  alias      = "account"
  host       = "https://accounts.azuredatabricks.net"
  account_id = var.databricks_account_id
}
