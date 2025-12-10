"""Unit tests for caching utilities."""

import time
from unittest.mock import MagicMock

import pytest

from src.utils.cache import (
    TTLCache,
    create_cache_key,
    get_agent_cache,
    get_benchmark_cache,
    invalidate_all_caches,
)


class TestTTLCache:
    """Tests for TTLCache class."""

    @pytest.fixture
    def cache(self) -> TTLCache[str]:
        """Create a test cache."""
        return TTLCache[str](ttl_seconds=1.0, max_size=5, name="test_cache")

    def test_set_and_get(self, cache: TTLCache[str]):
        """Test basic set and get operations."""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self, cache: TTLCache[str]):
        """Test getting a non-existent key."""
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self, cache: TTLCache[str]):
        """Test that entries expire after TTL."""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_custom_ttl(self, cache: TTLCache[str]):
        """Test setting a custom TTL for specific entry."""
        cache.set("key1", "value1", ttl_seconds=0.5)
        assert cache.get("key1") == "value1"

        time.sleep(0.6)
        assert cache.get("key1") is None

    def test_update_existing_key(self, cache: TTLCache[str]):
        """Test updating an existing key."""
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"

    def test_delete(self, cache: TTLCache[str]):
        """Test deleting a key."""
        cache.set("key1", "value1")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None

    def test_delete_nonexistent(self, cache: TTLCache[str]):
        """Test deleting a non-existent key."""
        assert cache.delete("nonexistent") is False

    def test_lru_eviction(self, cache: TTLCache[str]):
        """Test LRU eviction when cache is full."""
        # Fill cache to max_size (5)
        for i in range(5):
            cache.set(f"key{i}", f"value{i}")

        # Add one more, should evict key0 (least recently used)
        cache.set("key5", "value5")

        assert cache.get("key0") is None  # Evicted
        assert cache.get("key5") == "value5"  # Newest entry
        assert cache.size == 5

    def test_lru_access_refreshes_order(self, cache: TTLCache[str]):
        """Test that accessing a key moves it to most recently used."""
        for i in range(5):
            cache.set(f"key{i}", f"value{i}")

        # Access key0 to make it most recently used
        cache.get("key0")

        # Add new entry, should evict key1 (now least recently used)
        cache.set("key5", "value5")

        assert cache.get("key0") == "value0"  # Still present
        assert cache.get("key1") is None  # Evicted

    def test_clear(self, cache: TTLCache[str]):
        """Test clearing the cache."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.size == 0
        assert cache.get("key1") is None

    def test_invalidate_pattern(self, cache: TTLCache[str]):
        """Test invalidating keys by prefix pattern."""
        cache.set("user_1", "data1")
        cache.set("user_2", "data2")
        cache.set("product_1", "data3")

        count = cache.invalidate_pattern("user_")
        assert count == 2
        assert cache.get("user_1") is None
        assert cache.get("product_1") == "data3"

    def test_cleanup_expired(self, cache: TTLCache[str]):
        """Test cleanup of expired entries."""
        cache.set("key1", "value1", ttl_seconds=0.1)
        cache.set("key2", "value2", ttl_seconds=10.0)

        time.sleep(0.2)

        removed = cache.cleanup_expired()
        assert removed == 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_get_stats(self, cache: TTLCache[str]):
        """Test cache statistics."""
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        stats = cache.get_stats()
        assert stats["name"] == "test_cache"
        assert stats["size"] == 1
        assert stats["max_size"] == 5
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_hit_rate_calculation(self, cache: TTLCache[str]):
        """Test hit rate calculation."""
        # Empty cache has 0 hit rate
        assert cache.hit_rate == 0.0

        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        assert cache.hit_rate == 1.0

        cache.get("key2")  # Miss
        assert cache.hit_rate == 0.5

    def test_get_or_set(self, cache: TTLCache[str]):
        """Test get_or_set with factory function."""
        factory_called = [False]

        def factory():
            factory_called[0] = True
            return "computed_value"

        # First call should invoke factory
        result = cache.get_or_set("key1", factory)
        assert result == "computed_value"
        assert factory_called[0] is True

        # Reset flag
        factory_called[0] = False

        # Second call should return cached value
        result = cache.get_or_set("key1", factory)
        assert result == "computed_value"
        assert factory_called[0] is False  # Factory not called


class TestCacheKey:
    """Tests for cache key creation."""

    def test_create_cache_key_single_part(self):
        """Test key creation with single part."""
        key = create_cache_key("agent")
        assert key == "agent"

    def test_create_cache_key_multiple_parts(self):
        """Test key creation with multiple parts."""
        key = create_cache_key("agent", "lead_123", "2024-01-01")
        assert key == "agent_lead_123_2024-01-01"

    def test_create_cache_key_non_string(self):
        """Test key creation with non-string parts."""
        key = create_cache_key("search", 100, True)
        assert key == "search_100_True"


class TestGlobalCaches:
    """Tests for global cache instances."""

    def test_get_agent_cache_singleton(self):
        """Test that get_agent_cache returns singleton."""
        # Reset global caches first
        invalidate_all_caches()

        cache1 = get_agent_cache()
        cache2 = get_agent_cache()
        assert cache1 is cache2

    def test_get_benchmark_cache_singleton(self):
        """Test that get_benchmark_cache returns singleton."""
        invalidate_all_caches()

        cache1 = get_benchmark_cache()
        cache2 = get_benchmark_cache()
        assert cache1 is cache2

    def test_agent_cache_default_ttl(self):
        """Test agent cache has correct default TTL (5 minutes)."""
        invalidate_all_caches()
        cache = get_agent_cache()
        stats = cache.get_stats()
        assert stats["ttl_seconds"] == 300

    def test_benchmark_cache_default_ttl(self):
        """Test benchmark cache has correct default TTL (1 hour)."""
        invalidate_all_caches()
        cache = get_benchmark_cache()
        stats = cache.get_stats()
        assert stats["ttl_seconds"] == 3600

    def test_invalidate_all_caches(self):
        """Test invalidating all global caches."""
        # Populate caches
        agent_cache = get_agent_cache()
        benchmark_cache = get_benchmark_cache()
        agent_cache.set("key1", "value1")
        benchmark_cache.set("key2", "value2")

        # Invalidate
        invalidate_all_caches()

        # Verify caches are empty
        assert agent_cache.get("key1") is None
        assert benchmark_cache.get("key2") is None


class TestCacheThreadSafety:
    """Tests for cache thread safety."""

    def test_concurrent_set_get(self):
        """Test concurrent set and get operations."""
        import threading

        cache = TTLCache[int](ttl_seconds=10.0, max_size=1000)
        errors = []

        def worker(worker_id: int):
            try:
                for i in range(100):
                    key = f"worker_{worker_id}_key_{i}"
                    cache.set(key, i)
                    value = cache.get(key)
                    if value is not None and value != i:
                        errors.append(f"Value mismatch for {key}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
