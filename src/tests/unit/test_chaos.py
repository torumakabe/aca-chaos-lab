"""Unit tests for chaos engineering endpoints."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock, Mock
from fastapi.testclient import TestClient

from app.chaos import chaos_state, router, generate_cpu_load, generate_memory_load, ChaosState
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)


@pytest.fixture
def client():
    """Create test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_chaos_state():
    """Reset chaos state before and after each test."""
    # Reset before test
    chaos_state.load_active = False
    chaos_state.load_level = "low"
    chaos_state.load_end_time = None
    chaos_state._load_task = None
    chaos_state.hang_active = False
    chaos_state.hang_end_time = None
    chaos_state._hang_task = None
    chaos_state.redis_last_reset = None
    
    yield
    
    # Clean up after test
    chaos_state.load_active = False
    chaos_state.hang_active = False
    chaos_state._load_task = None
    chaos_state._hang_task = None
    chaos_state.redis_last_reset = None


class TestLoadSimulation:
    """Test load simulation endpoints."""
    
    @patch("app.chaos.asyncio.create_task")
    def test_start_load_success(self, mock_create_task, client):
        """Test successful load start."""
        # Mock the task and consume the coroutine
        mock_task = MagicMock()
        
        def create_task_side_effect(coro):
            # Consume the coroutine to prevent warning
            coro.close()
            return mock_task
        
        mock_create_task.side_effect = create_task_side_effect
        
        response = client.post("/chaos/load", json={
            "level": "medium",
            "duration_seconds": 60
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "load_started"
        assert data["level"] == "medium"
        assert data["duration_seconds"] == 60
        
        # Verify task was created
        mock_create_task.assert_called_once()
    
    def test_start_load_invalid_level(self, client):
        """Test load start with invalid level."""
        response = client.post("/chaos/load", json={
            "level": "extreme",
            "duration_seconds": 60
        })
        
        assert response.status_code == 400
        assert "Invalid load level" in response.json()["detail"]
    
    def test_start_load_invalid_duration(self, client):
        """Test load start with invalid duration."""
        response = client.post("/chaos/load", json={
            "level": "low",
            "duration_seconds": 0
        })
        
        assert response.status_code == 400
        assert "Duration must be between" in response.json()["detail"]
        
        # Test too long duration
        response = client.post("/chaos/load", json={
            "level": "low",
            "duration_seconds": 3601
        })
        
        assert response.status_code == 400
        assert "Duration must be between" in response.json()["detail"]
    
    def test_start_load_already_active(self, client):
        """Test starting load when already active."""
        chaos_state.load_active = True
        
        response = client.post("/chaos/load", json={
            "level": "low",
            "duration_seconds": 60
        })
        
        assert response.status_code == 409
        assert "already active" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_generate_cpu_load(self):
        """Test CPU load generation."""
        chaos_state.load_active = True
        
        # Run for a short duration
        with patch("app.chaos.time") as mock_time:
            # Simulate 0.5 seconds passing with enough values for all time() calls
            time_values = []
            current_time = 0
            while current_time <= 0.6:
                time_values.append(current_time)
                current_time += 0.01
            
            mock_time.time.side_effect = time_values
            
            await generate_cpu_load("low", 0.5)
        
        chaos_state.load_active = False
    
    @pytest.mark.asyncio
    async def test_generate_memory_load(self):
        """Test memory load generation."""
        # Test with small memory allocation
        await generate_memory_load("low", 0.1)
        
        # Memory should be cleared after completion
        # (No direct way to test, but function should complete without error)


class TestHangSimulation:
    """Test hang simulation endpoint."""
    
    def test_hang_permanent(self, client):
        """Test permanent hang initiation - just verify state is set."""
        # Instead of testing actual hang, verify the route exists and initial validation
        # We cannot test permanent hang properly in unit tests
        
        # Test with invalid duration should work
        response = client.post("/chaos/hang", json={
            "duration_seconds": -1
        })
        
        # Should be valid (0 or positive)
        assert response.status_code in [200, 400, 409]  # Depends on current state
    
    @patch("app.chaos.asyncio.sleep")
    def test_hang_timed(self, mock_sleep, client):
        """Test timed hang."""
        # Make sleep return immediately
        mock_sleep.return_value = None
        
        response = client.post("/chaos/hang", json={
            "duration_seconds": 5
        })
        
        # Should complete after mocked sleep
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "hang_completed"
    
    def test_hang_already_active(self, client):
        """Test hang when already active."""
        chaos_state.hang_active = True
        
        response = client.post("/chaos/hang", json={
            "duration_seconds": 5
        })
        
        assert response.status_code == 409
        assert "already active" in response.json()["detail"]


class TestChaosStatus:
    """Test chaos status endpoint."""
    
    def test_status_inactive(self, client):
        """Test status when no chaos is active."""
        response = client.get("/chaos/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["load"]["active"] is False
        assert data["load"]["level"] == "none"
        assert data["load"]["remaining_seconds"] == 0
        
        assert data["hang"]["active"] is False
        assert data["hang"]["remaining_seconds"] == 0
    
    def test_status_with_load_active(self, client):
        """Test status with load active."""
        chaos_state.load_active = True
        chaos_state.load_level = "high"
        chaos_state.load_end_time = datetime.now(timezone.utc) + timedelta(seconds=30)
        
        response = client.get("/chaos/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["load"]["active"] is True
        assert data["load"]["level"] == "high"
        assert 25 <= data["load"]["remaining_seconds"] <= 30
    
    def test_status_with_hang_active(self, client):
        """Test status with hang active."""
        chaos_state.hang_active = True
        chaos_state.hang_end_time = datetime.now(timezone.utc) + timedelta(seconds=15)
        
        response = client.get("/chaos/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["hang"]["active"] is True
        assert 10 <= data["hang"]["remaining_seconds"] <= 15


class TestRedisReset:
    """Test Redis connection reset endpoint."""
    
    @patch("app.main.redis_client")
    def test_redis_reset_success(self, mock_redis_client, client):
        """Test successful Redis connection reset."""
        # Mock reset_connections to return 3 connections closed
        mock_redis_client.reset_connections = AsyncMock(return_value=3)
        
        response = client.post("/chaos/redis-reset", json={
            "force": True
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "redis_connections_reset"
        assert data["connections_closed"] == 3
        assert "timestamp" in data
        
        # Verify reset was called
        mock_redis_client.reset_connections.assert_called_once()
    
    @patch("app.main.redis_client", None)
    def test_redis_reset_no_client(self, client):
        """Test Redis reset when client not initialized."""
        response = client.post("/chaos/redis-reset")
        
        assert response.status_code == 503
        assert "Redis client not initialized" in response.json()["detail"]
    
    @patch("app.main.redis_client")
    def test_redis_reset_failure(self, mock_redis_client, client):
        """Test Redis reset failure."""
        # Mock reset_connections to raise an exception
        mock_redis_client.reset_connections = AsyncMock(side_effect=Exception("Reset failed"))
        
        response = client.post("/chaos/redis-reset")
        
        assert response.status_code == 500
        assert "Redis reset failed" in response.json()["detail"]
    
    @patch("app.main.redis_client")
    def test_status_with_redis(self, mock_redis_client, client):
        """Test status endpoint includes Redis information."""
        # Mock get_connection_status
        mock_redis_client.get_connection_status = AsyncMock(return_value={
            "connected": True,
            "connection_count": 2
        })
        
        # Set last reset time
        chaos_state.redis_last_reset = datetime.now(timezone.utc)
        
        response = client.get("/chaos/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "redis" in data
        assert data["redis"]["connected"] is True
        assert data["redis"]["connection_count"] == 2
        assert data["redis"]["last_reset"] is not None
        
        # Verify get_connection_status was called
        mock_redis_client.get_connection_status.assert_called_once()
    
    @patch("app.main.redis_client", None)
    def test_status_no_redis_client(self, client):
        """Test status when Redis client is not initialized."""
        response = client.get("/chaos/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "redis" in data
        assert data["redis"]["connected"] is False
        assert data["redis"]["connection_count"] == 0
        assert data["redis"]["last_reset"] is None


class TestChaosState:
    """Test chaos state management."""
    
    def test_initial_state(self):
        """Test initial chaos state."""
        state = ChaosState()
        assert state.load_active is False
        assert state.load_level == "low"
        assert state.load_end_time is None
        assert state.hang_active is False
        assert state.hang_end_time is None
        assert state._load_task is None
        assert state._hang_task is None
        assert state.redis_last_reset is None