"""
Main Cache Handler API for CraftBeerPi4.

Provides a unified facade integrating cache store, event bus, and I2C coordinator
for simplified plugin access to brewing data.
"""

import logging
from typing import Any, Callable, Dict, Optional

from .cache_store import CacheType, DataCache
from .event_bus import Event, EventBus, EventTopic
from .i2c_coordinator import I2CCoordinator, I2CPriority

logger = logging.getLogger(__name__)


class CBPI4CacheHandler:
    """
    Unified cache handler for CraftBeerPi4 plugins.

    Integrates cache store, event bus, and I2C coordinator to provide:
    - Fast cached data access with automatic TTL expiration
    - Event-driven updates to eliminate polling
    - Coordinated I2C bus access to prevent conflicts
    """

    def __init__(
        self,
        cbpi_instance: Optional[Any] = None,
        enable_i2c: bool = True,
        cache_history_size: int = 100,
        i2c_queue_size: int = 1000,
    ):
        """
        Initialize the cache handler.

        Args:
            cbpi_instance: CraftBeerPi4 instance for data fetching
            enable_i2c: Whether to enable I2C coordinator (default: True)
            cache_history_size: Event history size (default: 100)
            i2c_queue_size: Max I2C queue size (default: 1000)
        """
        self._cbpi = cbpi_instance
        self._cache = DataCache(cbpi=cbpi_instance)
        self._event_bus = EventBus(history_size=cache_history_size)
        self._i2c_coordinator = I2CCoordinator(max_queue_size=i2c_queue_size) if enable_i2c else None
        self._running = False

    async def start(self) -> None:
        """Start the cache handler (starts I2C coordinator if enabled)."""
        if self._running:
            logger.warning("Cache handler already running")
            return

        if self._i2c_coordinator:
            await self._i2c_coordinator.start()

        self._running = True
        logger.info("Cache handler started")

    async def stop(self) -> None:
        """Stop the cache handler (stops I2C coordinator if enabled)."""
        if not self._running:
            return

        if self._i2c_coordinator:
            await self._i2c_coordinator.stop()

        self._running = False
        logger.info("Cache handler stopped")

    # Data Access Methods

    async def get_step_state(self, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get current brewing step state.

        Args:
            force_refresh: Force cache refresh (default: False)

        Returns:
            Step state dictionary or None
        """

        async def fetch_step_state():
            if self._cbpi and hasattr(self._cbpi, "step") and hasattr(self._cbpi.step, "get_state"):
                return await self._cbpi.step.get_state()
            return None

        return await self._cache.get(CacheType.STEP, fetch_func=fetch_step_state, force_refresh=force_refresh)

    async def get_kettle_state(self, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get all kettles state.

        Args:
            force_refresh: Force cache refresh (default: False)

        Returns:
            Kettle state dictionary or None
        """

        async def fetch_kettle_state():
            if self._cbpi and hasattr(self._cbpi, "kettle") and hasattr(self._cbpi.kettle, "get_state"):
                return await self._cbpi.kettle.get_state()
            return None

        return await self._cache.get(CacheType.KETTLE, fetch_func=fetch_kettle_state, force_refresh=force_refresh)

    async def get_sensor_state(self, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get all sensors state.

        Args:
            force_refresh: Force cache refresh (default: False)

        Returns:
            Sensor state dictionary or None
        """

        async def fetch_sensor_state():
            if self._cbpi and hasattr(self._cbpi, "sensor") and hasattr(self._cbpi.sensor, "get_state"):
                return await self._cbpi.sensor.get_state()
            return None

        return await self._cache.get(CacheType.SENSOR, fetch_func=fetch_sensor_state, force_refresh=force_refresh)

    async def get_sensor_value(self, sensor_id: str, force_refresh: bool = False) -> Optional[float]:
        """
        Get a specific sensor's value.

        Args:
            sensor_id: Sensor ID to read
            force_refresh: Force cache refresh (default: False)

        Returns:
            Sensor value or None
        """
        sensor_state = await self.get_sensor_state(force_refresh=force_refresh)
        if sensor_state and sensor_id in sensor_state:
            return sensor_state[sensor_id].get("value")
        return None

    async def get_actor_state(self, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get all actors state.

        Args:
            force_refresh: Force cache refresh (default: False)

        Returns:
            Actor state dictionary or None
        """

        async def fetch_actor_state():
            if self._cbpi and hasattr(self._cbpi, "actor") and hasattr(self._cbpi.actor, "get_state"):
                return await self._cbpi.actor.get_state()
            return None

        return await self._cache.get(CacheType.ACTOR, fetch_func=fetch_actor_state, force_refresh=force_refresh)

    async def get_config(self, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get configuration data.

        Args:
            force_refresh: Force cache refresh (default: False)

        Returns:
            Configuration dictionary or None
        """

        async def fetch_config():
            if self._cbpi and hasattr(self._cbpi, "config") and hasattr(self._cbpi.config, "get_state"):
                return await self._cbpi.config.get_state()
            return None

        return await self._cache.get(CacheType.CONFIG, fetch_func=fetch_config, force_refresh=force_refresh)

    # Cache Management Methods

    async def invalidate(self, cache_type: CacheType) -> None:
        """
        Invalidate a specific cache.

        Args:
            cache_type: Type of cache to invalidate
        """
        await self._cache.invalidate(cache_type)
        logger.debug(f"Invalidated cache: {cache_type.value}")

    async def invalidate_all(self) -> None:
        """Invalidate all caches."""
        await self._cache.invalidate(None)
        logger.debug("Invalidated all caches")

    async def refresh_all(self) -> None:
        """Force refresh all caches."""
        await self.get_step_state(force_refresh=True)
        await self.get_kettle_state(force_refresh=True)
        await self.get_sensor_state(force_refresh=True)
        await self.get_actor_state(force_refresh=True)
        await self.get_config(force_refresh=True)
        logger.debug("Refreshed all caches")

    async def warm_cache(self) -> None:
        """Pre-populate all caches."""
        await self.refresh_all()
        logger.info("Cache warmed successfully")

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return self._cache.get_stats()

    async def get_cache_info(self, cache_type: CacheType) -> Optional[Dict]:
        """
        Get info about a specific cache.

        Args:
            cache_type: Type of cache to get info for

        Returns:
            Cache info dictionary or None
        """
        return await self._cache.get_cache_info(cache_type)

    # Event Subscription Methods

    async def subscribe_to_step_changes(self, callback: Callable[[Event], Any]) -> None:
        """
        Subscribe to step state change events.

        Args:
            callback: Async function to call on step changes
        """
        await self._event_bus.subscribe(EventTopic.STEP_CHANGED, callback)

    async def subscribe_to_kettle_updates(self, callback: Callable[[Event], Any]) -> None:
        """
        Subscribe to kettle update events.

        Args:
            callback: Async function to call on kettle updates
        """
        await self._event_bus.subscribe(EventTopic.KETTLE_UPDATED, callback)

    async def subscribe_to_sensor_values(self, callback: Callable[[Event], Any]) -> None:
        """
        Subscribe to sensor value change events.

        Args:
            callback: Async function to call on sensor value changes
        """
        await self._event_bus.subscribe(EventTopic.SENSOR_VALUE, callback)

    async def subscribe_to_actor_state(self, callback: Callable[[Event], Any]) -> None:
        """
        Subscribe to actor state change events.

        Args:
            callback: Async function to call on actor state changes
        """
        await self._event_bus.subscribe(EventTopic.ACTOR_STATE, callback)

    async def subscribe_to_config_updates(self, callback: Callable[[Event], Any]) -> None:
        """
        Subscribe to config update events.

        Args:
            callback: Async function to call on config updates
        """
        await self._event_bus.subscribe(EventTopic.CONFIG_UPDATED, callback)

    async def unsubscribe(self, topic: EventTopic, callback: Callable[[Event], Any]) -> bool:
        """
        Unsubscribe from events.

        Args:
            topic: Event topic to unsubscribe from
            callback: Callback function to remove

        Returns:
            True if unsubscribed, False if not found
        """
        return await self._event_bus.unsubscribe(topic, callback)

    async def publish_event(self, topic: EventTopic, data: Any) -> None:
        """
        Publish an event (for manual event triggering).

        Args:
            topic: Event topic to publish to
            data: Event data
        """
        await self._event_bus.publish(topic, data)

    def get_event_stats(self) -> Dict:
        """
        Get event bus statistics.

        Returns:
            Dictionary with event statistics
        """
        return self._event_bus.get_statistics()

    # I2C Coordination Methods

    async def i2c_write(
        self,
        address: int,
        data: Any,
        priority: int = I2CPriority.NORMAL,
        register: Optional[int] = None,
        callback: Optional[Callable] = None,
    ) -> bool:
        """
        Queue an I2C write operation.

        Args:
            address: I2C device address (0-127)
            data: Data to write
            priority: Operation priority (default: NORMAL)
            register: Optional register address
            callback: Optional completion callback

        Returns:
            True if queued successfully, False otherwise
        """
        if not self._i2c_coordinator:
            logger.error("I2C coordinator not enabled")
            return False

        return await self._i2c_coordinator.enqueue_write(
            address=address,
            data=data,
            priority=priority,
            register=register,
            callback=callback,
        )

    async def i2c_read(
        self,
        address: int,
        register: Optional[int] = None,
        priority: int = I2CPriority.NORMAL,
        callback: Optional[Callable] = None,
    ) -> bool:
        """
        Queue an I2C read operation.

        Args:
            address: I2C device address (0-127)
            register: Optional register address
            priority: Operation priority (default: NORMAL)
            callback: Optional completion callback

        Returns:
            True if queued successfully, False otherwise
        """
        if not self._i2c_coordinator:
            logger.error("I2C coordinator not enabled")
            return False

        return await self._i2c_coordinator.enqueue_read(
            address=address, register=register, priority=priority, callback=callback
        )

    def get_i2c_stats(self) -> Optional[Dict]:
        """
        Get I2C coordinator statistics.

        Returns:
            Dictionary with I2C statistics or None if I2C disabled
        """
        if not self._i2c_coordinator:
            return None
        return self._i2c_coordinator.get_statistics()

    def get_i2c_queue_size(self) -> int:
        """
        Get current I2C queue size.

        Returns:
            Number of pending I2C operations, or 0 if I2C disabled
        """
        if not self._i2c_coordinator:
            return 0
        return self._i2c_coordinator.get_queue_size()

    # Utility Methods

    def set_cache_ttl(self, cache_type: CacheType, ttl: float) -> None:
        """
        Set TTL for a specific cache type.

        Args:
            cache_type: Type of cache
            ttl: Time-to-live in seconds
        """
        self._cache.set_ttl(cache_type, ttl)

    def get_cache_ttl(self, cache_type: CacheType) -> float:
        """
        Get TTL for a specific cache type.

        Args:
            cache_type: Type of cache

        Returns:
            TTL in seconds
        """
        return self._cache.get_ttl(cache_type)

    def __repr__(self) -> str:
        """Return string representation of cache handler."""
        i2c_status = "enabled" if self._i2c_coordinator else "disabled"
        return f"CBPI4CacheHandler(running={self._running}, i2c={i2c_status})"
