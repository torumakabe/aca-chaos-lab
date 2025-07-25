"""Application Insights telemetry setup."""

import logging
import os

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor


def setup_telemetry(app=None):
    """Configure Azure Application Insights telemetry."""
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    
    if not connection_string:
        logging.warning("APPLICATIONINSIGHTS_CONNECTION_STRING not set, telemetry disabled")
        return
    
    try:
        # Configure Azure Monitor
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name="aca-chaos-lab",
            instrumentation_options={
                "azure_sdk": {"enabled": False},  # Disable Azure SDK instrumentation
                "django": {"enabled": False},      # Disable Django instrumentation
                "flask": {"enabled": False},       # Disable Flask instrumentation
                "psycopg2": {"enabled": False},    # Disable psycopg2 instrumentation
            }
        )
        
        # Instrument FastAPI
        if app:
            FastAPIInstrumentor.instrument_app(app)
        
        # Instrument Redis
        RedisInstrumentor().instrument()
        
        # Instrument logging
        LoggingInstrumentor().instrument(set_logging_format=True)
        
        # Set up custom tracer
        tracer = trace.get_tracer("aca-chaos-lab", "0.1.0")
        
        logging.info("Application Insights telemetry configured successfully")
        return tracer
        
    except Exception as e:
        logging.error(f"Failed to configure Application Insights: {e}")
        return None


def get_tracer():
    """Get the configured tracer instance."""
    return trace.get_tracer("aca-chaos-lab", "0.1.0")