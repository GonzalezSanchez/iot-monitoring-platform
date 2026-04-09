# Aurora Serverless v2 cluster
# Auto-pauses after 5 minutes of inactivity (MinCapacity: 0.5 → scales to zero)
# Cold start on wake-up: ~5 seconds — acceptable for a scheduled batch pipeline
resource "aws_rds_cluster" "aurora" {
  cluster_identifier          = "p2a-${var.environment}-aurora"
  engine                      = "aurora-postgresql"
  engine_version              = "15.10"
  database_name               = var.db_name
  master_username             = var.db_username
  manage_master_user_password = true # AWS manages password in Secrets Manager

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 2
  }

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  storage_encrypted   = true
  deletion_protection = var.environment == "prod"
  skip_final_snapshot = true

  tags = {
    Name        = "p2a-${var.environment}-aurora"
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_rds_cluster_instance" "aurora" {
  identifier          = "p2a-${var.environment}-aurora-instance"
  cluster_identifier  = aws_rds_cluster.aurora.id
  instance_class      = "db.serverless"
  engine              = aws_rds_cluster.aurora.engine
  engine_version      = aws_rds_cluster.aurora.engine_version
  publicly_accessible = false

  tags = {
    Name = "p2a-${var.environment}-aurora-instance"
  }
}
