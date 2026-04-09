# Lambda deployment packages — built by scripts/build.sh before terraform apply
# Terraform's archive_file zips the staged source directories automatically.

data "archive_file" "extract" {
  type        = "zip"
  source_dir  = "${path.module}/../dist/staging/extract"
  output_path = "${path.module}/../dist/extract.zip"
}

data "archive_file" "transform" {
  type        = "zip"
  source_dir  = "${path.module}/../dist/staging/transform"
  output_path = "${path.module}/../dist/transform.zip"
}

data "archive_file" "analyze" {
  type        = "zip"
  source_dir  = "${path.module}/../dist/staging/analyze"
  output_path = "${path.module}/../dist/analyze.zip"
}

# Lambda layer: psycopg2-binary + python-dotenv compiled for Amazon Linux 2
resource "aws_lambda_layer_version" "python_deps" {
  filename            = "${path.module}/../dist/dependencies-layer.zip"
  layer_name          = "p2a-${var.environment}-python-deps"
  compatible_runtimes = ["python3.11"]
  source_code_hash    = filebase64sha256("${path.module}/../dist/dependencies-layer.zip")
}

locals {
  lambda_env = {
    SECRETS_MANAGER_SECRET_NAME = aws_secretsmanager_secret.db_credentials.name
    AWS_REGION                  = var.region
    LOG_LEVEL                   = "INFO"
    DYNAMODB_TABLE_EVENTS       = var.source_dynamodb_table_name
  }
}

resource "aws_lambda_function" "extract" {
  function_name    = "p2a-${var.environment}-extract"
  filename         = data.archive_file.extract.output_path
  source_code_hash = data.archive_file.extract.output_base64sha256
  handler          = "handler.handler"
  runtime          = "python3.11"
  role             = aws_iam_role.lambda.arn
  timeout          = 300 # DynamoDB scans can be large
  memory_size      = 256

  layers = [aws_lambda_layer_version.python_deps.arn]

  environment {
    variables = local.lambda_env
  }

  vpc_config {
    subnet_ids         = [aws_subnet.private_1.id, aws_subnet.private_2.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_lambda_function" "transform" {
  function_name    = "p2a-${var.environment}-transform"
  filename         = data.archive_file.transform.output_path
  source_code_hash = data.archive_file.transform.output_base64sha256
  handler          = "handler.handler"
  runtime          = "python3.11"
  role             = aws_iam_role.lambda.arn
  timeout          = 300
  memory_size      = 256

  layers = [aws_lambda_layer_version.python_deps.arn]

  environment {
    variables = local.lambda_env
  }

  vpc_config {
    subnet_ids         = [aws_subnet.private_1.id, aws_subnet.private_2.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_lambda_function" "analyze" {
  function_name    = "p2a-${var.environment}-analyze"
  filename         = data.archive_file.analyze.output_path
  source_code_hash = data.archive_file.analyze.output_base64sha256
  handler          = "handler.handler"
  runtime          = "python3.11"
  role             = aws_iam_role.lambda.arn
  timeout          = 300
  memory_size      = 256

  layers = [aws_lambda_layer_version.python_deps.arn]

  environment {
    variables = local.lambda_env
  }

  vpc_config {
    subnet_ids         = [aws_subnet.private_1.id, aws_subnet.private_2.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}
