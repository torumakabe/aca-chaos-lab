#!/bin/bash
set -euo pipefail

# Script to run integration tests with Testcontainers
# Usage: ./run-integration-tests.sh [test-pattern]

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Running integration tests with Testcontainers...${NC}"
echo "Prerequisites:"
echo "  - Docker must be running"
echo "  - Testcontainers will automatically start Redis container"
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

if uv run pytest "$TEST_PATTERN" -v -m integration; then
    echo -e "${GREEN}✅ All integration tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
