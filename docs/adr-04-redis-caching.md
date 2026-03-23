# ADR-04: Use Redis for All Application-Level Caching

**Status:** Accepted  
**Date:** 2025-01-15  
**Author:** Platform Engineering Team

---

## Context

As the platform scales, in-process caches (Python `dict`, `lru_cache`) create
inconsistency across multiple worker replicas (Celery workers, Kubernetes pods).
Each replica holds its own cache state, causing cache misses and stale reads.

## Decision

All application-level caching **MUST** use Redis instead of in-process structures.

- Use `redis-py` client with connection pooling.
- Default TTL: **300 seconds** unless domain-specific.
- Cache keys must follow the pattern: `{service}:{resource_type}:{identifier}`.

### Examples

```python
# ✅ Correct — Redis-backed cache
import redis
r = redis.Redis.from_url(os.getenv("REDIS_URL"))
r.setex(f"acr:pr_review:{pr_id}", 300, json.dumps(result))

# ❌ Incorrect — in-process dict cache
_cache = {}
_cache[pr_id] = result
```

## Consequences

- **Positive:** Cache is shared across all replicas; no stale reads on scale-out.
- **Positive:** Redis TTL auto-expires, preventing memory bloat.
- **Negative:** Adds a Redis dependency; must be part of the deployment manifest.

## References

- [Redis best practices](https://redis.io/docs/manual/patterns/)
- Internal benchmark: Redis reduced PR review latency by 40% under load (Q4 2024).
