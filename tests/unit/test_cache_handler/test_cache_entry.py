"""
Unit tests for CacheEntry class.

Tests cache entry data model including TTL validation, age tracking,
refresh capability, and serialization.
"""

import time

import pytest

from brewmotron_cache_handler.cache_entry import CacheEntry


class TestCacheEntry:
    """Test suite for CacheEntry class."""

    def test_cache_entry_creation(self):
        """Test cache entry can be created with data and TTL."""
        data = {"temperature": 65.5, "kettle": "mash_tun"}
        entry = CacheEntry(data=data, ttl=1.0, cache_type="kettle")

        assert entry.data == data
        assert entry.ttl == 1.0
        assert entry.cache_type == "kettle"
        assert isinstance(entry.timestamp, float)

    def test_cache_entry_defaults(self):
        """Test cache entry uses default values correctly."""
        entry = CacheEntry(data={"test": "data"})

        assert entry.data == {"test": "data"}
        assert entry.ttl == 1.0
        assert entry.cache_type == "unknown"
        assert entry.timestamp > 0

    def test_cache_entry_is_valid_when_fresh(self):
        """Test cache entry is valid immediately after creation."""
        entry = CacheEntry(data={"test": "data"}, ttl=1.0)
        assert entry.is_valid() is True

    def test_cache_entry_is_invalid_when_expired(self):
        """Test cache entry becomes invalid after TTL expires."""
        entry = CacheEntry(data={"test": "data"}, ttl=0.1)  # 100ms TTL
        time.sleep(0.15)  # Wait for expiration
        assert entry.is_valid() is False

    def test_cache_entry_age(self):
        """Test cache entry age calculation."""
        entry = CacheEntry(data={"test": "data"})
        time.sleep(0.05)  # 50ms
        age = entry.age()
        assert age >= 0.05
        assert age < 0.1  # Should be close to 50ms

    def test_cache_entry_time_until_expiration(self):
        """Test time until expiration calculation."""
        entry = CacheEntry(data={"test": "data"}, ttl=1.0)
        time_left = entry.time_until_expiration()
        assert time_left > 0.9  # Should have most of TTL remaining
        assert time_left <= 1.0

    def test_cache_entry_time_until_expiration_negative_when_expired(self):
        """Test time until expiration is negative when expired."""
        entry = CacheEntry(data={"test": "data"}, ttl=0.05)
        time.sleep(0.1)
        time_left = entry.time_until_expiration()
        assert time_left < 0

    def test_cache_entry_refresh(self):
        """Test cache entry refresh updates data and timestamp."""
        entry = CacheEntry(data={"old": "data"}, ttl=1.0)
        old_timestamp = entry.timestamp
        time.sleep(0.05)

        entry.refresh({"new": "data"})

        assert entry.data == {"new": "data"}
        assert entry.timestamp > old_timestamp
        assert entry.is_valid() is True

    def test_cache_entry_refresh_resets_ttl(self):
        """Test refresh resets TTL countdown."""
        entry = CacheEntry(data={"test": "data"}, ttl=0.2)
        time.sleep(0.15)  # Almost expired

        entry.refresh({"new": "data"})
        assert entry.is_valid() is True  # Should be valid again

    def test_cache_entry_to_dict(self):
        """Test cache entry serialization to dictionary."""
        data = {"temperature": 65.5}
        entry = CacheEntry(data=data, ttl=1.0, cache_type="sensor")

        result = entry.to_dict()

        assert result["data"] == data
        assert result["ttl"] == 1.0
        assert result["cache_type"] == "sensor"
        assert isinstance(result["timestamp"], float)
        assert isinstance(result["is_valid"], bool)
        assert isinstance(result["age"], float)

    def test_cache_entry_to_dict_reflects_validity(self):
        """Test to_dict correctly reflects validity state."""
        entry = CacheEntry(data={"test": "data"}, ttl=0.05)

        # Fresh entry
        result_fresh = entry.to_dict()
        assert result_fresh["is_valid"] is True

        # Expired entry
        time.sleep(0.1)
        result_expired = entry.to_dict()
        assert result_expired["is_valid"] is False

    def test_cache_entry_repr(self):
        """Test cache entry string representation."""
        entry = CacheEntry(data={"test": "data"}, ttl=1.0, cache_type="test")
        repr_str = repr(entry)

        assert "CacheEntry" in repr_str
        assert "type=test" in repr_str
        assert "ttl=1.0s" in repr_str
        assert "valid" in repr_str or "expired" in repr_str

    def test_cache_entry_repr_shows_expired_state(self):
        """Test repr shows expired state correctly."""
        entry = CacheEntry(data={"test": "data"}, ttl=0.05)
        time.sleep(0.1)
        repr_str = repr(entry)

        assert "expired" in repr_str

    def test_cache_entry_with_different_data_types(self):
        """Test cache entry works with various data types."""
        # Dict
        entry_dict = CacheEntry(data={"key": "value"})
        assert entry_dict.data == {"key": "value"}

        # List
        entry_list = CacheEntry(data=[1, 2, 3])
        assert entry_list.data == [1, 2, 3]

        # String
        entry_str = CacheEntry(data="test string")
        assert entry_str.data == "test string"

        # Number
        entry_num = CacheEntry(data=42.5)
        assert entry_num.data == 42.5

        # None
        entry_none = CacheEntry(data=None)
        assert entry_none.data is None

    def test_cache_entry_very_short_ttl(self):
        """Test cache entry with very short TTL (10ms)."""
        entry = CacheEntry(data={"test": "data"}, ttl=0.01)  # 10ms
        assert entry.is_valid() is True
        time.sleep(0.02)  # 20ms
        assert entry.is_valid() is False

    def test_cache_entry_long_ttl(self):
        """Test cache entry with long TTL (60s)."""
        entry = CacheEntry(data={"test": "data"}, ttl=60.0)
        assert entry.is_valid() is True
        assert entry.time_until_expiration() > 59.9

    def test_cache_entry_concurrent_validity_checks(self):
        """Test multiple validity checks return consistent results."""
        entry = CacheEntry(data={"test": "data"}, ttl=1.0)

        # Multiple checks should all return True when fresh
        results = [entry.is_valid() for _ in range(10)]
        assert all(results)

        # Multiple checks should all return False when expired
        entry_expired = CacheEntry(data={"test": "data"}, ttl=0.01)
        time.sleep(0.05)
        results_expired = [entry_expired.is_valid() for _ in range(10)]
        assert not any(results_expired)

    def test_cache_entry_edge_case_zero_ttl(self):
        """Test cache entry with zero TTL is immediately invalid."""
        entry = CacheEntry(data={"test": "data"}, ttl=0.0)
        # Should be immediately invalid since age > 0
        time.sleep(0.001)
        assert entry.is_valid() is False

    def test_cache_entry_refresh_preserves_ttl(self):
        """Test refresh preserves original TTL value."""
        entry = CacheEntry(data={"old": "data"}, ttl=2.5)
        original_ttl = entry.ttl

        entry.refresh({"new": "data"})

        assert entry.ttl == original_ttl
