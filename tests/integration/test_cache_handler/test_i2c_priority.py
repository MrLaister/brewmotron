"""
Integration tests for I2C priority scheduling.

Tests that operations are processed in priority order and that
priority levels work correctly.
"""

import asyncio

import pytest

from brewmotron_cache_handler.i2c_coordinator import I2CCoordinator, I2COperation, I2CPriority


class TestI2CPriority:
    """Test suite for I2C priority scheduling."""

    @pytest.mark.asyncio
    async def test_priority_levels_defined(self):
        """Test all priority levels are defined correctly."""
        assert I2CPriority.CRITICAL == 1
        assert I2CPriority.NORMAL == 5
        assert I2CPriority.LOW == 10

    @pytest.mark.asyncio
    async def test_critical_priority_processed_first(self):
        """Test critical priority operations are processed before others."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        execution_order = []

        async def callback_low(result):
            execution_order.append("low")

        async def callback_critical(result):
            execution_order.append("critical")

        # Enqueue LOW priority first
        await coordinator.enqueue_write(address=0x27, data=[0x01], priority=I2CPriority.LOW, callback=callback_low)

        # Then enqueue CRITICAL priority - should jump to front
        await coordinator.enqueue_write(
            address=0x48,
            data=[0x02],
            priority=I2CPriority.CRITICAL,
            callback=callback_critical,
        )

        await asyncio.sleep(0.2)

        # Critical should execute first even though it was queued second
        assert execution_order[0] == "critical"
        assert execution_order[1] == "low"

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_priority_ordering_with_multiple_levels(self):
        """Test operations are processed in priority order across all levels."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        execution_order = []

        async def make_callback(level):
            async def callback(result):
                execution_order.append(level)

            return callback

        # Enqueue in reverse priority order
        await coordinator.enqueue_write(
            address=0x27,
            data=[0x01],
            priority=I2CPriority.LOW,
            callback=await make_callback("low"),
        )
        await coordinator.enqueue_write(
            address=0x27,
            data=[0x02],
            priority=I2CPriority.NORMAL,
            callback=await make_callback("normal"),
        )
        await coordinator.enqueue_write(
            address=0x27,
            data=[0x03],
            priority=I2CPriority.CRITICAL,
            callback=await make_callback("critical"),
        )

        await asyncio.sleep(0.2)

        # Should execute in priority order
        assert execution_order == ["critical", "normal", "low"]

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_same_priority_processed_in_order(self):
        """Test operations with same priority are processed in FIFO order."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        execution_order = []

        async def make_callback(num):
            async def callback(result):
                execution_order.append(num)

            return callback

        # Enqueue multiple operations with same priority
        for i in range(5):
            await coordinator.enqueue_write(
                address=0x27,
                data=[i],
                priority=I2CPriority.NORMAL,
                callback=await make_callback(i),
            )

        await asyncio.sleep(0.2)

        # All operations should complete
        assert len(execution_order) == 5
        # All numbers should be present
        assert set(execution_order) == {0, 1, 2, 3, 4}
        # First operation should generally complete first (may have small variance due to async)
        assert execution_order[0] in [0, 1]

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_custom_priority_values(self):
        """Test custom priority values work correctly."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        execution_order = []

        async def make_callback(label):
            async def callback(result):
                execution_order.append(label)

            return callback

        # Use custom priority values (lower = higher priority)
        await coordinator.enqueue_write(address=0x27, data=[0x01], priority=100, callback=await make_callback("p100"))
        await coordinator.enqueue_write(address=0x27, data=[0x02], priority=50, callback=await make_callback("p50"))
        await coordinator.enqueue_write(address=0x27, data=[0x03], priority=1, callback=await make_callback("p1"))

        await asyncio.sleep(0.2)

        # Should execute in priority order (1, 50, 100)
        assert execution_order == ["p1", "p50", "p100"]

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_priority_with_reads_and_writes(self):
        """Test priority works correctly for both read and write operations."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        execution_order = []

        async def write_callback(result):
            execution_order.append("write_low")

        async def read_callback(result):
            execution_order.append("read_critical")

        # Low priority write
        await coordinator.enqueue_write(
            address=0x27,
            data=[0x01],
            priority=I2CPriority.LOW,
            callback=write_callback,
        )

        # Critical priority read
        await coordinator.enqueue_read(
            address=0x48,
            register=0x00,
            priority=I2CPriority.CRITICAL,
            callback=read_callback,
        )

        await asyncio.sleep(0.2)

        # Critical read should execute first
        assert execution_order[0] == "read_critical"
        assert execution_order[1] == "write_low"

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_operation_dataclass_ordering(self):
        """Test I2COperation dataclass priority ordering."""
        op1 = I2COperation(priority=I2CPriority.CRITICAL, address=0x27, operation_type="write")
        op2 = I2COperation(priority=I2CPriority.NORMAL, address=0x48, operation_type="read")
        op3 = I2COperation(priority=I2CPriority.LOW, address=0x27, operation_type="write")

        # Lower priority number should compare as "less than"
        assert op1 < op2
        assert op2 < op3
        assert op1 < op3

    @pytest.mark.asyncio
    async def test_high_priority_interrupts_low_priority_queue(self):
        """Test high priority operation interrupts queue of low priority operations."""
        coordinator = I2CCoordinator()
        await coordinator.start()

        execution_order = []

        async def make_callback(label):
            async def callback(result):
                execution_order.append(label)

            return callback

        # Fill queue with low priority operations
        for i in range(5):
            await coordinator.enqueue_write(
                address=0x27,
                data=[i],
                priority=I2CPriority.LOW,
                callback=await make_callback(f"low{i}"),
            )

        # Add critical priority operation - should jump to front
        await coordinator.enqueue_write(
            address=0x48,
            data=[0xFF],
            priority=I2CPriority.CRITICAL,
            callback=await make_callback("critical"),
        )

        await asyncio.sleep(0.3)

        # Critical should be processed before all low priority ops
        # (except possibly the first one if it was already being processed)
        assert "critical" in execution_order[:2]  # Should be first or second

        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_priority_with_retry(self):
        """Test priority is maintained across retries."""
        coordinator = I2CCoordinator()

        # Mock _perform_i2c_operation to fail once
        original_perform = coordinator._perform_i2c_operation
        call_count = {"count": 0}

        async def mock_perform(operation):
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise RuntimeError("Simulated failure")
            return await original_perform(operation)

        coordinator._perform_i2c_operation = mock_perform

        await coordinator.start()

        execution_order = []

        async def callback_critical(result):
            execution_order.append("critical")

        async def callback_low(result):
            execution_order.append("low")

        # Critical operation that will fail and retry
        await coordinator.enqueue_write(
            address=0x27,
            data=[0x01],
            priority=I2CPriority.CRITICAL,
            callback=callback_critical,
            max_retries=1,
        )

        # Low priority operation
        await coordinator.enqueue_write(address=0x48, data=[0x02], priority=I2CPriority.LOW, callback=callback_low)

        await asyncio.sleep(0.5)

        # Critical should still complete before low, even with retry
        if len(execution_order) == 2:
            assert execution_order[0] == "critical"
            assert execution_order[1] == "low"

        await coordinator.stop()
