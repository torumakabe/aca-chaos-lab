"""Unit tests for main FastAPI application."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_root_endpoint_without_redis(client):
    """Test root endpoint when Redis is disabled."""
    with patch("app.main.settings.redis_enabled", False):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Hello from Container Apps Chaos Lab"
        assert data["redis_data"] == "Redis unavailable"
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_root_endpoint_with_redis(client, mock_redis_client):
    """Test root endpoint with Redis connection."""
    with (
        patch("app.main.redis_client", mock_redis_client),
        patch("app.main.settings.redis_enabled", True),
    ):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Hello from Container Apps Chaos Lab"
        assert data["redis_data"] == "test_value"
        assert "timestamp" in data

        # Verify Redis operations were called
        mock_redis_client.get.assert_called_once()
        # Note: increment may not be called due to 90% reduction optimization


@pytest.mark.asyncio
async def test_root_endpoint_redis_failure(client):
    """Test root endpoint when Redis operations fail."""
    failing_redis = AsyncMock()
    failing_redis.get.side_effect = Exception("Redis connection failed")
    failing_redis.connect.side_effect = Exception("Cannot reconnect")

    with (
        patch("app.main.redis_client", failing_redis),
        patch("app.main.settings.redis_enabled", True),
    ):
        response = client.get("/")
        assert response.status_code == 503
        data = response.json()
        assert data["error"] == "Service Unavailable"
        assert "Redis operation failed" in data["detail"]
        assert "timestamp" in data


def test_health_endpoint_without_redis(client):
    """Test health endpoint when Redis is disabled."""
    with patch("app.main.settings.redis_enabled", False):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["redis"]["connected"] is False
        assert data["redis"]["latency_ms"] == 0
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_endpoint_with_redis(client, mock_redis_client):
    """Test health endpoint with Redis connection."""
    with (
        patch("app.main.redis_client", mock_redis_client),
        patch("app.main.settings.redis_enabled", True),
        patch("app.main._health_cache", {}),
    ):  # Clear cache for testing
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["redis"]["connected"] is True
        assert data["redis"]["latency_ms"] >= 0
        assert "timestamp" in data

        # Note: ping may be cached for 5 seconds to reduce Redis load


@pytest.mark.asyncio
async def test_health_endpoint_redis_failure(client):
    """Test health endpoint when Redis ping fails."""
    failing_redis = AsyncMock()
    failing_redis.ping.side_effect = Exception("Redis connection failed")

    with (
        patch("app.main.redis_client", failing_redis),
        patch("app.main.settings.redis_enabled", True),
        patch("app.main._health_cache", {}),
    ):  # Clear cache for testing
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["redis"]["connected"] is False
        assert data["redis"]["latency_ms"] == 0
