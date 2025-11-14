"""Pytest configuration for E2E tests."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from azd_env_helper import load_azd_environment

# Load environment from azd
azd_env = load_azd_environment()

# Test configuration from environment
BASE_URL = os.getenv("TEST_BASE_URL") or azd_env.get(
    "SERVICE_APP_URL", "http://localhost:8000"
)

# Skip E2E tests by default unless explicitly enabled
RUN_E2E = os.getenv("RUN_E2E_TESTS", "false").lower() == "true"


@pytest.fixture(scope="session")
def base_url():
    """Get base URL for E2E tests."""
    return BASE_URL


@pytest.fixture(scope="session")
def skip_if_e2e_disabled():
    """Skip E2E tests if not explicitly enabled."""
    if not RUN_E2E:
        pytest.skip("E2E tests disabled. Set RUN_E2E_TESTS=true to enable.")
