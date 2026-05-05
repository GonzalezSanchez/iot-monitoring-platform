output "s3_bucket_name" {
  description = "S3 bucket for raw sensor events (Parquet)"
  value       = aws_s3_bucket.sensor_events.bucket
}

output "airflow_worker_access_key_id" {
  description = "IAM access key ID for Airflow worker — add to .env"
  value       = aws_iam_access_key.airflow_worker.id
}

output "airflow_worker_secret_access_key" {
  description = "IAM secret access key for Airflow worker — add to .env"
  value       = aws_iam_access_key.airflow_worker.secret
  sensitive   = true
}
