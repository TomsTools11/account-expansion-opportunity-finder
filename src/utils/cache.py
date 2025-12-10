"""In-memory caching utility with TTL and LRU eviction."""

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """A single cache entry with value and expiration."""

    value: T
    expires_at: float
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() > self.expires_at


class TTLCache(Generic[T]):
    """Thread-safe in-memory cache with TTL and LRU eviction.

    Features:
    - Time-to-live (TTL) for automatic expiration
    - LRU (Least Recently Used) eviction when max size is reached
    - Thread-safe operations with locking
    - Manual invalidation support

    Usage:
        cache = TTLCache[str](ttl_seconds=300, max_size=1000)
        cache.set("key1", "value1")
        value = cache.get("key1")  # Returns "value1" or None if expired
    """

    def __init__(
        self,
        ttl_seconds: float = 300,
        max_size: int = 1000,
        name: str = "default",
    ):
        """Initialize the cache.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds (default 5 minutes)
            max_size: Maximum number of entries before LRU eviction
            name: Cache name for logging/debugging
        """
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._name = name
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    @property
    def name(self) -> str:
        """Return cache name."""
        return self._name

    @property
    def size(self) -> int:
        """Return current number of entries (including expired)."""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """Return cache hit rate (0-1)."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get(self, key: str) -> Optional[T]:
        """Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value if present and not expired, None otherwise
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: T, ttl_seconds: Optional[float] = None) -> None:
        """Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional custom TTL (uses default if not specified)
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        expires_at = time.time() + ttl

        with self._lock:
            # If key exists, update it and move to end
            if key in self._cache:
                self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
                self._cache.move_to_end(key)
            else:
                # Evict LRU entry if at max size
                if len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)

                self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    def delete(self, key: str) -> bool:
        """Delete a specific key from the cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was present and deleted, False otherwise
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern (prefix match).

        Args:
            pattern: Key prefix to match

        Returns:
            Number of keys invalidated
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, v in self._cache.items() if v.expires_at < now
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            return {
                "name": self._name,
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self.hit_rate,
            }

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl_seconds: Optional[float] = None,
    ) -> T:
        """Get a value from cache, or compute and cache it if missing.

        Args:
            key: Cache key
            factory: Function to compute value if not in cache
            ttl_seconds: Optional custom TTL

        Returns:
            Cached or computed value
        """
        value = self.get(key)
        if value is not None:
            return value

        # Compute value outside the lock
        computed_value = factory()
        self.set(key, computed_value, ttl_seconds)
        return computed_value


class AsyncTTLCache(Generic[T]):
    """Async-friendly TTL cache wrapper.

    Provides async methods that wrap the synchronous TTLCache,
    useful for async contexts where you want non-blocking cache operations.
    """

    def __init__(
        self,
        ttl_seconds: float = 300,
        max_size: int = 1000,
        name: str = "async_default",
    ):
        """Initialize the async cache."""
        self._cache = TTLCache[T](
            ttl_seconds=ttl_seconds, max_size=max_size, name=name
        )

    async def get(self, key: str) -> Optional[T]:
        """Async get from cache."""
        return self._cache.get(key)

    async def set(
        self, key: str, value: T, ttl_seconds: Optional[float] = None
    ) -> None:
        """Async set to cache."""
        self._cache.set(key, value, ttl_seconds)

    async def delete(self, key: str) -> bool:
        """Async delete from cache."""
        return self._cache.delete(key)

    async def clear(self) -> None:
        """Async clear cache."""
        self._cache.clear()

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl_seconds: Optional[float] = None,
    ) -> T:
        """Async get or set with factory."""
        return self._cache.get_or_set(key, factory, ttl_seconds)

    async def get_or_set_async(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl_seconds: Optional[float] = None,
    ) -> T:
        """Async get or set with async factory function.

        Args:
            key: Cache key
            factory: Async function to compute value if not in cache
            ttl_seconds: Optional custom TTL

        Returns:
            Cached or computed value
        """
        value = await self.get(key)
        if value is not None:
            return value

        # Await the async factory
        computed_value = await factory()
        await self.set(key, computed_value, ttl_seconds)
        return computed_value

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()


# Global cache instances for different data types
_agent_cache: Optional[TTLCache[Any]] = None
_benchmark_cache: Optional[TTLCache[Any]] = None


def get_agent_cache(
    ttl_seconds: float = 300, max_size: int = 1000
) -> TTLCache[Any]:
    """Get or create the global agent data cache.

    Args:
        ttl_seconds: TTL for agent data (default 5 minutes)
        max_size: Maximum entries

    Returns:
        Global agent cache instance
    """
    global _agent_cache
    if _agent_cache is None:
        _agent_cache = TTLCache(
            ttl_seconds=ttl_seconds, max_size=max_size, name="agent_cache"
        )
    return _agent_cache


def get_benchmark_cache(
    ttl_seconds: float = 3600, max_size: int = 100
) -> TTLCache[Any]:
    """Get or create the global benchmark data cache.

    Args:
        ttl_seconds: TTL for benchmark data (default 1 hour)
        max_size: Maximum entries

    Returns:
        Global benchmark cache instance
    """
    global _benchmark_cache
    if _benchmark_cache is None:
        _benchmark_cache = TTLCache(
            ttl_seconds=ttl_seconds, max_size=max_size, name="benchmark_cache"
        )
    return _benchmark_cache


def invalidate_all_caches() -> None:
    """Clear all global caches."""
    global _agent_cache, _benchmark_cache
    if _agent_cache:
        _agent_cache.clear()
    if _benchmark_cache:
        _benchmark_cache.clear()


def create_cache_key(*parts: str) -> str:
    """Create a standardized cache key from parts.

    Args:
        *parts: Key components to join

    Returns:
        Joined cache key
    """
    return "_".join(str(p) for p in parts)
