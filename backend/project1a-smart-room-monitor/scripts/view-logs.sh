#!/bin/bash
# View logs from different containers
# Usage: ./scripts/view-logs.sh [container]

CONTAINER=${1:-"localstack"}

case $CONTAINER in
  localstack)
    echo "📋 Viewing LocalStack logs..."
    docker logs iot-localstack -f
    ;;
  lambda)
    echo "📋 Viewing Lambda container logs..."
    docker logs iot-lambda -f
    ;;
  lambda-runtime)
    echo "📋 Viewing LocalStack Lambda runtime logs..."
    # Find and show logs from LocalStack's Lambda containers
    LAMBDA_CONTAINERS=$(docker ps --filter "name=localstack_lambda" --format "{{.Names}}")
    if [ -z "$LAMBDA_CONTAINERS" ]; then
      echo "❌ No LocalStack Lambda containers found"
      echo "💡 Deploy a Lambda function to LocalStack first"
    else
      echo "Found containers: $LAMBDA_CONTAINERS"
      for container in $LAMBDA_CONTAINERS; do
        echo ""
        echo "=== $container ==="
        docker logs $container --tail 50
      done
    fi
    ;;
  *)
    echo "Usage: ./scripts/view-logs.sh [localstack|lambda|lambda-runtime]"
    echo ""
    echo "Options:"
    echo "  localstack      - LocalStack main container logs"
    echo "  lambda          - Standalone iot-lambda container logs"
    echo "  lambda-runtime  - LocalStack's Lambda runtime container logs"
    exit 1
    ;;
esac
