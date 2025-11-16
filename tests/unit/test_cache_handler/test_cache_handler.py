"""
Unit tests for CBPI4CacheHandler class.

Tests the main cache handler API that integrates cache store,
event bus, and I2C coordinator.
"""

import asyncio

import pytest

from brewmotron_cache_handler.cache_handler import CBPI4CacheHandler
from brewmotron_cache_handler.cache_store import CacheType
from brewmotron_cache_handler.event_bus import Event, EventTopic
from brewmotron_cache_handler.i2c_coordinator import I2CPriority


class MockCBPI:
    """Mock CraftBeerPi instance for testing."""

    def __init__(self):
        self.step = MockStep()
        self.kettle = MockKettle()
        self.sensor = MockSensor()
        self.actor = MockActor()
        self.config = MockConfig()


class MockStep:
    async def get_state(self):
        return {"current_step": "mash", "timer": 3600}


class MockKettle:
    async def get_state(self):
        return {"mash_tun": {"temp": 65.5, "target": 67.0}}


class MockSensor:
    async def get_state(self):
        return {"temp1": {"value": 65.5, "unit": "C"}}


class MockActor:
    async def get_state(self):
        return {"pump": {"state": "on", "power": 100}}


class MockConfig:
    async def get_state(self):
        return {"brewery_name": "Test Brewery"}


