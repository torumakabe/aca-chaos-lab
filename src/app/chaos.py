"""Chaos engineering endpoints for load simulation and fault injection."""

import asyncio
import hashlib
import logging
import random
import time
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.models import (
    ChaosStatusResponse,
    ErrorResponse,
    HangRequest,
    LoadRequest,
    LoadResponse,
    RedisResetRequest,
    RedisResetResponse,
)
from app.telemetry import record_chaos_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chaos", tags=["chaos"])


class ChaosState:
    """Global state for chaos operations."""

    def __init__(self) -> None:
        self.load_active = False
        self.load_level = "low"
        self.load_end_time: datetime | None = None
        self.hang_active = False
        self.hang_end_time: datetime | None = None
        self._load_task: asyncio.Task | None = None
        self._hang_task: asyncio.Task | None = None
        self.redis_last_reset: datetime | None = None


# Global chaos state
chaos_state = ChaosState()


async def generate_cpu_load(level: str, duration: int) -> None:
    """Generate CPU load based on the specified level."""
    logger.info(f"Starting CPU load generation: level={level}, duration={duration}s")

    # Record start of chaos operation
    record_chaos_metrics("cpu_load", True)

    # Determine load intensity
    intensity = {
        "low": 0.3,  # 30% CPU
        "medium": 0.6,  # 60% CPU
        "high": 0.9,  # 90% CPU
    }.get(level, 0.3)

    start_time = time.time()
    end_time = start_time + duration

    try:
        while time.time() < end_time and chaos_state.load_active:
            # CPU-intensive operations
            work_duration = 0.1 * intensity  # Work for portion of time
            sleep_duration = 0.1 * (1 - intensity)  # Sleep for remaining time

            # Do CPU-intensive work
            work_start = time.time()
            while time.time() - work_start < work_duration:
                # Hash computation to consume CPU
                _ = hashlib.sha256(f"{random.random()}".encode()).hexdigest()  # noqa: S311

            # Sleep to control CPU usage
            await asyncio.sleep(sleep_duration)

        logger.info("CPU load generation completed")
    finally:
        # Record end of chaos operation
        actual_duration = time.time() - start_time
        record_chaos_metrics("cpu_load", False, actual_duration)


async def generate_memory_load(level: str, duration: int) -> None:
    """Generate memory load based on the specified level."""
    logger.info(f"Starting memory load generation: level={level}, duration={duration}s")

    # Record start of chaos operation
    record_chaos_metrics("memory_load", True)

    # Determine memory allocation in MB
    memory_mb = {
        "low": 100,  # 100MB
        "medium": 500,  # 500MB
        "high": 1000,  # 1GB
    }.get(level, 100)

    # Allocate memory
    memory_blocks = []
    block_size = 10 * 1024 * 1024  # 10MB blocks
    num_blocks = memory_mb // 10

    start_time = time.time()
    try:
        for _ in range(num_blocks):
            # Allocate and fill memory block
            block = bytearray(block_size)
            # Fill with random data to prevent optimization
            for i in range(0, block_size, 1024):
                block[i : i + 1024] = random.randbytes(min(1024, block_size - i))  # noqa: S311
            memory_blocks.append(block)

        # Hold memory for duration
        await asyncio.sleep(duration)

    finally:
        # Clear memory
        memory_blocks.clear()
        logger.info("Memory load generation completed")

        # Record end of chaos operation
        actual_duration = time.time() - start_time
        record_chaos_metrics("memory_load", False, actual_duration)


async def load_generator(level: str, duration: int) -> None:
    """Main load generator that combines CPU and memory load."""
    try:
        chaos_state.load_active = True
        chaos_state.load_level = level
        chaos_state.load_end_time = datetime.now(UTC) + timedelta(seconds=duration)

        # Run CPU and memory load concurrently
        await asyncio.gather(
            generate_cpu_load(level, duration), generate_memory_load(level, duration)
        )

    finally:
        chaos_state.load_active = False
        chaos_state.load_end_time = None
        chaos_state._load_task = None


@router.post("/load", response_model=LoadResponse)
async def start_load(request: LoadRequest, req: Request):
    """Start load simulation."""
    if chaos_state.load_active:
        error_response = ErrorResponse(
            error="Conflict",
            detail="Load simulation already active",
            timestamp=datetime.now(UTC).isoformat(),
            request_id=req.headers.get("X-Request-ID"),
        )
        return JSONResponse(
            status_code=409, content=error_response.model_dump(exclude_none=True)
        )

    if request.level not in ["low", "medium", "high"]:
        error_response = ErrorResponse(
            error="Bad Request",
            detail="Invalid load level. Must be 'low', 'medium', or 'high'",
            timestamp=datetime.now(UTC).isoformat(),
            request_id=req.headers.get("X-Request-ID"),
        )
        return JSONResponse(
            status_code=400, content=error_response.model_dump(exclude_none=True)
        )

    if request.duration_seconds <= 0 or request.duration_seconds > 3600:
        error_response = ErrorResponse(
            error="Bad Request",
            detail="Duration must be between 1 and 3600 seconds",
            timestamp=datetime.now(UTC).isoformat(),
            request_id=req.headers.get("X-Request-ID"),
        )
        return JSONResponse(
            status_code=400, content=error_response.model_dump(exclude_none=True)
        )

    # Start load generation in background
    chaos_state._load_task = asyncio.create_task(
        load_generator(request.level, request.duration_seconds)
    )

    logger.info(
        f"Load simulation started: level={request.level}, duration={request.duration_seconds}s"
    )

    return LoadResponse(
        status="load_started",
        level=request.level,
        duration_seconds=request.duration_seconds,
    )


