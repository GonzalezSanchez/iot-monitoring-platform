variable "resource_group_name" {
  type        = string
  description = "Azure resource group (pre-created; imported into Terraform state)"
}

variable "location" {
  type        = string
  default     = "westeurope"
  description = "Azure region for all resources"
}

variable "project" {
  type        = string
  default     = "p2c"
  description = "Short project prefix used in resource names"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Deployment environment: dev or prod"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod"
  }
}

# Storage account names are globally unique (3-24 chars, lowercase alphanumeric only)
variable "storage_account_name" {
  type        = string
  description = "Globally unique name for the ADLS Gen2 storage account (max 24 chars, lowercase alphanumeric)"
}

variable "key_vault_name" {
  type        = string
  description = "Globally unique name for the Azure Key Vault (3-24 chars)"
}

variable "databricks_host" {
  type        = string
  description = "Databricks workspace URL (https://adb-<id>.azuredatabricks.net) — available after workspace creation"
  default     = ""
}

variable "databricks_account_id" {
  type        = string
  description = "Databricks account ID (from accounts.azuredatabricks.net)"
}

variable "budget_alert_amount" {
  type        = number
  default     = 150
  description = "Monthly budget alert threshold in USD"
}

variable "alert_email" {
  type        = string
  description = "Email address for budget and job failure alerts"
}
