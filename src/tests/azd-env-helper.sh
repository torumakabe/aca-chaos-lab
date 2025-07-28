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
        RESOURCE_GROUP=$(get_env_value "AZURE_RESOURCE_GROUP" "${RESOURCE_GROUP:-}")
        export RESOURCE_GROUP
        CONTAINER_APP_NAME=$(get_env_value "AZURE_CONTAINER_APP_NAME" "${CONTAINER_APP_NAME:-}")
        export CONTAINER_APP_NAME
        CONTAINER_APP_URI=$(get_env_value "AZURE_CONTAINER_APP_URI" "${CONTAINER_APP_URI:-}")
        export CONTAINER_APP_URI
        REDIS_HOST=$(get_env_value "AZURE_REDIS_HOST" "${REDIS_HOST:-}")
        export REDIS_HOST
        LOCATION=$(get_env_value "AZURE_LOCATION" "${LOCATION:-}")
        export LOCATION

        # For network operations, we need to find the NSG name
        if [ -z "${NSG_NAME:-}" ] && [ -n "$RESOURCE_GROUP" ]; then
            NSG_NAME=$(az network nsg list -g "$RESOURCE_GROUP" --query "[0].name" -o tsv 2>/dev/null || echo "")
            export NSG_NAME
        fi
    else
        echo "Azure Developer CLI not found, using environment variables..." >&2
    fi
}
