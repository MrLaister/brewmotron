"""
Data Cache Store

Manages multiple cache entries with automatic TTL-based expiration.
Provides a centralized store for Step, Kettle, Sensor, Actor, and Config data.
"""

import asyncio
import logging
from enum import Enum
from typing import Any, Optional, Callable, Awaitable
from .cache_entry import CacheEntry

logger = logging.getLogger(__name__)


class CacheType(Enum):
    """Cache type identifiers for different CraftBeerPi4 data."""

    STEP = "step"
    KETTLE = "kettle"
    SENSOR = "sensor"
    ACTOR = "actor"
    CONFIG = "config"


class DataCache:
    """
    Multi-cache store with automatic TTL-based expiration.

    Manages separate caches for different data types (step, kettle, sensor,
    actor, config) with configurable TTL values optimized for each type.

    Cache TTL Defaults:
        - Step: 500ms (fast-changing during brewing)
        - Kettle: 1000ms (moderate changes)
        - Sensor: 500ms (frequent updates)
        - Actor: 250ms (rapid state changes)
        - Config: 60000ms (rarely changes)
    """

    def __init__(self, cbpi=None):
        """
        Initialize data cache with default TTL values.

        Args:
            cbpi: Optional CraftBeerPi4 instance for data fetching
        """
        self.cbpi = cbpi
        self._lock = asyncio.Lock()

        # Cache TTL configuration (milliseconds converted to seconds)
        self._ttl_config = {
            CacheType.STEP: 0.5,  # 500ms
            CacheType.KETTLE: 1.0,  # 1000ms
            CacheType.SENSOR: 0.5,  # 500ms
            CacheType.ACTOR: 0.25,  # 250ms
            CacheType.CONFIG: 60.0,  # 60000ms
        }

        # Initialize cache entries
        self._caches: dict[CacheType, Optional[CacheEntry]] = {
            CacheType.STEP: None,
            CacheType.KETTLE: None,
            CacheType.SENSOR: None,
            CacheType.ACTOR: None,
            CacheType.CONFIG: None,
        }

        # Statistics tracking
        self._stats = {
            "hits": 0,
            "misses": 0,
            "refreshes": 0,
            "invalidations": 0,
        }

        logger.info("DataCache initialized with TTL config: %s", self._ttl_config)

    def set_ttl(self, cache_type: CacheType, ttl_seconds: float) -> None:
        """
        Set custom TTL for a cache type.

        Args:
            cache_type: Type of cache to configure
            ttl_seconds: TTL in seconds
        """
        self._ttl_config[cache_type] = ttl_seconds
        logger.info("Cache TTL updated: %s = %.3fs", cache_type.value, ttl_seconds)

    def get_ttl(self, cache_type: CacheType) -> float:
        """
        Get configured TTL for a cache type.

        Args:
            cache_type: Type of cache

        Returns:
            float: TTL in seconds
        """
        return self._ttl_config.get(cache_type, 1.0)

    async def get(
        self,
        cache_type: CacheType,
        fetch_func: Optional[Callable[[], Awaitable[Any]]] = None,
        force_refresh: bool = False,
    ) -> Any:
        """
        Get data from cache or fetch if expired/missing.

        Args:
            cache_type: Type of cache to access
            fetch_func: Async function to fetch fresh data if cache invalid
            force_refresh: Force cache refresh even if valid

        Returns:
            Any: Cached data or freshly fetched data

        Raises:
            ValueError: If cache is invalid and no fetch function provided
        """
        async with self._lock:
            cache_entry = self._caches.get(cache_type)

            # Check if we need to fetch fresh data
            needs_fetch = (
                force_refresh
                or cache_entry is None
                or not cache_entry.is_valid()
            )

            if needs_fetch:
                if fetch_func is None:
                    if cache_entry is None:
                        raise ValueError(
                            f"No cached data for {cache_type.value} and no fetch function provided"
                        )
                    # Return stale data if no fetch function
                    logger.warning(
                        "Returning stale data for %s (age: %.2fs, ttl: %.2fs)",
                        cache_type.value,
                        cache_entry.age(),
                        cache_entry.ttl,
                    )
                    self._stats["misses"] += 1
                    return cache_entry.data

                # Fetch fresh data
                try:
                    fresh_data = await fetch_func()
                    await self.set(cache_type, fresh_data)
                    self._stats["refreshes"] += 1
                    logger.debug(
                        "Cache refreshed: %s (forced=%s)", cache_type.value, force_refresh
                    )
                    return fresh_data
                except Exception as e:
                    logger.error("Failed to fetch fresh data for %s: %s", cache_type.value, e)
                    # Return stale data if available
                    if cache_entry is not None:
                        logger.warning("Returning stale data after fetch failure")
                        return cache_entry.data
                    raise

            # Cache hit
            self._stats["hits"] += 1
            logger.debug(
                "Cache hit: %s (age: %.2fs, ttl: %.2fs)",
                cache_type.value,
                cache_entry.age(),
                cache_entry.ttl,
            )
            return cache_entry.data

    async def set(self, cache_type: CacheType, data: Any) -> None:
        """
        Set cache entry with fresh data.

        Args:
            cache_type: Type of cache to update
            data: Data to cache
        """
        async with self._lock:
            ttl = self.get_ttl(cache_type)
            cache_entry = self._caches.get(cache_type)

            if cache_entry is None:
                # Create new cache entry
                self._caches[cache_type] = CacheEntry(
                    data=data,
                    ttl=ttl,
                    cache_type=cache_type.value,
                )
                logger.debug("Cache created: %s", cache_type.value)
            else:
                # Refresh existing entry
                cache_entry.refresh(data)
                logger.debug("Cache updated: %s", cache_type.value)

    async def invalidate(self, cache_type: Optional[CacheType] = None) -> None:
        """
        Invalidate cache entries.

        Args:
            cache_type: Specific cache to invalidate, or None for all caches
        """
        async with self._lock:
            if cache_type is None:
                # Invalidate all caches
                for ct in CacheType:
                    self._caches[ct] = None
                logger.info("All caches invalidated")
                self._stats["invalidations"] += len(CacheType)
            else:
                # Invalidate specific cache
                self._caches[cache_type] = None
                logger.info("Cache invalidated: %s", cache_type.value)
                self._stats["invalidations"] += 1

    def is_valid(self, cache_type: CacheType) -> bool:
        """
        Check if cache entry is valid (not expired).

        Args:
            cache_type: Type of cache to check

        Returns:
            bool: True if valid, False if expired or missing
        """
        cache_entry = self._caches.get(cache_type)
        if cache_entry is None:
            return False
        return cache_entry.is_valid()

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            dict: Statistics including hits, misses, hit rate, etc.
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            self._stats["hits"] / total_requests if total_requests > 0 else 0.0
        )

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "refreshes": self._stats["refreshes"],
            "invalidations": self._stats["invalidations"],
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "cache_states": {
                ct.value: "valid" if self.is_valid(ct) else "invalid"
                for ct in CacheType
            },
        }

    def reset_stats(self) -> None:
        """Reset cache statistics counters."""
        self._stats = {
            "hits": 0,
            "misses": 0,
            "refreshes": 0,
            "invalidations": 0,
        }
        logger.info("Cache statistics reset")

    async def get_cache_info(self, cache_type: CacheType) -> Optional[dict]:
        """
        Get detailed information about a cache entry.

        Args:
            cache_type: Type of cache to inspect

        Returns:
            dict: Cache entry information or None if not cached
        """
        async with self._lock:
            cache_entry = self._caches.get(cache_type)
            if cache_entry is None:
                return None
            return cache_entry.to_dict()

    def __repr__(self) -> str:
        """String representation of cache store."""
        stats = self.get_stats()
        return f"DataCache(hit_rate={stats['hit_rate']:.1%}, requests={stats['total_requests']})"
