#!/bin/bash
set -euo pipefail

# Script to clear all chaos-related NSG rules

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source the azd environment helper
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/azd-env-helper.sh"

# Load environment from azd if available
load_azd_environment

# Check parameters or use azd values
if [ $# -eq 0 ] && [ -n "${AZURE_RESOURCE_GROUP:-}" ] && [ -n "${AZURE_NSG_NAME:-}" ]; then
    # Use azd environment values
    echo "Using values from Azure Developer CLI environment"
    RESOURCE_GROUP="${AZURE_RESOURCE_GROUP}"
    NSG_NAME="${AZURE_NSG_NAME}"
elif [ $# -lt 2 ]; then
    echo "Usage: $0 [resource-group] [nsg-name]"
    echo "  resource-group: Azure resource group name (or set via azd)"
    echo "  nsg-name: Network Security Group name (or set via azd)"
    exit 1
else
    RESOURCE_GROUP="$1"
    NSG_NAME="$2"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🧹 Clearing all chaos network failure rules...${NC}"
echo "Resource Group: $RESOURCE_GROUP"
echo "NSG: $NSG_NAME"

# Check if NSG exists
if ! az network nsg show -g "$RESOURCE_GROUP" -n "$NSG_NAME" &>/dev/null; then
    echo -e "${RED}❌ NSG '$NSG_NAME' not found in resource group '$RESOURCE_GROUP'${NC}"
    exit 1
fi

# Get all rules that start with "chaos-"
CHAOS_RULES=$(az network nsg rule list \
    --resource-group "$RESOURCE_GROUP" \
    --nsg-name "$NSG_NAME" \
    --query "[?starts_with(name, 'chaos-')].name" \
    --output tsv)

if [ -z "$CHAOS_RULES" ]; then
    echo -e "${GREEN}✅ No chaos rules found${NC}"
    exit 0
fi

# Count rules
RULE_COUNT=$(echo "$CHAOS_RULES" | wc -l)
echo -e "${YELLOW}Found ${RULE_COUNT} chaos rule(s) to remove${NC}"

# Remove each rule
while IFS= read -r RULE_NAME; do
    echo -e "${YELLOW}🔧 Removing rule: ${RULE_NAME}${NC}"
    az network nsg rule delete \
        --resource-group "$RESOURCE_GROUP" \
        --nsg-name "$NSG_NAME" \
        --name "$RULE_NAME" \
        --output none
done <<< "$CHAOS_RULES"

echo -e "${GREEN}✅ All chaos network failure rules cleared!${NC}"
