#!/bin/bash
set -euo pipefail

# Script to restore a working deployment by activating the previous revision
# Usage: ./restore-deployment.sh <resource-group> <container-app-name>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <resource-group> <container-app-name>"
    echo "  resource-group: Azure resource group name"
    echo "  container-app-name: Container App name"
    exit 1
fi

RESOURCE_GROUP="$1"
APP_NAME="$2"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Restoring deployment...${NC}"
echo "Resource Group: $RESOURCE_GROUP"
echo "Container App: $APP_NAME"

# Check if Container App exists
if ! az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" &>/dev/null; then
    echo -e "${RED}❌ Container App '$APP_NAME' not found in resource group '$RESOURCE_GROUP'${NC}"
    exit 1
fi

# List all revisions
echo -e "${YELLOW}📋 Current revisions:${NC}"
az containerapp revision list \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query "[].{Name:name, Active:properties.active, Status:properties.runningState, Created:properties.createdTime, Traffic:properties.trafficWeight}" \
    --output table

# Find the last non-chaos revision that was running
echo -e "${YELLOW}🔍 Finding last working revision...${NC}"
LAST_WORKING_REVISION=$(az containerapp revision list \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query "[?!contains(name, 'chaos') && properties.runningState=='Running'] | [0].name" \
    --output tsv)

if [ -z "$LAST_WORKING_REVISION" ]; then
    echo -e "${RED}❌ No working revision found!${NC}"
    echo "Looking for any running revision..."
    
    LAST_WORKING_REVISION=$(az containerapp revision list \
        --resource-group "$RESOURCE_GROUP" \
        --name "$APP_NAME" \
        --query "[?properties.runningState=='Running'] | [0].name" \
        --output tsv)
    
    if [ -z "$LAST_WORKING_REVISION" ]; then
        echo -e "${RED}❌ No running revisions found at all!${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ Found working revision: ${LAST_WORKING_REVISION}${NC}"

# Activate the working revision and deactivate chaos revisions
echo -e "${YELLOW}🚀 Activating working revision...${NC}"
az containerapp revision activate \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --revision "$LAST_WORKING_REVISION" \
    --output none

# Deactivate all chaos revisions
echo -e "${YELLOW}🛑 Deactivating chaos revisions...${NC}"
CHAOS_REVISIONS=$(az containerapp revision list \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query "[?contains(name, 'chaos') && properties.active==true].name" \
    --output tsv)

if [ -n "$CHAOS_REVISIONS" ]; then
    while IFS= read -r REVISION; do
        echo "  Deactivating: $REVISION"
        az containerapp revision deactivate \
            --resource-group "$RESOURCE_GROUP" \
            --name "$APP_NAME" \
            --revision "$REVISION" \
            --output none
    done <<< "$CHAOS_REVISIONS"
fi

# Update traffic to send 100% to the working revision
echo -e "${YELLOW}🔄 Updating traffic distribution...${NC}"
az containerapp update \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --traffic-weight "$LAST_WORKING_REVISION=100" \
    --output none

echo -e "${GREEN}✅ Deployment restored successfully!${NC}"

# Show final status
echo -e "${BLUE}📊 Final revision status:${NC}"
az containerapp revision list \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query "[].{Name:name, Active:properties.active, Status:properties.runningState, Traffic:properties.trafficWeight}" \
    --output table