"""Redis client with Entra ID authentication."""

import asyncio
from typing import Any

import redis.asyncio as redis
from azure.identity.aio import DefaultAzureCredential


class RedisClient:
    """Redis client with Azure Entra ID authentication support."""
    
    def __init__(self, host: str, port: int = 10000):
        """Initialize Redis client configuration."""
        self.host = host
        self.port = port
        self.client: redis.Redis | None = None
        self.credential: DefaultAzureCredential | None = None
        self._token_cache: dict[str, Any] = {}
        self._token_lock = asyncio.Lock()
    
    async def _get_entra_token(self) -> str:
        """Get Entra ID token for Redis authentication."""
        async with self._token_lock:
            # Check if we have a valid cached token
            if self._token_cache.get("token") and self._token_cache.get("expires_on", 0) > asyncio.get_event_loop().time():
                return str(self._token_cache["token"])
            
            # Get new token
            if not self.credential:
                self.credential = DefaultAzureCredential()
            
            token = await self.credential.get_token("https://redis.azure.com/.default")
            
            # Cache the token
            self._token_cache = {
                "token": token.token,
                "expires_on": token.expires_on,
            }
            
            return token.token
    
    async def connect(self):
        """Connect to Redis with Entra ID authentication."""
        try:
            # Get Entra ID token
            token = await self._get_entra_token()
            
            # Create Redis client with token as password
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                ssl=True,
                ssl_cert_reqs="required",
                username=token,  # Use token as username for Entra ID auth
                password="",  # Empty password for Entra ID auth
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            
            # Test connection
            await self.client.ping()
            
        except Exception as e:
            if self.client:
                await self.client.close()
                self.client = None
            raise Exception(f"Failed to connect to Redis: {str(e)}") from e
    
    async def get(self, key: str) -> str | None:
        """Get value from Redis."""
        if not self.client:
            raise Exception("Redis client not connected")
        
        try:
            value = await self.client.get(key)
            return value.decode() if value else None
        except redis.ConnectionError:
            # Try to reconnect with fresh token
            await self.connect()
            value = await self.client.get(key)
            return value.decode() if value else None
    
    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """Set value in Redis."""
        if not self.client:
            raise Exception("Redis client not connected")
        
        try:
            result = await self.client.set(key, value, ex=ex)
            return bool(result)
        except redis.ConnectionError:
            # Try to reconnect with fresh token
            await self.connect()
            result = await self.client.set(key, value, ex=ex)
            return bool(result)
    
    async def increment(self, key: str) -> int:
        """Increment counter in Redis."""
        if not self.client:
            raise Exception("Redis client not connected")
        
        try:
            result = await self.client.incr(key)
            return int(result)
        except redis.ConnectionError:
            # Try to reconnect with fresh token
            await self.connect()
            result = await self.client.incr(key)
            return int(result)
    
    async def ping(self) -> bool:
        """Ping Redis to check connection."""
        if not self.client:
            raise Exception("Redis client not connected")
        
        try:
            result = await self.client.ping()
            return bool(result)
        except redis.ConnectionError:
            # Try to reconnect with fresh token
            await self.connect()
            result = await self.client.ping()
            return bool(result)
    
    async def close(self):
        """Close Redis connection and cleanup."""
        if self.client:
            await self.client.close()
            self.client = None
        
        if self.credential:
            await self.credential.close()
            self.credential = None