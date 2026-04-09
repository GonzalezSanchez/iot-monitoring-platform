output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "aurora_endpoint" {
  description = "Aurora cluster endpoint"
  value       = aws_rds_cluster.aurora.endpoint
}

output "aurora_port" {
  description = "Aurora cluster port"
  value       = aws_rds_cluster.aurora.port
}

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda.arn
}

output "stepfunctions_role_arn" {
  description = "ARN of the Step Functions role"
  value       = aws_iam_role.stepfunctions.arn
}

output "eventbridge_role_arn" {
  description = "ARN of the EventBridge scheduler role"
  value       = aws_iam_role.eventbridge.arn
}

output "db_credentials_secret_arn" {
  description = "ARN of the DB credentials secret"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "lambda_security_group_id" {
  description = "Security group ID for Lambda functions"
  value       = aws_security_group.lambda.id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = [aws_subnet.private_1.id, aws_subnet.private_2.id]
}
