"""
Unit tests for DataCache class.

Tests multi-cache store with TTL management, async operations,
statistics tracking, and cache invalidation.
"""

import asyncio

import pytest

from brewmotron_cache_handler.cache_store import CacheType, DataCache


class TestDataCache:
    """Test suite for DataCache class."""

    def test_data_cache_initialization(self):
        """Test data cache initializes with correct defaults."""
        cache = DataCache()

        assert cache._caches[CacheType.STEP] is None
        assert cache._caches[CacheType.KETTLE] is None
        assert cache._caches[CacheType.SENSOR] is None
        assert cache._caches[CacheType.ACTOR] is None
        assert cache._caches[CacheType.CONFIG] is None

    def test_data_cache_default_ttl_values(self):
        """Test default TTL values are set correctly."""
        cache = DataCache()

        assert cache.get_ttl(CacheType.STEP) == 0.5
        assert cache.get_ttl(CacheType.KETTLE) == 1.0
        assert cache.get_ttl(CacheType.SENSOR) == 0.5
        assert cache.get_ttl(CacheType.ACTOR) == 0.25
        assert cache.get_ttl(CacheType.CONFIG) == 60.0

    def test_set_ttl(self):
        """Test custom TTL can be set for cache types."""
        cache = DataCache()

        cache.set_ttl(CacheType.STEP, 2.0)
        assert cache.get_ttl(CacheType.STEP) == 2.0

        cache.set_ttl(CacheType.KETTLE, 0.1)
        assert cache.get_ttl(CacheType.KETTLE) == 0.1

    @pytest.mark.asyncio
    async def test_set_and_get_cache(self):
        """Test setting and getting cache data."""
        cache = DataCache()
        test_data = {"temperature": 65.5, "kettle": "mash_tun"}

        await cache.set(CacheType.KETTLE, test_data)
        result = await cache.get(CacheType.KETTLE)

        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_with_fetch_function(self):
        """Test get with fetch function when cache is empty."""
        cache = DataCache()
        fetch_called = False

        async def fetch_data():
            nonlocal fetch_called
            fetch_called = True
            return {"fetched": "data"}

        result = await cache.get(CacheType.STEP, fetch_func=fetch_data)

        assert fetch_called is True
        assert result == {"fetched": "data"}

    @pytest.mark.asyncio
    async def test_get_without_fetch_raises_when_empty(self):
        """Test get without fetch function raises when cache is empty."""
        cache = DataCache()

        with pytest.raises(ValueError, match="No cached data"):
            await cache.get(CacheType.STEP)

    @pytest.mark.asyncio
    async def test_get_uses_cached_data_when_valid(self):
        """Test get returns cached data without fetching when valid."""
        cache = DataCache()
        fetch_count = 0

        async def fetch_data():
            nonlocal fetch_count
            fetch_count += 1
            return {"count": fetch_count}

        # First call - should fetch
        result1 = await cache.get(CacheType.KETTLE, fetch_func=fetch_data)
        assert result1 == {"count": 1}
        assert fetch_count == 1

        # Second call - should use cache
        result2 = await cache.get(CacheType.KETTLE, fetch_func=fetch_data)
        assert result2 == {"count": 1}  # Same data
        assert fetch_count == 1  # Fetch not called again

    @pytest.mark.asyncio
    async def test_get_refreshes_when_expired(self):
        """Test get fetches fresh data when cache expires."""
        cache = DataCache()
        cache.set_ttl(CacheType.SENSOR, 0.05)  # 50ms TTL
        fetch_count = 0

        async def fetch_data():
            nonlocal fetch_count
            fetch_count += 1
            return {"count": fetch_count}

        # First fetch
        result1 = await cache.get(CacheType.SENSOR, fetch_func=fetch_data)
        assert result1 == {"count": 1}

        # Wait for expiration
        await asyncio.sleep(0.1)

        # Should fetch again
        result2 = await cache.get(CacheType.SENSOR, fetch_func=fetch_data)
        assert result2 == {"count": 2}
        assert fetch_count == 2

    @pytest.mark.asyncio
    async def test_force_refresh(self):
        """Test force refresh bypasses valid cache."""
        cache = DataCache()
        fetch_count = 0

        async def fetch_data():
            nonlocal fetch_count
            fetch_count += 1
            return {"count": fetch_count}

        # First fetch
        await cache.get(CacheType.ACTOR, fetch_func=fetch_data)
        assert fetch_count == 1

        # Force refresh even though cache is valid
        result = await cache.get(CacheType.ACTOR, fetch_func=fetch_data, force_refresh=True)
        assert result == {"count": 2}
        assert fetch_count == 2

    @pytest.mark.asyncio
    async def test_invalidate_specific_cache(self):
        """Test invalidating a specific cache type."""
        cache = DataCache()

        await cache.set(CacheType.STEP, {"step": "data"})
        await cache.set(CacheType.KETTLE, {"kettle": "data"})

        assert cache.is_valid(CacheType.STEP) is True
        assert cache.is_valid(CacheType.KETTLE) is True

        await cache.invalidate(CacheType.STEP)

        assert cache.is_valid(CacheType.STEP) is False
        assert cache.is_valid(CacheType.KETTLE) is True

    @pytest.mark.asyncio
    async def test_invalidate_all_caches(self):
        """Test invalidating all caches at once."""
        cache = DataCache()

        # Set all caches
        await cache.set(CacheType.STEP, {"step": "data"})
        await cache.set(CacheType.KETTLE, {"kettle": "data"})
        await cache.set(CacheType.SENSOR, {"sensor": "data"})
        await cache.set(CacheType.ACTOR, {"actor": "data"})
        await cache.set(CacheType.CONFIG, {"config": "data"})

        # Invalidate all
        await cache.invalidate()

        assert cache.is_valid(CacheType.STEP) is False
        assert cache.is_valid(CacheType.KETTLE) is False
        assert cache.is_valid(CacheType.SENSOR) is False
        assert cache.is_valid(CacheType.ACTOR) is False
        assert cache.is_valid(CacheType.CONFIG) is False

    def test_is_valid_returns_false_when_empty(self):
        """Test is_valid returns False for uninitialized cache."""
        cache = DataCache()
        assert cache.is_valid(CacheType.STEP) is False

    @pytest.mark.asyncio
    async def test_statistics_tracking(self):
        """Test cache statistics are tracked correctly."""
        cache = DataCache()

        async def fetch_data():
            return {"test": "data"}

        # First call - miss + refresh
        await cache.get(CacheType.STEP, fetch_func=fetch_data)

        # Second call - hit
        await cache.get(CacheType.STEP, fetch_func=fetch_data)

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 0
        assert stats["refreshes"] == 1

    @pytest.mark.asyncio
    async def test_statistics_hit_rate_calculation(self):
        """Test hit rate is calculated correctly."""
        cache = DataCache()

        async def fetch_data():
            return {"test": "data"}

        # 1 miss (initial fetch) + 3 hits
        await cache.get(CacheType.KETTLE, fetch_func=fetch_data)
        await cache.get(CacheType.KETTLE, fetch_func=fetch_data)
        await cache.get(CacheType.KETTLE, fetch_func=fetch_data)
        await cache.get(CacheType.KETTLE, fetch_func=fetch_data)

        stats = cache.get_stats()
        assert stats["hits"] == 3
        assert stats["total_requests"] == 3
        assert stats["hit_rate"] == 1.0  # 3/3 = 100%

    @pytest.mark.asyncio
    async def test_statistics_invalidation_count(self):
        """Test invalidation statistics are tracked."""
        cache = DataCache()

        await cache.set(CacheType.STEP, {"test": "data"})
        await cache.invalidate(CacheType.STEP)
        await cache.invalidate(CacheType.STEP)  # Invalidate twice

        stats = cache.get_stats()
        assert stats["invalidations"] == 2

    def test_reset_statistics(self):
        """Test statistics can be reset."""
        cache = DataCache()
        cache._stats["hits"] = 100
        cache._stats["misses"] = 50

        cache.reset_stats()

        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["refreshes"] == 0
        assert stats["invalidations"] == 0

    @pytest.mark.asyncio
    async def test_get_cache_info(self):
        """Test getting detailed cache information."""
        cache = DataCache()
        test_data = {"temperature": 65.5}

        await cache.set(CacheType.SENSOR, test_data)
        info = await cache.get_cache_info(CacheType.SENSOR)

        assert info is not None
        assert info["data"] == test_data
        assert info["cache_type"] == "sensor"
        assert info["is_valid"] is True
        assert "age" in info
        assert "ttl" in info

    @pytest.mark.asyncio
    async def test_get_cache_info_returns_none_when_empty(self):
        """Test get_cache_info returns None for empty cache."""
        cache = DataCache()
        info = await cache.get_cache_info(CacheType.STEP)
        assert info is None

    @pytest.mark.asyncio
    async def test_concurrent_access_with_lock(self):
        """Test concurrent access is properly synchronized."""
        cache = DataCache()
        results = []

        async def fetch_and_store(delay):
            await asyncio.sleep(delay)

            async def fetch_data():
                return {"delay": delay}

            result = await cache.get(CacheType.ACTOR, fetch_func=fetch_data, force_refresh=True)
            results.append(result)

        # Run multiple concurrent operations
        await asyncio.gather(
            fetch_and_store(0.01),
            fetch_and_store(0.02),
            fetch_and_store(0.03),
        )

        # All operations should complete
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_fetch_function_exception_handling(self):
        """Test exception in fetch function is handled correctly."""
        cache = DataCache()

        async def failing_fetch():
            raise ValueError("Fetch failed!")

        with pytest.raises(ValueError, match="Fetch failed"):
            await cache.get(CacheType.STEP, fetch_func=failing_fetch)

    @pytest.mark.asyncio
    async def test_fetch_failure_returns_stale_data_if_available(self):
        """Test fetch failure returns stale data if cache exists."""
        cache = DataCache()
        cache.set_ttl(CacheType.KETTLE, 0.05)  # 50ms TTL

        # Initial successful fetch
        async def successful_fetch():
            return {"status": "success"}

        await cache.get(CacheType.KETTLE, fetch_func=successful_fetch)

        # Wait for expiration
        await asyncio.sleep(0.1)

        # Fetch function fails, should return stale data
        async def failing_fetch():
            raise ValueError("Fetch failed!")

        result = await cache.get(CacheType.KETTLE, fetch_func=failing_fetch)
        assert result == {"status": "success"}  # Stale data returned

    def test_cache_repr(self):
        """Test cache string representation."""
        cache = DataCache()
        repr_str = repr(cache)

        assert "DataCache" in repr_str
        assert "hit_rate" in repr_str
        assert "requests" in repr_str

    @pytest.mark.asyncio
    async def test_all_cache_types_independent(self):
        """Test all cache types are independent."""
        cache = DataCache()

        # Set different data for each cache type
        await cache.set(CacheType.STEP, {"type": "step"})
        await cache.set(CacheType.KETTLE, {"type": "kettle"})
        await cache.set(CacheType.SENSOR, {"type": "sensor"})
        await cache.set(CacheType.ACTOR, {"type": "actor"})
        await cache.set(CacheType.CONFIG, {"type": "config"})

        # Verify each returns correct data
        assert (await cache.get(CacheType.STEP))["type"] == "step"
        assert (await cache.get(CacheType.KETTLE))["type"] == "kettle"
        assert (await cache.get(CacheType.SENSOR))["type"] == "sensor"
        assert (await cache.get(CacheType.ACTOR))["type"] == "actor"
        assert (await cache.get(CacheType.CONFIG))["type"] == "config"

    @pytest.mark.asyncio
    async def test_cache_with_cbpi_instance(self):
        """Test cache can be initialized with CraftBeerPi instance."""
        mock_cbpi = {"version": "4.0"}
        cache = DataCache(cbpi=mock_cbpi)

        assert cache.cbpi == mock_cbpi

    @pytest.mark.asyncio
    async def test_statistics_cache_states(self):
        """Test statistics include cache state information."""
        cache = DataCache()

        await cache.set(CacheType.STEP, {"test": "data"})
        # Leave other caches empty

        stats = cache.get_stats()
        cache_states = stats["cache_states"]

        assert cache_states[CacheType.STEP.value] == "valid"
        assert cache_states[CacheType.KETTLE.value] == "invalid"
        assert cache_states[CacheType.SENSOR.value] == "invalid"
        assert cache_states[CacheType.ACTOR.value] == "invalid"
        assert cache_states[CacheType.CONFIG.value] == "invalid"
