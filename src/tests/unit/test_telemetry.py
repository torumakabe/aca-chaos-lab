import pytest; pytestmark = pytest.mark.unit
"""Unit tests for telemetry module."""

from unittest.mock import Mock, patch

from app.telemetry import (
    record_chaos_metrics,
    record_redis_metrics,
    record_span_error,
    setup_telemetry,
)


class TestRecordSpanError:
    """Test cases for record_span_error function."""

    @patch("app.telemetry._tracer")
    @patch("app.telemetry.trace.get_current_span")
    def test_record_span_error_with_active_span(
        self, mock_get_current_span, mock_tracer
    ):
        """Test recording error in active span."""
        # Arrange
        mock_tracer.return_value = Mock()
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_get_current_span.return_value = mock_span

        test_exception = ValueError("Test error")

        # Act
        record_span_error(test_exception)

        # Assert
        mock_span.set_status.assert_called_once()
        mock_span.record_exception.assert_called_once_with(test_exception)

    @patch("app.telemetry._tracer", None)
    def test_record_span_error_no_tracer(self, caplog):
        """Test behavior when tracer is not initialized."""
        # Arrange
        test_exception = ValueError("Test error")

        # Act
        record_span_error(test_exception)

        # Assert
        assert "Tracer not initialized" in caplog.text

    @patch("app.telemetry._tracer")
    @patch("app.telemetry.trace.get_current_span")
    def test_record_span_error_no_active_span(self, mock_get_current_span, mock_tracer):
        """Test behavior when no active span exists."""
        # Arrange
        mock_tracer.return_value = Mock()
        mock_get_current_span.return_value = None

        test_exception = ValueError("Test error")

        # Act
        record_span_error(test_exception)

        # Assert - should not raise exception


class TestRecordRedisMetrics:
    """Test cases for record_redis_metrics function."""

    @patch("app.config.Settings")
    @patch("app.telemetry._meter")
    def test_record_redis_metrics_enabled(self, mock_meter, mock_settings_class):
        """Test recording Redis metrics when enabled."""
        # Arrange
        mock_settings = Mock()
        mock_settings.custom_metrics_enabled = True
        mock_settings.telemetry_sampling_rate = 1.0  # Always sample for test
        mock_settings_class.return_value = mock_settings

        mock_gauge = Mock()
        mock_histogram = Mock()
        mock_meter.create_gauge.return_value = mock_gauge
        mock_meter.create_histogram.return_value = mock_histogram

        # Act
        record_redis_metrics(True, 50)

        # Assert
        mock_meter.create_gauge.assert_called()
        mock_meter.create_histogram.assert_called()
        mock_gauge.set.assert_called_with(1)
        mock_histogram.record.assert_called_with(50)

    @patch("app.config.Settings")
    @patch("app.telemetry._meter")
    def test_record_redis_metrics_disabled(self, mock_meter, mock_settings_class):
        """Test behavior when custom metrics are disabled."""
        # Arrange
        mock_settings = Mock()
        mock_settings.custom_metrics_enabled = False
        mock_settings.telemetry_sampling_rate = 1.0  # Not used when disabled
        mock_settings_class.return_value = mock_settings

        # Act
        record_redis_metrics(True, 50)

        # Assert
        mock_meter.create_gauge.assert_not_called()
        mock_meter.create_histogram.assert_not_called()

    @patch("app.config.Settings")
    @patch("app.telemetry._meter")
    def test_record_redis_metrics_disconnected(self, mock_meter, mock_settings_class):
        """Test recording metrics for disconnected Redis."""
        # Arrange
        mock_settings = Mock()
        mock_settings.custom_metrics_enabled = True
        mock_settings.telemetry_sampling_rate = 1.0  # Always sample for test
        mock_settings_class.return_value = mock_settings

        mock_gauge = Mock()
        mock_meter.create_gauge.return_value = mock_gauge
        mock_meter.create_histogram.return_value = Mock()

        # Act
        record_redis_metrics(False, -1)

        # Assert
        mock_gauge.set.assert_called_with(0)
        # Histogram should not be called for negative latency
        mock_meter.create_histogram.assert_not_called()


