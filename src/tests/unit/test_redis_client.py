"""Unit tests for Redis client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
    mock_azure_credential.get_token.assert_called_once_with("https://redis.azure.com/.default")


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
    
    with patch("redis.asyncio.Redis") as mock_redis_class:
        mock_redis = AsyncMock()
        mock_redis_class.return_value = mock_redis
        
        await redis_client_instance.connect()
        
        # Verify Redis client was created with correct parameters
        mock_redis_class.assert_called_once()
        call_kwargs = mock_redis_class.call_args.kwargs
        assert call_kwargs["host"] == "test.redis.azure.com"
        assert call_kwargs["port"] == 10000
        assert call_kwargs["ssl"] is True
        assert call_kwargs["username"] == "mock_token"
        assert call_kwargs["password"] == ""
        
        # Verify ping was called
        mock_redis.ping.assert_called_once()


@pytest.mark.asyncio
async def test_connect_failure(redis_client_instance, mock_azure_credential):
    """Test Redis connection failure."""
    redis_client_instance.credential = mock_azure_credential
    
    with patch("redis.asyncio.Redis") as mock_redis_class:
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = redis.ConnectionError("Connection failed")
        mock_redis_class.return_value = mock_redis
        
        with pytest.raises(Exception) as exc_info:
            await redis_client_instance.connect()
        
        assert "Failed to connect to Redis" in str(exc_info.value)
        # close is called in the exception handler
        mock_redis.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_operation(redis_client_instance):
    """Test Redis get operation."""
    mock_redis = AsyncMock()
    # Redis returns bytes, not strings
    mock_redis.get.return_value = b"test_value"
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
async def test_operation_with_reconnect(redis_client_instance, mock_azure_credential):
    """Test Redis operation with automatic reconnection."""
    redis_client_instance.credential = mock_azure_credential
    
    mock_redis = AsyncMock()
    # First call fails with connection error, second returns bytes
    mock_redis.get.side_effect = [redis.ConnectionError("Lost connection"), b"test_value"]
    redis_client_instance.client = mock_redis
    
    with patch.object(redis_client_instance, "connect", new_callable=AsyncMock) as mock_connect:
        result = await redis_client_instance.get("test_key")
        assert result == "test_value"
        mock_connect.assert_called_once()
        assert mock_redis.get.call_count == 2


@pytest.mark.asyncio
async def test_close(redis_client_instance, mock_azure_credential):
    """Test Redis client cleanup."""
    mock_redis = AsyncMock()
    redis_client_instance.client = mock_redis
    redis_client_instance.credential = mock_azure_credential
    
    await redis_client_instance.close()
    
    mock_redis.close.assert_called_once()
    mock_azure_credential.close.assert_called_once()
    assert redis_client_instance.client is None
    assert redis_client_instance.credential is None