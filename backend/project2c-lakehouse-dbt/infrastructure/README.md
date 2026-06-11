# Infrastructure — Project 2c

Terraform IaC for the Azure Databricks Lakehouse. Manages all resources: resource group, ADLS Gen2, Databricks workspace, Access Connector, Key Vault, Unity Catalog, SQL Warehouse, and budget alert.

## Prerequisites

- Terraform >= 1.9.0
- Azure CLI (`az login` with an active subscription)
- `terraform.tfvars` filled in (copy from `terraform.tfvars.example`)

## Deploy

Two steps are required because the Databricks workspace URL is only known after the workspace is created, and the remaining Databricks resources (Unity Catalog, SQL Warehouse) need that URL.

```bash
cd infrastructure

# Step 1 — always run on first use or after changes to providers.tf
terraform init

# Step 2 — create workspace first (chicken-and-egg)
terraform apply -target=azurerm_databricks_workspace.main -auto-approve

# Step 3 — copy workspace URL from output into terraform.tfvars
# databricks_host = "https://<output-url>"

# Step 4 — create all remaining resources
terraform apply -auto-approve
```

After deploy, copy the outputs into `.env`:
- `databricks_workspace_url` → `DATABRICKS_HOST`
- `sql_warehouse_http_path` → `DATABRICKS_HTTP_PATH`

> **Note**: `no_public_ip = false` is set deliberately to avoid the NAT Gateway cost (~€1/day). In production use `true` (Secure Cluster Connectivity).

## Destroy

```bash
cd infrastructure

terraform destroy -auto-approve
```

If destroy fails with "Schema is not empty" or "External location has dependent tables", the Unity Catalog metadata must be cleaned up via the REST API first:

```bash
# Get a token
TOKEN=$(az account get-access-token --resource 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d --query accessToken -o tsv)
HOST="https://<workspace-url>"  # from terraform.tfvars

# Delete tables
curl -X DELETE -H "Authorization: Bearer $TOKEN" "$HOST/api/2.1/unity-catalog/tables/p2c_dev.bronze.sensor_events"
curl -X DELETE -H "Authorization: Bearer $TOKEN" "$HOST/api/2.1/unity-catalog/tables/p2c_dev.silver.sensor_events"
curl -X DELETE -H "Authorization: Bearer $TOKEN" "$HOST/api/2.1/unity-catalog/tables/p2c_dev.silver.sensor_events_quarantine"

# Force-delete external location (if "has dependent managed tables")
curl -X DELETE -H "Authorization: Bearer $TOKEN" "$HOST/api/2.1/unity-catalog/external-locations/p2c-dev-metastore?force=true"

# Force-delete storage credential
curl -X DELETE -H "Authorization: Bearer $TOKEN" "$HOST/api/2.1/unity-catalog/storage-credentials/p2c-dev-storage-credential?force=true"

# Remove orphaned resources from Terraform state
terraform state rm databricks_storage_credential.adls
terraform state rm databricks_external_location.adls_metastore

# Then destroy remaining Azure resources
terraform destroy -auto-approve
```

## Resources created

| Resource | Type | Notes |
|---|---|---|
| `rg-p2c-iot` | Resource group | All resources live here |
| `stp2cdeviotags` | ADLS Gen2 | Containers: bronze, silver, gold, metastore |
| `p2c-dev-workspace` | Databricks workspace | Premium SKU (required for Unity Catalog) |
| `p2c-dev-access-connector` | Access Connector | Managed Identity — no keys needed |
| `kv-p2c-dev-ags` | Key Vault | Stores storage account name + key |
| `p2c-dev-storage-credential` | UC storage credential | Links Access Connector to Unity Catalog |
| `p2c-dev-bronze` / `p2c-dev-metastore` | UC external locations | Separate containers to avoid LOCATION_OVERLAP |
| `p2c_dev` / `p2c_prod` | UC catalogs | Schemas: bronze, silver, gold |
| `p2c-dev-warehouse` | SQL Warehouse | 2X-Small serverless, auto-stop 30 min |

> Azure also creates a managed resource group `databricks-rg-rg-p2c-iot` automatically — this is controlled by Azure, not Terraform.
