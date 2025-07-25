"""End-to-end tests for complete chaos scenarios."""

import asyncio
import os
import subprocess
import time
from typing import Dict, List
import pytest
import httpx
import logging

logger = logging.getLogger(__name__)

# Test configuration
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
RESOURCE_GROUP = os.getenv("TEST_RESOURCE_GROUP")
CONTAINER_APP_NAME = os.getenv("TEST_CONTAINER_APP_NAME")
NSG_NAME = os.getenv("TEST_NSG_NAME")


class ChaosOrchestrator:
    """Orchestrates chaos scenarios for testing."""
    
    def __init__(self):
        self.active_chaos: List[str] = []
        self.client = httpx.AsyncClient(timeout=30.0, base_url=BASE_URL)
    
    async def inject_load(self, level: str = "medium", duration: int = 60):
        """Inject CPU/memory load via API."""
        try:
            response = await self.client.post(
                "/chaos/load",
                json={"level": level, "duration_seconds": duration}
            )
            if response.status_code == 200:
                self.active_chaos.append("load")
                logger.info(f"Injected {level} load for {duration}s")
                return True
        except Exception as e:
            logger.error(f"Failed to inject load: {e}")
        return False
    
    def inject_network_failure(self, duration: int = 60) -> bool:
        """Inject network failure using script."""
        if not all([RESOURCE_GROUP, NSG_NAME]):
            logger.warning("Skipping network injection - Azure resources not configured")
            return False
        
        try:
            result = subprocess.run(
                ["./scripts/inject-network-failure.sh", RESOURCE_GROUP, NSG_NAME, str(duration)],
                capture_output=True,
                text=True,
                check=True
            )
            self.active_chaos.append("network")
            logger.info(f"Injected network failure for {duration}s")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to inject network failure: {e.stderr}")
            return False
    
    def inject_deployment_failure(self, failure_type: str = "nonexistent-image") -> bool:
        """Inject deployment failure using script."""
        if not all([RESOURCE_GROUP, CONTAINER_APP_NAME]):
            logger.warning("Skipping deployment injection - Azure resources not configured")
            return False
        
        try:
            result = subprocess.run(
                ["./scripts/inject-deployment-failure.sh", RESOURCE_GROUP, CONTAINER_APP_NAME, failure_type],
                capture_output=True,
                text=True,
                check=True
            )
            self.active_chaos.append("deployment")
            logger.info(f"Injected deployment failure: {failure_type}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to inject deployment failure: {e.stderr}")
            return False
    
    def clear_all_chaos(self):
        """Clear all active chaos."""
        if "network" in self.active_chaos and all([RESOURCE_GROUP, NSG_NAME]):
            try:
                subprocess.run(
                    ["./scripts/clear-network-failures.sh", RESOURCE_GROUP, NSG_NAME],
                    capture_output=True,
                    check=True
                )
                logger.info("Cleared network failures")
            except:
                pass
        
        if "deployment" in self.active_chaos and all([RESOURCE_GROUP, CONTAINER_APP_NAME]):
            try:
                subprocess.run(
                    ["./scripts/restore-deployment.sh", RESOURCE_GROUP, CONTAINER_APP_NAME],
                    capture_output=True,
                    check=True
                )
                logger.info("Restored deployment")
            except:
                pass
        
        self.active_chaos.clear()
    
    async def close(self):
        """Clean up resources."""
        await self.client.aclose()


@pytest.fixture
async def chaos_orchestrator():
    """Create chaos orchestrator."""
    orchestrator = ChaosOrchestrator()
    yield orchestrator
    orchestrator.clear_all_chaos()
    await orchestrator.close()


