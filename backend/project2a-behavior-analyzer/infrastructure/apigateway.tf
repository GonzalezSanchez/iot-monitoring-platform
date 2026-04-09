# API Gateway v2 (HTTP API) — project 2a Behavior Pattern Analyzer
#
# Routes:
#   POST /analyze/patterns                      → post_analyze Lambda
#   GET  /analyze/patterns/{job_id}             → get_patterns Lambda
#   GET  /insights/{entity_type}/{entity_id}    → get_insights Lambda

resource "aws_apigatewayv2_api" "main" {
  name          = "p2a-${var.environment}-api"
  protocol_type = "HTTP"

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

# ──────────────────────────────────────────────────────────────────────────────
# Stage
# ──────────────────────────────────────────────────────────────────────────────

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

# ──────────────────────────────────────────────────────────────────────────────
# Integrations
# ──────────────────────────────────────────────────────────────────────────────

resource "aws_apigatewayv2_integration" "post_analyze" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.post_analyze.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "get_patterns" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.get_patterns.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "get_insights" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.get_insights.invoke_arn
  payload_format_version = "2.0"
}

# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

resource "aws_apigatewayv2_route" "post_analyze" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /analyze/patterns"
  target    = "integrations/${aws_apigatewayv2_integration.post_analyze.id}"
}

resource "aws_apigatewayv2_route" "get_patterns" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /analyze/patterns/{job_id}"
  target    = "integrations/${aws_apigatewayv2_integration.get_patterns.id}"
}

resource "aws_apigatewayv2_route" "get_insights" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /insights/{entity_type}/{entity_id}"
  target    = "integrations/${aws_apigatewayv2_integration.get_insights.id}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Lambda permissions — allow API Gateway to invoke each function
# ──────────────────────────────────────────────────────────────────────────────

resource "aws_lambda_permission" "apigw_post_analyze" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.post_analyze.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_get_patterns" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.get_patterns.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_get_insights" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.get_insights.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
