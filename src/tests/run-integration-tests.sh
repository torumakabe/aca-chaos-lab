#!/bin/bash
set -euo pipefail

# Script to run integration tests
# Usage: ./run-integration-tests.sh [test-pattern]

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source the azd environment helper
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/azd-env-helper.sh"

# Load environment from azd if available
load_azd_environment

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Export environment variables for tests
export TEST_BASE_URL="${SERVICE_APP_URI:-http://localhost:8000}"
export TEST_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"
export TEST_CONTAINER_APP_NAME="${SERVICE_APP_NAME:-}"
export TEST_NSG_NAME="${AZURE_NSG_NAME:-}"

echo -e "${BLUE}🧪 Running integration tests...${NC}"
echo "Test environment:"
echo "  BASE_URL: $TEST_BASE_URL"
echo "  RESOURCE_GROUP: $TEST_RESOURCE_GROUP"
echo "  CONTAINER_APP: $TEST_CONTAINER_APP_NAME"
echo "  NSG: $TEST_NSG_NAME"
echo ""

# Ensure we're in the src directory
cd "${SCRIPT_DIR}/.."

# Install test dependencies if needed
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}📦 Installing test dependencies...${NC}"
    uv venv
    uv pip install -e ".[dev]"
fi

# Activate virtual environment
# shellcheck source=/dev/null
source .venv/bin/activate

# Run tests
TEST_PATTERN="${1:-tests/integration/}"
echo -e "${YELLOW}🚀 Running tests: $TEST_PATTERN${NC}"

if uv run pytest "$TEST_PATTERN" -v; then
    echo -e "${GREEN}✅ All integration tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
