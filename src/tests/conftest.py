"""Pytest configuration and fixtures."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    client = AsyncMock()
    client.get = AsyncMock(return_value="test_value")
    client.set = AsyncMock(return_value=True)
    client.ping = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_azure_credential():
    """Mock Azure credential for testing."""
    credential = MagicMock()
    credential.get_token = MagicMock(
        return_value=MagicMock(token="mock_token", expires_on=9999999999)
    )
    return credential
