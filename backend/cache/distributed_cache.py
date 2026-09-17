"""
Distributed Cache Layer for CraftAI (Upgrade 11).

Provides multi-tenant, multi-namespace Redis caching for:
- planning results
- semantic search results
- media metadata
- rendered thumbnails
- user sessions
- tenant configuration
- dashboard queries

Features:
- Namespaced key isolation
- TTL management per namespace
- Tag-based and pattern-based cache invalidation
- Single-flight stampede protection using distributed mutex locking
- Cache warming runner
- Prometheus hit/miss/ratio metrics
"""
import time
import json
import logging
import hashlib
from typing import Any, Optional, Dict, List, Callable, Union

logger = logging.getLogger("uvicorn")


class CacheNamespace:
    PLANNING = "planning"
    SEMANTIC = "semantic"
    MEDIA = "media"
    THUMBNAIL = "thumbnail"
    USER_SESSION = "user"
    TENANT_CONFIG = "tenant"
    DASHBOARD = "dashboard"


DEFAULT_TTLS: Dict[str, int] = {
    CacheNamespace.PLANNING: 3600,        # 1 hour
    CacheNamespace.SEMANTIC: 86400,       # 24 hours
    CacheNamespace.MEDIA: 604800,         # 7 days
    CacheNamespace.THUMBNAIL: 2592000,    # 30 days
    CacheNamespace.USER_SESSION: 900,     # 15 minutes
    CacheNamespace.TENANT_CONFIG: 1800,   # 30 minutes
    CacheNamespace.DASHBOARD: 60,         # 1 minute
}


