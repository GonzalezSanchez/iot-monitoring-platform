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
  description = "ARN of the source DynamoDB SensorEvents table (from project 1a)"
}

variable "db_name" {
  type        = string
  default     = "p2a_prod"
  description = "Aurora database name"
}

variable "db_username" {
  type        = string
  default     = "p2admin"
  sensitive   = true
  description = "Aurora master username"
}
