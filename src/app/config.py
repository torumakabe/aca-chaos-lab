"""Application configuration."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.azd_env import get_azd_env_value


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application settings
    app_port: int = 8000
    log_level: str = "INFO"

    # Redis settings
    redis_host: str = get_azd_env_value(
        "AZURE_REDIS_HOST", os.getenv("REDIS_HOST", "localhost")
    )
    redis_port: int = int(
        get_azd_env_value("AZURE_REDIS_PORT", os.getenv("REDIS_PORT", "10000"))
    )
    redis_ssl: bool = os.getenv("REDIS_SSL", "true").lower() == "true"
    redis_enabled: bool = os.getenv("REDIS_ENABLED", "true").lower() == "true"

    # Redis connection pool settings
    redis_max_connections: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
    redis_socket_timeout: int = int(os.getenv("REDIS_SOCKET_TIMEOUT", "3"))
    redis_socket_connect_timeout: int = int(
        os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "3")
    )

    # Redis retry settings (using redis-py's built-in retry mechanism)
    redis_max_retries: int = int(os.getenv("REDIS_MAX_RETRIES", "1"))
    redis_backoff_base: float = float(os.getenv("REDIS_BACKOFF_BASE", "1"))
    redis_backoff_cap: float = float(os.getenv("REDIS_BACKOFF_CAP", "3"))

    # Azure settings
    azure_tenant_id: str | None = os.getenv("AZURE_TENANT_ID")
    azure_client_id: str | None = get_azd_env_value(
        "AZURE_MANAGED_IDENTITY_CLIENT_ID", os.getenv("AZURE_CLIENT_ID")
    )

    # Application Insights
    applicationinsights_connection_string: str | None = get_azd_env_value(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"),
    )

    # Telemetry settings
    telemetry_enabled: bool = os.getenv("TELEMETRY_ENABLED", "true").lower() == "true"
    custom_metrics_enabled: bool = (
        os.getenv("CUSTOM_METRICS_ENABLED", "true").lower() == "true"
    )
    log_telemetry_integration: bool = (
        os.getenv("LOG_TELEMETRY_INTEGRATION", "true").lower() == "true"
    )
    telemetry_sampling_rate: float = float(os.getenv("TELEMETRY_SAMPLING_RATE", "0.1"))