class DistributedCache:
    """Production-grade Redis Distributed Cache Manager."""

    _instance: Optional["DistributedCache"] = None

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis_client = None
        self._local_fallback: Dict[str, Dict[str, Any]] = {}
        self._hits = 0
        self._misses = 0
        self._init_client()

    def _init_client(self):
        """Initialize Redis connection client with fallback."""
        try:
            import redis
            self._redis_client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            self._redis_client.ping()
            logger.info("DistributedCache: Redis connection established")
        except Exception as e:
            logger.warning(f"DistributedCache: Redis connection unavailable ({e}), using memory fallback")
            self._redis_client = None

    @classmethod
    def get_instance(cls, redis_url: str = "redis://localhost:6379/0") -> "DistributedCache":
        if cls._instance is None:
            cls._instance = cls(redis_url=redis_url)
        return cls._instance

    def _build_key(self, namespace: str, key: str, tenant_id: str = "global") -> str:
        """Construct namespaced redis key."""
        return f"craftai:{tenant_id}:{namespace}:{key}"

    def get(self, namespace: str, key: str, tenant_id: str = "global") -> Optional[Any]:
        """Fetch item from cache with metrics collection."""
        full_key = self._build_key(namespace, key, tenant_id)
        val = None

        if self._redis_client:
            try:
                raw = self._redis_client.get(full_key)
                if raw is not None:
                    val = json.loads(raw)
            except Exception as e:
                logger.error(f"DistributedCache.get error: {e}")

        if val is None and full_key in self._local_fallback:
            entry = self._local_fallback[full_key]
            if entry["expires_at"] > time.time():
                val = entry["value"]
            else:
                del self._local_fallback[full_key]

        if val is not None:
            self._hits += 1
            self._record_metric("hit", namespace)
            return val
        else:
            self._misses += 1
            self._record_metric("miss", namespace)
            return None

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        tenant_id: str = "global",
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Store item in cache with TTL and optional tag indexing."""
        full_key = self._build_key(namespace, key, tenant_id)
        effective_ttl = ttl or DEFAULT_TTLS.get(namespace, 3600)
        serialized = json.dumps(value)

        success = False
        if self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.setex(full_key, effective_ttl, serialized)
                if tags:
                    for tag in tags:
                        tag_key = f"craftai:tag:{tenant_id}:{tag}"
                        pipe.sadd(tag_key, full_key)
                        pipe.expire(tag_key, effective_ttl + 3600)
                pipe.execute()
                success = True
            except Exception as e:
                logger.error(f"DistributedCache.set error: {e}")

        # Local fallback store
        self._local_fallback[full_key] = {
            "value": value,
            "expires_at": time.time() + effective_ttl,
            "tags": tags or []
        }
        return True

    def get_or_compute(
        self,
        namespace: str,
        key: str,
        compute_fn: Callable[[], Any],
        tenant_id: str = "global",
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get value from cache, or compute and store it with single-flight mutex lock.
        Protects against Cache Stampedes during high concurrent requests.
        """
        cached = self.get(namespace, key, tenant_id)
        if cached is not None:
            return cached

        # Stampede protection lock
        lock_key = self._build_key("lock", f"{namespace}:{key}", tenant_id)
        acquired_lock = False

        if self._redis_client:
            try:
                acquired_lock = self._redis_client.set(lock_key, "locked", nx=True, ex=10)
            except Exception:
                acquired_lock = True
        else:
            acquired_lock = True

        if acquired_lock:
            try:
                value = compute_fn()
                self.set(namespace, key, value, tenant_id=tenant_id, ttl=ttl)
                return value
            finally:
                if self._redis_client:
                    try:
                        self._redis_client.delete(lock_key)
                    except Exception:
                        pass
        else:
            # Wait briefly for lock holder to compute and populate cache
            time.sleep(0.1)
            retry_val = self.get(namespace, key, tenant_id)
            if retry_val is not None:
                return retry_val
            return compute_fn()

    def invalidate(self, namespace: str, key: str, tenant_id: str = "global") -> bool:
        """Invalidate a specific cache key."""
        full_key = self._build_key(namespace, key, tenant_id)
        if self._redis_client:
            try:
                self._redis_client.delete(full_key)
            except Exception as e:
                logger.error(f"DistributedCache.invalidate error: {e}")
        self._local_fallback.pop(full_key, None)
        return True

    def invalidate_prefix(self, namespace: str, tenant_id: str = "global") -> int:
        """Invalidate all keys matching namespace prefix."""
        prefix = f"craftai:{tenant_id}:{namespace}:*"
        count = 0
        if self._redis_client:
            try:
                keys = self._redis_client.keys(prefix)
                if keys:
                    count = self._redis_client.delete(*keys)
            except Exception as e:
                logger.error(f"DistributedCache.invalidate_prefix error: {e}")

        # Clean local fallback
        to_del = [k for k in self._local_fallback if k.startswith(f"craftai:{tenant_id}:{namespace}:")]
        for k in to_del:
            self._local_fallback.pop(k, None)
            count += 1
        return count

    def invalidate_tag(self, tag: str, tenant_id: str = "global") -> int:
        """Invalidate all cache entries associated with tag."""
        tag_key = f"craftai:tag:{tenant_id}:{tag}"
        count = 0
        if self._redis_client:
            try:
                keys = self._redis_client.smembers(tag_key)
                if keys:
                    count = self._redis_client.delete(*keys)
                self._redis_client.delete(tag_key)
            except Exception as e:
                logger.error(f"DistributedCache.invalidate_tag error: {e}")

        # Local fallback tag invalidation
        to_del = [k for k, v in self._local_fallback.items() if tag in v.get("tags", [])]
        for k in to_del:
            self._local_fallback.pop(k, None)
            count += 1
        return count

    def warm_cache(self, namespace: str, items: Dict[str, Any], tenant_id: str = "global") -> int:
        """Bulk populate cache for cache warming strategies."""
        warmed = 0
        for k, v in items.items():
            if self.set(namespace, k, v, tenant_id=tenant_id):
                warmed += 1
        logger.info(f"DistributedCache: Warmed {warmed} items for namespace {namespace}")
        return warmed

    def get_metrics(self) -> Dict[str, Any]:
        """Return cache hit/miss statistics and hit ratio."""
        total = self._hits + self._misses
        ratio = (self._hits / total) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_ratio": round(ratio, 4),
            "redis_connected": self._redis_client is not None,
            "fallback_entries_count": len(self._local_fallback)
        }

    def _record_metric(self, metric_type: str, namespace: str):
        """Hook into observability metrics if present."""
        try:
            from backend.observability.metrics import metrics
            if metric_type == "hit":
                metrics.inc_counter("cache_hits_total", 1, namespace=namespace)
            else:
                metrics.inc_counter("cache_misses_total", 1, namespace=namespace)
        except Exception:
            pass


# Global singleton helper
cache = DistributedCache.get_instance()
