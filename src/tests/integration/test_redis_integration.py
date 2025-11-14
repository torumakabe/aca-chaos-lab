"""Integration tests for Redis client."""

import pytest
from redis.asyncio import Redis

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
class TestRedisIntegration:
    """Test Redis client integration with real Redis."""

    async def test_redis_connection(self, redis_client):
        """Test basic Redis connection."""
        result = await redis_client.ping()
        assert result is True

    async def test_redis_set_get(self, redis_client):
        """Test Redis SET and GET operations."""
        await redis_client.set("test_key", "test_value")
        value = await redis_client.get("test_key")
        assert value == "test_value"

    async def test_redis_delete(self, redis_client):
        """Test Redis DELETE operation."""
        await redis_client.set("delete_test", "value")
        await redis_client.delete("delete_test")
        value = await redis_client.get("delete_test")
        assert value is None

    async def test_redis_incr(self, redis_client):
        """Test Redis INCR operation."""
        await redis_client.set("counter", "0")
        result = await redis_client.incr("counter")
        assert result == 1
        result = await redis_client.incr("counter")
        assert result == 2

    async def test_create_direct_redis_client(self, redis_host_port):
        """Test creating Redis client directly."""
        host, port = redis_host_port

        # Create client without SSL for local testing
        client = Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

        try:
            # Test connection
            result = await client.ping()
            assert result is True

            # Test operations
            await client.set("integration_test", "success")
            value = await client.get("integration_test")
            assert value == "success"
        finally:
            await client.aclose()
