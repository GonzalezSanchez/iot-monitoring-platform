# IAM user for Airflow worker running outside AWS (Docker Compose on acer-server)
resource "aws_iam_user" "airflow_worker" {
  name = "p2b-${var.environment}-airflow-worker"

  tags = {
    Project     = "p2b-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_iam_access_key" "airflow_worker" {
  user = aws_iam_user.airflow_worker.name
}

resource "aws_iam_user_policy" "s3_access" {
  name = "S3SensorEventsAccess"
  user = aws_iam_user.airflow_worker.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ]
      Resource = [
        aws_s3_bucket.sensor_events.arn,
        "${aws_s3_bucket.sensor_events.arn}/*"
      ]
    }]
  })
}

resource "aws_iam_user_policy" "dynamodb_read" {
  name = "DynamoDBReadSource"
  user = aws_iam_user.airflow_worker.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:Query", "dynamodb:Scan", "dynamodb:GetItem"]
      Resource = var.source_dynamodb_table_arn
    }]
  })
}
