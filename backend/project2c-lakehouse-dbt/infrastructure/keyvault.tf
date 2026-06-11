# ─────────────────────────────────────────────
# Azure Key Vault
# RBAC authorization model (not access policies) — modern, least-privilege
# ─────────────────────────────────────────────

resource "azurerm_key_vault" "main" {
  name                       = var.key_vault_name
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 7
  purge_protection_enabled   = false

  tags = {
    project     = var.project
    environment = var.environment
  }
}

# ─────────────────────────────────────────────
# IAM — own account: create and update secrets during setup
# ─────────────────────────────────────────────

resource "azurerm_role_assignment" "kv_secrets_officer" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# ─────────────────────────────────────────────
# IAM — Access Connector: read secrets from Databricks notebooks
# Separate role from above — least-privilege: read-only, no create/delete
# ─────────────────────────────────────────────

resource "azurerm_role_assignment" "kv_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_databricks_access_connector.main.identity[0].principal_id
}

# ─────────────────────────────────────────────
# Placeholder secrets — values set after workspace provisioning
# Access in notebooks: dbutils.secrets.get(scope="p2c-kv", key="<name>")
# ─────────────────────────────────────────────

resource "azurerm_key_vault_secret" "storage_account_name" {
  name         = "adls-storage-account-name"
  value        = azurerm_storage_account.adls.name
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "storage_account_key" {
  name         = "adls-storage-account-key"
  value        = azurerm_storage_account.adls.primary_access_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.kv_secrets_officer]
}

# ─────────────────────────────────────────────
# Databricks secret scope backed by Key Vault
# Key Vault-backed scope: Databricks never stores secrets itself;
# all reads go through Key Vault RBAC
# ─────────────────────────────────────────────

resource "databricks_secret_scope" "kv" {
  name = "p2c-kv"

  keyvault_metadata {
    resource_id = azurerm_key_vault.main.id
    dns_name    = azurerm_key_vault.main.vault_uri
  }

  depends_on = [azurerm_databricks_workspace.main]
}
