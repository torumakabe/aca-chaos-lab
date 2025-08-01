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

# Check if we have both Liveness and Readiness probes
LIVENESS_EXISTS=$(echo "$CURRENT_PROBES" | jq -r '.[] | select(.type == "Liveness") | .type' 2>/dev/null || echo "")
READINESS_EXISTS=$(echo "$CURRENT_PROBES" | jq -r '.[] | select(.type == "Readiness") | .type' 2>/dev/null || echo "")

if [ "$LIVENESS_EXISTS" = "Liveness" ] && [ "$READINESS_EXISTS" = "Readiness" ]; then
    log_info "✅ Health probes already properly configured for Container App '$CONTAINER_APP_NAME'"
    log_info "Found: Liveness and Readiness probes"
    log_info "Skipping health probe configuration (already complete)"
    exit 0
fi

if [ "$CURRENT_PROBES" != "null" ] && [ "$CURRENT_PROBES" != "[]" ]; then
    log_warn "Partial health probe configuration detected"
    log_info "Current probes:"
    echo "$CURRENT_PROBES" | jq '.[].type' 2>/dev/null || echo "Unable to parse probe types"
    log_info "Will reconfigure to ensure both Liveness and Readiness probes are present"
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
        "httpGet": {
            "path": "/health",
            "port": 8000,
            "scheme": "HTTP"
        },
        "initialDelaySeconds": 30,
        "periodSeconds": 10,
        "timeoutSeconds": 5,
        "failureThreshold": 3,
        "successThreshold": 1
    },
    {
        "type": "Readiness",
        "httpGet": {
            "path": "/health",
            "port": 8000,
            "scheme": "HTTP"
        },
        "initialDelaySeconds": 5,
        "periodSeconds": 5,
        "timeoutSeconds": 3,
        "failureThreshold": 3,
        "successThreshold": 1
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
    log_info "✅ Health probes added successfully!"
    log_info "Container App '$CONTAINER_APP_NAME' now has Liveness and Readiness probes configured."
    log_info "Probes are monitoring the /health endpoint on port 8000"
else
    log_error "Failed to add health probes to Container App"
    exit 1
fi