class TestRecordChaosMetrics:
    """Test cases for record_chaos_metrics function."""

    @patch("app.config.Settings")
    @patch("app.telemetry._meter")
    def test_record_chaos_metrics_start(self, mock_meter, mock_settings_class):
        """Test recording chaos metrics at operation start."""
        # Arrange
        mock_settings = Mock()
        mock_settings.custom_metrics_enabled = True
        mock_settings.telemetry_sampling_rate = 1.0  # Always sample for test
        mock_settings_class.return_value = mock_settings

        mock_gauge = Mock()
        mock_meter.create_gauge.return_value = mock_gauge

        # Act
        record_chaos_metrics("cpu_load", True)

        # Assert
        mock_meter.create_gauge.assert_called()
        mock_gauge.set.assert_called_with(1, {"operation": "cpu_load"})

    @patch("app.config.Settings")
    @patch("app.telemetry._meter")
    def test_record_chaos_metrics_end(self, mock_meter, mock_settings_class):
        """Test recording chaos metrics at operation end."""
        # Arrange
        mock_settings = Mock()
        mock_settings.custom_metrics_enabled = True
        mock_settings.telemetry_sampling_rate = 1.0  # Always sample for test
        mock_settings_class.return_value = mock_settings

        mock_gauge = Mock()
        mock_meter.create_gauge.return_value = mock_gauge

        # Act
        record_chaos_metrics("cpu_load", False)

        # Assert
        mock_meter.create_gauge.assert_called()
        mock_gauge.set.assert_called_with(0, {"operation": "cpu_load"})


class TestSetupTelemetry:
    """Test cases for setup_telemetry function."""

    @patch("app.config.Settings")
    @patch.dict("os.environ", {}, clear=True)
    def test_setup_telemetry_disabled(self, mock_settings_class, caplog):
        """Test setup when telemetry is disabled."""
        # Arrange
        mock_settings = Mock()
        mock_settings.telemetry_enabled = False
        mock_settings.telemetry_sampling_rate = 0.1  # Add sampling rate
        mock_settings_class.return_value = mock_settings

        # Capture logs for the telemetry module
        with caplog.at_level("INFO", logger="app.telemetry"):
            # Act
            setup_telemetry()

        # Assert
        assert "Telemetry is disabled via TELEMETRY_ENABLED setting" in caplog.text

    @patch("app.config.Settings")
    @patch.dict("os.environ", {}, clear=True)
    def test_setup_telemetry_no_connection_string(self, mock_settings_class, caplog):
        """Test setup when connection string is missing."""
        # Arrange
        mock_settings = Mock()
        mock_settings.telemetry_enabled = True
        mock_settings.telemetry_sampling_rate = 0.1  # Add sampling rate
        mock_settings_class.return_value = mock_settings

        # Act
        setup_telemetry()

        # Assert
        assert "APPLICATIONINSIGHTS_CONNECTION_STRING not set" in caplog.text

    @patch("app.config.Settings")
    @patch("app.telemetry.configure_azure_monitor")
    @patch("app.telemetry.FastAPIInstrumentor")
    @patch("app.telemetry.RedisInstrumentor")
    @patch("app.telemetry.metrics.get_meter")
    @patch("app.telemetry.trace.get_tracer")
    @patch.dict(
        "os.environ",
        {"APPLICATIONINSIGHTS_CONNECTION_STRING": "test-connection-string"},
    )
    def test_setup_telemetry_success(
        self,
        mock_get_tracer,
        mock_get_meter,
        mock_redis_instrumentor,
        mock_fastapi_instrumentor,
        mock_configure_azure_monitor,
        mock_settings_class,
        caplog,
    ):
        """Test successful telemetry setup."""
        # Arrange
        mock_settings = Mock()
        mock_settings.telemetry_enabled = True
        mock_settings.telemetry_sampling_rate = 0.1  # Add sampling rate
        mock_settings_class.return_value = mock_settings

        mock_app = Mock()
        mock_meter = Mock()
        mock_tracer = Mock()
        mock_get_meter.return_value = mock_meter
        mock_get_tracer.return_value = mock_tracer

        mock_redis_instrumentor_instance = Mock()
        mock_redis_instrumentor.return_value = mock_redis_instrumentor_instance

        # Capture logs for the telemetry module
        with caplog.at_level("INFO", logger="app.telemetry"):
            # Act
            setup_telemetry(mock_app)

        # Assert
        mock_configure_azure_monitor.assert_called_once()
        mock_fastapi_instrumentor.instrument_app.assert_called_once_with(
            mock_app, excluded_urls="health"
        )
        mock_redis_instrumentor_instance.instrument.assert_called_once()
        assert "Application Insights telemetry configured successfully" in caplog.text


