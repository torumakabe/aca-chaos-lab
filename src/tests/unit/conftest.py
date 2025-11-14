"""Shared fixtures for unit tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_azure_credential():
    """Mock Azure credential for testing."""
    credential = MagicMock()

    # Mock token
    mock_token = MagicMock()
    mock_token.token = "mock_token"
    mock_token.expires_on = int(datetime.now(UTC).timestamp()) + 3600

    # get_token は非同期関数として await 可能
    credential.get_token = AsyncMock(return_value=mock_token)

    # close も非同期
    credential.close = AsyncMock()

    return credential
