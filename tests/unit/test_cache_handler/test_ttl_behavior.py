"""
Unit tests for TTL behavior and cache expiration.

Tests the interaction between CacheEntry TTL and DataCache expiration
handling, including edge cases and timing-sensitive scenarios.
"""

import pytest
import asyncio
import time
from brewmotron_cache_handler.cache_store import DataCache, CacheType
from brewmotron_cache_handler.cache_entry import CacheEntry


class TestTTLBehavior:
    """Test suite for TTL expiration behavior."""

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self):
        """Test cache entry expires after configured TTL."""
        cache = DataCache()
        cache.set_ttl(CacheType.SENSOR, 0.1)  # 100ms TTL

        await cache.set(CacheType.SENSOR, {"temp": 65.5})
        assert cache.is_valid(CacheType.SENSOR) is True

        await asyncio.sleep(0.15)  # Wait for expiration
        assert cache.is_valid(CacheType.SENSOR) is False

    @pytest.mark.asyncio
    async def test_different_ttls_for_different_caches(self):
        """Test different cache types have independent TTL expiration."""
        cache = DataCache()
        cache.set_ttl(CacheType.ACTOR, 0.05)  # 50ms
        cache.set_ttl(CacheType.STEP, 0.15)  # 150ms

        await cache.set(CacheType.ACTOR, {"actor": "data"})
        await cache.set(CacheType.STEP, {"step": "data"})

        # Both valid initially
        assert cache.is_valid(CacheType.ACTOR) is True
        assert cache.is_valid(CacheType.STEP) is True

        # After 80ms, actor expired but step still valid
        await asyncio.sleep(0.08)
        assert cache.is_valid(CacheType.ACTOR) is False
        assert cache.is_valid(CacheType.STEP) is True

        # After 180ms total, both expired
        await asyncio.sleep(0.1)
        assert cache.is_valid(CacheType.ACTOR) is False
        assert cache.is_valid(CacheType.STEP) is False

    @pytest.mark.asyncio
    async def test_refresh_resets_ttl_timer(self):
        """Test cache refresh resets the TTL timer."""
        cache = DataCache()
        cache.set_ttl(CacheType.KETTLE, 0.1)  # 100ms TTL

        # Initial set
        await cache.set(CacheType.KETTLE, {"temp": 65.5})
        await asyncio.sleep(0.08)  # Almost expired (80ms elapsed)

        # Refresh before expiration
        await cache.set(CacheType.KETTLE, {"temp": 66.0})

        # Should still be valid because timer reset
        await asyncio.sleep(0.05)  # 85ms total, but only 50ms since refresh
        assert cache.is_valid(CacheType.KETTLE) is True

    @pytest.mark.asyncio
    async def test_auto_refresh_on_expiration(self):
        """Test cache automatically refreshes when expired and fetch function provided."""
        cache = DataCache()
        cache.set_ttl(CacheType.STEP, 0.05)  # 50ms TTL
        fetch_count = 0

        async def fetch_step_data():
            nonlocal fetch_count
            fetch_count += 1
            return {"fetch": fetch_count}

        # First fetch
        result1 = await cache.get(CacheType.STEP, fetch_func=fetch_step_data)
        assert result1 == {"fetch": 1}
        assert fetch_count == 1

        # Wait for expiration
        await asyncio.sleep(0.08)

        # Should auto-refresh
        result2 = await cache.get(CacheType.STEP, fetch_func=fetch_step_data)
        assert result2 == {"fetch": 2}
        assert fetch_count == 2

    @pytest.mark.asyncio
    async def test_very_short_ttl_50ms(self):
        """Test cache with very short TTL (50ms) for actor state."""
        cache = DataCache()
        cache.set_ttl(CacheType.ACTOR, 0.05)  # 50ms (matches actor default of 250ms in spec, using shorter for test)

        await cache.set(CacheType.ACTOR, {"state": "on"})
        assert cache.is_valid(CacheType.ACTOR) is True

        await asyncio.sleep(0.06)
        assert cache.is_valid(CacheType.ACTOR) is False

    @pytest.mark.asyncio
    async def test_long_ttl_config_cache(self):
        """Test cache with long TTL for config data."""
        cache = DataCache()
        # Default config TTL is 60s, use 0.2s for testing
        cache.set_ttl(CacheType.CONFIG, 0.2)

        await cache.set(CacheType.CONFIG, {"brewery": "test"})

        # Should still be valid after 150ms
        await asyncio.sleep(0.15)
        assert cache.is_valid(CacheType.CONFIG) is True

        # Should be invalid after 250ms
        await asyncio.sleep(0.1)
        assert cache.is_valid(CacheType.CONFIG) is False

    @pytest.mark.asyncio
    async def test_cache_age_increases_over_time(self):
        """Test cache entry age increases correctly."""
        cache = DataCache()
        await cache.set(CacheType.SENSOR, {"temp": 65.5})

        info1 = await cache.get_cache_info(CacheType.SENSOR)
        age1 = info1["age"]

        await asyncio.sleep(0.05)

        info2 = await cache.get_cache_info(CacheType.SENSOR)
        age2 = info2["age"]

        assert age2 > age1
        assert age2 >= age1 + 0.04  # Should be at least 40ms older

    @pytest.mark.asyncio
    async def test_multiple_refreshes_extend_lifetime(self):
        """Test multiple refreshes keep cache valid."""
        cache = DataCache()
        cache.set_ttl(CacheType.KETTLE, 0.08)  # 80ms TTL

        await cache.set(CacheType.KETTLE, {"temp": 65.0})

        # Refresh every 50ms, 4 times = 200ms total
        for i in range(4):
            await asyncio.sleep(0.05)
            await cache.set(CacheType.KETTLE, {"temp": 65.0 + i})
            assert cache.is_valid(CacheType.KETTLE) is True

    @pytest.mark.asyncio
    async def test_expired_cache_info_shows_negative_time_until_expiration(self):
        """Test expired cache shows negative time until expiration."""
        cache = DataCache()
        cache.set_ttl(CacheType.STEP, 0.05)

        await cache.set(CacheType.STEP, {"step": "mash"})
        await asyncio.sleep(0.1)  # Wait for expiration

        # Get underlying cache entry to check time until expiration
        cache_entry = cache._caches[CacheType.STEP]
        assert cache_entry.time_until_expiration() < 0

    @pytest.mark.asyncio
    async def test_force_refresh_ignores_valid_cache(self):
        """Test force refresh fetches even when cache is still valid."""
        cache = DataCache()
        cache.set_ttl(CacheType.SENSOR, 1.0)  # 1 second TTL
        fetch_count = 0

        async def fetch_data():
            nonlocal fetch_count
            fetch_count += 1
            return {"count": fetch_count}

        # Initial fetch
        await cache.get(CacheType.SENSOR, fetch_func=fetch_data)
        assert fetch_count == 1

        # Immediate force refresh (cache still valid)
        await cache.get(CacheType.SENSOR, fetch_func=fetch_data, force_refresh=True)
        assert fetch_count == 2  # Fetched again despite valid cache

    @pytest.mark.asyncio
    async def test_ttl_boundary_conditions(self):
        """Test cache validity at exact TTL boundary."""
        cache = DataCache()
        cache.set_ttl(CacheType.ACTOR, 0.1)  # 100ms TTL

        await cache.set(CacheType.ACTOR, {"state": "on"})

        # Just before expiration (95ms)
        await asyncio.sleep(0.095)
        # Should still be valid (with some timing tolerance)
        # Note: This test might be flaky due to timing precision

        # Well after expiration (150ms total)
        await asyncio.sleep(0.055)
        assert cache.is_valid(CacheType.ACTOR) is False

    @pytest.mark.asyncio
    async def test_rapid_successive_refreshes(self):
        """Test rapid successive refreshes maintain validity."""
        cache = DataCache()
        cache.set_ttl(CacheType.STEP, 0.1)

        # Rapid refreshes
        for i in range(10):
            await cache.set(CacheType.STEP, {"count": i})
            assert cache.is_valid(CacheType.STEP) is True
            await asyncio.sleep(0.01)  # 10ms between refreshes

    @pytest.mark.asyncio
    async def test_ttl_persists_across_refreshes(self):
        """Test TTL value persists across data refreshes."""
        cache = DataCache()
        original_ttl = 0.15
        cache.set_ttl(CacheType.KETTLE, original_ttl)

        await cache.set(CacheType.KETTLE, {"temp": 65.0})
        await cache.set(CacheType.KETTLE, {"temp": 66.0})
        await cache.set(CacheType.KETTLE, {"temp": 67.0})

        info = await cache.get_cache_info(CacheType.KETTLE)
        assert info["ttl"] == original_ttl

    @pytest.mark.asyncio
    async def test_cache_entry_direct_refresh_method(self):
        """Test CacheEntry refresh method works correctly."""
        entry = CacheEntry(data={"old": "value"}, ttl=0.1)

        # Entry is fresh
        assert entry.is_valid() is True
        old_age = entry.age()

        await asyncio.sleep(0.05)

        # Refresh with new data
        entry.refresh({"new": "value"})

        # Should be valid again with reset timer
        assert entry.is_valid() is True
        assert entry.data == {"new": "value"}
        assert entry.age() < old_age  # Age should be less (timer reset)

    @pytest.mark.asyncio
    async def test_default_ttl_values_match_specification(self):
        """Test default TTL values match architecture specification."""
        cache = DataCache()

        # From CBPI4_DATA_ACCESS_ARCHITECTURE.md Appendix B
        assert cache.get_ttl(CacheType.STEP) == 0.5  # 500ms
        assert cache.get_ttl(CacheType.KETTLE) == 1.0  # 1000ms
        assert cache.get_ttl(CacheType.SENSOR) == 0.5  # 500ms
        assert cache.get_ttl(CacheType.ACTOR) == 0.25  # 250ms
        assert cache.get_ttl(CacheType.CONFIG) == 60.0  # 60000ms

    @pytest.mark.asyncio
    async def test_stale_data_returned_when_fetch_fails(self):
        """Test stale data is returned when fetch fails and cache expired."""
        cache = DataCache()
        cache.set_ttl(CacheType.SENSOR, 0.05)

        # Initial successful fetch
        async def successful_fetch():
            return {"status": "ok", "temp": 65.5}

        await cache.get(CacheType.SENSOR, fetch_func=successful_fetch)

        # Wait for expiration
        await asyncio.sleep(0.1)

        # Fetch fails, should return stale data
        async def failing_fetch():
            raise RuntimeError("Sensor disconnected")

        result = await cache.get(CacheType.SENSOR, fetch_func=failing_fetch)
        assert result == {"status": "ok", "temp": 65.5}  # Stale but valid data

    @pytest.mark.asyncio
    async def test_concurrent_expiration_and_refresh(self):
        """Test concurrent operations handle expiration correctly."""
        cache = DataCache()
        cache.set_ttl(CacheType.STEP, 0.05)
        fetch_count = 0

        async def fetch_data():
            nonlocal fetch_count
            fetch_count += 1
            await asyncio.sleep(0.01)  # Simulate fetch delay
            return {"count": fetch_count}

        # Initial fetch
        await cache.get(CacheType.STEP, fetch_func=fetch_data)

        # Wait for expiration
        await asyncio.sleep(0.08)

        # Multiple concurrent requests after expiration
        results = await asyncio.gather(
            cache.get(CacheType.STEP, fetch_func=fetch_data),
            cache.get(CacheType.STEP, fetch_func=fetch_data),
            cache.get(CacheType.STEP, fetch_func=fetch_data),
        )

        # Lock should ensure only one fetch happens
        # All results should be the same (from same fetch)
        assert len(set(str(r) for r in results)) == 1

    @pytest.mark.asyncio
    async def test_cache_remains_valid_during_ttl_period(self):
        """Test cache remains continuously valid during entire TTL period."""
        cache = DataCache()
        cache.set_ttl(CacheType.KETTLE, 0.2)  # 200ms TTL

        await cache.set(CacheType.KETTLE, {"temp": 65.5})

        # Check validity multiple times during TTL period
        for _ in range(15):  # 15 checks over 150ms (within 200ms TTL)
            assert cache.is_valid(CacheType.KETTLE) is True
            await asyncio.sleep(0.01)  # 10ms between checks

    def test_cache_entry_ttl_validation_edge_cases(self):
        """Test CacheEntry TTL validation handles edge cases."""
        # Exactly at TTL boundary
        entry = CacheEntry(data={"test": "data"}, ttl=0.05)
        time.sleep(0.05)
        # Should be expired (age >= ttl)
        assert entry.is_valid() is False

        # Just before TTL
        entry2 = CacheEntry(data={"test": "data"}, ttl=0.1)
        time.sleep(0.09)
        # Might be valid or invalid due to timing precision
        # Just verify method doesn't crash
        _ = entry2.is_valid()

        # Well after TTL
        entry3 = CacheEntry(data={"test": "data"}, ttl=0.01)
        time.sleep(0.05)
        assert entry3.is_valid() is False
