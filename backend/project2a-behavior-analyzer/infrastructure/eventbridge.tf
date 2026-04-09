# EventBridge scheduled rule — triggers the ETL pipeline every Sunday at 02:00 UTC.
# Input: { "days_back": 7 } → Extract Lambda computes the window automatically.

resource "aws_cloudwatch_event_rule" "weekly_etl" {
  name                = "p2a-${var.environment}-weekly-etl"
  description         = "Run the p2a ETL pipeline weekly (last 7 days of sensor data)"
  schedule_expression = "cron(0 2 ? * SUN *)"
  state               = "ENABLED"

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "sfn_target" {
  rule     = aws_cloudwatch_event_rule.weekly_etl.name
  arn      = aws_sfn_state_machine.etl_pipeline.arn
  role_arn = aws_iam_role.eventbridge.arn

  input = jsonencode({
    days_back = 7
  })
}
