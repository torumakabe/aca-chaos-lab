"""Locust load test scenarios for Azure Container Apps Chaos Lab."""

import random
import time
from locust import HttpUser, between, task, events
from locust.env import Environment


class ChaosLabUser(HttpUser):
    """Load test user for the Chaos Lab application."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Called when a user starts."""
        self.chaos_active = False
        self.start_time = time.time()
    
    @task(3)
    def check_health(self):
        """Check application health endpoint."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "unhealthy":
                    response.failure("Health check returned unhealthy status")
            elif response.status_code == 0:
                response.failure("Health check failed with status 0 - Connection error or timeout")
            else:
                response.failure(f"Health check failed with status {response.status_code}")
    
    @task(5)
    def main_endpoint(self):
        """Access main endpoint that interacts with Redis."""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                # Check if Redis data is available
                if data.get("redis_data") == "Redis unavailable":
                    # This might be expected during chaos testing
                    response.success()
                else:
                    response.success()
            elif response.status_code == 0:
                response.failure("Main endpoint failed with status 0 - Connection error or timeout")
            else:
                response.failure(f"Main endpoint failed with status {response.status_code}")
    
    @task(1)
    def check_chaos_status(self):
        """Check chaos engineering status."""
        with self.client.get("/chaos/status", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                self.chaos_active = data.get("load", {}).get("active", False) or \
                                   data.get("hang", {}).get("active", False)
                response.success()
            elif response.status_code == 0:
                response.failure("Chaos status check failed with status 0 - Connection error or timeout")
            else:
                response.failure(f"Chaos status check failed with status {response.status_code}")
    
    @task(0)  # Disabled by default, enable for chaos testing
    def trigger_load(self):
        """Trigger load simulation (chaos injection)."""
        if not self.chaos_active and random.random() < 0.1:  # 10% chance
            load_level = random.choice(["low", "medium", "high"])
            duration = random.randint(30, 120)  # 30-120 seconds
            
            with self.client.post("/chaos/load", 
                                json={"level": load_level, "duration_seconds": duration},
                                catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 409:
                    # Load already active, this is expected
                    response.success()
                else:
                    response.failure(f"Failed to trigger load: {response.status_code}")


class SteadyLoadUser(ChaosLabUser):
    """User that generates steady load without chaos injection."""
    
    @task
    def trigger_load(self):
        """Override to disable chaos injection."""
        pass


class ChaosTestUser(ChaosLabUser):
    """User that actively triggers chaos scenarios."""
    
    wait_time = between(5, 10)  # Wait longer between tasks
    
    @task(1)
    def trigger_load(self):
        """Actively trigger load simulation."""
        if not self.chaos_active:
            load_level = random.choice(["low", "medium", "high"])
            duration = random.randint(60, 180)  # 60-180 seconds
            
            with self.client.post("/chaos/load", 
                                json={"level": load_level, "duration_seconds": duration},
                                catch_response=True) as response:
                if response.status_code in [200, 409]:
                    response.success()
                else:
                    response.failure(f"Failed to trigger load: {response.status_code}")
    
    @task(0)  # Disabled by default - hang is disruptive
    def trigger_hang(self):
        """Trigger application hang (use with caution)."""
        if not self.chaos_active and random.random() < 0.05:  # 5% chance
            duration = random.randint(5, 15)  # 5-15 seconds
            
            # Note: This will timeout from the client side
            with self.client.post("/chaos/hang", 
                                json={"duration_seconds": duration},
                                catch_response=True,
                                timeout=2) as response:
                # We expect this to timeout
                response.success()


class SpikeTestUser(ChaosLabUser):
    """User for spike testing - sudden increase in load."""
    
    wait_time = between(0.1, 0.5)  # Very short wait times
    
    @task(10)
    def main_endpoint(self):
        """Hammer the main endpoint."""
        super().main_endpoint()
    
    @task(1)
    def check_health(self):
        """Less frequent health checks during spike."""
        super().check_health()


# Event handlers for test lifecycle
@events.test_start.add_listener
def on_test_start(environment: Environment, **kwargs):
    """Called when test starts."""
    print("🚀 Starting Chaos Lab load test...")
    print(f"Target host: {environment.host}")
    print(f"Total users: {environment.parsed_options.num_users}")
    print(f"Spawn rate: {environment.parsed_options.spawn_rate}")


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **kwargs):
    """Called when test stops."""
    print("\n📊 Test Summary:")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failure rate: {environment.stats.total.fail_ratio * 100:.2f}%")
    print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")


# Custom event for chaos injection tracking
chaos_injections = []

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, **kwargs):
    """Track chaos injection requests."""
    if name == "/chaos/load" and response.status_code == 200:
        chaos_injections.append({
            "timestamp": time.time(),
            "type": "load",
            "response": response.json() if response else None
        })
    elif name == "/chaos/hang" and response.status_code == 200:
        chaos_injections.append({
            "timestamp": time.time(),
            "type": "hang",
            "response": response.json() if response else None
        })


@events.quitting.add_listener
def on_quitting(environment: Environment, **kwargs):
    """Called when Locust is quitting."""
    if chaos_injections:
        print(f"\n🔥 Chaos injections during test: {len(chaos_injections)}")
        for injection in chaos_injections[-5:]:  # Show last 5
            print(f"  - {injection['type']} at {injection['timestamp']}")