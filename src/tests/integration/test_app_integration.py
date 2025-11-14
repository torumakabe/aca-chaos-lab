"""Integration tests for FastAPI app with real dependencies."""

import pytest
import pytest_asyncio

from app.redis_client import RedisClient

pytestmark = pytest.mark.integration


class TestAppIntegration:
    """Test FastAPI app integration with real Redis via Testcontainers."""

    @pytest_asyncio.fixture
    async def redis_test_client(self, redis_host_port):
        """Create RedisClient for testing with Testcontainers (Access Key auth)."""
        host, port = redis_host_port

        # Create test settings
        test_settings = type(
            "TestSettings",
            (),
            {
                "redis_host": host,
                "redis_port": port,
                "redis_ssl": False,  # Testcontainers uses plain Redis
                "redis_enabled": True,
                "redis_max_connections": 10,
                "redis_socket_timeout": 3,
                "redis_socket_connect_timeout": 3,
                "redis_max_retries": 1,
                "redis_backoff_base": 1,
                "redis_backoff_cap": 3,
            },
        )()

        # Use RedisClient with Access Key auth (no Entra ID, no password)
        client = RedisClient(
            host=host,
            port=port,
            settings=test_settings,
            use_entra_auth=False,  # Disable Entra ID for testing
            password=None,  # Testcontainers Redis has no password
        )

        await client.connect()
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_redis_client_basic_operations(self, redis_test_client):
        """Test RedisClient basic operations with Testcontainers."""
        # Test connection
        assert await redis_test_client.is_connected()

        # Test set/get
        await redis_test_client.set("test_key", "test_value")
        value = await redis_test_client.get("test_key")
        assert value == "test_value"

        # Test delete
        deleted = await redis_test_client.delete("test_key")
        assert deleted is True

        # Verify deletion
        value = await redis_test_client.get("test_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_redis_client_counter(self, redis_test_client):
        """Test RedisClient counter operations."""
        # Clean up first
        await redis_test_client.delete("test_counter")

        # Test increment
        count1 = await redis_test_client.incr("test_counter")
        assert count1 == 1

        count2 = await redis_test_client.incr("test_counter")
        assert count2 == 2

        # Clean up
        await redis_test_client.delete("test_counter")
