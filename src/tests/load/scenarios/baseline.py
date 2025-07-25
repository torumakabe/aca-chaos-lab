"""Baseline load test scenario - steady load without chaos."""

from locust import HttpUser, between, task, constant
import logging

logger = logging.getLogger(__name__)


class BaselineUser(HttpUser):
    """User for baseline performance testing."""
    
    wait_time = constant(1)  # Consistent 1 second between requests
    
    def on_start(self):
        """Initialize user session."""
        self.request_count = 0
        self.error_count = 0
        logger.info("Starting baseline user session")
    
    @task(5)
    def get_main(self):
        """GET / - Main endpoint with Redis interaction."""
        self.request_count += 1
        
        with self.client.get("/", name="Main Endpoint") as response:
            if response.status_code != 200:
                self.error_count += 1
                logger.error(f"Main endpoint returned {response.status_code}")
            else:
                # Verify response structure
                try:
                    data = response.json()
                    assert "message" in data
                    assert "timestamp" in data
                    # redis_data might be None if Redis is not configured
                except Exception as e:
                    logger.error(f"Invalid response format: {e}")
                    response.failure(f"Invalid response format: {e}")
    
    @task(2)
    def get_health(self):
        """GET /health - Health check endpoint."""
        self.request_count += 1
        
        with self.client.get("/health", name="Health Check") as response:
            if response.status_code != 200:
                self.error_count += 1
                logger.error(f"Health check returned {response.status_code}")
            else:
                # Verify health response
                try:
                    data = response.json()
                    assert "status" in data
                    assert "timestamp" in data
                    
                    # Log if unhealthy
                    if data["status"] != "healthy":
                        logger.warning(f"Application reported unhealthy: {data}")
                except Exception as e:
                    logger.error(f"Invalid health response: {e}")
                    response.failure(f"Invalid health response: {e}")
    
    @task(1)
    def get_chaos_status(self):
        """GET /chaos/status - Check chaos status (should be inactive)."""
        self.request_count += 1
        
        with self.client.get("/chaos/status", name="Chaos Status") as response:
            if response.status_code != 200:
                self.error_count += 1
                logger.error(f"Chaos status returned {response.status_code}")
            else:
                # Verify no chaos is active
                try:
                    data = response.json()
                    if data.get("load", {}).get("active"):
                        logger.warning("Load simulation is active during baseline test!")
                    if data.get("hang", {}).get("active"):
                        logger.warning("Hang simulation is active during baseline test!")
                except Exception as e:
                    logger.error(f"Invalid chaos status response: {e}")
                    response.failure(f"Invalid chaos status response: {e}")
    
    def on_stop(self):
        """Clean up and report session statistics."""
        error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
        logger.info(f"Baseline user session ended - Requests: {self.request_count}, Errors: {self.error_count} ({error_rate:.2f}%)")


class BaselineConfig:
    """Configuration for baseline test scenario."""
    
    # Test parameters
    USERS = 10  # Number of concurrent users
    SPAWN_RATE = 2  # Users spawned per second
    RUN_TIME = "5m"  # Test duration
    
    # Performance thresholds
    MAX_RESPONSE_TIME_MS = 500  # Maximum acceptable response time
    MAX_ERROR_RATE = 0.01  # Maximum acceptable error rate (1%)
    MIN_RPS = 20  # Minimum requests per second
    
    @classmethod
    def get_command(cls, host: str) -> str:
        """Get the Locust command for this scenario."""
        return (
            f"locust -f baseline.py "
            f"--host {host} "
            f"--users {cls.USERS} "
            f"--spawn-rate {cls.SPAWN_RATE} "
            f"--run-time {cls.RUN_TIME} "
            f"--headless "
            f"--html baseline_report.html"
        )