class TestStandardSampling:
    """Test cases for OpenTelemetry standard sampling functionality."""

    @patch("app.config.Settings")
    def test_setup_telemetry_with_sampling(self, mock_settings_class, caplog):
        """Test telemetry setup with OpenTelemetry standard sampling via environment variables."""
        # Arrange
        mock_settings = Mock()
        mock_settings.telemetry_enabled = True
        mock_settings.telemetry_sampling_rate = 0.1  # 10% sampling
        mock_settings_class.return_value = mock_settings

        # Mock environment
        with (
            patch.dict(
                "os.environ",
                {"APPLICATIONINSIGHTS_CONNECTION_STRING": "test-connection-string"},
            ),
            patch("app.telemetry.configure_azure_monitor") as mock_configure,
            caplog.at_level("INFO", logger="app.telemetry"),
        ):
            # Act
            setup_telemetry()

            # Assert
            mock_configure.assert_called_once()
            assert (
                "Configured OpenTelemetry sampling via environment variables: 10.0%"
                in caplog.text
            )

            # Verify environment variables were set
            import os

            assert os.environ.get("OTEL_TRACES_SAMPLER") == "traceidratio"
            assert os.environ.get("OTEL_TRACES_SAMPLER_ARG") == "0.1"

    @patch("app.config.Settings")
    @patch("app.telemetry._meter")
    def test_record_redis_metrics_always_recorded(
        self, mock_meter, mock_settings_class
    ):
        """Test Redis metrics are always recorded.

        Sampling is handled by OpenTelemetry.
        """
        # Arrange
        mock_settings = Mock()
        mock_settings.custom_metrics_enabled = True
        mock_settings.telemetry_sampling_rate = 0.1  # 10% sampling
        mock_settings_class.return_value = mock_settings

        mock_gauge = Mock()
        mock_histogram = Mock()
        mock_meter.create_gauge.return_value = mock_gauge
        mock_meter.create_histogram.return_value = mock_histogram

        # Act
        record_redis_metrics(True, 50)  # Connected, good performance

        # Assert - Always recorded, sampling handled at trace level
        mock_meter.create_gauge.assert_called()
        mock_meter.create_histogram.assert_called()
        mock_gauge.set.assert_called_with(1)
        mock_histogram.record.assert_called_with(50)

    @patch("app.config.Settings")
    @patch("app.telemetry._meter")
    def test_record_chaos_metrics_always_recorded(
        self, mock_meter, mock_settings_class
    ):
        """Test Chaos metrics are always recorded.

        Sampling is handled by OpenTelemetry.
        """
        # Arrange
        mock_settings = Mock()
        mock_settings.custom_metrics_enabled = True
        mock_settings.telemetry_sampling_rate = 0.1  # 10% sampling
        mock_settings_class.return_value = mock_settings

        mock_gauge = Mock()
        mock_meter.create_gauge.return_value = mock_gauge

        # Act
        record_chaos_metrics("cpu_load", True)

        # Assert - Always recorded, sampling handled at trace level
        mock_meter.create_gauge.assert_called()
        mock_gauge.set.assert_called_with(1, {"operation": "cpu_load"})
