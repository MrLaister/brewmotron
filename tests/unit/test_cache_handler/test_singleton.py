"""
Unit tests for singleton cache handler pattern.

Tests the global shared cache handler factory and ensures
proper singleton behavior across multiple accesses.
"""

import asyncio

import pytest

from brewmotron_cache_handler import get_cache_handler, get_cache_handler_sync, reset_cache_handler


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


class TestSingleton:
    """Test suite for singleton cache handler pattern."""

    @pytest.mark.asyncio
    async def test_first_call_requires_cbpi_instance(self):
        """Test first call to get_cache_handler requires cbpi_instance."""
        await reset_cache_handler()

        with pytest.raises(ValueError, match="First call to get_cache_handler"):
            await get_cache_handler()

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_creates_cache_handler_on_first_call(self):
        """Test cache handler is created on first call."""
        await reset_cache_handler()

        cbpi = MockCBPI()
        handler = await get_cache_handler(cbpi_instance=cbpi)

        assert handler is not None
        assert handler._running is True
        assert handler._cbpi is cbpi

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_returns_same_instance_on_subsequent_calls(self):
        """Test subsequent calls return the same instance."""
        await reset_cache_handler()

        cbpi = MockCBPI()
        handler1 = await get_cache_handler(cbpi_instance=cbpi)
        handler2 = await get_cache_handler()
        handler3 = await get_cache_handler()

        assert handler1 is handler2
        assert handler2 is handler3

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_subsequent_calls_can_omit_cbpi_instance(self):
        """Test subsequent calls don't need cbpi_instance."""
        await reset_cache_handler()

        cbpi = MockCBPI()
        handler1 = await get_cache_handler(cbpi_instance=cbpi)
        handler2 = await get_cache_handler()  # No cbpi_instance

        assert handler1 is handler2

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_concurrent_first_calls_create_single_instance(self):
        """Test concurrent first calls only create one instance."""
        await reset_cache_handler()

        cbpi = MockCBPI()

        # Simulate multiple plugins trying to get cache handler simultaneously
        handlers = await asyncio.gather(
            get_cache_handler(cbpi_instance=cbpi),
            get_cache_handler(cbpi_instance=cbpi),
            get_cache_handler(cbpi_instance=cbpi),
        )

        # All should be the same instance
        assert handlers[0] is handlers[1]
        assert handlers[1] is handlers[2]

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_cache_handler_is_started(self):
        """Test cache handler is automatically started."""
        await reset_cache_handler()

        cbpi = MockCBPI()
        handler = await get_cache_handler(cbpi_instance=cbpi)

        assert handler._running is True

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_reset_cache_handler_stops_instance(self):
        """Test reset_cache_handler stops the current instance."""
        await reset_cache_handler()

        cbpi = MockCBPI()
        handler = await get_cache_handler(cbpi_instance=cbpi)

        assert handler._running is True

        await reset_cache_handler()

        assert handler._running is False

    @pytest.mark.asyncio
    async def test_reset_allows_new_instance_creation(self):
        """Test reset allows creating a new instance."""
        await reset_cache_handler()

        cbpi1 = MockCBPI()
        handler1 = await get_cache_handler(cbpi_instance=cbpi1)

        await reset_cache_handler()

        cbpi2 = MockCBPI()
        handler2 = await get_cache_handler(cbpi_instance=cbpi2)

        # Should be different instances
        assert handler1 is not handler2
        assert handler1._cbpi is cbpi1
        assert handler2._cbpi is cbpi2

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_get_cache_handler_sync_returns_existing(self):
        """Test get_cache_handler_sync returns existing instance."""
        await reset_cache_handler()

        # Initially should return None
        assert get_cache_handler_sync() is None

        cbpi = MockCBPI()
        handler = await get_cache_handler(cbpi_instance=cbpi)

        # Now should return the instance
        sync_handler = get_cache_handler_sync()
        assert sync_handler is handler

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_get_cache_handler_sync_does_not_create(self):
        """Test get_cache_handler_sync doesn't create new instance."""
        await reset_cache_handler()

        sync_handler = get_cache_handler_sync()
        assert sync_handler is None

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_shared_cache_between_plugins(self):
        """Test multiple plugins share the same cache data."""
        await reset_cache_handler()

        cbpi = MockCBPI()

        # Plugin 1 gets cache and fetches data
        cache1 = await get_cache_handler(cbpi_instance=cbpi)
        state1 = await cache1.get_step_state()

        # Plugin 2 gets cache
        cache2 = await get_cache_handler()

        # Both should be same instance
        assert cache1 is cache2

        # Should have same cached data
        assert cache1._cache is cache2._cache

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_shared_i2c_coordinator(self):
        """Test multiple plugins share the same I2C coordinator."""
        await reset_cache_handler()

        cbpi = MockCBPI()

        cache1 = await get_cache_handler(cbpi_instance=cbpi)
        cache2 = await get_cache_handler()

        # Should share I2C coordinator
        assert cache1._i2c_coordinator is cache2._i2c_coordinator

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_shared_event_bus(self):
        """Test multiple plugins share the same event bus."""
        await reset_cache_handler()

        cbpi = MockCBPI()

        cache1 = await get_cache_handler(cbpi_instance=cbpi)
        cache2 = await get_cache_handler()

        # Should share event bus
        assert cache1._event_bus is cache2._event_bus

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_custom_configuration_on_first_call(self):
        """Test custom configuration is respected on first call."""
        await reset_cache_handler()

        cbpi = MockCBPI()
        handler = await get_cache_handler(
            cbpi_instance=cbpi,
            enable_i2c=False,
            cache_history_size=50,
            i2c_queue_size=500,
        )

        assert handler._i2c_coordinator is None  # I2C disabled
        assert handler._event_bus._history_size == 50

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_multiple_plugins_can_use_cache_methods(self):
        """Test multiple plugins can independently use cache methods."""
        await reset_cache_handler()

        cbpi = MockCBPI()

        # Plugin 1
        cache1 = await get_cache_handler(cbpi_instance=cbpi)
        step_state1 = await cache1.get_step_state()

        # Plugin 2
        cache2 = await get_cache_handler()
        step_state2 = await cache2.get_step_state()

        # Both should get the same data (shared cache)
        assert step_state1 == step_state2

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_cache_invalidation_affects_all_plugins(self):
        """Test cache invalidation in one plugin affects all."""
        await reset_cache_handler()

        cbpi = MockCBPI()

        cache1 = await get_cache_handler(cbpi_instance=cbpi)
        cache2 = await get_cache_handler()

        # Plugin 1 fetches data
        await cache1.get_step_state()

        # Cache should be valid
        from brewmotron_cache_handler import CacheType

        assert cache1._cache.is_valid(CacheType.STEP)
        assert cache2._cache.is_valid(CacheType.STEP)

        # Plugin 2 invalidates cache
        await cache2.invalidate(CacheType.STEP)

        # Should be invalid for both (same cache)
        assert not cache1._cache.is_valid(CacheType.STEP)
        assert not cache2._cache.is_valid(CacheType.STEP)

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_singleton_thread_safety(self):
        """Test singleton is thread-safe under concurrent access."""
        await reset_cache_handler()

        cbpi = MockCBPI()

        # Simulate high concurrency
        handlers = await asyncio.gather(*[get_cache_handler(cbpi_instance=cbpi) for _ in range(20)])

        # All should be the same instance
        for handler in handlers:
            assert handler is handlers[0]

        await reset_cache_handler()

    @pytest.mark.asyncio
    async def test_reset_under_concurrent_access(self):
        """Test reset works correctly even with concurrent access."""
        await reset_cache_handler()

        cbpi = MockCBPI()
        handler1 = await get_cache_handler(cbpi_instance=cbpi)

        # Reset while potentially accessing
        await reset_cache_handler()

        # New instance should be created
        handler2 = await get_cache_handler(cbpi_instance=cbpi)
        assert handler1 is not handler2

        await reset_cache_handler()
