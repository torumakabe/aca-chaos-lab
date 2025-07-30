"""Pydantic models for API requests and responses."""


from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    redis: dict[str, bool | int]
    timestamp: str


class MainResponse(BaseModel):
    """Main endpoint response model."""

    message: str
    redis_data: str | None
    timestamp: str


class LoadRequest(BaseModel):
    """Load simulation request model."""

    level: str = "low"  # low, medium, high
    duration_seconds: int = 60


class LoadResponse(BaseModel):
    """Load simulation response model."""

    status: str
    level: str
    duration_seconds: int


class HangRequest(BaseModel):
    """Hang request model."""

    duration_seconds: int = 0  # 0 means permanent


class RedisResetRequest(BaseModel):
    """Redis connection reset request model."""

    force: bool = True


class RedisResetResponse(BaseModel):
    """Redis connection reset response model."""

    status: str
    connections_closed: int
    timestamp: str


class ChaosStatusResponse(BaseModel):
    """Chaos status response model."""

    load: dict[str, bool | str | int]
    hang: dict[str, bool | int]
    redis: dict[str, bool | int | str | None]


class ErrorResponse(BaseModel):
    """Standardized error response model."""

    error: str
    detail: str | None = None
    timestamp: str
    request_id: str | None = None
