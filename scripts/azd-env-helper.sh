#!/bin/bash
# Helper script to get environment values from azd or fallback to environment variables

# Function to get value from azd or environment
get_env_value() {
    local key="$1"
    local default="$2"

    # Try to get from azd first
    if command -v azd &> /dev/null; then
        local azd_value
        azd_value=$(azd env get-value "$key" 2>/dev/null || echo "")
        if [ -n "$azd_value" ]; then
            # Remove surrounding quotes if present
            azd_value="${azd_value%\"}"
            azd_value="${azd_value#\"}"
            echo "$azd_value"
            return
        fi
    fi

    # Fallback to environment variable
    local env_var="${!key:-$default}"
    echo "$env_var"
}

# Function to check if azd is available
is_azd_available() {
    command -v azd &> /dev/null
}

# Function to get all required environment values
load_azd_environment() {
    # Check if azd is available
    if is_azd_available; then
        echo "Using Azure Developer CLI environment values..." >&2

        # Export common values
        AZURE_RESOURCE_GROUP=$(get_env_value "AZURE_RESOURCE_GROUP" "${AZURE_RESOURCE_GROUP:-}")
        export AZURE_RESOURCE_GROUP
        SERVICE_APP_NAME=$(get_env_value "SERVICE_APP_NAME" "${SERVICE_APP_NAME:-}")
        export SERVICE_APP_NAME
        SERVICE_APP_URL=$(get_env_value "SERVICE_APP_URL" "${SERVICE_APP_URL:-}")
        export SERVICE_APP_URL
        AZURE_REDIS_HOST=$(get_env_value "AZURE_REDIS_HOST" "${AZURE_REDIS_HOST:-}")
        export AZURE_REDIS_HOST
        AZURE_LOCATION=$(get_env_value "AZURE_LOCATION" "${AZURE_LOCATION:-}")
        export AZURE_LOCATION
        AZURE_NSG_NAME=$(get_env_value "AZURE_NSG_NAME" "${AZURE_NSG_NAME:-}")
        export AZURE_NSG_NAME

        # For network operations, we need to find the NSG name if not provided
        if [ -z "${AZURE_NSG_NAME:-}" ] && [ -n "${AZURE_RESOURCE_GROUP:-}" ]; then
            AZURE_NSG_NAME=$(az network nsg list -g "$AZURE_RESOURCE_GROUP" --query "[0].name" -o tsv 2>/dev/null || echo "")
            export AZURE_NSG_NAME
        fi
    else
        echo "Azure Developer CLI not found, using environment variables..." >&2
    fi
}
