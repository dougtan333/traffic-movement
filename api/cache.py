"""
API response cache — eliminates downtime during Bluetooth poller writes.

Simple in-memory TTL cache keyed by request URL (path + query string).
The Bluetooth poller locks the speed DB for a few seconds every 5 minutes;
this cache ensures users always get an instant response from the most
recent successful query.

Default TTL is 300s (matches the 5-minute poll interval), so cached data
is always current. Cache is thread-safe via a threading lock.

Usage in endpoints:
    from api.cache import cache_response
    result = cache_response(cache_key, fetch_fn, ttl=300)
    
Or as middleware (applied in main.py) for automatic caching of all GET
requests under /api/.
"""

import time
import threading
from typing import Any, Callable, Optional

_cache: dict[str, tuple[float, Any]] = {}  # key -> (expiry_ts, response_data)
_lock = threading.Lock()

DEFAULT_TTL = 300  # 5 minutes — matches Bluetooth poll interval


def get(key: str) -> Optional[Any]:
    """Return cached value if present and not expired, else None."""
    with _lock:
        entry = _cache.get(key)
        if entry and entry[0] > time.time():
            return entry[1]
        if entry:
            del _cache[key]
    return None


def put(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    """Store a value with TTL (seconds)."""
    with _lock:
        _cache[key] = (time.time() + ttl, value)


def cache_response(key: str, fetch_fn: Callable[[], Any], ttl: int = DEFAULT_TTL) -> Any:
    """Return cached value or call fetch_fn, cache the result, and return it."""
    cached = get(key)
    if cached is not None:
        return cached
    result = fetch_fn()
    put(key, result, ttl)
    return result


def clear() -> None:
    """Flush the entire cache (e.g. after a data refresh)."""
    with _lock:
        _cache.clear()


def evict_prefix(prefix: str) -> int:
    """Remove all keys starting with prefix. Returns count evicted."""
    with _lock:
        keys = [k for k in _cache if k.startswith(prefix)]
        for k in keys:
            del _cache[k]
        return len(keys)


def stats() -> dict:
    """Return cache size and entry count (for health endpoint)."""
    with _lock:
        now = time.time()
        live = sum(1 for _, (exp, _) in _cache.items() if exp > now)
        return {"entries": len(_cache), "live": live, "expired": len(_cache) - live}
