resource "aws_s3_bucket" "sensor_events" {
  bucket = "p2b-${var.environment}-sensor-events"

  tags = {
    Name        = "p2b-${var.environment}-sensor-events"
    Project     = "p2b-behavior-analyzer"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "sensor_events" {
  bucket = aws_s3_bucket.sensor_events.id

  versioning_configuration {
    status = "Disabled"
  }
}
