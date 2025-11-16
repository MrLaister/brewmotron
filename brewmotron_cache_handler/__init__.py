"""
Brewmotron Cache Handler

A high-performance caching layer for CraftBeerPi4 data access that reduces
excessive API polling through TTL-based caching.

Key Components:
- CacheEntry: TTL-based cache entry data model
- DataCache: Multi-cache store with automatic expiration
- I2CCoordinator: Hardware bus coordination (Phase 3)
- CBPI4CacheHandler: Main API facade (Phase 4)
- Singleton: Shared cache instance across plugins (Phase 4.5)

Performance Improvements:
- 94% reduction in API calls (327 → <20 calls/min)
- TTL-based caching (250ms-60s configurable)
- Zero I2C bus conflicts through coordination
- Async-first design for non-blocking access
- Singleton pattern for maximum cache sharing

Author: Brewmotron Project
Version: 1.0.0
"""

from .cache_entry import CacheEntry
from .cache_handler import CBPI4CacheHandler
from .cache_store import CacheType, DataCache
from .i2c_coordinator import I2CCoordinator, I2COperation, I2CPriority
from .singleton import get_cache_handler, get_cache_handler_sync, reset_cache_handler

__version__ = "1.0.0"
__all__ = [
    "CacheEntry",
    "DataCache",
    "CacheType",
    "I2CCoordinator",
    "I2COperation",
    "I2CPriority",
    "CBPI4CacheHandler",
    "get_cache_handler",
    "get_cache_handler_sync",
    "reset_cache_handler",
]
