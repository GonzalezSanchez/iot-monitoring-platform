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

output "api_gateway_url" {
  description = "Base URL of the HTTP API Gateway"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = [aws_subnet.private_1.id, aws_subnet.private_2.id]
}

output "etl_state_machine_arn" {
  description = "ARN of the ETL Step Functions state machine"
  value       = aws_sfn_state_machine.etl_pipeline.arn
}

output "extract_lambda_arn" {
  description = "ARN of the Extract Lambda function"
  value       = aws_lambda_function.extract.arn
}

output "transform_lambda_arn" {
  description = "ARN of the Transform Lambda function"
  value       = aws_lambda_function.transform.arn
}

output "analyze_lambda_arn" {
  description = "ARN of the Analyze Lambda function"
  value       = aws_lambda_function.analyze.arn
}
