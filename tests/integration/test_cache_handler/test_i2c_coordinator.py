"""
Integration tests for I2CCoordinator class.

Tests basic I2C coordinator functionality including queue operations,
operation execution, and statistics tracking.
"""

import asyncio

import pytest

from brewmotron_cache_handler.i2c_coordinator import I2CCoordinator, I2COperation, I2CPriority


class TestI2CCoordinator:
    """Test suite for I2CCoordinator class."""

    @pytest.mark.asyncio
    async def test_coordinator_initialization(self):
        """Test I2C coordinator can be created with default settings."""
        coordinator = I2CCoordinator()
        assert coordinator is not None
        assert coordinator.get_queue_size() == 0
        assert not coordinator._running

    @pytest.mark.asyncio
    async def test_coordinator_custom_settings(self):
        """Test coordinator can be created with custom settings."""
        coordinator = I2CCoordinator(max_queue_size=500, bus_timeout=2.0, retry_delay=0.2)
        assert coordinator._max_queue_size == 500
        assert coordinator._bus_timeout == 2.0
        assert coordinator._retry_delay == 0.2

    @pytest.mark.asyncio
    async def test_start_and_stop_coordinator(self):
        """Test starting and stopping the coordinator."""
        coordinator = I2CCoordinator()

        await coordinator.start()
        assert coordinator._running is True
        assert coordinator._processor_task is not None

        await coordinator.stop()
        assert coordinator._running is False

    @pytest.mark.asyncio
    async def test_enqueue_write_operation(self):
        """Test enqueueing a write operation."""
        coordinator = I2CCoordinator()
        result = await coordinator.enqueue_write(address=0x27, data=[0x01, 0x02], priority=I2CPriority.NORMAL)

        assert result is True
        assert coordinator.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_enqueue_read_operation(self):
        """Test enqueueing a read operation."""
        coordinator = I2CCoordinator()
        result = await coordinator.enqueue_read(address=0x48, register=0x00, priority=I2CPriority.CRITICAL)

        assert result is True
        assert coordinator.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_queue_overflow_protection(self):
        """Test queue overflow protection with small queue."""
        coordinator = I2CCoordinator(max_queue_size=2)

        # Fill the queue
        await coordinator.enqueue_write(address=0x27, data=[0x01])
        await coordinator.enqueue_write(address=0x27, data=[0x02])

        # Try to add one more - should fail
        result = await coordinator.enqueue_write(address=0x27, data=[0x03])

        assert result is False
        stats = coordinator.get_statistics()
        assert stats["queue_overflows"] == 1

    @pytest.mark.asyncio
    async def test_operation_processing(self):
        """Test operations are processed from queue."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        # Enqueue an operation
        await coordinator.enqueue_write(address=0x27, data=[0x01])

        # Wait for processing
        await asyncio.sleep(0.1)

        stats = coordinator.get_statistics()
        assert stats["operations_completed"] >= 1
        assert coordinator.get_queue_size() == 0

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_flush_queue(self):
        """Test flushing pending operations from queue."""
        coordinator = I2CCoordinator()

        # Add several operations
        await coordinator.enqueue_write(address=0x27, data=[0x01])
        await coordinator.enqueue_write(address=0x27, data=[0x02])
        await coordinator.enqueue_write(address=0x27, data=[0x03])

        assert coordinator.get_queue_size() == 3

        # Flush the queue
        flushed = await coordinator.flush_queue()

        assert flushed == 3
        assert coordinator.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_statistics_tracking(self):
        """Test coordinator tracks statistics correctly."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        await coordinator.enqueue_write(address=0x27, data=[0x01])
        await coordinator.enqueue_read(address=0x48, register=0x00)

        await asyncio.sleep(0.1)

        stats = coordinator.get_statistics()
        assert stats["operations_queued"] == 2
        assert stats["operations_completed"] >= 1
        assert "queue_size" in stats
        assert "is_running" in stats

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_reset_statistics(self):
        """Test statistics can be reset."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        await coordinator.enqueue_write(address=0x27, data=[0x01])
        await asyncio.sleep(0.1)

        coordinator.reset_statistics()
        stats = coordinator.get_statistics()

        assert stats["operations_queued"] == 0
        assert stats["operations_completed"] == 0

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_callback_on_completion(self):
        """Test callback is called when operation completes."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        callback_called = False
        result_data = None

        async def completion_callback(result):
            nonlocal callback_called, result_data
            callback_called = True
            result_data = result

        await coordinator.enqueue_read(address=0x48, register=0x00, callback=completion_callback)

        await asyncio.sleep(0.1)

        assert callback_called is True
        assert result_data is not None

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_sync_callback_support(self):
        """Test synchronous callbacks are supported."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        callback_called = False

        def sync_callback(result):
            nonlocal callback_called
            callback_called = True

        await coordinator.enqueue_write(address=0x27, data=[0x01], callback=sync_callback)

        await asyncio.sleep(0.1)

        assert callback_called is True

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_repr_string(self):
        """Test string representation of coordinator."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        await coordinator.enqueue_write(address=0x27, data=[0x01])
        await asyncio.sleep(0.1)

        repr_str = repr(coordinator)
        assert "I2CCoordinator" in repr_str
        assert "running" in repr_str
        assert "completed" in repr_str

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_multiple_operations_processed(self):
        """Test multiple operations are processed in order."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        # Enqueue multiple operations
        for i in range(10):
            await coordinator.enqueue_write(address=0x27, data=[i])

        # Wait for all to complete
        await asyncio.sleep(0.2)

        stats = coordinator.get_statistics()
        assert stats["operations_completed"] == 10

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_coordinator_double_start_ignored(self):
        """Test starting coordinator twice doesn't create issues."""
        coordinator = I2CCoordinator()

        await coordinator.start()
        task1 = coordinator._processor_task

        # Try to start again
        await coordinator.start()
        task2 = coordinator._processor_task

        # Should be the same task
        assert task1 is task2

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_coordinator_stops_cleanly_with_pending_operations(self):
        """Test coordinator stops cleanly even with pending operations."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        # Add operations but stop immediately
        await coordinator.enqueue_write(address=0x27, data=[0x01])
        await coordinator.enqueue_write(address=0x27, data=[0x02])

        await coordinator.stop()

        # Should complete without hanging
        assert coordinator._running is False
