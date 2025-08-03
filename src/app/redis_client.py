"""Redis client with Entra ID authentication."""

import asyncio
import logging
import time
from typing import Any

import redis.asyncio as redis
from azure.identity.aio import DefaultAzureCredential
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.telemetry import record_redis_metrics

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client with Azure Entra ID authentication support."""

    def __init__(self, host: str, port: int = 10000, settings=None):
        """Initialize Redis client configuration."""
        self.host = host
        self.port = port
        self.settings = settings
        self.client: redis.Redis | None = None
        self.credential: DefaultAzureCredential | None = None
        self._token_cache: dict[str, Any] = {}
        self._token_lock = asyncio.Lock()
        self._connection_count = 0
        self._connection_lock = asyncio.Lock()

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

            # Use connection pool settings from config or defaults
            max_connections = (
                getattr(self.settings, "redis_max_connections", 50)
                if self.settings
                else 50
            )
            socket_timeout = (
                getattr(self.settings, "redis_socket_timeout", 3)
                if self.settings
                else 3
            )
            socket_connect_timeout = (
                getattr(self.settings, "redis_socket_connect_timeout", 3)
                if self.settings
                else 3
            )

            # Configure retry with exponential backoff
            # Default: 1 retry with exponential backoff (1s base, 3s cap)
            max_retries = (
                getattr(self.settings, "redis_max_retries", 1) if self.settings else 1
            )
            backoff_base = (
                getattr(self.settings, "redis_backoff_base", 1) if self.settings else 1
            )
            backoff_cap = (
                getattr(self.settings, "redis_backoff_cap", 3) if self.settings else 3
            )

            retry_strategy = Retry(
                backoff=ExponentialBackoff(base=backoff_base, cap=backoff_cap),
                retries=max_retries,
            )

            # Create Redis client with connection pool
            # redis-py will manage the connection pool internally
            self.client = await redis.from_url(
                f"rediss://{self.host}:{self.port}",
                username=client_id,
                password=token,
                decode_responses=True,
                socket_connect_timeout=socket_connect_timeout,
                socket_timeout=socket_timeout,
                retry=retry_strategy,
                retry_on_error=[redis.ConnectionError, redis.TimeoutError],
                health_check_interval=30,
                max_connections=max_connections,
            )

            # Test connection
            logger.info("Testing Redis connection with ping")
            await self.client.ping()
            logger.info("Redis connection successful!")

            # Increment connection count
            self._connection_count += 1

        except Exception as e:
            logger.error(f"Redis connection failed: {str(e)}")
            if self.client:
                await self.client.aclose()
                self.client = None
            raise Exception(f"Failed to connect to Redis: {str(e)}") from e

    async def is_connected(self) -> bool:
        """Check if Redis client is connected."""
        if not self.client:
            record_redis_metrics(False, -1)
            return False
        try:
            start_time = time.time()
            await self.client.ping()
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            record_redis_metrics(True, latency_ms)
            return True
        except Exception:
            record_redis_metrics(False, -1)
            return False

    async def get(self, key: str) -> str | None:
        """Get value from Redis."""
        if not self.client:
            raise Exception("Redis client not initialized")

        value = await self.client.get(key)
        return value if value else None

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """Set value in Redis."""
        if not self.client:
            raise Exception("Redis client not initialized")

        result = await self.client.set(key, value, ex=ex)
        return bool(result)

    async def increment(self, key: str) -> int:
        """Increment counter in Redis."""
        if not self.client:
            raise Exception("Redis client not initialized")

        result = await self.client.incr(key)
        return int(result)

    async def ping(self) -> bool:
        """Ping Redis to check connection."""
        if not self.client:
            raise Exception("Redis client not initialized")

        start_time = time.time()
        try:
            result = await self.client.ping()
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            # Record metrics for successful ping
            record_redis_metrics(True, latency_ms)
            return bool(result)
        except Exception as e:
            # Record metrics for failed ping
            record_redis_metrics(False, -1)
            raise e

    async def reset_connections(self) -> int:
        """Reset all Redis connections."""
        async with self._connection_lock:
            closed_count = 0
            if self.client and hasattr(self.client, "connection_pool"):
                try:
                    logger.info("Resetting Redis connections")
                    pool = self.client.connection_pool

                    # Disconnect all connections in the pool
                    # This is the standard way to reset connections
                    # Note: pool.disconnect() returns None in redis-py
                    await pool.disconnect()

                    # Use our connection count tracker
                    closed_count = self._connection_count
                    self._connection_count = 0

                    logger.info(
                        f"Redis connections reset: {closed_count} connections closed"
                    )
                except Exception as e:
                    logger.error(f"Error during Redis reset: {e}")
                    raise

            return closed_count

    async def close(self):
        """Close Redis connection and cleanup."""
        if self.client:
            await self.client.aclose()
            self.client = None

        if self.credential:
            await self.credential.close()
            self.credential = None
