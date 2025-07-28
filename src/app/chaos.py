"""Chaos engineering endpoints for load simulation and fault injection."""

import asyncio
import hashlib
import logging
import random
import time
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models import (
    ChaosStatusResponse,
    HangRequest,
    LoadRequest,
    LoadResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chaos", tags=["chaos"])


class ChaosState:
    """Global state for chaos operations."""

    def __init__(self):
        self.load_active = False
        self.load_level = "low"
        self.load_end_time: datetime | None = None
        self.hang_active = False
        self.hang_end_time: datetime | None = None
        self._load_task: asyncio.Task | None = None
        self._hang_task: asyncio.Task | None = None


# Global chaos state
chaos_state = ChaosState()


async def generate_cpu_load(level: str, duration: int):
    """Generate CPU load based on the specified level."""
    logger.info(f"Starting CPU load generation: level={level}, duration={duration}s")

    # Determine load intensity
    intensity = {
        "low": 0.3,  # 30% CPU
        "medium": 0.6,  # 60% CPU
        "high": 0.9,  # 90% CPU
    }.get(level, 0.3)

    start_time = time.time()
    end_time = start_time + duration

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


async def generate_memory_load(level: str, duration: int):
    """Generate memory load based on the specified level."""
    logger.info(f"Starting memory load generation: level={level}, duration={duration}s")

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


async def load_generator(level: str, duration: int):
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
async def start_load(request: LoadRequest):
    """Start load simulation."""
    if chaos_state.load_active:
        raise HTTPException(status_code=409, detail="Load simulation already active")

    if request.level not in ["low", "medium", "high"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid load level. Must be 'low', 'medium', or 'high'",
        )

    if request.duration_seconds <= 0 or request.duration_seconds > 3600:
        raise HTTPException(
            status_code=400, detail="Duration must be between 1 and 3600 seconds"
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
async def hang(request: HangRequest):
    """Cause the application to hang/become unresponsive."""
    if chaos_state.hang_active:
        raise HTTPException(status_code=409, detail="Hang already active")

    chaos_state.hang_active = True
    if request.duration_seconds > 0:
        chaos_state.hang_end_time = datetime.now(UTC) + timedelta(
            seconds=request.duration_seconds
        )
    else:
        chaos_state.hang_end_time = None  # Permanent hang

    logger.warning(f"Entering hang state for {request.duration_seconds}s (0=permanent)")

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


@router.get("/status", response_model=ChaosStatusResponse)
async def get_status():
    """Get current chaos status."""
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

    return ChaosStatusResponse(
        load={
            "active": chaos_state.load_active,
            "level": chaos_state.load_level if chaos_state.load_active else "none",
            "remaining_seconds": load_remaining,
        },
        hang={"active": chaos_state.hang_active, "remaining_seconds": hang_remaining},
    )
