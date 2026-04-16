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

data "archive_file" "migrate" {
  type        = "zip"
  source_dir  = "${path.module}/../dist/staging/migrate"
  output_path = "${path.module}/../dist/migrate.zip"
}

data "archive_file" "post_analyze" {
  type        = "zip"
  source_dir  = "${path.module}/../dist/staging/post_analyze"
  output_path = "${path.module}/../dist/post_analyze.zip"
}

data "archive_file" "get_patterns" {
  type        = "zip"
  source_dir  = "${path.module}/../dist/staging/get_patterns"
  output_path = "${path.module}/../dist/get_patterns.zip"
}

data "archive_file" "get_insights" {
  type        = "zip"
  source_dir  = "${path.module}/../dist/staging/get_insights"
  output_path = "${path.module}/../dist/get_insights.zip"
}

# Lambda layer: psycopg2-binary + python-dotenv compiled for Amazon Linux 2
resource "aws_lambda_layer_version" "python_deps" {
  filename            = "${path.module}/../dist/dependencies-layer.zip"
  layer_name          = "p2a-${var.environment}-python-deps"
  compatible_runtimes = ["python3.11"]
  source_code_hash    = try(filebase64sha256("${path.module}/../dist/dependencies-layer.zip"), null)
}

locals {
  lambda_env = {
    SECRETS_MANAGER_SECRET_NAME = aws_secretsmanager_secret.db_credentials.name
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

resource "aws_lambda_function" "migrate" {
  function_name    = "p2a-${var.environment}-migrate"
  filename         = data.archive_file.migrate.output_path
  source_code_hash = data.archive_file.migrate.output_base64sha256
  handler          = "handler.handler"
  runtime          = "python3.11"
  role             = aws_iam_role.lambda.arn
  timeout          = 60
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

# ──────────────────────────────────────────────────────────────────────────────
# API Lambdas
# ──────────────────────────────────────────────────────────────────────────────

locals {
  api_lambda_env = merge(local.lambda_env, {
    STATE_MACHINE_ARN = aws_sfn_state_machine.etl_pipeline.arn
  })
}

resource "aws_lambda_function" "post_analyze" {
  function_name    = "p2a-${var.environment}-post-analyze"
  filename         = data.archive_file.post_analyze.output_path
  source_code_hash = data.archive_file.post_analyze.output_base64sha256
  handler          = "post_analyze.handler"
  runtime          = "python3.11"
  role             = aws_iam_role.lambda.arn
  timeout          = 30
  memory_size      = 256

  layers = [aws_lambda_layer_version.python_deps.arn]

  environment {
    variables = local.api_lambda_env
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

resource "aws_lambda_function" "get_patterns" {
  function_name    = "p2a-${var.environment}-get-patterns"
  filename         = data.archive_file.get_patterns.output_path
  source_code_hash = data.archive_file.get_patterns.output_base64sha256
  handler          = "get_patterns.handler"
  runtime          = "python3.11"
  role             = aws_iam_role.lambda.arn
  timeout          = 30
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

resource "aws_lambda_function" "get_insights" {
  function_name    = "p2a-${var.environment}-get-insights"
  filename         = data.archive_file.get_insights.output_path
  source_code_hash = data.archive_file.get_insights.output_base64sha256
  handler          = "get_insights.handler"
  runtime          = "python3.11"
  role             = aws_iam_role.lambda.arn
  timeout          = 30
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
