"""
I2C Coordinator for CraftBeerPi4 cache handler.

Provides queued I2C bus access with priority scheduling to prevent bus conflicts
and deadlocks when multiple plugins access I2C devices simultaneously.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class I2CPriority(IntEnum):
    """Priority levels for I2C operations (lower number = higher priority)."""

    CRITICAL = 1  # Sensor reads during active brewing
    NORMAL = 5  # Display updates, actor state reads
    LOW = 10  # Configuration reads, periodic updates


@dataclass(order=True)
class I2COperation:
    """Represents a queued I2C operation with priority."""

    priority: int = field(compare=True)
    address: int = field(compare=False)
    operation_type: str = field(compare=False)  # 'read' or 'write'
    data: Any = field(default=None, compare=False)
    register: Optional[int] = field(default=None, compare=False)
    callback: Optional[Callable] = field(default=None, compare=False)
    retry_count: int = field(default=0, compare=False)
    max_retries: int = field(default=3, compare=False)

    def __post_init__(self):
        """Validate operation after initialization."""
        if self.operation_type not in ["read", "write"]:
            raise ValueError(f"Invalid operation_type: {self.operation_type}")
        if not 0 <= self.address <= 127:
            raise ValueError(f"Invalid I2C address: {self.address}")


class I2CCoordinator:
    """
    Coordinates I2C bus access with priority-based queuing.

    Prevents bus conflicts and deadlocks by serializing all I2C operations
    through a priority queue with async processing.
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        bus_timeout: float = 1.0,
        retry_delay: float = 0.1,
    ):
        """
        Initialize the I2C coordinator.

        Args:
            max_queue_size: Maximum number of queued operations (default: 1000)
            bus_timeout: Maximum time to wait for bus lock in seconds (default: 1.0)
            retry_delay: Base delay between retries in seconds (default: 0.1)
        """
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._bus_lock = asyncio.Lock()
        self._max_queue_size = max_queue_size
        self._bus_timeout = bus_timeout
        self._retry_delay = retry_delay
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False
        self._stats = {
            "operations_queued": 0,
            "operations_completed": 0,
            "operations_failed": 0,
            "retries": 0,
            "queue_overflows": 0,
            "timeouts": 0,
        }

    async def start(self) -> None:
        """Start the background queue processor."""
        if self._running:
            logger.warning("I2C coordinator already running")
            return

        self._running = True
        self._processor_task = asyncio.create_task(self._process_queue())
        logger.info("I2C coordinator started")

    async def stop(self, timeout: float = 2.0) -> None:
        """Stop the background queue processor and wait for completion.

        Args:
            timeout: Maximum time to wait for graceful shutdown (default: 2.0s)
        """
        if not self._running:
            return

        self._running = False

        if self._processor_task and not self._processor_task.done():
            try:
                # Try graceful shutdown first
                await asyncio.wait_for(self._processor_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Coordinator stop timeout after {timeout}s - forcing cancellation")
                self._processor_task.cancel()
                try:
                    await self._processor_task
                except asyncio.CancelledError:
                    logger.info("Coordinator task cancelled successfully")
            finally:
                self._processor_task = None

        logger.info("I2C coordinator stopped")

    async def enqueue_write(
        self,
        address: int,
        data: Any,
        priority: int = I2CPriority.NORMAL,
        register: Optional[int] = None,
        callback: Optional[Callable] = None,
        max_retries: int = 3,
    ) -> bool:
        """
        Enqueue an I2C write operation.

        Args:
            address: I2C device address (0-127)
            data: Data to write to the device
            priority: Operation priority (default: NORMAL)
            register: Optional register address to write to
            callback: Optional callback to call after completion
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            True if operation was queued, False if queue is full
        """
        operation = I2COperation(
            priority=priority,
            address=address,
            operation_type="write",
            data=data,
            register=register,
            callback=callback,
            max_retries=max_retries,
        )
        return await self._enqueue_operation(operation)

    async def enqueue_read(
        self,
        address: int,
        register: Optional[int] = None,
        priority: int = I2CPriority.NORMAL,
        callback: Optional[Callable] = None,
        max_retries: int = 3,
    ) -> bool:
        """
        Enqueue an I2C read operation.

        Args:
            address: I2C device address (0-127)
            register: Optional register address to read from
            priority: Operation priority (default: NORMAL)
            callback: Optional callback to call with read result
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            True if operation was queued, False if queue is full
        """
        operation = I2COperation(
            priority=priority,
            address=address,
            operation_type="read",
            register=register,
            callback=callback,
            max_retries=max_retries,
        )
        return await self._enqueue_operation(operation)

    async def _enqueue_operation(self, operation: I2COperation) -> bool:
        """
        Add an operation to the priority queue.

        Args:
            operation: The I2C operation to queue

        Returns:
            True if queued successfully, False if queue is full
        """
        try:
            self._queue.put_nowait(operation)
            self._stats["operations_queued"] += 1
            logger.debug(
                f"Queued {operation.operation_type} operation for address 0x{operation.address:02X} "
                f"with priority {operation.priority}"
            )
            return True
        except asyncio.QueueFull:
            self._stats["queue_overflows"] += 1
            logger.error(f"Queue overflow: Cannot queue {operation.operation_type} for address 0x{operation.address:02X}")
            return False

    async def _process_queue(self) -> None:
        """
        Background task that processes queued I2C operations.

        Operations are processed in priority order with automatic retry on failure.
        """
        logger.info("I2C queue processor started")

        while self._running or not self._queue.empty():
            try:
                # Wait for next operation (with timeout to check running flag)
                operation = await asyncio.wait_for(self._queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            # Execute the operation
            await self._execute_operation(operation)

        logger.info("I2C queue processor stopped")

    async def _execute_operation(self, operation: I2COperation) -> None:
        """
        Execute a single I2C operation with retry logic.

        Args:
            operation: The operation to execute
        """
        try:
            # Acquire bus lock with timeout to prevent deadlocks
            async with asyncio.timeout(self._bus_timeout):
                async with self._bus_lock:
                    # Perform the actual I2C operation
                    result = await self._perform_i2c_operation(operation)

                    # Call callback if provided (with timeout protection)
                    if operation.callback:
                        try:
                            if asyncio.iscoroutinefunction(operation.callback):
                                # Protect against hanging async callbacks
                                await asyncio.wait_for(operation.callback(result), timeout=1.0)
                            else:
                                # Sync callbacks should complete quickly
                                operation.callback(result)
                        except asyncio.TimeoutError:
                            logger.error(f"Callback timeout for operation on address 0x{operation.address:02X}")
                        except Exception as e:
                            logger.error(f"Callback error for operation on address 0x{operation.address:02X}: {e}")

                    self._stats["operations_completed"] += 1
                    logger.debug(f"Completed {operation.operation_type} for address 0x{operation.address:02X}")

        except asyncio.TimeoutError:
            self._stats["timeouts"] += 1
            logger.error(f"Timeout waiting for bus lock for address 0x{operation.address:02X}")
            await self._handle_operation_failure(operation, "timeout")

        except Exception as e:
            logger.error(f"Error executing {operation.operation_type} for address 0x{operation.address:02X}: {e}")
            await self._handle_operation_failure(operation, str(e))

    async def _perform_i2c_operation(self, operation: I2COperation) -> Any:
        """
        Perform the actual I2C operation.

        This is a placeholder that would be replaced with actual I2C bus interaction.
        In tests, this can be mocked.

        Args:
            operation: The operation to perform

        Returns:
            Result of the operation (for reads), or None (for writes)
        """
        # Placeholder for actual I2C interaction
        # In production, this would use smbus2 or similar library
        logger.debug(f"Performing {operation.operation_type} on address 0x{operation.address:02X}")

        if operation.operation_type == "write":
            # Simulate write operation
            await asyncio.sleep(0.001)  # Simulate I2C latency
            return None
        else:
            # Simulate read operation
            await asyncio.sleep(0.001)  # Simulate I2C latency
            return {"address": operation.address, "data": 0}

    async def _handle_operation_failure(self, operation: I2COperation, error: str) -> None:
        """
        Handle a failed operation with retry logic.

        Args:
            operation: The failed operation
            error: Error description
        """
        operation.retry_count += 1

        if operation.retry_count <= operation.max_retries:
            # Retry with exponential backoff
            delay = self._retry_delay * (2 ** (operation.retry_count - 1))
            logger.info(
                f"Retrying {operation.operation_type} for address 0x{operation.address:02X} "
                f"(attempt {operation.retry_count}/{operation.max_retries}) after {delay:.2f}s"
            )

            await asyncio.sleep(delay)
            await self._queue.put(operation)
            self._stats["retries"] += 1
        else:
            # Max retries exceeded
            self._stats["operations_failed"] += 1
            logger.error(
                f"Failed {operation.operation_type} for address 0x{operation.address:02X} "
                f"after {operation.max_retries} retries: {error}"
            )

    async def flush_queue(self) -> int:
        """
        Clear all pending operations from the queue.

        Returns:
            Number of operations that were flushed
        """
        count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break

        logger.info(f"Flushed {count} operations from queue")
        return count

    def get_queue_size(self) -> int:
        """
        Get the current number of operations in the queue.

        Returns:
            Number of pending operations
        """
        return self._queue.qsize()

    def get_statistics(self) -> dict:
        """
        Get I2C coordinator statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            **self._stats,
            "queue_size": self.get_queue_size(),
            "is_running": self._running,
        }

    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        self._stats = {
            "operations_queued": 0,
            "operations_completed": 0,
            "operations_failed": 0,
            "retries": 0,
            "queue_overflows": 0,
            "timeouts": 0,
        }

    def __repr__(self) -> str:
        """Return string representation of I2CCoordinator."""
        return (
            f"I2CCoordinator(running={self._running}, "
            f"queued={self.get_queue_size()}, "
            f"completed={self._stats['operations_completed']})"
        )
