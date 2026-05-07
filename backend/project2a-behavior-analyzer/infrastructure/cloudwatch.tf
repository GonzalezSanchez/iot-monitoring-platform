resource "aws_cloudwatch_log_group" "lambda_extract" {
  name              = "/aws/lambda/p2a-${var.environment}-extract"
  retention_in_days = 7

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "lambda_transform" {
  name              = "/aws/lambda/p2a-${var.environment}-transform"
  retention_in_days = 7

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "lambda_analyze" {
  name              = "/aws/lambda/p2a-${var.environment}-analyze"
  retention_in_days = 7

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "lambda_migrate" {
  name              = "/aws/lambda/p2a-${var.environment}-migrate"
  retention_in_days = 7

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "lambda_post_analyze" {
  name              = "/aws/lambda/p2a-${var.environment}-post-analyze"
  retention_in_days = 7

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "lambda_get_patterns" {
  name              = "/aws/lambda/p2a-${var.environment}-get-patterns"
  retention_in_days = 7

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "lambda_get_insights" {
  name              = "/aws/lambda/p2a-${var.environment}-get-insights"
  retention_in_days = 7

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}
