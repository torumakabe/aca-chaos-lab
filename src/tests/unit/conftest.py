"""Shared fixtures for unit tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone


@pytest.fixture
def mock_azure_credential():
    """Mock Azure credential for testing."""
    credential = MagicMock()
    
    # Mock token
    mock_token = MagicMock()
    mock_token.token = "mock_token"
    mock_token.expires_on = int(datetime.now(timezone.utc).timestamp()) + 3600
    
    # Make get_token return an awaitable
    async def async_get_token(*args, **kwargs):
        return mock_token
    
    credential.get_token = AsyncMock(side_effect=async_get_token)
    
    # Make close return an awaitable
    credential.close = AsyncMock()
    
    return credential