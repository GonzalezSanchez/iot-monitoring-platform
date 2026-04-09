# Lambda execution role
resource "aws_iam_role" "lambda" {
  name = "p2a-${var.environment}-LambdaExecutionRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_access" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "DynamoDBReadSource"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:Query", "dynamodb:Scan", "dynamodb:GetItem"]
      Resource = var.source_dynamodb_table_arn
    }]
  })
}

resource "aws_iam_role_policy" "lambda_secrets" {
  name = "SecretsManagerReadDB"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.region}:*:secret:p2a-${var.environment}-db-credentials*"
      },
      {
        # Aurora manages its own secret for the master password
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_rds_cluster.aurora.master_user_secret[0].secret_arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_stepfunctions" {
  name = "StepFunctionsDescribe"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["states:DescribeExecution", "states:StartExecution"]
      Resource = "arn:aws:states:${var.region}:*:stateMachine:p2a-${var.environment}-etl-pipeline"
    }]
  })
}

# Step Functions role — invokes Lambda functions
resource "aws_iam_role" "stepfunctions" {
  name = "p2a-${var.environment}-StepFunctionsRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "stepfunctions_invoke_lambda" {
  name = "InvokeLambdas"
  role = aws_iam_role.stepfunctions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = "arn:aws:lambda:${var.region}:*:function:p2a-${var.environment}-*"
    }]
  })
}

# EventBridge Scheduler role — starts Step Functions state machine
resource "aws_iam_role" "eventbridge" {
  name = "p2a-${var.environment}-EventBridgeRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_start_sfn" {
  name = "StartStepFunctions"
  role = aws_iam_role.eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "states:StartExecution"
      Resource = "arn:aws:states:${var.region}:*:stateMachine:p2a-${var.environment}-etl-pipeline"
    }]
  })
}
