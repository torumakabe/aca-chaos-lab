"""Pytest configuration for integration tests."""

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def redis_container():
    """Start Redis container for integration tests."""
    container = RedisContainer("redis:7-alpine")
    container.start()
    yield container
    container.stop()


@pytest_asyncio.fixture(scope="function")
async def redis_client(redis_container):
    """Create Redis client connected to test container."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    
    client = Redis(
        host=host,
        port=int(port),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    
    # Verify connection
    await client.ping()
    
    yield client
    
    # Cleanup
    await client.flushall()
    await client.aclose()


@pytest.fixture
def redis_host_port(redis_container) -> tuple[str, int]:
    """Get Redis host and port for app testing."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return host, int(port)
