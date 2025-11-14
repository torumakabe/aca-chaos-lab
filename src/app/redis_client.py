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

    def __init__(
        self,
        host: str,
        port: int = 10000,
        settings=None,
        use_entra_auth: bool = True,
        password: str | None = None,
    ):
        """Initialize Redis client configuration.

        Args:
            host: Redis server hostname
            port: Redis server port
            settings: Application settings object
            use_entra_auth: If True, use Entra ID authentication (default).
                          If False, use Access Key authentication (for testing)
            password: Access key password (only used when use_entra_auth=False)
        """
        self.host = host
        self.port = port
        self.settings = settings
        self.use_entra_auth = use_entra_auth
        self.password = password
        self.client: redis.Redis | None = None
        self.credential: DefaultAzureCredential | None = None
        self._token_cache: dict[str, Any] = {}
        self._token_lock = asyncio.Lock()
        self._connection_count = 0
        self._connection_lock = asyncio.Lock()

    def _is_auth_error(self, exc: Exception) -> bool:
        """Detect if the exception indicates an authentication problem."""
        if isinstance(exc, redis.AuthenticationError):
            return True
        # Some servers return ResponseError with NOAUTH/WRONGPASS messages
        if isinstance(exc, redis.ResponseError):
            msg = str(exc).upper()
            return "NOAUTH" in msg or "WRONGPASS" in msg or "AUTH" in msg
        return False

    async def _reconnect_with_new_token(self) -> None:
        """Reconnect Redis client with a fresh Entra ID token."""
        # Get Entra ID token
        token = await self._get_entra_token()

        # Recreate client (same options as connect())
        import os

        client_id = os.getenv("AZURE_CLIENT_ID", "")

        max_connections = (
            getattr(self.settings, "redis_max_connections", 50) if self.settings else 50
        )
        socket_timeout = (
            getattr(self.settings, "redis_socket_timeout", 3) if self.settings else 3
        )
        socket_connect_timeout = (
            getattr(self.settings, "redis_socket_connect_timeout", 3)
            if self.settings
            else 3
        )

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

        self.client = redis.from_url(
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

        # Validate connection
        _ = await self.client.ping()  # type: ignore[misc]
        self._connection_count += 1

    async def _get_entra_token(self) -> str:
        """Get Entra ID token for Redis authentication.

        Uses epoch time (time.time) and a safety margin to determine cache validity.
        """
        async with self._token_lock:
            # Check if we have a valid cached token (with safety margin)
            cached_token = self._token_cache.get("token")
            expires_on = self._token_cache.get("expires_on", 0)
            now = time.time()
            safety_seconds = 120  # refresh 2 minutes before expiry to be safe

            if cached_token and float(expires_on) - safety_seconds > now:
                logger.debug("Using cached Entra ID token for Redis authentication")
                return str(cached_token)

            # Get new token
            logger.info("Getting new Entra ID token for Redis authentication")
            if not self.credential:
                self.credential = DefaultAzureCredential()

            token = await self.credential.get_token("https://redis.azure.com/.default")
            logger.info(
                f"Successfully obtained token, expires at (epoch): {token.expires_on}"
            )

            # Cache the token
            self._token_cache = {
                "token": token.token,
                "expires_on": token.expires_on,
            }

            return token.token

    async def _connect_with_access_key(self):
        """Connect to Redis using Access Key authentication (for testing)."""
        try:
            logger.info("Using Access Key authentication for Redis connection")

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

            # Determine SSL based on settings (default: no SSL for access key mode)
            use_ssl = (
                getattr(self.settings, "redis_ssl", False) if self.settings else False
            )
            protocol = "rediss" if use_ssl else "redis"

            # Create Redis client with Access Key authentication
            # For testing with Testcontainers, use redis:// (no SSL)
            connection_kwargs = {
                "decode_responses": True,
                "socket_connect_timeout": socket_connect_timeout,
                "socket_timeout": socket_timeout,
                "retry": retry_strategy,
                "retry_on_error": [redis.ConnectionError, redis.TimeoutError],
                "health_check_interval": 30,
                "max_connections": max_connections,
            }

            if self.password:
                connection_kwargs["password"] = self.password

            self.client = redis.from_url(
                f"{protocol}://{self.host}:{self.port}",
                **connection_kwargs,
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

    async def connect(self):
        """Connect to Redis with Entra ID or Access Key authentication."""
        try:
            logger.info(f"Connecting to Redis at {self.host}:{self.port}")

            # Use Access Key authentication for testing (no Entra ID)
            if not self.use_entra_auth:
                return await self._connect_with_access_key()

            # Get Entra ID token for production
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
            # NOTE: redis.asyncio.from_url is a synchronous factory that returns a client
            self.client = redis.from_url(
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
            _ = await self.client.ping()  # type: ignore[misc]
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
        try:
            value = await self.client.get(key)
            return value if value else None
        except Exception as e:
            if self._is_auth_error(e):
                # Single retry after re-authentication
                backoff = (
                    getattr(self.settings, "redis_backoff_base", 1)
                    if self.settings
                    else 1
                )
                await asyncio.sleep(backoff)
                await self._reconnect_with_new_token()
                value = await self.client.get(key)
                return value if value else None
            raise

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """Set value in Redis."""
        if not self.client:
            raise Exception("Redis client not initialized")
        try:
            result = await self.client.set(key, value, ex=ex)
            return bool(result)
        except Exception as e:
            if self._is_auth_error(e):
                backoff = (
                    getattr(self.settings, "redis_backoff_base", 1)
                    if self.settings
                    else 1
                )
                await asyncio.sleep(backoff)
                await self._reconnect_with_new_token()
                result = await self.client.set(key, value, ex=ex)
                return bool(result)
            raise

    async def increment(self, key: str) -> int:
        """Increment counter in Redis."""
        if not self.client:
            raise Exception("Redis client not initialized")
        try:
            result = await self.client.incr(key)
            return int(result)
        except Exception as e:
            if self._is_auth_error(e):
                backoff = (
                    getattr(self.settings, "redis_backoff_base", 1)
                    if self.settings
                    else 1
                )
                await asyncio.sleep(backoff)
                await self._reconnect_with_new_token()
                result = await self.client.incr(key)
                return int(result)
            raise

    async def incr(self, key: str) -> int:
        """Alias for increment method for consistency with redis-py API."""
        return await self.increment(key)

    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        if not self.client:
            raise Exception("Redis client not initialized")
        try:
            result = await self.client.delete(key)
            return bool(result)
        except Exception as e:
            if self._is_auth_error(e):
                backoff = (
                    getattr(self.settings, "redis_backoff_base", 1)
                    if self.settings
                    else 1
                )
                await asyncio.sleep(backoff)
                await self._reconnect_with_new_token()
                result = await self.client.delete(key)
                return bool(result)
            raise

    async def ping(self) -> bool:
        """Ping Redis to check connection."""
        if not self.client:
            raise Exception("Redis client not initialized")

        start_time = time.time()
        try:
            result: bool = await self.client.ping()  # type: ignore[misc]
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            # Record metrics for successful ping
            record_redis_metrics(True, latency_ms)
            return bool(result)
        except Exception as e:
            # Attempt re-auth once if the error is authentication-related
            if self._is_auth_error(e):
                backoff = (
                    getattr(self.settings, "redis_backoff_base", 1)
                    if self.settings
                    else 1
                )
                await asyncio.sleep(backoff)
                await self._reconnect_with_new_token()
                retry_result: bool = await self.client.ping()  # type: ignore[misc]
                end_time = time.time()
                latency_ms = int((end_time - start_time) * 1000)
                record_redis_metrics(True, latency_ms)
                return bool(retry_result)
            # Record metrics for failed ping
            record_redis_metrics(False, -1)
            raise

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
