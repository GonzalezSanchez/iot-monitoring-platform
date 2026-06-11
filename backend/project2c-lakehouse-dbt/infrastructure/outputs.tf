output "adls_storage_account_name" {
  value       = azurerm_storage_account.adls.name
  description = "ADLS Gen2 storage account name — used in .env AZURE_STORAGE_ACCOUNT_NAME"
}

output "databricks_workspace_url" {
  value       = azurerm_databricks_workspace.main.workspace_url
  description = "Databricks workspace URL — used in .env DATABRICKS_HOST"
}

output "sql_warehouse_http_path" {
  value       = "/sql/1.0/warehouses/${databricks_sql_endpoint.main.id}"
  description = "SQL Warehouse HTTP path — used in .env DATABRICKS_HTTP_PATH and dbt profiles.yml"
  sensitive   = false
}

output "key_vault_uri" {
  value       = azurerm_key_vault.main.vault_uri
  description = "Azure Key Vault URI — used when creating the Databricks secret scope"
}
