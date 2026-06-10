# ─────────────────────────────────────────────
# Azure Budget alert
# Alerts at 80% and 100% of the monthly threshold.
# Databricks + ADLS costs are unpredictable during development — alert early.
# ─────────────────────────────────────────────

resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "${var.project}-${var.environment}-budget"
  resource_group_id = data.azurerm_resource_group.main.id

  amount     = var.budget_alert_amount
  time_grain = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"

    contact_emails = [var.alert_email]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Actual"

    contact_emails = [var.alert_email]
  }

  lifecycle {
    # start_date uses timestamp() which changes on every plan; ignore to prevent drift
    ignore_changes = [time_period]
  }
}
