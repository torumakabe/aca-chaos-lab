"""Application configuration."""

import os

from pydantic_settings import BaseSettings

from app.azd_env import get_azd_env_value


class Settings(BaseSettings):
    """Application settings."""
    
    # Application settings
    app_port: int = 8000
    log_level: str = "INFO"
    
    # Redis settings
    redis_host: str = get_azd_env_value("AZURE_REDIS_HOST", os.getenv("REDIS_HOST", "localhost"))
    redis_port: int = int(get_azd_env_value("AZURE_REDIS_PORT", os.getenv("REDIS_PORT", "10000")))
    redis_ssl: bool = os.getenv("REDIS_SSL", "true").lower() == "true"
    redis_enabled: bool = os.getenv("REDIS_ENABLED", "true").lower() == "true"
    
    # Azure settings
    azure_tenant_id: str | None = os.getenv("AZURE_TENANT_ID")
    azure_client_id: str | None = get_azd_env_value("AZURE_MANAGED_IDENTITY_CLIENT_ID", os.getenv("AZURE_CLIENT_ID"))
    
    # Application Insights
    applicationinsights_connection_string: str | None = get_azd_env_value(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"