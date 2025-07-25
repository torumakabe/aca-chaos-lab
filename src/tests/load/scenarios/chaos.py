"""Chaos test scenario - load testing while injecting failures."""

from locust import HttpUser, between, task, events
from locust.env import Environment
import random
import time
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ChaosInjector:
    """Manages chaos injection during load test."""
    
    def __init__(self, host: str):
        self.host = host
        self.active_chaos = {
            "load": False,
            "network": False,
            "deployment": False
        }
        self.injection_history: List[Dict] = []
    
    def inject_load_chaos(self, client, level: str = "medium", duration: int = 60):
        """Inject CPU/memory load via API."""
        if self.active_chaos["load"]:
            return False
        
        try:
            response = client.post(
                "/chaos/load",
                json={"level": level, "duration_seconds": duration},
                catch_response=True
            )
            
            if response.status_code == 200:
                self.active_chaos["load"] = True
                self.injection_history.append({
                    "type": "load",
                    "level": level,
                    "duration": duration,
                    "timestamp": time.time(),
                    "success": True
                })
                logger.info(f"Injected {level} load for {duration}s")
                return True
            else:
                logger.error(f"Failed to inject load: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error injecting load: {e}")
            return False
    
    def clear_load_chaos(self):
        """Mark load chaos as cleared (it auto-expires)."""
        self.active_chaos["load"] = False
        logger.info("Load chaos cleared")
    
    def inject_network_chaos(self):
        """Inject network failure (requires external script)."""
        # This would call the inject-network-failure.sh script
        # For load testing, we'll just track the state
        self.active_chaos["network"] = True
        self.injection_history.append({
            "type": "network",
            "timestamp": time.time(),
            "success": True
        })
        logger.info("Network chaos injected (simulated)")
    
    def clear_network_chaos(self):
        """Clear network failure."""
        self.active_chaos["network"] = False
        logger.info("Network chaos cleared")
    
    def get_active_chaos(self) -> List[str]:
        """Get list of active chaos types."""
        return [k for k, v in self.active_chaos.items() if v]


# Global chaos injector instance
chaos_injector = None


class ChaosTestUser(HttpUser):
    """User that operates under chaos conditions."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Initialize user session."""
        self.request_count = 0
        self.error_count = 0
        self.chaos_errors = 0
    
    @task(5)
    def get_main_with_resilience(self):
        """GET / with resilience handling."""
        self.request_count += 1
        
        with self.client.get("/", 
                            name="Main Endpoint",
                            catch_response=True) as response:
            if response.status_code != 200:
                self.error_count += 1
                
                # Check if error is chaos-related
                if chaos_injector and chaos_injector.get_active_chaos():
                    self.chaos_errors += 1
                    # During chaos, some errors are expected
                    response.success()
                else:
                    response.failure(f"Unexpected error: {response.status_code}")
            else:
                # Check response content
                try:
                    data = response.json()
                    # During network chaos, Redis might be unavailable
                    if data.get("redis_data") == "Redis unavailable":
                        if chaos_injector and "network" in chaos_injector.get_active_chaos():
                            # Expected during network chaos
                            response.success()
                        else:
                            response.failure("Redis unavailable without network chaos")
                except Exception as e:
                    response.failure(f"Invalid response: {e}")
    
    @task(2)
    def get_health_with_monitoring(self):
        """GET /health with chaos awareness."""
        with self.client.get("/health", 
                            name="Health Check",
                            catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    # Log health status during chaos
                    if data["status"] == "unhealthy":
                        active_chaos = chaos_injector.get_active_chaos() if chaos_injector else []
                        logger.info(f"Unhealthy during chaos: {active_chaos}")
                except:
                    pass
    
    @task(1)
    def check_chaos_status(self):
        """Monitor chaos state."""
        with self.client.get("/chaos/status", name="Chaos Status") as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    # Update local chaos state
                    if chaos_injector:
                        chaos_injector.active_chaos["load"] = data.get("load", {}).get("active", False)
                except:
                    pass
    
    def on_stop(self):
        """Report chaos-aware statistics."""
        if self.request_count > 0:
            error_rate = self.error_count / self.request_count * 100
            chaos_error_rate = self.chaos_errors / self.request_count * 100
            logger.info(
                f"User session ended - "
                f"Requests: {self.request_count}, "
                f"Errors: {self.error_count} ({error_rate:.2f}%), "
                f"Chaos errors: {self.chaos_errors} ({chaos_error_rate:.2f}%)"
            )


# Chaos injection schedule
CHAOS_SCHEDULE = [
    # (time_offset_seconds, chaos_type, parameters)
    (30, "load", {"level": "low", "duration": 60}),
    (120, "network", {"duration": 30}),
    (180, "load", {"level": "medium", "duration": 90}),
    (300, "load", {"level": "high", "duration": 60}),
    (420, "network", {"duration": 60}),
]


@events.test_start.add_listener
def on_test_start(environment: Environment, **kwargs):
    """Initialize chaos testing."""
    global chaos_injector
    chaos_injector = ChaosInjector(environment.host)
    logger.info("Chaos test started - failures will be injected according to schedule")


@events.init.add_listener
def on_locust_init(environment: Environment, **kwargs):
    """Schedule chaos injections."""
    if not isinstance(environment.runner, type(None)):
        start_time = time.time()
        
        def check_and_inject_chaos():
            """Check if it's time to inject chaos."""
            elapsed = time.time() - start_time
            
            for scheduled_time, chaos_type, params in CHAOS_SCHEDULE:
                # Check if this chaos should be injected
                if elapsed >= scheduled_time and elapsed < scheduled_time + 5:
                    # Find if this chaos was already injected
                    already_injected = any(
                        inj["timestamp"] > start_time + scheduled_time - 10
                        for inj in chaos_injector.injection_history
                        if inj["type"] == chaos_type
                    )
                    
                    if not already_injected:
                        if chaos_type == "load":
                            # Use first available user client
                            if environment.runner.user_classes:
                                user = next(iter(environment.runner.user_classes))
                                if hasattr(user, 'client'):
                                    chaos_injector.inject_load_chaos(
                                        user.client,
                                        params.get("level", "medium"),
                                        params.get("duration", 60)
                                    )
                        elif chaos_type == "network":
                            chaos_injector.inject_network_chaos()
        
        # Check every 5 seconds
        environment.runner.greenlet.spawn(
            lambda: [check_and_inject_chaos() or time.sleep(5) for _ in range(200)]
        )


@events.test_stop.add_listener  
def on_test_stop(environment: Environment, **kwargs):
    """Report chaos injection summary."""
    if chaos_injector:
        print("\n🔥 Chaos Injection Summary:")
        print(f"Total injections: {len(chaos_injector.injection_history)}")
        
        for injection in chaos_injector.injection_history:
            timestamp = time.strftime("%H:%M:%S", time.localtime(injection["timestamp"]))
            print(f"  - {timestamp}: {injection['type']} "
                  f"({'success' if injection.get('success') else 'failed'})")


class ChaosTestConfig:
    """Configuration for chaos test scenario."""
    
    # Test parameters
    USERS = 50  # Moderate user count
    SPAWN_RATE = 5
    RUN_TIME = "10m"  # Long enough for all chaos injections
    
    @classmethod
    def get_command(cls, host: str) -> str:
        """Get the Locust command for this scenario."""
        return (
            f"locust -f chaos.py "
            f"--host {host} "
            f"--users {cls.USERS} "
            f"--spawn-rate {cls.SPAWN_RATE} "
            f"--run-time {cls.RUN_TIME} "
            f"--headless "
            f"--html chaos_report.html "
            f"--csv chaos_metrics"
        )