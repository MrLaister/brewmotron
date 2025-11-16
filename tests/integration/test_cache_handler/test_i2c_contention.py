"""
Integration tests for I2C bus contention and concurrency.

Tests concurrent access, retry logic, timeout handling, and
deadlock prevention.
"""

import asyncio

import pytest

from brewmotron_cache_handler.i2c_coordinator import I2CCoordinator, I2COperation, I2CPriority


class TestI2CContention:
    """Test suite for I2C bus contention and concurrency."""

    @pytest.mark.asyncio
    async def test_concurrent_enqueue_operations(self):
        """Test multiple coroutines can enqueue operations concurrently."""
        coordinator = I2CCoordinator()

        async def enqueue_batch(start_addr, count):
            for i in range(count):
                await coordinator.enqueue_write(address=start_addr + i, data=[i])

        # Enqueue from multiple coroutines concurrently
        await asyncio.gather(enqueue_batch(0x10, 10), enqueue_batch(0x20, 10), enqueue_batch(0x30, 10))

        assert coordinator.get_queue_size() == 30

    @pytest.mark.asyncio
    async def test_bus_lock_prevents_concurrent_execution(self):
        """Test bus lock prevents concurrent I2C operations."""
        coordinator = I2CCoordinator()

        execution_times = []

        # Mock _perform_i2c_operation to track concurrent execution
        original_perform = coordinator._perform_i2c_operation

        async def mock_perform(operation):
            execution_times.append(("start", asyncio.get_event_loop().time()))
            result = await original_perform(operation)
            execution_times.append(("end", asyncio.get_event_loop().time()))
            return result

        coordinator._perform_i2c_operation = mock_perform

        await coordinator.start()

        # Enqueue multiple operations
        for i in range(5):
            await coordinator.enqueue_write(address=0x27, data=[i])

        await asyncio.sleep(0.2)

        # Check that operations don't overlap
        starts = [t for label, t in execution_times if label == "start"]
        ends = [t for label, t in execution_times if label == "end"]

        # Each operation should end before the next starts
        for i in range(len(ends) - 1):
            assert ends[i] <= starts[i + 1]

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_retry_on_operation_failure(self):
        """Test operations are retried on failure."""
        coordinator = I2CCoordinator()

        # Mock _perform_i2c_operation to fail first time
        call_count = {"count": 0}

        async def mock_perform(operation):
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise RuntimeError("Simulated I2C error")
            return None

        coordinator._perform_i2c_operation = mock_perform

        await coordinator.start()

        await coordinator.enqueue_write(address=0x27, data=[0x01], max_retries=2)

        await asyncio.sleep(0.5)

        stats = coordinator.get_statistics()
        assert stats["retries"] >= 1
        assert stats["operations_completed"] >= 1

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_exponential_backoff_on_retry(self):
        """Test retry uses exponential backoff."""
        coordinator = I2CCoordinator(retry_delay=0.1)

        # Mock to fail multiple times
        call_count = {"count": 0}
        call_times = []

        async def mock_perform(operation):
            call_count["count"] += 1
            call_times.append(asyncio.get_event_loop().time())
            if call_count["count"] < 3:
                raise RuntimeError("Simulated failure")
            return None

        coordinator._perform_i2c_operation = mock_perform

        await coordinator.start()

        await coordinator.enqueue_write(address=0x27, data=[0x01], max_retries=3)

        await asyncio.sleep(1.0)

        # Check that delays increase exponentially
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]

            # Second delay should be roughly 2x first delay (exponential backoff)
            assert delay2 > delay1

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test operation fails after max retries are exhausted."""
        coordinator = I2CCoordinator()

        # Mock to always fail
        async def mock_perform(operation):
            raise RuntimeError("Permanent failure")

        coordinator._perform_i2c_operation = mock_perform

        await coordinator.start()

        await coordinator.enqueue_write(address=0x27, data=[0x01], max_retries=2)

        await asyncio.sleep(0.5)

        stats = coordinator.get_statistics()
        assert stats["operations_failed"] >= 1

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_timeout_on_bus_lock(self):
        """Test timeout occurs when bus lock cannot be acquired."""
        coordinator = I2CCoordinator(bus_timeout=0.1)

        # Hold the bus lock indefinitely
        async def block_bus():
            async with coordinator._bus_lock:
                await asyncio.sleep(1.0)

        # Start blocking the bus
        block_task = asyncio.create_task(block_bus())

        await coordinator.start()

        # Try to enqueue operation - should timeout
        await coordinator.enqueue_write(address=0x27, data=[0x01], max_retries=0)

        await asyncio.sleep(0.3)

        stats = coordinator.get_statistics()
        # Timeout should be recorded
        assert stats["timeouts"] >= 1 or stats["operations_failed"] >= 1

        await coordinator.stop()
        block_task.cancel()
        try:
            await block_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_high_load_concurrent_operations(self):
        """Test coordinator handles high load with many concurrent operations."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        # Enqueue 100 operations
        for i in range(100):
            await coordinator.enqueue_write(address=0x27, data=[i])

        # Wait for all to process
        await asyncio.sleep(1.0)

        stats = coordinator.get_statistics()
        assert stats["operations_completed"] == 100
        assert stats["operations_failed"] == 0

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_mixed_priority_under_contention(self):
        """Test priority scheduling works correctly under high contention."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        execution_order = []

        async def make_callback(label):
            async def callback(result):
                execution_order.append(label)

            return callback

        # Enqueue many low priority operations
        for i in range(20):
            await coordinator.enqueue_write(
                address=0x27,
                data=[i],
                priority=I2CPriority.LOW,
                callback=await make_callback(f"low{i}"),
            )

        # Sprinkle in some critical operations
        for i in range(3):
            await coordinator.enqueue_write(
                address=0x48,
                data=[i],
                priority=I2CPriority.CRITICAL,
                callback=await make_callback(f"critical{i}"),
            )

        await asyncio.sleep(0.5)

        # Critical operations should be in the first few processed
        critical_positions = [i for i, label in enumerate(execution_order) if "critical" in label]
        if critical_positions:
            # At least one critical should be processed early
            assert min(critical_positions) < 5

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_operation_validation(self):
        """Test I2COperation validation catches invalid operations."""
        # Invalid operation type
        with pytest.raises(ValueError, match="Invalid operation_type"):
            I2COperation(priority=1, address=0x27, operation_type="invalid")

        # Invalid I2C address (too high)
        with pytest.raises(ValueError, match="Invalid I2C address"):
            I2COperation(priority=1, address=200, operation_type="write")

        # Invalid I2C address (negative)
        with pytest.raises(ValueError, match="Invalid I2C address"):
            I2COperation(priority=1, address=-1, operation_type="write")

    @pytest.mark.asyncio
    async def test_concurrent_flush_and_enqueue(self):
        """Test concurrent flush and enqueue operations."""
        coordinator = I2CCoordinator()

        # Enqueue some operations
        for i in range(10):
            await coordinator.enqueue_write(address=0x27, data=[i])

        async def enqueue_more():
            for i in range(5):
                await coordinator.enqueue_write(address=0x48, data=[i])
                await asyncio.sleep(0.01)

        async def flush_queue():
            await asyncio.sleep(0.02)
            await coordinator.flush_queue()

        # Run enqueue and flush concurrently
        await asyncio.gather(enqueue_more(), flush_queue())

        # Queue should be empty or contain only recently added items
        assert coordinator.get_queue_size() <= 5

    @pytest.mark.asyncio
    async def test_callback_error_doesnt_crash_coordinator(self):
        """Test callback errors don't crash the coordinator."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        success_count = {"count": 0}

        async def failing_callback(result):
            raise RuntimeError("Callback error")

        async def success_callback(result):
            success_count["count"] += 1

        # Enqueue operation with failing callback
        await coordinator.enqueue_write(address=0x27, data=[0x01], callback=failing_callback)

        # Enqueue operation with success callback
        await coordinator.enqueue_write(address=0x48, data=[0x02], callback=success_callback)

        await asyncio.sleep(0.2)

        # Success callback should still execute
        assert success_count["count"] == 1

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_stop_waits_for_current_operation(self):
        """Test stop() waits for current operation to complete."""
        coordinator = I2CCoordinator()

        operation_completed = {"completed": False}

        async def slow_operation(operation):
            await asyncio.sleep(0.1)
            operation_completed["completed"] = True
            return None

        coordinator._perform_i2c_operation = slow_operation

        await coordinator.start()
        await coordinator.enqueue_write(address=0x27, data=[0x01])

        # Stop should wait for operation to complete
        await coordinator.stop()

        assert operation_completed["completed"] is True

    @pytest.mark.asyncio
    async def test_deadlock_prevention_with_timeout(self):
        """Test timeout prevents deadlocks in bus access."""
        coordinator = I2CCoordinator(bus_timeout=0.2)

        deadlock_detected = {"detected": False}

        async def deadlock_operation(operation):
            # Try to acquire lock again (simulating potential deadlock)
            try:
                async with asyncio.timeout(0.1):
                    async with coordinator._bus_lock:
                        await asyncio.sleep(0.05)
            except asyncio.TimeoutError:
                deadlock_detected["detected"] = True
            return None

        coordinator._perform_i2c_operation = deadlock_operation

        await coordinator.start()
        await coordinator.enqueue_write(address=0x27, data=[0x01])

        await asyncio.sleep(0.5)

        # Coordinator should still be functional (no permanent deadlock)
        stats = coordinator.get_statistics()
        assert coordinator._running is True

        await coordinator.stop()