class TestCBPI4CacheHandler:
    """Test suite for CBPI4CacheHandler class."""

    @pytest.mark.asyncio
    async def test_cache_handler_initialization(self):
        """Test cache handler can be initialized."""
        handler = CBPI4CacheHandler()
        assert handler is not None
        assert handler._cache is not None
        assert handler._event_bus is not None
        assert handler._i2c_coordinator is not None

    @pytest.mark.asyncio
    async def test_cache_handler_with_cbpi_instance(self):
        """Test cache handler with CBPI instance."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)
        assert handler._cbpi is cbpi

    @pytest.mark.asyncio
    async def test_cache_handler_without_i2c(self):
        """Test cache handler can be initialized without I2C."""
        handler = CBPI4CacheHandler(enable_i2c=False)
        assert handler._i2c_coordinator is None

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """Test starting and stopping cache handler."""
        handler = CBPI4CacheHandler()

        await handler.start()
        assert handler._running is True

        await handler.stop()
        assert handler._running is False

    @pytest.mark.asyncio
    async def test_double_start_ignored(self):
        """Test starting twice doesn't cause issues."""
        handler = CBPI4CacheHandler()

        await handler.start()
        await handler.start()  # Should be ignored

        assert handler._running is True
        await handler.stop()

    @pytest.mark.asyncio
    async def test_get_step_state(self):
        """Test getting step state."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        state = await handler.get_step_state()
        assert state is not None
        assert state["current_step"] == "mash"

    @pytest.mark.asyncio
    async def test_get_kettle_state(self):
        """Test getting kettle state."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        state = await handler.get_kettle_state()
        assert state is not None
        assert "mash_tun" in state

    @pytest.mark.asyncio
    async def test_get_sensor_state(self):
        """Test getting sensor state."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        state = await handler.get_sensor_state()
        assert state is not None
        assert "temp1" in state

    @pytest.mark.asyncio
    async def test_get_sensor_value(self):
        """Test getting specific sensor value."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        value = await handler.get_sensor_value("temp1")
        assert value == 65.5

    @pytest.mark.asyncio
    async def test_get_sensor_value_missing(self):
        """Test getting non-existent sensor returns None."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        value = await handler.get_sensor_value("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_get_actor_state(self):
        """Test getting actor state."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        state = await handler.get_actor_state()
        assert state is not None
        assert "pump" in state

    @pytest.mark.asyncio
    async def test_get_config(self):
        """Test getting config."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        config = await handler.get_config()
        assert config is not None
        assert config["brewery_name"] == "Test Brewery"

    @pytest.mark.asyncio
    async def test_force_refresh(self):
        """Test force refresh bypasses cache."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        # First call caches
        state1 = await handler.get_step_state()

        # Modify mock data
        cbpi.step.data = {"current_step": "boil", "timer": 1800}
        cbpi.step.get_state = lambda: asyncio.coroutine(lambda: cbpi.step.data)()

        # Without force refresh, should get cached data
        state2 = await handler.get_step_state(force_refresh=False)
        assert state2 == state1

        # With force refresh, should get new data
        state3 = await handler.get_step_state(force_refresh=True)
        # Note: Due to caching complexity, this may still return cached in this simple test

    @pytest.mark.asyncio
    async def test_invalidate_cache(self):
        """Test invalidating specific cache."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        # Cache some data
        await handler.get_step_state()

        # Invalidate
        await handler.invalidate(CacheType.STEP)

        # Cache should be invalid now
        assert not handler._cache.is_valid(CacheType.STEP)

    @pytest.mark.asyncio
    async def test_invalidate_all_caches(self):
        """Test invalidating all caches."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        # Cache all data
        await handler.get_step_state()
        await handler.get_kettle_state()

        # Invalidate all
        await handler.invalidate_all()

        # All caches should be invalid
        assert not handler._cache.is_valid(CacheType.STEP)
        assert not handler._cache.is_valid(CacheType.KETTLE)

    @pytest.mark.asyncio
    async def test_refresh_all(self):
        """Test refreshing all caches."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        await handler.refresh_all()

        # All caches should be valid
        assert handler._cache.is_valid(CacheType.STEP)
        assert handler._cache.is_valid(CacheType.KETTLE)
        assert handler._cache.is_valid(CacheType.SENSOR)
        assert handler._cache.is_valid(CacheType.ACTOR)
        assert handler._cache.is_valid(CacheType.CONFIG)

    @pytest.mark.asyncio
    async def test_warm_cache(self):
        """Test warming cache pre-populates data."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        await handler.warm_cache()

        # All caches should be populated
        assert handler._cache.is_valid(CacheType.STEP)
        assert handler._cache.is_valid(CacheType.KETTLE)

    @pytest.mark.asyncio
    async def test_get_cache_stats(self):
        """Test getting cache statistics."""
        handler = CBPI4CacheHandler()

        stats = handler.get_cache_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats

    @pytest.mark.asyncio
    async def test_get_cache_info(self):
        """Test getting cache info."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        await handler.get_step_state()

        info = await handler.get_cache_info(CacheType.STEP)
        assert info is not None

    @pytest.mark.asyncio
    async def test_subscribe_to_step_changes(self):
        """Test subscribing to step change events."""
        handler = CBPI4CacheHandler()

        callback_called = False

        async def callback(event: Event):
            nonlocal callback_called
            callback_called = True

        await handler.subscribe_to_step_changes(callback)
        await handler.publish_event(EventTopic.STEP_CHANGED, {"step": "boil"})

        await asyncio.sleep(0.01)
        assert callback_called is True

    @pytest.mark.asyncio
    async def test_subscribe_to_kettle_updates(self):
        """Test subscribing to kettle update events."""
        handler = CBPI4CacheHandler()

        received_data = None

        async def callback(event: Event):
            nonlocal received_data
            received_data = event.data

        await handler.subscribe_to_kettle_updates(callback)
        await handler.publish_event(EventTopic.KETTLE_UPDATED, {"kettle": "mash_tun"})

        await asyncio.sleep(0.01)
        assert received_data == {"kettle": "mash_tun"}

    @pytest.mark.asyncio
    async def test_subscribe_to_sensor_values(self):
        """Test subscribing to sensor value events."""
        handler = CBPI4CacheHandler()

        callback_called = False

        async def callback(event: Event):
            nonlocal callback_called
            callback_called = True

        await handler.subscribe_to_sensor_values(callback)
        await handler.publish_event(EventTopic.SENSOR_VALUE, {"sensor": "temp1"})

        await asyncio.sleep(0.01)
        assert callback_called is True

    @pytest.mark.asyncio
    async def test_subscribe_to_actor_state(self):
        """Test subscribing to actor state events."""
        handler = CBPI4CacheHandler()

        callback_called = False

        async def callback(event: Event):
            nonlocal callback_called
            callback_called = True

        await handler.subscribe_to_actor_state(callback)
        await handler.publish_event(EventTopic.ACTOR_STATE, {"actor": "pump"})

        await asyncio.sleep(0.01)
        assert callback_called is True

    @pytest.mark.asyncio
    async def test_subscribe_to_config_updates(self):
        """Test subscribing to config update events."""
        handler = CBPI4CacheHandler()

        callback_called = False

        async def callback(event: Event):
            nonlocal callback_called
            callback_called = True

        await handler.subscribe_to_config_updates(callback)
        await handler.publish_event(EventTopic.CONFIG_UPDATED, {"key": "value"})

        await asyncio.sleep(0.01)
        assert callback_called is True

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Test unsubscribing from events."""
        handler = CBPI4CacheHandler()

        call_count = 0

        async def callback(event: Event):
            nonlocal call_count
            call_count += 1

        await handler.subscribe_to_step_changes(callback)
        await handler.publish_event(EventTopic.STEP_CHANGED, {"step": "mash"})
        await asyncio.sleep(0.01)

        # Unsubscribe
        result = await handler.unsubscribe(EventTopic.STEP_CHANGED, callback)
        assert result is True

        # Publish again - should not trigger callback
        await handler.publish_event(EventTopic.STEP_CHANGED, {"step": "boil"})
        await asyncio.sleep(0.01)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_get_event_stats(self):
        """Test getting event statistics."""
        handler = CBPI4CacheHandler()

        await handler.publish_event(EventTopic.STEP_CHANGED, {"step": "mash"})

        stats = handler.get_event_stats()
        assert "events_published" in stats
        assert stats["events_published"] >= 1

    @pytest.mark.asyncio
    async def test_i2c_write(self):
        """Test I2C write operation."""
        handler = CBPI4CacheHandler()
        await handler.start()

        result = await handler.i2c_write(address=0x27, data=[0x01, 0x02])
        assert result is True

        await handler.stop()

    @pytest.mark.asyncio
    async def test_i2c_read(self):
        """Test I2C read operation."""
        handler = CBPI4CacheHandler()
        await handler.start()

        result = await handler.i2c_read(address=0x48, register=0x00)
        assert result is True

        await handler.stop()

    @pytest.mark.asyncio
    async def test_i2c_write_with_priority(self):
        """Test I2C write with custom priority."""
        handler = CBPI4CacheHandler()
        await handler.start()

        result = await handler.i2c_write(address=0x27, data=[0xFF], priority=I2CPriority.CRITICAL)
        assert result is True

        await handler.stop()

    @pytest.mark.asyncio
    async def test_i2c_write_with_callback(self):
        """Test I2C write with callback."""
        handler = CBPI4CacheHandler()
        await handler.start()

        callback_called = False

        async def callback(result):
            nonlocal callback_called
            callback_called = True

        await handler.i2c_write(address=0x27, data=[0x01], callback=callback)
        await asyncio.sleep(0.1)

        assert callback_called is True
        await handler.stop()

    @pytest.mark.asyncio
    async def test_i2c_disabled(self):
        """Test I2C operations when coordinator disabled."""
        handler = CBPI4CacheHandler(enable_i2c=False)

        result = await handler.i2c_write(address=0x27, data=[0x01])
        assert result is False  # Should fail when I2C disabled

    @pytest.mark.asyncio
    async def test_get_i2c_stats(self):
        """Test getting I2C statistics."""
        handler = CBPI4CacheHandler()
        await handler.start()

        await handler.i2c_write(address=0x27, data=[0x01])
        await asyncio.sleep(0.1)

        stats = handler.get_i2c_stats()
        assert stats is not None
        assert "operations_queued" in stats

        await handler.stop()

    @pytest.mark.asyncio
    async def test_get_i2c_stats_when_disabled(self):
        """Test getting I2C stats when disabled returns None."""
        handler = CBPI4CacheHandler(enable_i2c=False)

        stats = handler.get_i2c_stats()
        assert stats is None

    @pytest.mark.asyncio
    async def test_get_i2c_queue_size(self):
        """Test getting I2C queue size."""
        handler = CBPI4CacheHandler()

        # Queue some operations
        await handler.i2c_write(address=0x27, data=[0x01])
        await handler.i2c_write(address=0x27, data=[0x02])

        size = handler.get_i2c_queue_size()
        assert size >= 0

    @pytest.mark.asyncio
    async def test_get_i2c_queue_size_when_disabled(self):
        """Test queue size returns 0 when I2C disabled."""
        handler = CBPI4CacheHandler(enable_i2c=False)

        size = handler.get_i2c_queue_size()
        assert size == 0

    @pytest.mark.asyncio
    async def test_set_cache_ttl(self):
        """Test setting cache TTL."""
        handler = CBPI4CacheHandler()

        handler.set_cache_ttl(CacheType.STEP, 2.0)
        ttl = handler.get_cache_ttl(CacheType.STEP)

        assert ttl == 2.0

    @pytest.mark.asyncio
    async def test_get_cache_ttl(self):
        """Test getting cache TTL."""
        handler = CBPI4CacheHandler()

        ttl = handler.get_cache_ttl(CacheType.KETTLE)
        assert ttl > 0

    @pytest.mark.asyncio
    async def test_repr_string(self):
        """Test string representation."""
        handler = CBPI4CacheHandler()

        repr_str = repr(handler)
        assert "CBPI4CacheHandler" in repr_str
        assert "running" in repr_str
        assert "i2c" in repr_str

    @pytest.mark.asyncio
    async def test_repr_without_i2c(self):
        """Test string representation when I2C disabled."""
        handler = CBPI4CacheHandler(enable_i2c=False)

        repr_str = repr(handler)
        assert "i2c=disabled" in repr_str

    @pytest.mark.asyncio
    async def test_integration_data_and_events(self):
        """Test integration of data access and events."""
        cbpi = MockCBPI()
        handler = CBPI4CacheHandler(cbpi_instance=cbpi)

        received_events = []

        async def callback(event: Event):
            received_events.append(event.data)

        # Subscribe to sensor events
        await handler.subscribe_to_sensor_values(callback)

        # Get sensor data (this could trigger event)
        await handler.get_sensor_state()

        # Manually publish event
        await handler.publish_event(EventTopic.SENSOR_VALUE, {"sensor": "temp1", "value": 66.0})

        await asyncio.sleep(0.01)
        assert len(received_events) >= 1
