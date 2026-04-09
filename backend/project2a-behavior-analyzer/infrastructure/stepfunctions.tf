# ETL pipeline state machine: Extract → Transform → Analyze
#
# Input from EventBridge (scheduled) or manual trigger:
#   { "job_id": "<sfn-execution-name>", "days_back": 7 }
#
# The SetJobContext Pass state injects the execution name as job_id,
# then each Lambda receives the full state and passes it forward.

resource "aws_sfn_state_machine" "etl_pipeline" {
  name     = "p2a-${var.environment}-etl-pipeline"
  role_arn = aws_iam_role.stepfunctions.arn
  type     = "STANDARD"

  definition = jsonencode({
    Comment = "p2a ETL pipeline: Extract -> Transform -> Analyze"
    StartAt = "SetJobContext"
    States = {
      # Inject a unique job_id from the execution name (avoids UUID dependency)
      SetJobContext = {
        Type = "Pass"
        Parameters = {
          "job_id.$"   = "$$.Execution.Name"
          "days_back.$" = "$.days_back"
        }
        Next = "Extract"
      }

      Extract = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.extract.arn
          "Payload.$"  = "$"
        }
        OutputPath = "$.Payload"
        Next       = "Transform"
        Retry = [{
          ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.TooManyRequestsException"]
          IntervalSeconds = 5
          MaxAttempts     = 2
          BackoffRate     = 2
        }]
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "JobFailed"
        }]
      }

      Transform = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.transform.arn
          "Payload.$"  = "$"
        }
        OutputPath = "$.Payload"
        Next       = "Analyze"
        Retry = [{
          ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.TooManyRequestsException"]
          IntervalSeconds = 5
          MaxAttempts     = 2
          BackoffRate     = 2
        }]
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "JobFailed"
        }]
      }

      Analyze = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.analyze.arn
          "Payload.$"  = "$"
        }
        OutputPath = "$.Payload"
        Next       = "JobSucceeded"
        Retry = [{
          ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.TooManyRequestsException"]
          IntervalSeconds = 5
          MaxAttempts     = 2
          BackoffRate     = 2
        }]
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "JobFailed"
        }]
      }

      JobSucceeded = {
        Type = "Succeed"
      }

      JobFailed = {
        Type  = "Fail"
        Error = "ETLJobFailed"
        Cause = "One or more ETL steps failed — check CloudWatch Logs"
      }
    }
  })

  tags = {
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}
