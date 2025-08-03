"""Basic API integration tests."""

import os
import sys
from typing import Any

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from azd_env_helper import load_azd_environment

# Load environment from azd
azd_env = load_azd_environment()

# Test configuration from environment
BASE_URL = os.getenv("TEST_BASE_URL") or azd_env.get(
    "CONTAINER_APP_URI", "http://localhost:8000"
)


class APIClient:
    """Simple HTTP client for API testing."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_health(self) -> dict[str, Any]:
        """Get health status."""
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return dict(response.json())

    async def get_main(self) -> dict[str, Any]:
        """Get main endpoint."""
        response = await self.client.get(f"{self.base_url}/")
        response.raise_for_status()
        return dict(response.json())

    async def get_chaos_status(self) -> dict[str, Any]:
        """Get chaos status."""
        response = await self.client.get(f"{self.base_url}/chaos/status")
        response.raise_for_status()
        return dict(response.json())

    async def close(self):
        """Close the client."""
        await self.client.aclose()


@pytest.fixture
async def api_client():
    """Create API client."""
    client = APIClient(BASE_URL)
    yield client
    await client.close()


@pytest.mark.asyncio
class TestBasicAPI:
    """Test basic API functionality."""

    async def test_health_endpoint(self, api_client):
        """Test health endpoint returns expected structure."""
        health = await api_client.get_health()

        assert health["status"] in ["healthy", "unhealthy"]
        assert "timestamp" in health
        assert "redis" in health
        assert isinstance(health["redis"]["connected"], bool)

    async def test_main_endpoint(self, api_client):
        """Test main endpoint returns expected data."""
        data = await api_client.get_main()

        assert data["message"] == "Hello from Container Apps Chaos Lab"
        assert "timestamp" in data
        # redis_data might be None if Redis is not configured

    async def test_chaos_status_initial(self, api_client):
        """Test chaos status endpoint returns expected structure."""
        status = await api_client.get_chaos_status()

        assert "load" in status
        assert "hang" in status
        assert isinstance(status["load"]["active"], bool)
        assert isinstance(status["hang"]["active"], bool)
        assert "level" in status["load"]
        assert "remaining_seconds" in status["load"]
