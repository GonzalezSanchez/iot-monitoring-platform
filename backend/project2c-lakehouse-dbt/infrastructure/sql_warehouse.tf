# ─────────────────────────────────────────────
# SQL Warehouse (serverless compute for SQL)
# Required for: Power BI DirectQuery, dbt-databricks, Materialized Views
# Classic Compute (interactive clusters) does NOT work for these use cases
# ─────────────────────────────────────────────

resource "databricks_sql_endpoint" "main" {
  name             = "${var.project}-${var.environment}-warehouse"
  cluster_size     = "2X-Small"
  max_num_clusters = 1

  # Stop automatically after 30 minutes of inactivity to control costs
  auto_stop_mins = 30

  # Serverless: no cluster management, fastest cold start
  enable_serverless_compute = true

  tags {
    custom_tags {
      key   = "project"
      value = var.project
    }
    custom_tags {
      key   = "environment"
      value = var.environment
    }
  }

  depends_on = [databricks_metastore_assignment.main]
}
