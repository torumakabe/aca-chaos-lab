"""Main FastAPI application module."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.chaos import router as chaos_router
from app.config import Settings
from app.models import ErrorResponse, HealthResponse, MainResponse
from app.redis_client import RedisClient
from app.telemetry import record_span_error, setup_telemetry

# Global instances
settings = Settings()
redis_client: RedisClient | None = None

# Health check cache to reduce Redis ping frequency
# Health check cache (5-second TTL to reduce Redis load)
_health_cache: dict[str, Any] = {}
_HEALTH_CACHE_TTL = 5.0  # seconds


def _is_health_cache_valid() -> bool:
    """Check if cached health status is still valid."""
    timestamp = _health_cache.get("timestamp")
    if timestamp is None or not isinstance(timestamp, int | float):
        return False

    current_time = asyncio.get_event_loop().time()
    return bool((current_time - timestamp) < _HEALTH_CACHE_TTL)


def _update_health_cache(health_response: HealthResponse) -> None:
    """Update health cache with new response."""
    current_time = asyncio.get_event_loop().time()
    _health_cache["status"] = health_response
    _health_cache["timestamp"] = current_time
    _health_cache["ttl"] = _HEALTH_CACHE_TTL


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifespan manager."""
    global redis_client

    # Startup
    logger.info("Starting Azure Container Apps Chaos Lab")

    # Setup Redis
    if settings.redis_enabled:
        logger.info(
            f"Setting up Redis client for {settings.redis_host}:{settings.redis_port}"
        )
        redis_client = RedisClient(settings.redis_host, settings.redis_port, settings)

        try:
            await redis_client.connect()
            logger.info("Successfully connected to Redis at startup")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis at startup: {e}")
            logger.info("Redis connection will be retried on first use")
            # Continue startup - connection will be retried on first operation
    else:
        logger.info("Redis is disabled via REDIS_ENABLED setting")

    yield

    # Shutdown
    logger.info("Shutting down Azure Container Apps Chaos Lab")
    if redis_client:
        await redis_client.close()


app = FastAPI(
    title="Azure Container Apps Chaos Lab",
    version="0.1.0",
    lifespan=lifespan,
)

# Setup telemetry after app creation
setup_telemetry(app)

# Include chaos router
app.include_router(chaos_router)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all uncaught exceptions with standardized error response."""
    logger.exception(f"Unhandled exception: {exc}")

    # Record error in OpenTelemetry span
    record_span_error(exc)

    error_response = ErrorResponse(
        error="Internal Server Error",
        detail=str(exc) if settings.log_level == "DEBUG" else None,
        timestamp=datetime.now(UTC).isoformat(),
        request_id=request.headers.get("X-Request-ID"),
    )

    return JSONResponse(
        status_code=500, content=error_response.model_dump(exclude_none=True)
    )


@app.get("/", response_model=MainResponse)
async def root(request: Request):
    """Main endpoint that interacts with Redis."""
    timestamp = datetime.now(UTC).isoformat()
    redis_data: str | None = "Redis unavailable"
    redis_error = None

    if redis_client and settings.redis_enabled:
        try:
            # Try to get data from Redis (redis-py will handle retries internally)
            key = "chaos_lab:data:sample"
            redis_data = await redis_client.get(key)

            if not redis_data:
                # Set initial data if not exists
                redis_data = f"Data created at {timestamp}"
                await redis_client.set(key, redis_data)

            # Redis optimization: Only increment counter for ~10% of requests to reduce load
            # This represents a 90% reduction in Redis operations for request counting
            if hash(timestamp[:19]) % 10 == 0:  # ~10% of requests
                await redis_client.increment("chaos_lab:counter:requests")

        except Exception as e:
            # Log error
            logger.error(f"Redis operation failed: {e}")
            redis_error = str(e)

    # If Redis is enabled but we have an error, return 503
    if settings.redis_enabled and redis_error:
        error_response = ErrorResponse(
            error="Service Unavailable",
            detail=f"Redis operation failed: {redis_error}",
            timestamp=timestamp,
            request_id=request.headers.get("X-Request-ID"),
        )
        return JSONResponse(
            status_code=503, content=error_response.model_dump(exclude_none=True)
        )

    return MainResponse(
        message="Hello from Container Apps Chaos Lab",
        redis_data=redis_data,
        timestamp=timestamp,
    )


@app.get("/health", response_model=HealthResponse)
async def health(_: Request):
    """Health check endpoint with caching to reduce Redis load."""
    # Check if we can use cached health status
    if _is_health_cache_valid() and _health_cache["status"]:
        return _health_cache["status"]

    redis_connected = False
    redis_latency_ms = 0

    if redis_client and settings.redis_enabled:
        try:
            start_time = asyncio.get_event_loop().time()
            await redis_client.ping()
            end_time = asyncio.get_event_loop().time()

            redis_connected = True
            redis_latency_ms = int((end_time - start_time) * 1000)
        except Exception:
            redis_connected = False

    # Determine overall health status
    status = "healthy" if not settings.redis_enabled or redis_connected else "unhealthy"

    # Build response
    health_response = HealthResponse(
        status=status,
        redis={
            "connected": redis_connected,
            "latency_ms": redis_latency_ms,
        },
        timestamp=datetime.now(UTC).isoformat(),
    )

    # Cache the result using helper function
    _update_health_cache(health_response)

    # Return 503 if unhealthy
    if status == "unhealthy":
        return JSONResponse(status_code=503, content=health_response.model_dump())

    return health_response