@router.post("/hang")
async def hang(request: HangRequest, req: Request) -> JSONResponse:
    """Cause the application to hang/become unresponsive."""
    if chaos_state.hang_active:
        error_response = ErrorResponse(
            error="Conflict",
            detail="Hang already active",
            timestamp=datetime.now(UTC).isoformat(),
            request_id=req.headers.get("X-Request-ID"),
        )
        return JSONResponse(
            status_code=409, content=error_response.model_dump(exclude_none=True)
        )

    # Record start of hang operation
    record_chaos_metrics("hang", True)
    start_time = time.time()

    chaos_state.hang_active = True
    if request.duration_seconds > 0:
        chaos_state.hang_end_time = datetime.now(UTC) + timedelta(
            seconds=request.duration_seconds
        )
    else:
        chaos_state.hang_end_time = None  # Permanent hang

    logger.warning(f"Entering hang state for {request.duration_seconds}s (0=permanent)")

    try:
        # This endpoint will not return a response - it hangs
        if request.duration_seconds == 0:
            # Permanent hang
            while True:  # noqa: ASYNC110
                await asyncio.sleep(1)
        else:
            # Timed hang
            await asyncio.sleep(request.duration_seconds)
            chaos_state.hang_active = False
            chaos_state.hang_end_time = None

        # This line should never be reached for permanent hangs
        return JSONResponse(content={"status": "hang_completed"})
    finally:
        # Record end of hang operation (if we ever get here)
        duration = time.time() - start_time
        record_chaos_metrics("hang", False, duration)


@router.post("/redis-reset", response_model=RedisResetResponse)
async def reset_redis_connections(
    req: Request, request: RedisResetRequest | None = None
):
    """Reset Redis connections."""
    from app.main import redis_client

    if not redis_client:
        error_response = ErrorResponse(
            error="Service Unavailable",
            detail="Redis client not initialized",
            timestamp=datetime.now(UTC).isoformat(),
            request_id=req.headers.get("X-Request-ID") if req else None,
        )
        return JSONResponse(
            status_code=503, content=error_response.model_dump(exclude_none=True)
        )

    try:
        # Record start of redis reset operation
        record_chaos_metrics("redis_reset", True)

        # Get force parameter
        force = True
        if request and hasattr(request, "force"):
            force = request.force

        start_time = time.time()

        # Reset connections
        connections_closed = await redis_client.reset_connections()

        # Update state
        chaos_state.redis_last_reset = datetime.now(UTC)

        # Record end of redis reset operation
        duration = time.time() - start_time
        record_chaos_metrics("redis_reset", False, duration)

        logger.info(
            f"Redis connections reset: {connections_closed} connections closed (force={force})"
        )

        return RedisResetResponse(
            status="redis_connections_reset",
            connections_closed=connections_closed,
            timestamp=chaos_state.redis_last_reset.isoformat(),
        )

    except Exception as e:
        # Record failed redis reset operation
        duration = time.time() - start_time if "start_time" in locals() else 0
        record_chaos_metrics("redis_reset", False, duration)

        logger.error(f"Redis reset failed: {e}")
        error_response = ErrorResponse(
            error="Internal Server Error",
            detail=f"Redis reset failed: {str(e)}",
            timestamp=datetime.now(UTC).isoformat(),
            request_id=req.headers.get("X-Request-ID") if req else None,
        )
        return JSONResponse(
            status_code=500, content=error_response.model_dump(exclude_none=True)
        )


@router.get("/status", response_model=ChaosStatusResponse)
async def get_status():
    """Get current chaos status."""
    from app.main import redis_client

    now = datetime.now(UTC)

    # Calculate remaining seconds for load
    load_remaining = 0
    if chaos_state.load_active and chaos_state.load_end_time:
        remaining = (chaos_state.load_end_time - now).total_seconds()
        load_remaining = max(0, int(remaining))

    # Calculate remaining seconds for hang
    hang_remaining = 0
    if chaos_state.hang_active and chaos_state.hang_end_time:
        remaining = (chaos_state.hang_end_time - now).total_seconds()
        hang_remaining = max(0, int(remaining))

    # Get Redis status
    redis_status = {"connected": False, "connection_count": 0, "last_reset": None}
    if redis_client:
        try:
            redis_status["connected"] = await redis_client.is_connected()
            redis_status["connection_count"] = redis_client._connection_count
        except Exception as e:
            logger.error(f"Failed to get Redis status: {e}")

    if chaos_state.redis_last_reset:
        redis_status["last_reset"] = chaos_state.redis_last_reset.isoformat()

    return ChaosStatusResponse(
        load={
            "active": chaos_state.load_active,
            "level": chaos_state.load_level if chaos_state.load_active else "none",
            "remaining_seconds": load_remaining,
        },
        hang={"active": chaos_state.hang_active, "remaining_seconds": hang_remaining},
        redis=redis_status,
    )
