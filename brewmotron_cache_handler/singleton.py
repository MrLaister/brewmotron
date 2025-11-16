"""
Singleton factory for shared cache handler instance.

Provides a global shared cache handler instance that can be accessed by
multiple brewmotron plugins, ensuring I2C coordination and minimizing
duplicate API calls to CraftBeerPi4.
"""

import asyncio
import logging
from typing import Any, Optional

from .cache_handler import CBPI4CacheHandler

logger = logging.getLogger(__name__)

# Global shared cache handler instance
_global_cache_handler: Optional[CBPI4CacheHandler] = None
_global_lock: Optional[asyncio.Lock] = None


async def get_cache_handler(
    cbpi_instance: Optional[Any] = None,
    enable_i2c: bool = True,
    i2c_queue_size: int = 1000,
) -> CBPI4CacheHandler:
    """
    Get or create the global shared cache handler instance.

    This factory function ensures all brewmotron plugins share a single
    cache handler instance, providing:
    - Single I2C coordinator (true bus coordination)
    - Shared cache (maximum API call reduction)

    The first call MUST provide cbpi_instance. Subsequent calls from other
    plugins can omit it and will receive the same shared instance.

    Args:
        cbpi_instance: CraftBeerPi4 instance (required on first call)
        enable_i2c: Whether to enable I2C coordinator (default: True)
        i2c_queue_size: Max I2C queue size (default: 1000)

    Returns:
        Shared CBPI4CacheHandler instance

    Raises:
        ValueError: If first call doesn't provide cbpi_instance

    Example:
        ```python
        # First plugin to load
        cache = await get_cache_handler(cbpi_instance=cbpi)

        # Subsequent plugins
        cache = await get_cache_handler()  # Gets same instance
        ```
    """
    global _global_cache_handler, _global_lock

    # Initialize lock on first access
    if _global_lock is None:
        _global_lock = asyncio.Lock()

    async with _global_lock:
        if _global_cache_handler is None:
            if cbpi_instance is None:
                raise ValueError(
                    "First call to get_cache_handler() must provide cbpi_instance. " "Subsequent calls can omit it."
                )

            logger.info("Creating global shared cache handler instance")
            _global_cache_handler = CBPI4CacheHandler(
                cbpi_instance=cbpi_instance,
                enable_i2c=enable_i2c,
                i2c_queue_size=i2c_queue_size,
            )
            await _global_cache_handler.start()
            logger.info("Global cache handler started and ready")
        else:
            logger.debug("Returning existing global cache handler instance")

        return _global_cache_handler


async def reset_cache_handler() -> None:
    """
    Reset the global cache handler instance.

    This stops and destroys the current global cache handler, allowing
    a new one to be created. Primarily used for testing.

    Warning:
        This should NOT be called in production code. It will disrupt
        all plugins currently using the cache handler.
    """
    global _global_cache_handler, _global_lock

    if _global_lock is None:
        _global_lock = asyncio.Lock()

    async with _global_lock:
        if _global_cache_handler is not None:
            logger.warning("Resetting global cache handler instance")
            await _global_cache_handler.stop()
            _global_cache_handler = None
            logger.info("Global cache handler reset complete")


def get_cache_handler_sync() -> Optional[CBPI4CacheHandler]:
    """
    Get the global cache handler instance synchronously (if it exists).

    This is a synchronous accessor that returns the existing cache handler
    without creating it. Returns None if no cache handler has been created yet.

    Returns:
        Existing CBPI4CacheHandler instance or None

    Note:
        This does NOT create the cache handler. Use get_cache_handler() for that.
    """
    return _global_cache_handler
