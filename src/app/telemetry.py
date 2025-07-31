"""Application Insights telemetry setup."""

import logging
import os

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)


def setup_telemetry(app=None):
    """Configure Azure Application Insights telemetry."""
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if not connection_string:
        logger.warning(
            "APPLICATIONINSIGHTS_CONNECTION_STRING not set, telemetry disabled"
        )
        return

    try:
        # Create resource with service name (role name)
        resource = Resource.create(
            {
                "service.name": "app",
                "service.version": "0.1.0",
            }
        )

        # Configure Azure Monitor
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name="aca-chaos-lab",
            resource=resource,
        )

        # Instrument FastAPI explicitly with health check exclusion
        if app:
            FastAPIInstrumentor.instrument_app(
                app,
                excluded_urls="health",  # Exclude URLs containing 'health'
            )

        # Redis needs separate instrumentation
        RedisInstrumentor().instrument()

        logger.info("Application Insights telemetry configured successfully")

    except Exception as e:
        logger.error(f"Failed to configure Application Insights: {e}")
