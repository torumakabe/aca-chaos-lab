"""Pytest configuration and fixtures."""

from unittest.mock import AsyncMock

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
