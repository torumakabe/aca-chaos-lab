#!/bin/bash
set -euo pipefail

# Script to list all Container App revisions and their status

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
elif [ $# -lt 2 ]; then
    echo "Usage: $0 [resource-group] [container-app-name]"
    echo "  resource-group: Azure resource group name (or set via azd)"
    echo "  container-app-name: Container App name (or set via azd)"
    exit 1
else
    RESOURCE_GROUP="$1"
    APP_NAME="$2"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📋 Container App Revisions${NC}"
echo "Resource Group: $RESOURCE_GROUP"
echo "Container App: $APP_NAME"
echo ""

# Check if Container App exists
if ! az containerapp show -g "$RESOURCE_GROUP" -n "$APP_NAME" &>/dev/null; then
    echo -e "${RED}❌ Container App '$APP_NAME' not found in resource group '$RESOURCE_GROUP'${NC}"
    exit 1
fi

# Get detailed revision information
echo -e "${YELLOW}Fetching revision details...${NC}"

# List all revisions with detailed information
REVISIONS=$(az containerapp revision list \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query "[].{
        Name:name,
        Active:properties.active,
        Status:properties.runningState,
        Replicas:properties.replicas,
        TrafficWeight:properties.trafficWeight,
        CreatedTime:properties.createdTime,
        Image:properties.template.containers[0].image
    }" \
    --output json)

# Display in a formatted table
echo -e "${GREEN}Current Revisions:${NC}"
echo "$REVISIONS" | jq -r '
    ["NAME", "ACTIVE", "STATUS", "REPLICAS", "TRAFFIC%", "CREATED", "IMAGE"],
    ["----", "------", "------", "--------", "--------", "-------", "-----"],
    (.[] | [
        .Name,
        (.Active | tostring),
        .Status,
        (.Replicas | tostring),
        ((.TrafficWeight // 0) | tostring) + "%",
        (.CreatedTime | split("T")[0]),
        (.Image | split("/")[-1] | split(":")[0])
    ])
    | @tsv' | column -t -s $'\t'

# Count statistics
TOTAL_REVISIONS=$(echo "$REVISIONS" | jq '. | length')
ACTIVE_REVISIONS=$(echo "$REVISIONS" | jq '[.[] | select(.Active == true)] | length')
RUNNING_REVISIONS=$(echo "$REVISIONS" | jq '[.[] | select(.Status == "Running" or .Status == "RunningAtMaxScale")] | length')
CHAOS_REVISIONS=$(echo "$REVISIONS" | jq '[.[] | select(.Name | contains("chaos"))] | length')

echo ""
echo -e "${BLUE}Statistics:${NC}"
echo "  Total revisions: $TOTAL_REVISIONS"
echo "  Active revisions: $ACTIVE_REVISIONS"
echo "  Running revisions: $RUNNING_REVISIONS"
echo "  Chaos revisions: $CHAOS_REVISIONS"

# Show current traffic distribution
echo ""
echo -e "${BLUE}Traffic Distribution:${NC}"
TRAFFIC=$(az containerapp show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --query "properties.configuration.ingress.traffic[]" \
    --output json 2>/dev/null)

if [ "$TRAFFIC" != "null" ] && [ -n "$TRAFFIC" ]; then
    echo "$TRAFFIC" | jq -r '.[] | "  \(.revisionName // "latest"): \(.weight)%"'
else
    echo "  Default: Latest active revision receives 100% traffic"
fi