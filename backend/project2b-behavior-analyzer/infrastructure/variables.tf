variable "environment" {
  type        = string
  default     = "prod"
  description = "Deployment environment"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod."
  }
}

variable "region" {
  type        = string
  default     = "eu-central-1"
  description = "AWS region"
}

variable "source_dynamodb_table_arn" {
  type        = string
  description = "ARN of source DynamoDB SensorEvents table (project 1a)"
}
