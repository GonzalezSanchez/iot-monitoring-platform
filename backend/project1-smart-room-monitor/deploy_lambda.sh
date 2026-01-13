#!/bin/bash
# Build and upload Lambda deployment package
# Usage: ./deploy_lambda.sh <lambda_function_name>

set -e

LAMBDA_NAME="$1"
if [ -z "$LAMBDA_NAME" ]; then
  echo "Geef de Lambda functie naam op als argument!"
  exit 1
fi

WORKDIR="$(dirname "$0")"
cd "$WORKDIR"

# Maak een tijdelijke directory voor het package
rm -rf lambda_build
mkdir lambda_build
cp -r src lambda_build/
cp requirements.txt lambda_build/

cd lambda_build
# Installeer dependencies lokaal in package (optioneel, als je extra packages nodig hebt)
# pip install -r requirements.txt -t .

# Maak zip
zip -r ../lambda_package.zip .
cd ..
rm -rf lambda_build

echo "Upload lambda_package.zip naar AWS Lambda via de Console of CLI."
echo "Stel de handler in op src.handlers.get_rooms.lambda_handler (of de juiste handler)."
