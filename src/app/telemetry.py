"""Application Insights telemetry setup."""

import logging
import os

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)

# Global telemetry components
_meter: metrics.Meter | None = None
_tracer: trace.Tracer | None = None


def setup_telemetry(app=None):
    """Configure Azure Application Insights telemetry with OpenTelemetry standard sampling."""
    # Import here to avoid circular dependency
    from app.config import Settings

    settings = Settings()

    if not settings.telemetry_enabled:
        logger.info("Telemetry is disabled via TELEMETRY_ENABLED setting")
        return

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

        # Configure OpenTelemetry standard sampling using environment variables
        # This is the recommended approach for consistent sampling behavior
        sampling_rate = settings.telemetry_sampling_rate
        if sampling_rate < 1.0:
            # Set OpenTelemetry standard environment variables
            os.environ["OTEL_TRACES_SAMPLER"] = "traceidratio"
            os.environ["OTEL_TRACES_SAMPLER_ARG"] = str(sampling_rate)
            logger.info(
                f"Configured OpenTelemetry sampling via environment variables: {sampling_rate:.1%}"
            )

        # Configure Azure Monitor (will respect OTEL environment variables)
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name="aca-chaos-lab",
            resource=resource,
        )

        # Initialize global telemetry components
        global _meter, _tracer
        _meter = metrics.get_meter("aca-chaos-lab", "0.1.0")
        _tracer = trace.get_tracer("aca-chaos-lab", "0.1.0")

        # Instrument FastAPI explicitly with health check exclusion
        if app:
            FastAPIInstrumentor.instrument_app(
                app,
                excluded_urls="health",  # Exclude URLs containing 'health'
            )

        # Redis instrumentation - let it respect the sampling configuration
        # Note: Health check PING commands will also be sampled
        RedisInstrumentor().instrument()

        logger.info("Application Insights telemetry configured successfully")

    except Exception as e:
        logger.error(f"Failed to configure Application Insights: {e}")


def record_span_error(exc: Exception, span_name: str | None = None) -> None:
    """Record error information in the current OpenTelemetry span."""
    if not _tracer:
        logger.warning("Tracer not initialized, cannot record span error")
        return

    try:
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_status(Status(StatusCode.ERROR, str(exc)))
            current_span.record_exception(exc)
            logger.debug(f"Recorded exception in span: {exc}")
        else:
            logger.debug("No active span to record exception")
    except Exception as e:
        logger.error(f"Failed to record span error: {e}")


def record_redis_metrics(connected: bool, latency_ms: int) -> None:
    """Record Redis connection metrics.

    Note: Sampling is handled at the OpenTelemetry trace level, not here.
    All metrics are recorded; sampling occurs during trace export.
    """
    # Import here to avoid circular dependency
    from app.config import Settings

    settings = Settings()

    if not settings.custom_metrics_enabled or not _meter:
        if not settings.custom_metrics_enabled:
            logger.debug("Custom metrics disabled, skipping Redis metrics")
        else:
            logger.warning("Meter not initialized, cannot record Redis metrics")
        return

    try:
        # Connection status (gauge) - always record, sampling handled by OpenTelemetry
        connection_gauge = _meter.create_gauge(
            name="redis_connection_status",
            description="Redis connection status (1=connected, 0=disconnected)",
        )
        connection_gauge.set(1 if connected else 0)

        # Latency histogram (only if connected)
        if connected and latency_ms >= 0:
            latency_histogram = _meter.create_histogram(
                name="redis_connection_latency_ms",
                description="Redis connection latency in milliseconds",
                unit="ms",
            )
            latency_histogram.record(latency_ms)

        logger.debug(
            f"Recorded Redis metrics: connected={connected}, latency={latency_ms}ms"
        )

    except Exception as e:
        logger.error(f"Failed to record Redis metrics: {e}")


def record_chaos_metrics(operation: str, active: bool) -> None:
    """Record chaos operation metrics.

    Note: Sampling is handled at the OpenTelemetry trace level, not here.
    All metrics are recorded; sampling occurs during trace export.
    """
    # Import here to avoid circular dependency
    from app.config import Settings

    settings = Settings()

    if not settings.custom_metrics_enabled or not _meter:
        if not settings.custom_metrics_enabled:
            logger.debug("Custom metrics disabled, skipping chaos metrics")
        else:
            logger.warning("Meter not initialized, cannot record chaos metrics")
        return

    try:
        # Active operations gauge - always record, sampling handled by OpenTelemetry
        active_gauge = _meter.create_gauge(
            name="chaos_operation_active",
            description="Number of active chaos operations",
        )
        active_gauge.set(1 if active else 0, {"operation": operation})

        logger.debug(f"Recorded chaos metrics: operation={operation}, active={active}")

    except Exception as e:
        logger.error(f"Failed to record chaos metrics: {e}")
