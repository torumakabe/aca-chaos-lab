#!/bin/bash
set -euo pipefail

# Script to list all chaos-related NSG rules
# Usage: ./list-network-failures.sh <resource-group> <nsg-name>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <resource-group> <nsg-name>"
    echo "  resource-group: Azure resource group name"
    echo "  nsg-name: Network Security Group name"
    exit 1
fi

RESOURCE_GROUP="$1"
NSG_NAME="$2"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📋 Listing chaos network failure rules...${NC}"
echo "Resource Group: $RESOURCE_GROUP"
echo "NSG: $NSG_NAME"
echo ""

# Check if NSG exists
if ! az network nsg show -g "$RESOURCE_GROUP" -n "$NSG_NAME" &>/dev/null; then
    echo -e "${RED}❌ NSG '$NSG_NAME' not found in resource group '$RESOURCE_GROUP'${NC}"
    exit 1
fi

# Get all rules that start with "chaos-"
CHAOS_RULES=$(az network nsg rule list \
    --resource-group "$RESOURCE_GROUP" \
    --nsg-name "$NSG_NAME" \
    --query "[?starts_with(name, 'chaos-')].{Name:name, Priority:priority, Access:access, Direction:direction, Protocol:protocol, DestinationPortRanges:destinationPortRanges[0], Description:description}" \
    --output json)

if [ "$CHAOS_RULES" == "[]" ]; then
    echo -e "${GREEN}✅ No chaos rules found${NC}"
    exit 0
fi

# Display rules in a formatted way
echo -e "${YELLOW}Active chaos rules:${NC}"
echo "$CHAOS_RULES" | jq -r '.[] | "
Rule: \(.Name)
  Priority: \(.Priority)
  Access: \(.Access)
  Direction: \(.Direction)
  Protocol: \(.Protocol)
  Port: \(.DestinationPortRanges)
  Description: \(.Description)
"'

# Count rules
RULE_COUNT=$(echo "$CHAOS_RULES" | jq '. | length')
echo -e "${BLUE}Total chaos rules: $RULE_COUNT${NC}"