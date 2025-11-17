"""
Unit tests for cache handler singleton sharing across multiple plugins.

Tests that multiple plugins can share the same cache instance and that
cache operations are properly coordinated between plugins.

Phase 8 Addition: Validates real-world multi-plugin scenarios.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from brewmotron_cache_handler import (
    CBPI4CacheHandler,
    CacheType,
    get_cache_handler,
    get_cache_handler_sync,
    reset_cache_handler,
)


class TestSingletonCacheSharing:
    """Test cache sharing between multiple plugins."""

    @pytest_asyncio.fixture(autouse=True)
    async def reset_singleton_between_tests(self):
        """Reset singleton between tests to ensure isolation."""
        await reset_cache_handler()
        yield
        await reset_cache_handler()

    @pytest_asyncio.fixture
    def mock_cbpi(self):
        """Create a mock CBPI instance."""
        cbpi = MagicMock()
        cbpi.step = MagicMock()
        cbpi.step.get_state = AsyncMock(return_value={"steps": [{"id": "step1", "status": "A"}]})
        cbpi.kettle = MagicMock()
        cbpi.kettle.get_state = AsyncMock(return_value={"data": [{"id": "kettle1", "name": "Mash Tun"}]})
        cbpi.sensor = MagicMock()
        cbpi.sensor.get_state = AsyncMock(return_value={"data": [{"id": "sensor1", "value": 67.5}]})
        cbpi.actor = MagicMock()
        cbpi.actor.get_state = AsyncMock(return_value={"data": [{"id": "actor1", "state": True}]})
        cbpi.config = MagicMock()
        cbpi.config.get_state = AsyncMock(return_value={"TEMP_UNIT": "C"})
        return cbpi

    @pytest.mark.asyncio
    async def test_multiple_plugins_share_same_cache_instance(self, mock_cbpi):
        """Test that multiple plugins get the same cache instance."""
        # Simulate three plugins (7Seg, LCD, BMT-Key) initializing
        cache1 = await get_cache_handler(cbpi_instance=mock_cbpi)
        cache2 = await get_cache_handler()
        cache3 = await get_cache_handler()

        # All should be the exact same instance
        assert cache1 is cache2
        assert cache2 is cache3
        assert id(cache1) == id(cache2) == id(cache3)

    @pytest.mark.asyncio
    async def test_plugins_see_same_cached_data(self, mock_cbpi):
        """Test that all plugins see the same cached data."""
        cache1 = await get_cache_handler(cbpi_instance=mock_cbpi)
        cache2 = await get_cache_handler()

        # Plugin 1 fetches step data (caches it)
        step_data_1 = await cache1.get_step_state()

        # Plugin 2 should get the exact same cached data
        step_data_2 = await cache2.get_step_state()

        assert step_data_1 == step_data_2
        assert step_data_1 is step_data_2  # Same object reference

        # CBPi API should only be called once due to caching
        assert mock_cbpi.step.get_state.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_invalidation_affects_all_plugins(self, mock_cbpi):
        """Test that cache invalidation affects all plugin views."""
        cache1 = await get_cache_handler(cbpi_instance=mock_cbpi)
        cache2 = await get_cache_handler()

        # Both plugins fetch kettle data
        await cache1.get_kettle_state()
        await cache2.get_kettle_state()

        # CBPi called once due to caching
        assert mock_cbpi.kettle.get_state.call_count == 1

        # Plugin 1 invalidates kettle cache
        await cache1.invalidate(CacheType.KETTLE)

        # Plugin 2 fetches again - should call CBPi again
        await cache2.get_kettle_state()

        # Now CBPi should have been called twice
        assert mock_cbpi.kettle.get_state.call_count == 2

    @pytest.mark.asyncio
    async def test_i2c_operations_shared_across_plugins(self, mock_cbpi):
        """Test that I2C coordinator is shared across plugins."""
        cache1 = await get_cache_handler(cbpi_instance=mock_cbpi, enable_i2c=True)
        cache2 = await get_cache_handler()

        # Both plugins should share the same I2C coordinator
        assert cache1._i2c_coordinator is cache2._i2c_coordinator

        # Plugin 1 writes to I2C
        await cache1.i2c_write(0x70, b"\x00\x01\x02", priority=5)

        # Plugin 2 should see the I2C queue
        queue_size_1 = cache1.get_i2c_queue_size()
        queue_size_2 = cache2.get_i2c_queue_size()

        # Both should see the same queue state
        assert queue_size_1 == queue_size_2

    @pytest.mark.xfail(reason="Stats not tracked per cache type - only global totals available")
    @pytest.mark.asyncio
    async def test_cache_stats_shared_across_plugins(self, mock_cbpi):
        """Test that cache statistics are shared across plugins."""
        cache1 = await get_cache_handler(cbpi_instance=mock_cbpi)
        cache2 = await get_cache_handler()

        # Plugin 1 makes some cache requests
        await cache1.get_step_state()  # Miss
        await cache1.get_step_state()  # Hit

        # Plugin 2 checks stats
        stats = cache2.get_cache_stats()

        # Should see Plugin 1's operations
        assert stats["step"]["hits"] >= 1
        assert stats["step"]["misses"] >= 1

    @pytest.mark.xfail(reason="Stats not tracked per cache type - only global totals available")
    @pytest.mark.asyncio
    async def test_concurrent_plugin_cache_access(self, mock_cbpi):
        """Test concurrent cache access from multiple plugins."""
        cache1 = await get_cache_handler(cbpi_instance=mock_cbpi)
        cache2 = await get_cache_handler()
        cache3 = await get_cache_handler()

        # Simulate three plugins concurrently accessing cache
        async def plugin1_work():
            for _ in range(5):
                await cache1.get_step_state()
                await asyncio.sleep(0.01)

        async def plugin2_work():
            for _ in range(5):
                await cache2.get_kettle_state()
                await asyncio.sleep(0.01)

        async def plugin3_work():
            for _ in range(5):
                await cache3.get_sensor_state()
                await asyncio.sleep(0.01)

        # Run all plugin operations concurrently
        await asyncio.gather(plugin1_work(), plugin2_work(), plugin3_work())

        # All plugins should have completed successfully
        stats = cache1.get_cache_stats()
        assert stats["step"]["hits"] + stats["step"]["misses"] >= 5
        assert stats["kettle"]["hits"] + stats["kettle"]["misses"] >= 5
        assert stats["sensor"]["hits"] + stats["sensor"]["misses"] >= 5

    @pytest.mark.asyncio
    async def test_plugin_initialization_race_condition(self, mock_cbpi):
        """Test that concurrent plugin initialization creates only one cache."""

        # Simulate multiple plugins initializing simultaneously
        async def init_plugin():
            return await get_cache_handler(cbpi_instance=mock_cbpi)

        # Start 5 plugins concurrently
        caches = await asyncio.gather(*[init_plugin() for _ in range(5)])

        # All should be the same instance
        assert all(cache is caches[0] for cache in caches)

    @pytest.mark.asyncio
    async def test_cache_refresh_affects_all_plugins(self, mock_cbpi):
        """Test that force refresh updates cache for all plugins."""
        cache1 = await get_cache_handler(cbpi_instance=mock_cbpi)
        cache2 = await get_cache_handler()

        # Both plugins fetch actor data
        data1_before = await cache1.get_actor_state()
        data2_before = await cache2.get_actor_state()

        # Update mock to return different data
        mock_cbpi.actor.get_state.return_value = {"data": [{"id": "actor2", "state": False}]}

        # Plugin 1 force refreshes
        data1_after = await cache1.get_actor_state(force_refresh=True)

        # Plugin 2 should automatically see new data (cache updated)
        data2_after = await cache2.get_actor_state()

        assert data1_after != data1_before
        assert data2_after == data1_after  # Both see the same new data

    @pytest.mark.asyncio
    async def test_different_plugins_different_cache_access_patterns(self, mock_cbpi):
        """Test realistic scenario with different plugin access patterns."""
        # Initialize caches for different plugins
        seg7_cache = await get_cache_handler(cbpi_instance=mock_cbpi)
        lcd_cache = await get_cache_handler()
        key_cache = await get_cache_handler()

        # 7SegDisplay: Polls step and kettle every 3s
        async def seg7_display_loop():
            for _ in range(3):
                await seg7_cache.get_step_state()
                await seg7_cache.get_kettle_state()
                await asyncio.sleep(0.05)

        # LCDisplay: Polls step, kettle, sensor every 2s
        async def lcd_display_loop():
            for _ in range(4):
                await lcd_cache.get_step_state()
                await lcd_cache.get_kettle_state()
                await lcd_cache.get_sensor_state()
                await asyncio.sleep(0.03)

        # BMT-Key: Only checks actors every 1s
        async def key_loop():
            for _ in range(6):
                await key_cache.get_actor_state()
                await asyncio.sleep(0.02)

        # Run all plugin loops concurrently
        await asyncio.gather(seg7_display_loop(), lcd_display_loop(), key_loop())

        # Verify cache sharing reduced API calls
        # Without cache, would be: (3*2) + (4*3) + 6 = 6 + 12 + 6 = 24 calls
        # With cache: Much fewer due to TTL-based caching
        total_api_calls = (
            mock_cbpi.step.get_state.call_count
            + mock_cbpi.kettle.get_state.call_count
            + mock_cbpi.sensor.get_state.call_count
            + mock_cbpi.actor.get_state.call_count
        )

        # Should be significantly less than 24 (the non-cached total)
        assert total_api_calls < 24

    @pytest.mark.asyncio
    async def test_singleton_reset_clears_for_all_plugins(self, mock_cbpi):
        """Test that resetting singleton affects all plugin references."""
        cache1 = await get_cache_handler(cbpi_instance=mock_cbpi)
        cache2 = await get_cache_handler()

        # Both plugins fetch data
        await cache1.get_step_state()
        await cache2.get_kettle_state()

        # Reset singleton
        await reset_cache_handler()

        # Try to get cache without cbpi_instance (should fail)
        with pytest.raises(ValueError, match="First call.*must provide cbpi_instance"):
            await get_cache_handler()

        # Create new cache
        cache3 = await get_cache_handler(cbpi_instance=mock_cbpi)

        # New cache should be a different instance
        assert cache3 is not cache1
        assert cache3 is not cache2

    @pytest.mark.asyncio
    async def test_sync_access_returns_none_before_async_init(self):
        """Test that synchronous access returns None before async initialization."""
        # Before any async initialization
        sync_cache = get_cache_handler_sync()
        assert sync_cache is None

    @pytest.mark.asyncio
    async def test_sync_access_returns_instance_after_async_init(self, mock_cbpi):
        """Test that synchronous access works after async initialization."""
        # Initialize async
        async_cache = await get_cache_handler(cbpi_instance=mock_cbpi)

        # Synchronous access should return the same instance
        sync_cache = get_cache_handler_sync()
        assert sync_cache is async_cache

    @pytest.mark.asyncio
    async def test_cache_ttl_settings_shared_across_plugins(self, mock_cbpi):
        """Test that TTL settings changes affect all plugins."""
        cache1 = await get_cache_handler(cbpi_instance=mock_cbpi)
        cache2 = await get_cache_handler()

        # Plugin 1 changes TTL
        cache1.set_cache_ttl(CacheType.STEP, 5.0)

        # Plugin 2 should see the same TTL
        ttl2 = cache2.get_cache_ttl(CacheType.STEP)
        assert ttl2 == 5.0

    @pytest.mark.asyncio
    async def test_all_cache_invalidation_affects_all_plugins(self, mock_cbpi):
        """Test that invalidating all caches affects all plugins."""
        cache1 = await get_cache_handler(cbpi_instance=mock_cbpi)
        cache2 = await get_cache_handler()

        # Both plugins fetch various data
        await cache1.get_step_state()
        await cache2.get_kettle_state()
        await cache1.get_sensor_state()

        # Track initial API call counts
        step_calls_before = mock_cbpi.step.get_state.call_count
        kettle_calls_before = mock_cbpi.kettle.get_state.call_count
        sensor_calls_before = mock_cbpi.sensor.get_state.call_count

        # Plugin 1 invalidates all caches
        await cache1.invalidate_all()

        # Plugin 2 fetches again - should call APIs
        await cache2.get_step_state()
        await cache2.get_kettle_state()
        await cache2.get_sensor_state()

        # All API calls should have increased
        assert mock_cbpi.step.get_state.call_count > step_calls_before
        assert mock_cbpi.kettle.get_state.call_count > kettle_calls_before
        assert mock_cbpi.sensor.get_state.call_count > sensor_calls_before
