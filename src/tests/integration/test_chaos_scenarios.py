"""Integration tests for chaos engineering scenarios."""

import asyncio
import os
import time
from typing import Optional
import pytest
import httpx
from azure.identity.aio import DefaultAzureCredential
import logging

logger = logging.getLogger(__name__)

# Test configuration from environment
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
RESOURCE_GROUP = os.getenv("TEST_RESOURCE_GROUP")
NSG_NAME = os.getenv("TEST_NSG_NAME")
CONTAINER_APP_NAME = os.getenv("TEST_CONTAINER_APP_NAME")


class ChaosLabClient:
    """HTTP client for chaos lab application."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_health(self) -> dict:
        """Get health status."""
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    async def get_main(self) -> dict:
        """Get main endpoint."""
        response = await self.client.get(f"{self.base_url}/")
        response.raise_for_status()
        return response.json()
    
    async def start_load(self, level: str, duration: int) -> dict:
        """Start load simulation."""
        response = await self.client.post(
            f"{self.base_url}/chaos/load",
            json={"level": level, "duration_seconds": duration}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_chaos_status(self) -> dict:
        """Get chaos status."""
        response = await self.client.get(f"{self.base_url}/chaos/status")
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the client."""
        await self.client.aclose()


@pytest.fixture
async def chaos_client():
    """Create chaos lab client."""
    client = ChaosLabClient(BASE_URL)
    yield client
    await client.close()


@pytest.mark.asyncio
class TestBasicFunctionality:
    """Test basic application functionality."""
    
    async def test_health_endpoint(self, chaos_client):
        """Test health endpoint returns healthy status."""
        health = await chaos_client.get_health()
        
        assert health["status"] in ["healthy", "unhealthy"]
        assert "timestamp" in health
        assert "redis" in health
    
    async def test_main_endpoint(self, chaos_client):
        """Test main endpoint returns expected data."""
        data = await chaos_client.get_main()
        
        assert data["message"] == "Hello from Container Apps Chaos Lab"
        assert "timestamp" in data
        # redis_data might be None if Redis is not configured
    
    async def test_chaos_status_initial(self, chaos_client):
        """Test chaos status shows no active chaos initially."""
        status = await chaos_client.get_chaos_status()
        
        assert not status["load"]["active"]
        assert not status["hang"]["active"]


@pytest.mark.asyncio
@pytest.mark.skipif(not all([RESOURCE_GROUP, NSG_NAME, CONTAINER_APP_NAME]), 
                    reason="Azure resources not configured")
class TestChaosScenarios:
    """Test chaos injection scenarios."""
    
    async def test_load_simulation(self, chaos_client):
        """Test CPU/memory load simulation."""
        # Start load
        response = await chaos_client.start_load("low", 30)
        assert response["status"] == "load_started"
        
        # Verify load is active
        await asyncio.sleep(2)
        status = await chaos_client.get_chaos_status()
        assert status["load"]["active"]
        assert status["load"]["level"] == "low"
        
        # Application should still respond during low load
        health = await chaos_client.get_health()
        assert health["status"] == "healthy"
        
        # Wait for load to complete
        await asyncio.sleep(35)
        status = await chaos_client.get_chaos_status()
        assert not status["load"]["active"]
    
    async def test_network_failure_recovery(self, chaos_client):
        """Test application recovery from network failure."""
        # First ensure Redis is working
        initial_data = await chaos_client.get_main()
        
        # TODO: Inject network failure using Azure CLI
        # This would require running the inject-network-failure.sh script
        
        # During network failure, Redis should be unavailable
        # but the application should still respond
        
        # TODO: Clear network failure
        
        # Verify recovery
        await asyncio.sleep(5)
        recovery_data = await chaos_client.get_main()
        assert recovery_data is not None
    
    async def test_cascading_failures(self, chaos_client):
        """Test behavior under multiple simultaneous failures."""
        # Start high load
        await chaos_client.start_load("high", 60)
        
        # TODO: Also inject network failure
        
        # Monitor application behavior
        errors = 0
        success = 0
        
        for i in range(10):
            try:
                await chaos_client.get_health()
                success += 1
            except Exception:
                errors += 1
            await asyncio.sleep(2)
        
        # Application should handle some requests even under stress
        assert success > 0
        logger.info(f"Cascading failure test: {success} success, {errors} errors")


@pytest.mark.asyncio
class TestObservability:
    """Test observability during chaos."""
    
    async def test_metrics_during_chaos(self, chaos_client):
        """Test that metrics are properly recorded during chaos."""
        # Start medium load
        await chaos_client.start_load("medium", 45)
        
        # Make several requests to generate metrics
        for i in range(5):
            try:
                await chaos_client.get_main()
                await chaos_client.get_health()
            except:
                pass  # Some failures expected
            await asyncio.sleep(2)
        
        # In a real test, we would query Application Insights
        # to verify metrics were recorded
        
        # Check chaos status shows accurate information
        status = await chaos_client.get_chaos_status()
        assert status["load"]["active"]
        assert status["load"]["remaining_seconds"] > 0


@pytest.mark.asyncio
class TestResilience:
    """Test application resilience patterns."""
    
    async def test_circuit_breaker_pattern(self, chaos_client):
        """Test that circuit breaker prevents cascading failures."""
        # This test would verify that when Redis fails repeatedly,
        # the application stops trying and fails fast
        pass
    
    async def test_graceful_degradation(self, chaos_client):
        """Test application degrades gracefully under load."""
        # Start high load
        await chaos_client.start_load("high", 30)
        
        # Application should still respond, even if slower
        start_time = time.time()
        response = await chaos_client.get_health()
        response_time = time.time() - start_time
        
        assert response is not None
        assert response_time < 5.0  # Should respond within 5 seconds
        
        # Wait for load to clear
        await asyncio.sleep(35)


# Helper functions for running chaos scripts
async def inject_network_failure(duration: int = 60):
    """Inject network failure using Azure CLI."""
    if not all([RESOURCE_GROUP, NSG_NAME]):
        pytest.skip("Azure resources not configured")
    
    cmd = f"./scripts/inject-network-failure.sh {RESOURCE_GROUP} {NSG_NAME} {duration}"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        raise Exception(f"Failed to inject network failure: {stderr.decode()}")
    
    return stdout.decode()


async def clear_network_failures():
    """Clear all network failures."""
    if not all([RESOURCE_GROUP, NSG_NAME]):
        return
    
    cmd = f"./scripts/clear-network-failures.sh {RESOURCE_GROUP} {NSG_NAME}"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()


# Cleanup fixture
@pytest.fixture(autouse=True)
async def cleanup_chaos():
    """Ensure chaos is cleared after each test."""
    yield
    # Clear any network failures
    await clear_network_failures()
    # Wait a bit for any active chaos to complete
    await asyncio.sleep(5)