"""
Cache Entry Data Model

Provides TTL-based cache entry with automatic expiration validation.
Each cache entry stores data, timestamp, and TTL for intelligent caching.
"""

import time
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """
    A single cache entry with TTL (Time To Live) support.

    Attributes:
        data: The cached data (dict, list, or any JSON-serializable type)
        timestamp: Unix timestamp when data was cached
        ttl: Time to live in seconds (cache validity duration)
        cache_type: Type identifier for this cache entry
    """

    data: Any
    timestamp: float = field(default_factory=time.time)
    ttl: float = 1.0
    cache_type: str = "unknown"

    def is_valid(self) -> bool:
        """
        Check if cache entry is still valid based on TTL.

        Returns:
            bool: True if cache is still valid, False if expired
        """
        age = time.time() - self.timestamp
        return age < self.ttl

    def age(self) -> float:
        """
        Get the age of the cache entry in seconds.

        Returns:
            float: Age in seconds since cache creation
        """
        return time.time() - self.timestamp

    def time_until_expiration(self) -> float:
        """
        Get time remaining until cache expires.

        Returns:
            float: Seconds until expiration (negative if already expired)
        """
        return self.ttl - self.age()

    def refresh(self, new_data: Any) -> None:
        """
        Refresh cache entry with new data and reset timestamp.

        Args:
            new_data: New data to cache
        """
        self.data = new_data
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        """
        Convert cache entry to dictionary for serialization.

        Returns:
            dict: Cache entry as dictionary
        """
        return {
            "data": self.data,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
            "cache_type": self.cache_type,
            "is_valid": self.is_valid(),
            "age": self.age(),
        }

    def __repr__(self) -> str:
        """String representation of cache entry."""
        status = "valid" if self.is_valid() else "expired"
        return f"CacheEntry(type={self.cache_type}, age={self.age():.2f}s, ttl={self.ttl}s, {status})"
