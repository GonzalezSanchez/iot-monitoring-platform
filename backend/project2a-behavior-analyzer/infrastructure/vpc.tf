# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "p2a-${var.environment}-vpc"
    Project     = "p2a-behavior-analyzer"
    Environment = var.environment
  }
}

# Private subnets — 2 AZs required by Aurora
resource "aws_subnet" "private_1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "${var.region}a"

  tags = {
    Name = "p2a-${var.environment}-private-1"
  }
}

resource "aws_subnet" "private_2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.region}b"

  tags = {
    Name = "p2a-${var.environment}-private-2"
  }
}

# Route table for private subnets (no default route — traffic via VPC endpoints)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "p2a-${var.environment}-private-rt"
  }
}

resource "aws_route_table_association" "private_1" {
  subnet_id      = aws_subnet.private_1.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_2" {
  subnet_id      = aws_subnet.private_2.id
  route_table_id = aws_route_table.private.id
}

# Security group for Lambda functions
resource "aws_security_group" "lambda" {
  name        = "p2a-${var.environment}-lambda-sg"
  description = "Security group for ETL Lambda functions"
  vpc_id      = aws_vpc.main.id

  egress {
    description = "HTTPS to VPC endpoints"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "PostgreSQL to Aurora in VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  tags = {
    Name = "p2a-${var.environment}-lambda-sg"
  }
}

# Security group for Aurora — only accepts connections from Lambda SG
resource "aws_security_group" "aurora" {
  name        = "p2a-${var.environment}-aurora-sg"
  description = "Security group for Aurora PostgreSQL cluster"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from Lambda"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  tags = {
    Name = "p2a-${var.environment}-aurora-sg"
  }
}

# Security group for VPC Interface Endpoints
resource "aws_security_group" "vpc_endpoints" {
  name        = "p2a-${var.environment}-endpoint-sg"
  description = "Security group for VPC Interface Endpoints"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "HTTPS from Lambda"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  tags = {
    Name = "p2a-${var.environment}-endpoint-sg"
  }
}

# DB subnet group (required by Aurora)
resource "aws_db_subnet_group" "main" {
  name       = "p2a-${var.environment}-db-subnet-group"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]

  tags = {
    Name = "p2a-${var.environment}-db-subnet-group"
  }
}

# --- VPC Endpoints (no NAT Gateway) ---
# Deliberate choice: Lambda in private subnets reaches AWS APIs via VPC endpoints.
# Benefits:
#   - Traffic stays within the AWS network (no public internet exposure)
#   - Lower latency than routing via NAT Gateway
#   - Cheaper: ~$14/month vs ~$32/month for a NAT Gateway
# Three endpoints are required:
#   - DynamoDB  : Gateway Endpoint (free)
#   - Secrets Manager : Interface Endpoint (~$7/month)
#   - CloudWatch Logs : Interface Endpoint (~$7/month) — mandatory for Lambda
#                       in a private subnet to emit logs

# DynamoDB Gateway Endpoint — FREE
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  tags = {
    Name = "p2a-${var.environment}-dynamodb-endpoint"
  }
}

# Secrets Manager Interface Endpoint — ~$7.20/month (1 AZ)
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_1.id]
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "p2a-${var.environment}-secretsmanager-endpoint"
  }
}

# CloudWatch Logs Interface Endpoint — ~$7.20/month (1 AZ)
resource "aws_vpc_endpoint" "cloudwatch_logs" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_1.id]
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "p2a-${var.environment}-logs-endpoint"
  }
}
