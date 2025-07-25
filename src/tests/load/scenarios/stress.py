"""Stress test scenario - gradually increasing load to find breaking point."""

from locust import HttpUser, between, task, LoadTestShape
import math
import logging

logger = logging.getLogger(__name__)


class StressTestUser(HttpUser):
    """User for stress testing - similar to baseline but with variable wait times."""
    
    wait_time = between(0.5, 2)  # Variable wait time
    
    def on_start(self):
        """Initialize user session."""
        self.request_count = 0
        self.error_count = 0
        self.consecutive_errors = 0
    
    @task(5)
    def get_main(self):
        """GET / - Main endpoint with Redis interaction."""
        self.request_count += 1
        
        with self.client.get("/", 
                            name="Main Endpoint",
                            catch_response=True) as response:
            if response.status_code != 200:
                self.error_count += 1
                self.consecutive_errors += 1
                
                # If too many consecutive errors, back off
                if self.consecutive_errors > 5:
                    logger.warning(f"Too many consecutive errors ({self.consecutive_errors}), backing off")
                    self.wait_time = between(2, 5)
            else:
                self.consecutive_errors = 0
                self.wait_time = between(0.5, 2)  # Reset to normal
                
                # Still verify response structure
                try:
                    data = response.json()
                    if "message" not in data:
                        response.failure("Missing 'message' in response")
                except Exception as e:
                    response.failure(f"Invalid JSON response: {e}")
    
    @task(2)
    def get_health(self):
        """GET /health - Health check endpoint."""
        with self.client.get("/health", name="Health Check") as response:
            if response.status_code != 200:
                logger.warning(f"Health check failed: {response.status_code}")
    
    @task(1)
    def get_chaos_status(self):
        """GET /chaos/status - Monitor chaos state during stress."""
        with self.client.get("/chaos/status", name="Chaos Status") as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    # Log if system is under internal stress
                    if data.get("load", {}).get("active"):
                        load_level = data["load"].get("level", "unknown")
                        logger.info(f"System under {load_level} load simulation")
                except:
                    pass


class StressTestShape(LoadTestShape):
    """
    Custom load shape for stress testing.
    Gradually increases users in steps until failure or max is reached.
    """
    
    # Test stages (duration in seconds, target user count)
    stages = [
        (60, 10),    # Warm up: 1 min at 10 users
        (180, 25),   # Step 1: 2 min at 25 users
        (300, 50),   # Step 2: 2 min at 50 users
        (420, 100),  # Step 3: 2 min at 100 users
        (540, 150),  # Step 4: 2 min at 150 users
        (660, 200),  # Step 5: 2 min at 200 users
        (780, 250),  # Step 6: 2 min at 250 users
        (900, 300),  # Step 7: 2 min at 300 users
        (960, 0),    # Cool down: ramp down to 0
    ]
    
    def tick(self):
        """
        Returns user count and spawn rate for the current tick.
        Returns None when test is complete.
        """
        run_time = self.get_run_time()
        
        # Find current stage
        for stage_time, user_count in self.stages:
            if run_time < stage_time:
                # Calculate spawn rate for smooth ramping
                if user_count > self.get_current_user_count():
                    # Ramping up
                    spawn_rate = 5
                elif user_count < self.get_current_user_count():
                    # Ramping down
                    spawn_rate = 10
                else:
                    # Maintaining current level
                    spawn_rate = 0
                
                return (user_count, spawn_rate)
        
        # Test complete
        return None


class StressTestConfig:
    """Configuration for stress test scenario."""
    
    # Performance degradation thresholds
    RESPONSE_TIME_THRESHOLD_MS = 1000  # When to consider system degraded
    ERROR_RATE_THRESHOLD = 0.05  # 5% error rate indicates stress
    
    @classmethod
    def get_command(cls, host: str) -> str:
        """Get the Locust command for this scenario."""
        return (
            f"locust -f stress.py "
            f"--host {host} "
            f"--headless "
            f"--html stress_report.html "
            f"--csv stress_metrics"
        )
    
    @classmethod
    def analyze_results(cls, stats_file: str) -> dict:
        """Analyze stress test results to find breaking point."""
        # This would parse the CSV output to find:
        # - User count when response time exceeded threshold
        # - User count when error rate exceeded threshold
        # - Maximum sustainable load
        pass