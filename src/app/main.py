"""Main FastAPI application module."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from app.chaos import router as chaos_router
from app.config import Settings
from app.models import HealthResponse, MainResponse
from app.redis_client import RedisClient
from app.telemetry import setup_telemetry

# Global instances
settings = Settings()
redis_client: RedisClient | None = None
tracer = None

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global redis_client

    # Startup
    logger.info("Starting Azure Container Apps Chaos Lab")

    # Setup Redis
    if settings.redis_enabled:
        logger.info(
            f"Attempting to connect to Redis at {settings.redis_host}:{settings.redis_port}"
        )
        redis_client = RedisClient(settings.redis_host, settings.redis_port)
        try:
            await redis_client.connect()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.exception("Redis connection error details:")
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
tracer = setup_telemetry(app)

# Include chaos router
app.include_router(chaos_router)


@app.get("/", response_model=MainResponse)
async def root():
    """Main endpoint that interacts with Redis."""
    if tracer:
        with tracer.start_as_current_span("root_endpoint") as span:
            return await _root_with_span(span)
    else:
        return await _root_with_span(None)


async def _root_with_span(span):
    """Internal root handler with optional span."""
    timestamp = datetime.now(UTC).isoformat()
    redis_data = "Redis unavailable"

    if span:
        span.set_attribute("app.endpoint", "/")
        span.set_attribute("app.timestamp", timestamp)

    if redis_client and settings.redis_enabled:
        try:
            # Try to get data from Redis
            key = "chaos_lab:data:sample"
            redis_data = await redis_client.get(key)

            if not redis_data:
                # Set initial data if not exists
                redis_data = f"Data created at {timestamp}"
                await redis_client.set(key, redis_data)
                if span:
                    span.add_event("Created new Redis data")

            # Increment request counter
            counter = await redis_client.increment("chaos_lab:counter:requests")
            if span:
                span.set_attribute("app.request_count", counter)

        except Exception as e:
            # Log error but don't fail the request
            logger.error(f"Redis operation failed: {e}")
            redis_data = "Redis unavailable"
            if span:
                span.record_exception(e)
                span.set_attribute("app.redis_error", str(e))

    return MainResponse(
        message="Hello from Container Apps Chaos Lab",
        redis_data=redis_data,
        timestamp=timestamp,
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    if tracer:
        with tracer.start_as_current_span("health_check") as span:
            return await _health_with_span(span)
    else:
        return await _health_with_span(None)


async def _health_with_span(span):
    """Internal health check handler with optional span."""
    redis_connected = False
    redis_latency_ms = 0

    if span:
        span.set_attribute("app.endpoint", "/health")

    if redis_client and settings.redis_enabled:
        try:
            start_time = asyncio.get_event_loop().time()
            await redis_client.ping()
            end_time = asyncio.get_event_loop().time()

            redis_connected = True
            redis_latency_ms = int((end_time - start_time) * 1000)

            if span:
                span.set_attribute("app.redis_connected", True)
                span.set_attribute("app.redis_latency_ms", redis_latency_ms)
        except Exception as e:
            redis_connected = False
            if span:
                span.set_attribute("app.redis_connected", False)
                span.record_exception(e)

    # Determine overall health status
    status = "healthy" if not settings.redis_enabled or redis_connected else "unhealthy"

    if span:
        span.set_attribute("app.health_status", status)

    return HealthResponse(
        status=status,
        redis={
            "connected": redis_connected,
            "latency_ms": redis_latency_ms,
        },
        timestamp=datetime.now(UTC).isoformat(),
    )
