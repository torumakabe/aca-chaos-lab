"""Redis client with Entra ID authentication."""

import asyncio
import logging
from typing import Any

import redis.asyncio as redis
from azure.identity.aio import DefaultAzureCredential

logger = logging.getLogger(__name__)


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
            if (
                self._token_cache.get("token")
                and self._token_cache.get("expires_on", 0)
                > asyncio.get_event_loop().time()
            ):
                logger.debug("Using cached token")
                return str(self._token_cache["token"])

            # Get new token
            logger.info("Getting new Entra ID token for Redis authentication")
            if not self.credential:
                self.credential = DefaultAzureCredential()

            token = await self.credential.get_token("https://redis.azure.com/.default")
            logger.info(f"Successfully obtained token, expires at: {token.expires_on}")

            # Cache the token
            self._token_cache = {
                "token": token.token,
                "expires_on": token.expires_on,
            }

            return token.token

    async def connect(self):
        """Connect to Redis with Entra ID authentication."""
        try:
            logger.info(f"Connecting to Redis at {self.host}:{self.port}")

            # Get Entra ID token
            token = await self._get_entra_token()

            # Create Redis client with token as password
            logger.info("Creating Redis client with Entra ID authentication")
            # For Redis Enterprise, use the object ID as username
            import os

            client_id = os.getenv("AZURE_CLIENT_ID", "")
            logger.info(f"Using client ID: {client_id}")

            self.client = await redis.from_url(
                f"rediss://{self.host}:{self.port}",
                username=client_id,  # Use client ID as username for Redis Enterprise
                password=token,  # Use token as password
                decode_responses=True,
                socket_connect_timeout=10,  # Increased timeout
                socket_timeout=10,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Test connection
            logger.info("Testing Redis connection with ping")
            await self.client.ping()
            logger.info("Redis connection successful!")

        except Exception as e:
            logger.error(f"Redis connection failed: {str(e)}")
            if self.client:
                await self.client.aclose()
                self.client = None
            raise Exception(f"Failed to connect to Redis: {str(e)}") from e

    async def get(self, key: str) -> str | None:
        """Get value from Redis."""
        if not self.client:
            raise Exception("Redis client not connected")

        try:
            value = await self.client.get(key)
            return value if value else None
        except redis.ConnectionError:
            # Try to reconnect with fresh token
            await self.connect()
            value = await self.client.get(key)
            return value if value else None

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
            await self.client.aclose()
            self.client = None

        if self.credential:
            await self.credential.close()
            self.credential = None
