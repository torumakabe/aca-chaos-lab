#!/bin/bash
set -euo pipefail

# Script to inject network failures by adding NSG rules to block Redis traffic

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source the azd environment helper
source "${SCRIPT_DIR}/azd-env-helper.sh"

# Load environment from azd if available
load_azd_environment

# Check parameters or use azd values
if [ $# -eq 0 ] && [ -n "$RESOURCE_GROUP" ] && [ -n "$NSG_NAME" ]; then
    # Use azd environment values
    echo "Using values from Azure Developer CLI environment"
    DURATION="60"
elif [ $# -lt 2 ]; then
    echo "Usage: $0 [resource-group] [nsg-name] [duration-seconds]"
    echo "  resource-group: Azure resource group name (or set via azd)"
    echo "  nsg-name: Network Security Group name (or set via azd)"
    echo "  duration-seconds: How long to block traffic (default: 60, use 0 for permanent)"
    exit 1
else
    RESOURCE_GROUP="$1"
    NSG_NAME="$2"
    DURATION="${3:-60}"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚨 Injecting network failure...${NC}"
echo "Resource Group: $RESOURCE_GROUP"
echo "NSG: $NSG_NAME"
echo "Duration: ${DURATION}s (0 = permanent)"

# Check if NSG exists
if ! az network nsg show -g "$RESOURCE_GROUP" -n "$NSG_NAME" &>/dev/null; then
    echo -e "${RED}❌ NSG '$NSG_NAME' not found in resource group '$RESOURCE_GROUP'${NC}"
    exit 1
fi

# Create rule to block Redis traffic (port 10000)
RULE_NAME="chaos-block-redis-$(date +%s)"
PRIORITY=100

echo -e "${YELLOW}📝 Creating NSG rule to block Redis traffic...${NC}"
az network nsg rule create \
    --resource-group "$RESOURCE_GROUP" \
    --nsg-name "$NSG_NAME" \
    --name "$RULE_NAME" \
    --priority "$PRIORITY" \
    --direction Outbound \
    --access Deny \
    --protocol Tcp \
    --destination-port-ranges 10000 \
    --description "Chaos engineering: Block Redis traffic" \
    --output none

echo -e "${GREEN}✅ Network failure injected successfully!${NC}"
echo "Rule name: $RULE_NAME"

# If duration is specified and not 0, schedule removal
if [ "$DURATION" -gt 0 ]; then
    echo -e "${YELLOW}⏰ Scheduling rule removal in ${DURATION}s...${NC}"
    
    # Create a background job to remove the rule after duration
    (
        sleep "$DURATION"
        echo -e "${YELLOW}🔧 Removing network failure rule...${NC}"
        az network nsg rule delete \
            --resource-group "$RESOURCE_GROUP" \
            --nsg-name "$NSG_NAME" \
            --name "$RULE_NAME" \
            --output none
        echo -e "${GREEN}✅ Network failure cleared!${NC}"
    ) &
    
    CLEANUP_PID=$!
    echo "Cleanup scheduled (PID: $CLEANUP_PID)"
    echo -e "${YELLOW}💡 To remove the rule manually, run:${NC}"
    echo "az network nsg rule delete -g $RESOURCE_GROUP --nsg-name $NSG_NAME -n $RULE_NAME"
else
    echo -e "${YELLOW}⚠️  Rule will remain until manually removed${NC}"
    echo -e "${YELLOW}💡 To remove the rule, run:${NC}"
    echo "az network nsg rule delete -g $RESOURCE_GROUP --nsg-name $NSG_NAME -n $RULE_NAME"
fi