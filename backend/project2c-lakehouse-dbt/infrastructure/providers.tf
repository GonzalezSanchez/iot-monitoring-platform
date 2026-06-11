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

# Workspace-level provider — all Databricks resources
# Authentication: Azure CLI (az login)
# Azure auto-creates and assigns the Unity Catalog metastore for new workspaces,
# so the account-level provider (accounts.azuredatabricks.net) is not needed.
provider "databricks" {
  host = var.databricks_host
}
