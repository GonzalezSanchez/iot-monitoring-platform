# Multi-stage Dockerfile for AWS Lambda Python runtime
FROM public.ecr.aws/lambda/python:3.11 as builder

# Install build dependencies in isolated build directory
WORKDIR /build

# Copy requirements
COPY requirements.txt .

# Install Python dependencies to /build/python
RUN pip install --no-cache-dir -r requirements.txt -t /build/python


# Final stage
FROM public.ecr.aws/lambda/python:3.11

# Copy dependencies first (better layer caching)
COPY --from=builder /build/python/ /var/task/

# Copy application source code directly to /var/task (not /var/task/src)
COPY src/ /var/task/

# Lambda handler - clean path without src prefix
# Override via docker-compose environment variable or Lambda configuration
CMD ["handlers.get_rooms.lambda_handler"]
