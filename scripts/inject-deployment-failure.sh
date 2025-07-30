#!/bin/bash
set -euo pipefail

# Script to inject deployment failures by creating a broken container revision

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source the azd environment helper
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/azd-env-helper.sh"

# Load environment from azd if available
load_azd_environment

# Check parameters or use azd values
if [ $# -eq 0 ] && [ -n "${AZURE_RESOURCE_GROUP:-}" ] && [ -n "${AZURE_CONTAINER_APP_NAME:-}" ]; then
    # Use azd environment values
    echo "Using values from Azure Developer CLI environment"
    RESOURCE_GROUP="${AZURE_RESOURCE_GROUP}"
    APP_NAME="${AZURE_CONTAINER_APP_NAME}"
    FAILURE_TYPE="startup-failure"
elif [ $# -eq 1 ] && [ -n "${AZURE_RESOURCE_GROUP:-}" ] && [ -n "${AZURE_CONTAINER_APP_NAME:-}" ]; then
    # Use azd environment values with provided failure type
    echo "Using values from Azure Developer CLI environment"
    RESOURCE_GROUP="${AZURE_RESOURCE_GROUP}"
    APP_NAME="${AZURE_CONTAINER_APP_NAME}"
    FAILURE_TYPE="$1"
elif [ $# -lt 2 ]; then
    echo "Usage: $0 [resource-group] [container-app-name] [failure-type]"
    echo "  resource-group: Azure resource group name (or set via azd)"
    echo "  container-app-name: Container App name (or set via azd)"
    echo "  failure-type: Type of failure (startup-failure, bad-env)"
    echo "                Default: startup-failure"
    exit 1
else
    RESOURCE_GROUP="$1"
    APP_NAME="$2"
    FAILURE_TYPE="${3:-startup-failure}"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚨 Injecting deployment failure...${NC}"
echo "Resource Group: $RESOURCE_GROUP"
echo "Container App: $APP_NAME"
echo "Failure Type: $FAILURE_TYPE"

# Check if Container App exists
if ! az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" &>/dev/null; then
    echo -e "${RED}❌ Container App '$APP_NAME' not found in resource group '$RESOURCE_GROUP'${NC}"
    exit 1
fi

# Get current configuration
echo -e "${YELLOW}📋 Getting current configuration...${NC}"
CURRENT_IMAGE=$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" \
    --query "properties.template.containers[0].image" -o tsv)
CURRENT_CPU=$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" \
    --query "properties.template.containers[0].resources.cpu" -o tsv)
CURRENT_MEMORY=$(az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" \
    --query "properties.template.containers[0].resources.memory" -o tsv)

echo "Current image: $CURRENT_IMAGE"
echo "Current CPU: $CURRENT_CPU"
echo "Current memory: $CURRENT_MEMORY"

# Create revision suffix
REVISION_SUFFIX="chaos-$(date +%s)"

case "$FAILURE_TYPE" in
    "startup-failure")
        echo -e "${YELLOW}💥 Creating revision with startup failure command...${NC}"
        az containerapp update \
            --resource-group "$RESOURCE_GROUP" \
            --name "$APP_NAME" \
            --command "/bin/sh" \
            --args '["sh", "-c", "echo Simulating startup failure && exit 1"]' \
            --revision-suffix "$REVISION_SUFFIX" \
            --output none
        ;;

    "bad-env")
        echo -e "${YELLOW}💥 Creating revision with invalid environment variable...${NC}"
        az containerapp update \
            --resource-group "$RESOURCE_GROUP" \
            --name "$APP_NAME" \
            --set-env-vars "REDIS_HOST=" "REDIS_PORT=invalid" \
            --revision-suffix "$REVISION_SUFFIX" \
            --output none
        ;;

    *)
        echo -e "${RED}❌ Unknown failure type: ${FAILURE_TYPE}${NC}"
        echo "Valid types: startup-failure, bad-env"
        exit 1
        ;;
esac

echo -e "${GREEN}✅ Deployment failure injected!${NC}"
echo "Revision suffix: $REVISION_SUFFIX"

# Show revision status
echo -e "${YELLOW}📊 Checking revision status...${NC}"
sleep 5  # Wait a bit for the revision to be created

az containerapp revision list \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query "[?contains(name, '$REVISION_SUFFIX')].{Name:name, Active:properties.active, Status:properties.runningState, Replicas:properties.replicas}" \
    --output table

echo -e "${YELLOW}💡 To restore the previous working revision, use:${NC}"
echo "To restore, run: azd deploy"
