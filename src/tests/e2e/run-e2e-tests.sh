#!/bin/bash
set -euo pipefail

# Script to run E2E tests
# Usage: ./run-e2e-tests.sh [test-pattern]

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source the azd environment helper
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/../azd-env-helper.sh"

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
export RUN_E2E_TESTS="true"

echo -e "${BLUE}🧪 Running E2E tests...${NC}"
echo "Test environment:"
echo "  BASE_URL: $TEST_BASE_URL"
echo "  RESOURCE_GROUP: $TEST_RESOURCE_GROUP"
echo "  CONTAINER_APP: $TEST_CONTAINER_APP_NAME"
echo "  NSG: $TEST_NSG_NAME"
echo ""

# Ensure we're in the src directory
cd "${SCRIPT_DIR}/../.."

# Activate virtual environment if exists
if [ -d ".venv" ]; then
    # shellcheck source=/dev/null
    source .venv/bin/activate
fi

# Run tests
TEST_PATTERN="${1:-tests/e2e/}"
echo -e "${YELLOW}🚀 Running tests: $TEST_PATTERN${NC}"

if uv run pytest "$TEST_PATTERN" -v -m e2e; then
    echo -e "${GREEN}✅ All E2E tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