@pytest.mark.asyncio
@pytest.mark.e2e
class TestCompleteScenarios:
    """Test complete end-to-end chaos scenarios."""
    
    async def test_single_failure_recovery(self, chaos_orchestrator):
        """Test recovery from a single type of failure."""
        # Baseline: ensure app is healthy
        response = await chaos_orchestrator.client.get("/health")
        assert response.status_code == 200
        initial_health = response.json()
        assert initial_health["status"] == "healthy"
        
        # Inject network failure
        chaos_orchestrator.inject_network_failure(30)
        await asyncio.sleep(5)
        
        # App should still respond but Redis should be unavailable
        response = await chaos_orchestrator.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("redis_data") == "Redis unavailable"
        
        # Wait for recovery
        await asyncio.sleep(35)
        
        # Verify recovery
        response = await chaos_orchestrator.client.get("/health")
        assert response.status_code == 200
        health = response.json()
        assert health["redis"]["connected"] == True
    
    async def test_cascading_failures(self, chaos_orchestrator):
        """Test application behavior under multiple simultaneous failures."""
        results = {
            "baseline_success": 0,
            "during_chaos_success": 0,
            "during_chaos_errors": 0,
            "recovery_success": 0
        }
        
        # Baseline performance
        for i in range(5):
            try:
                response = await chaos_orchestrator.client.get("/")
                if response.status_code == 200:
                    results["baseline_success"] += 1
            except:
                pass
            await asyncio.sleep(1)
        
        # Inject multiple failures
        await chaos_orchestrator.inject_load("high", 60)
        chaos_orchestrator.inject_network_failure(45)
        
        # Monitor during chaos
        await asyncio.sleep(5)
        for i in range(10):
            try:
                response = await chaos_orchestrator.client.get("/health", timeout=5.0)
                if response.status_code == 200:
                    results["during_chaos_success"] += 1
            except:
                results["during_chaos_errors"] += 1
            await asyncio.sleep(2)
        
        # Clear chaos and wait for recovery
        chaos_orchestrator.clear_all_chaos()
        await asyncio.sleep(20)
        
        # Verify recovery
        for i in range(5):
            try:
                response = await chaos_orchestrator.client.get("/")
                if response.status_code == 200:
                    results["recovery_success"] += 1
            except:
                pass
            await asyncio.sleep(1)
        
        # Assertions
        assert results["baseline_success"] >= 4, "Baseline should be mostly successful"
        assert results["during_chaos_success"] > 0, "Some requests should succeed during chaos"
        assert results["recovery_success"] >= 4, "Recovery should be mostly successful"
        
        logger.info(f"Cascading failure test results: {results}")
    
    async def test_progressive_degradation(self, chaos_orchestrator):
        """Test application degrades gracefully under increasing load."""
        response_times = {
            "baseline": [],
            "low_load": [],
            "medium_load": [],
            "high_load": []
        }
        
        async def measure_response_time(endpoint: str = "/") -> float:
            """Measure response time for an endpoint."""
            start = time.time()
            try:
                response = await chaos_orchestrator.client.get(endpoint, timeout=10.0)
                if response.status_code == 200:
                    return time.time() - start
            except:
                return -1
            return -1
        
        # Baseline measurements
        for i in range(5):
            rt = await measure_response_time()
            if rt > 0:
                response_times["baseline"].append(rt)
            await asyncio.sleep(1)
        
        # Low load
        await chaos_orchestrator.inject_load("low", 30)
        await asyncio.sleep(5)
        for i in range(5):
            rt = await measure_response_time()
            if rt > 0:
                response_times["low_load"].append(rt)
            await asyncio.sleep(1)
        
        # Wait for low load to clear, then medium load
        await asyncio.sleep(25)
        await chaos_orchestrator.inject_load("medium", 30)
        await asyncio.sleep(5)
        for i in range(5):
            rt = await measure_response_time()
            if rt > 0:
                response_times["medium_load"].append(rt)
            await asyncio.sleep(1)
        
        # Wait for medium load to clear, then high load
        await asyncio.sleep(25)
        await chaos_orchestrator.inject_load("high", 30)
        await asyncio.sleep(5)
        for i in range(5):
            rt = await measure_response_time()
            if rt > 0:
                response_times["high_load"].append(rt)
            await asyncio.sleep(1)
        
        # Calculate averages
        avg_baseline = sum(response_times["baseline"]) / len(response_times["baseline"]) if response_times["baseline"] else 0
        avg_low = sum(response_times["low_load"]) / len(response_times["low_load"]) if response_times["low_load"] else 0
        avg_medium = sum(response_times["medium_load"]) / len(response_times["medium_load"]) if response_times["medium_load"] else 0
        avg_high = sum(response_times["high_load"]) / len(response_times["high_load"]) if response_times["high_load"] else 0
        
        logger.info(f"Response times - Baseline: {avg_baseline:.3f}s, Low: {avg_low:.3f}s, Medium: {avg_medium:.3f}s, High: {avg_high:.3f}s")
        
        # Verify progressive degradation
        assert avg_baseline < avg_low < avg_medium < avg_high, "Response times should increase with load"
        assert avg_high < 5.0, "Even under high load, responses should be under 5 seconds"
    
    @pytest.mark.skipif(not all([RESOURCE_GROUP, CONTAINER_APP_NAME]), 
                        reason="Azure resources not configured")
    async def test_deployment_rollback(self, chaos_orchestrator):
        """Test deployment failure and rollback."""
        # Get current revision
        result = subprocess.run(
            ["./scripts/list-revisions.sh", RESOURCE_GROUP, CONTAINER_APP_NAME],
            capture_output=True,
            text=True
        )
        initial_revisions = result.stdout
        
        # Inject deployment failure
        chaos_orchestrator.inject_deployment_failure("nonexistent-image")
        await asyncio.sleep(10)
        
        # The app should still be accessible (old revision still active)
        response = await chaos_orchestrator.client.get("/health")
        assert response.status_code == 200
        
        # Restore deployment
        chaos_orchestrator.clear_all_chaos()
        await asyncio.sleep(10)
        
        # Verify restoration
        response = await chaos_orchestrator.client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.e2e
class TestObservabilityScenarios:
    """Test observability during chaos scenarios."""
    
    async def test_metrics_collection_during_chaos(self, chaos_orchestrator):
        """Verify metrics are collected during chaos."""
        # This would integrate with Application Insights to verify:
        # 1. Request counts are recorded
        # 2. Error rates are tracked
        # 3. Response times are measured
        # 4. Custom chaos events are logged
        
        # For now, we'll just verify the chaos status endpoint works
        await chaos_orchestrator.inject_load("medium", 30)
        
        status_checks = []
        for i in range(5):
            response = await chaos_orchestrator.client.get("/chaos/status")
            if response.status_code == 200:
                status_checks.append(response.json())
            await asyncio.sleep(5)
        
        # Verify we got status updates
        assert len(status_checks) >= 4
        assert any(s["load"]["active"] for s in status_checks)
        
        # Verify remaining time decreases
        remaining_times = [s["load"]["remaining_seconds"] for s in status_checks if s["load"]["active"]]
        assert remaining_times == sorted(remaining_times, reverse=True)