"""Unit tests for Redis client."""

from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as redis

from app.redis_client import RedisClient


@pytest.fixture
def redis_client_instance():
    """Create Redis client instance."""
    return RedisClient("test.redis.azure.com", 10000)


@pytest.mark.asyncio
async def test_get_entra_token(redis_client_instance, mock_azure_credential):
    """Test Entra ID token retrieval."""
    redis_client_instance.credential = mock_azure_credential

    token = await redis_client_instance._get_entra_token()
    assert token == "mock_token"

    # Verify get_token was called
    mock_azure_credential.get_token.assert_called_once_with(
        "https://redis.azure.com/.default"
    )


@pytest.mark.asyncio
async def test_get_entra_token_caching(redis_client_instance, mock_azure_credential):
    """Test Entra ID token caching."""
    redis_client_instance.credential = mock_azure_credential

    # First call should get new token
    token1 = await redis_client_instance._get_entra_token()
    assert token1 == "mock_token"
    assert mock_azure_credential.get_token.call_count == 1

    # Second call should use cached token
    token2 = await redis_client_instance._get_entra_token()
    assert token2 == "mock_token"
    assert mock_azure_credential.get_token.call_count == 1  # Still 1, not 2


@pytest.mark.asyncio
async def test_connect_success(redis_client_instance, mock_azure_credential):
    """Test successful Redis connection."""
    redis_client_instance.credential = mock_azure_credential

    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        # from_url は同期関数としてクライアントを返す
        mock_from_url.return_value = mock_redis

        with patch.dict("os.environ", {"AZURE_CLIENT_ID": "test-client-id"}):
            await redis_client_instance.connect()

        # Verify Redis client was created with correct parameters
        mock_from_url.assert_called_once()
        call_args = mock_from_url.call_args
        assert "rediss://test.redis.azure.com:10000" in call_args[0]
        call_kwargs = mock_from_url.call_args.kwargs
        assert call_kwargs["username"] == "test-client-id"
        assert call_kwargs["password"] == "mock_token"
        assert call_kwargs["decode_responses"] is True

        # Verify ping was called
        mock_redis.ping.assert_called_once()


@pytest.mark.asyncio
async def test_connect_failure(redis_client_instance, mock_azure_credential):
    """Test Redis connection failure."""
    redis_client_instance.credential = mock_azure_credential

    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = redis.ConnectionError("Connection failed")
        # from_url は同期関数としてクライアントを返す
        mock_from_url.return_value = mock_redis

        with patch.dict("os.environ", {"AZURE_CLIENT_ID": "test-client-id"}):
            with pytest.raises(Exception) as exc_info:
                await redis_client_instance.connect()

        assert "Failed to connect to Redis" in str(exc_info.value)
        # aclose is called in the exception handler
        mock_redis.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_get_operation(redis_client_instance):
    """Test Redis get operation."""
    mock_redis = AsyncMock()
    # With decode_responses=True, Redis returns strings
    mock_redis.get.return_value = "test_value"
    redis_client_instance.client = mock_redis

    result = await redis_client_instance.get("test_key")
    assert result == "test_value"
    mock_redis.get.assert_called_once_with("test_key")


@pytest.mark.asyncio
async def test_set_operation(redis_client_instance):
    """Test Redis set operation."""
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True
    redis_client_instance.client = mock_redis

    result = await redis_client_instance.set("test_key", "test_value", ex=60)
    assert result is True
    mock_redis.set.assert_called_once_with("test_key", "test_value", ex=60)


@pytest.mark.asyncio
async def test_increment_operation(redis_client_instance):
    """Test Redis increment operation."""
    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 5
    redis_client_instance.client = mock_redis

    result = await redis_client_instance.increment("counter_key")
    assert result == 5
    mock_redis.incr.assert_called_once_with("counter_key")


@pytest.mark.asyncio
async def test_operation_with_error(redis_client_instance):
    """Test Redis operation with connection error."""
    mock_redis = AsyncMock()
    # Redis will fail with connection error
    mock_redis.get.side_effect = redis.ConnectionError("Lost connection")
    redis_client_instance.client = mock_redis

    # Operation should raise the exception (redis-py handles retries internally)
    with pytest.raises(redis.ConnectionError) as exc_info:
        await redis_client_instance.get("test_key")

    assert "Lost connection" in str(exc_info.value)
    mock_redis.get.assert_called_once_with("test_key")


@pytest.mark.asyncio
async def test_operation_without_client(redis_client_instance):
    """Test Redis operation when client is not initialized."""
    redis_client_instance.client = None

    with pytest.raises(Exception) as exc_info:
        await redis_client_instance.get("test_key")

    assert "Redis client not initialized" in str(exc_info.value)


@pytest.mark.asyncio
async def test_reset_connections(redis_client_instance):
    """Test Redis connection reset."""
    mock_redis = AsyncMock()
    redis_client_instance.client = mock_redis
    redis_client_instance._connection_count = 3

    # Mock connection pool with disconnect method
    mock_pool = AsyncMock()
    mock_pool.disconnect.return_value = 3
    mock_redis.connection_pool = mock_pool

    result = await redis_client_instance.reset_connections()

    assert result == 3
    mock_pool.disconnect.assert_called_once()
    assert redis_client_instance.client is not None  # Client instance is preserved
    assert redis_client_instance._connection_count == 0


@pytest.mark.asyncio
async def test_reset_connections_no_client(redis_client_instance):
    """Test Redis connection reset when client is not connected."""
    result = await redis_client_instance.reset_connections()

    assert result == 0
    assert redis_client_instance.client is None


@pytest.mark.asyncio
async def test_reset_connections_with_error(redis_client_instance):
    """Test Redis connection reset with error during disconnect."""
    mock_redis = AsyncMock()
    redis_client_instance.client = mock_redis
    redis_client_instance._connection_count = 2

    # Mock connection pool with disconnect that raises error
    mock_pool = AsyncMock()
    mock_pool.disconnect.side_effect = Exception("Disconnect failed")
    mock_redis.connection_pool = mock_pool

    with pytest.raises(Exception) as exc_info:
        await redis_client_instance.reset_connections()

    assert "Disconnect failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_close(redis_client_instance, mock_azure_credential):
    """Test Redis client cleanup."""
    mock_redis = AsyncMock()
    redis_client_instance.client = mock_redis
    redis_client_instance.credential = mock_azure_credential

    await redis_client_instance.close()

    mock_redis.aclose.assert_called_once()
    mock_azure_credential.close.assert_called_once()
    assert redis_client_instance.client is None
    assert redis_client_instance.credential is None
