#!/bin/bash

# Add health probes to existing Container App using Azure CLI
# This script runs as a postprovision hook in Azure Developer CLI
# and is designed to be idempotent (safe to run multiple times)

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get environment variables from azd
RESOURCE_GROUP=${AZURE_RESOURCE_GROUP:-}
CONTAINER_APP_NAME=${SERVICE_APP_NAME:-}

if [ -z "$RESOURCE_GROUP" ] || [ -z "$CONTAINER_APP_NAME" ]; then
    log_error "Missing required environment variables"
    log_error "AZURE_RESOURCE_GROUP and SERVICE_APP_NAME must be set"
    log_error "These should be automatically set by 'azd deploy'"
    exit 1
fi

log_info "Processing Container App: $CONTAINER_APP_NAME in Resource Group: $RESOURCE_GROUP"

# Check if Container App exists
log_info "Verifying Container App exists..."
if ! az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    log_error "Container App '$CONTAINER_APP_NAME' not found in resource group '$RESOURCE_GROUP'"
    exit 1
fi

# Check if health probes already exist
log_info "Checking current health probe configuration..."
CURRENT_PROBES=$(az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query 'properties.template.containers[0].probes' \
    --output json 2>/dev/null || echo "null")

# Always (re)configure to desired probes to ensure settings match this project
if [ "$CURRENT_PROBES" != "null" ] && [ "$CURRENT_PROBES" != "[]" ]; then
    log_info "Existing probe configuration detected. Will (re)apply desired probes."
    echo "$CURRENT_PROBES" | jq '.' >/dev/null 2>&1 || true
fi

# Add health probes to Container App using JSON configuration
log_info "Adding health probes to Container App..."

# Get current container configuration
CONTAINER_CONFIG=$(az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query 'properties.template.containers[0]' \
    --output json)

if [ $? -ne 0 ]; then
    log_error "Failed to get current container configuration"
    exit 1
fi

# Add probes to the existing configuration
UPDATED_CONFIG=$(echo "$CONTAINER_CONFIG" | jq '.probes = [
    {
        "type": "Liveness",
        "tcpSocket": {
            "port": 8000
        },
        "initialDelaySeconds": 60,
        "periodSeconds": 10,
        "timeoutSeconds": 10,
        "failureThreshold": 5,
        "successThreshold": 1
    },
    {
        "type": "Readiness",
        "httpGet": {
            "path": "/health",
            "port": 8000,
            "scheme": "HTTP"
        },
        "initialDelaySeconds": 10,
        "periodSeconds": 5,
        "timeoutSeconds": 3,
        "failureThreshold": 2,
        "successThreshold": 2
    }
]')

# Create JSON configuration with updated container
echo "$UPDATED_CONFIG" | jq '{
  "properties": {
    "template": {
      "containers": [.]
    }
  }
}' | az containerapp update \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --yaml /dev/stdin \
    --output table

if [ $? -eq 0 ]; then
    log_info "✅ Health probes configured successfully!"
    log_info "Container App '$CONTAINER_APP_NAME' now uses:"
    log_info "- Liveness (TCP): port 8000"
    log_info "- Readiness (HTTP): GET /health on port 8000"
else
    log_error "Failed to add health probes to Container App"
    exit 1
fi
