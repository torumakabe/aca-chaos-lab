#!/bin/bash
set -euo pipefail

# Script to inject network failures by adding NSG rules to block Redis traffic

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
    DURATION="60"
elif [ $# -eq 1 ] && [ -n "${AZURE_RESOURCE_GROUP:-}" ] && [ -n "${AZURE_NSG_NAME:-}" ]; then
    # Use azd environment values with custom duration
    echo "Using values from Azure Developer CLI environment with custom duration"
    RESOURCE_GROUP="${AZURE_RESOURCE_GROUP}"
    NSG_NAME="${AZURE_NSG_NAME}"
    DURATION="$1"
elif [ $# -lt 2 ]; then
    echo "Usage: $0 [duration-seconds]"
    echo "       $0 [resource-group] [nsg-name] [duration-seconds]"
    echo ""
    echo "  When using azd environment (AZURE_RESOURCE_GROUP and AZURE_NSG_NAME are set):"
    echo "    duration-seconds: How long to block traffic (default: 60, use 0 for permanent)"
    echo ""
    echo "  When not using azd environment:"
    echo "    resource-group: Azure resource group name"
    echo "    nsg-name: Network Security Group name"
    echo "    duration-seconds: How long to block traffic (default: 60, use 0 for permanent)"
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
    --direction Inbound \
    --access Deny \
    --protocol Tcp \
    --destination-port-ranges 10000 \
    --description "Chaos engineering: Block Redis traffic" \
    --output none

echo -e "${GREEN}✅ Network failure injected successfully!${NC}"
echo "Rule name: $RULE_NAME"

# Wait for NSG rule to propagate before restarting container
echo -e "${YELLOW}⏳ Waiting 30 seconds for NSG rule to propagate...${NC}"
sleep 30

# Reset Redis connections using the chaos API
if [ -n "${SERVICE_APP_URI:-}" ]; then
    echo -e "${YELLOW}🔄 Resetting Redis connections via API to apply network rules...${NC}"

    # Call the Redis reset API
    echo -e "${YELLOW}📡 Calling Redis reset API at ${SERVICE_APP_URI}/chaos/redis-reset${NC}"

    # Use curl to call the API with retry logic
    MAX_RETRIES=3
    RETRY_COUNT=0
    SUCCESS=false

    while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
        if curl -X POST "${SERVICE_APP_URI}/chaos/redis-reset" \
            -H "Content-Type: application/json" \
            -d '{"force": true}' \
            -s -w "\nHTTP Status: %{http_code}\n" \
            --connect-timeout 10 \
            --max-time 30; then
            SUCCESS=true
            echo -e "${GREEN}✅ Redis connections reset successfully${NC}"
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo -e "${YELLOW}⚠️  API call failed, retrying in 5 seconds... (attempt $((RETRY_COUNT + 1))/${MAX_RETRIES})${NC}"
                sleep 5
            else
                echo -e "${RED}❌ Failed to reset Redis connections after ${MAX_RETRIES} attempts${NC}"
                echo -e "${YELLOW}💡 The NSG rule has been applied but existing connections may persist${NC}"
                echo -e "${YELLOW}💡 New connections to Redis will be blocked${NC}"
            fi
        fi
    done
else
    echo -e "${YELLOW}⚠️  SERVICE_APP_URI not set. Please reset Redis connections manually:${NC}"
    echo "curl -X POST https://<your-app-uri>/chaos/redis-reset -H 'Content-Type: application/json' -d '{\"force\": true}'"
fi

# If duration is specified and not 0, schedule removal
if [ "$DURATION" -gt 0 ]; then
    echo -e "${YELLOW}⏰ Scheduling rule removal in ${DURATION}s...${NC}"

    # Create a background job to remove the rule after duration
    # Use nohup and redirect all I/O to prevent terminal interaction
    nohup bash -c "
        sleep $DURATION
        echo -e '${YELLOW}🔧 Removing network failure rule...${NC}'
        az network nsg rule delete \
            --resource-group '$RESOURCE_GROUP' \
            --nsg-name '$NSG_NAME' \
            --name '$RULE_NAME' \
            --output none
        echo -e '${GREEN}✅ Network failure cleared!${NC}'
    " > "/tmp/chaos-cleanup-$RULE_NAME.log" 2>&1 &

    CLEANUP_PID=$!
    echo "Cleanup scheduled (PID: $CLEANUP_PID)"
    echo -e "${YELLOW}💡 To remove the rule manually, run:${NC}"
    echo "az network nsg rule delete -g $RESOURCE_GROUP --nsg-name $NSG_NAME -n $RULE_NAME"
    echo -e "${YELLOW}📝 Cleanup log: /tmp/chaos-cleanup-${RULE_NAME}.log${NC}"
else
    echo -e "${YELLOW}⚠️  Rule will remain until manually removed${NC}"
    echo -e "${YELLOW}💡 To remove the rule, run:${NC}"
    echo "az network nsg rule delete -g $RESOURCE_GROUP --nsg-name $NSG_NAME -n $RULE_NAME"
fi
