# DB credentials secret for ETL Lambda functions
# Aurora endpoint is wired in automatically — no manual update needed after deploy
# The master password is managed by Aurora (manage_master_user_password = true)
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "p2a-${var.environment}-db-credentials"
  description = "Aurora PostgreSQL connection details for project 2a ETL lambdas"

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id

  secret_string = jsonencode({
    host              = aws_rds_cluster.aurora.endpoint
    port              = 5432
    dbname            = var.db_name
    username          = var.db_username
    # Password is managed by Aurora — retrieve from master_secret_arn below
    master_secret_arn = aws_rds_cluster.aurora.master_user_secret[0].secret_arn
  })
}
